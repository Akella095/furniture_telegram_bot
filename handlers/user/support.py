# handlers/user/support.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, \
    KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import logging

from db.queries import create_support_request
from states.order import SupportStates
from config import MANAGER_CHAT_ID
from keyboards.inline import support_keyboard
from keyboards.reply import question_cancel_keyboard, main_menu_keyboard as reply_main_menu
from logger import logger

router = Router(name="user_support")


# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============

async def safe_delete_message(message):
    """Безопасное удаление сообщения"""
    try:
        await message.delete()
        return True
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
        return False


async def safe_callback_answer(callback: CallbackQuery, text: str = None, show_alert: bool = False):
    """Безопасный ответ на callback"""
    try:
        if text:
            await callback.answer(text, show_alert=show_alert)
        else:
            await callback.answer()
    except Exception as e:
        logger.warning(f"Не удалось ответить на callback: {e}")


async def back_to_main_menu(message: Message, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    from keyboards.inline import main_menu_keyboard
    await message.answer(
        "🏠 <b>Главное меню</b>\n\nВыберите раздел:",
        reply_markup=main_menu_keyboard()
    )


# ============= ОСНОВНЫЕ ОБРАБОТЧИКИ =============

@router.callback_query(F.data == "ask_support")
async def ask_support(callback: CallbackQuery, state: FSMContext):
    """Задать вопрос поддержке"""
    await safe_delete_message(callback.message)
    await callback.message.answer(
        "📝 <b>Задать вопрос</b>\n\n"
        "Опишите ваш вопрос подробно.\n"
        "Наш менеджер ответит вам в ближайшее время:\n"
        "(или нажмите кнопку ниже для отмены)",
        reply_markup=question_cancel_keyboard()
    )
    await state.set_state(SupportStates.waiting_question)
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("ask_"))
async def ask_question_from_product(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Задать вопрос о товаре"""
    product_id = int(callback.data.split("_")[1])

    from db.queries import get_product
    product = await get_product(session, product_id)

    if product:
        await state.update_data(
            product_id=product.id,
            product_name=product.name,
            from_product=True
        )

        await safe_delete_message(callback.message)
        await callback.message.answer(
            f"📝 <b>Задать вопрос о товаре</b>\n\n"
            f"<b>Товар:</b> {product.name}\n\n"
            f"Напишите ваш вопрос:\n"
            f"(или нажмите кнопку ниже для отмены)",
            reply_markup=question_cancel_keyboard()
        )
    else:
        await safe_delete_message(callback.message)
        await callback.message.answer(
            "📝 <b>Задать вопрос</b>\n\n"
            "Опишите ваш вопрос подробно.\n"
            "Наш менеджер ответит вам в ближайшее время:\n"
            "(или нажмите кнопку ниже для отмены)",
            reply_markup=question_cancel_keyboard()
        )

    await state.set_state(SupportStates.waiting_question)
    await safe_callback_answer(callback)


@router.message(F.text == "❌ Отменить вопрос")
async def cancel_question(message: Message, state: FSMContext, session: AsyncSession):
    """Отмена вопроса"""
    data = await state.get_data()
    from_product = data.get('from_product', False)
    product_id = data.get('product_id')

    await state.clear()

    # Удаляем reply-клавиатуру
    await message.answer(
        "⏳ Отмена вопроса...",
        reply_markup=ReplyKeyboardRemove()
    )

    if from_product and product_id:
        # Возвращаемся к товару
        from handlers.user.catalog import show_product
        class FakeCallback:
            def __init__(self, message):
                self.message = message
                self.data = f"prod_{product_id}"

            async def answer(self, text=None, show_alert=False):
                pass

        fake_callback = FakeCallback(message)
        await show_product(fake_callback, session)
    else:
        # Возвращаемся в поддержку
        await message.answer(
            "❌ Вопрос отменен.\n\n"
            "📞 <b>Служба поддержки</b>",
            reply_markup=support_keyboard()
        )


@router.message(F.text == "🏠 Главное меню")
async def back_to_main_menu_handler(message: Message, state: FSMContext):
    """Возврат в главное меню"""
    await back_to_main_menu(message, state)


@router.message(SupportStates.waiting_question)
async def process_support_question(
        message: Message,
        state: FSMContext,
        session: AsyncSession
):
    """Обработка вопроса в поддержку"""
    # Проверка на отмену
    if message.text == "❌ Отменить вопрос":
        await cancel_question(message, state, session)
        return

    if message.text == "🏠 Главное меню":
        await back_to_main_menu(message, state)
        return

    question = message.text.strip()

    if len(question) < 10:
        await message.answer(
            "❌ Слишком короткий вопрос. Пожалуйста, опишите подробнее (минимум 10 символов):",
            reply_markup=question_cancel_keyboard()
        )
        return

    # Получаем данные из состояния
    data = await state.get_data()
    product_id = data.get('product_id')
    product_name = data.get('product_name')
    from_product = data.get('from_product', False)

    # Формируем полный текст вопроса с информацией о товаре
    full_question = question
    if from_product and product_name:
        full_question = f"Товар: {product_name}\n\nВопрос: {question}"

    # Сохраняем запрос в БД
    support_request = await create_support_request(
        session=session,
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        message=full_question
    )

    # Отправляем пользователю подтверждение
    await message.answer(
        "✅ <b>Ваш вопрос отправлен!</b>\n\n"
        "Менеджер ответит вам в ближайшее время.\n"
        f"Номер обращения: #{support_request.id}\n"
        "Спасибо за обращение! 📨",
        reply_markup=support_keyboard()
    )

    # Отправляем менеджеру с кнопкой для ответа
    if MANAGER_CHAT_ID:
        try:
            # Создаем клавиатуру с кнопкой для ответа
            reply_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"✍️ Ответить пользователю @{message.from_user.username or 'пользователю'}",
                    callback_data=f"reply_to_user_{support_request.id}"
                )],
                [InlineKeyboardButton(
                    text="✅ Отметить как решенный",
                    callback_data=f"resolve_request_{support_request.id}"
                )]
            ])

            # Формируем текст уведомления
            text = (
                f"❓ <b>НОВЫЙ ВОПРОС В ПОДДЕРЖКУ</b>\n\n"
                f"<b>От:</b> {message.from_user.full_name}\n"
                f"<b>Username:</b> @{message.from_user.username or 'нет'}\n"
                f"<b>User ID:</b> <code>{message.from_user.id}</code>\n"
            )

            # Добавляем информацию о товаре, если есть
            if from_product and product_name:
                text += f"<b>Товар:</b> {product_name}\n"
                if product_id:
                    text += f"<b>ID товара:</b> {product_id}\n"

            text += f"\n<b>Вопрос #{support_request.id}:</b>\n\n{full_question}\n\n"
            text += f"<i>Нажмите кнопку ниже, чтобы ответить пользователю</i>"

            # Отправляем сообщение и сохраняем ID
            sent_message = await message.bot.send_message(
                MANAGER_CHAT_ID,
                text,
                parse_mode="HTML",
                reply_markup=reply_keyboard
            )

            # Обновляем запрос с ID сообщения
            support_request.reply_message_id = sent_message.message_id
            await session.commit()

        except Exception as e:
            logger.error(f"Ошибка отправки вопроса менеджеру: {e}")

    await state.clear()


# ============= ДОПОЛНИТЕЛЬНЫЕ ОБРАБОТЧИКИ =============

@router.callback_query(F.data == "support")
async def show_support(callback: CallbackQuery):
    """Показать меню поддержки"""
    from keyboards.inline import support_keyboard

    text = (
        "📞 <b>Служба поддержки</b>\n\n"
        "Если у вас возникли вопросы:\n\n"
        "• Нажмите «Задать вопрос» и напишите нам\n"
        "• Позвоните по телефону\n"
        "• Напишите на email\n"
        "• Посетите наш магазин\n\n"
        "Мы всегда рады помочь!"
    )

    await safe_delete_message(callback.message)
    await callback.message.answer(text, reply_markup=support_keyboard())
    await safe_callback_answer(callback)


@router.callback_query(F.data == "address")
async def show_address(callback: CallbackQuery):
    """Показать адрес магазина"""
    text = (
        "📍 <b>Наш адрес</b>\n\n"
        "г. Грозный, ул. Сайханова, д. 1\n\n"
        "🚇 Ближайшая остановка: «Сайханова»\n"
        "🚗 Парковка: бесплатная на территории"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺 Открыть на карте", url="https://maps.google.com/?q=Грозный+ул.+Сайханова+1")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="support")]
    ])

    await safe_delete_message(callback.message)
    await callback.message.answer(text, reply_markup=kb)
    await safe_callback_answer(callback)