# handlers/user/orders.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, \
    KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import logging

from db.models import Order, Product
from db.queries import get_product, create_order, get_orders, update_order_status, create_consultation
from keyboards.inline import (
    product_card_keyboard, order_confirm_keyboard, my_orders_keyboard
)
from keyboards.reply import phone_keyboard, remove_keyboard, order_cancel_keyboard
from states.order import OrderStates, ConsultationStates
from utils.helpers import validate_phone, format_phone, format_order_text
from config import ADMIN_IDS, MANAGER_CHAT_ID
from logger import logger

router = Router(name="user_orders")


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


def clean_phone_for_url(phone: str) -> str:
    """Очищает номер телефона для использования в URL"""
    cleaned = phone.replace(" ", "").replace("(", "").replace(")", "").replace("-", "")
    if not cleaned.startswith("+"):
        cleaned = "+" + cleaned
    return cleaned


# ============= ОФОРМЛЕНИЕ ЗАКАЗА =============

@router.callback_query(F.data.startswith("order_"))
async def start_order(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начать оформление заказа"""
    product_id = int(callback.data.split("_")[1])
    product = await get_product(session, product_id)

    if not product:
        await safe_callback_answer(callback, "Товар не найден", True)
        return

    # Сохраняем данные в FSM
    await state.update_data(
        product_id=product.id,
        product_name=product.name
    )

    logger.info(f"Начало оформления заказа для товара: {product.name} (ID: {product.id})")

    await safe_delete_message(callback.message)

    await callback.message.answer(
        "📝 <b>Оформление заказа</b>\n\n"
        "Пожалуйста, введите ваше имя:\n"
        "(или нажмите кнопку ниже для отмены)",
        reply_markup=order_cancel_keyboard()
    )

    await state.set_state(OrderStates.waiting_name)
    await safe_callback_answer(callback)


@router.message(F.text == "❌ Отменить заказ")
async def cancel_order_form(message: Message, state: FSMContext, session: AsyncSession):
    """Отмена оформления заказа"""
    data = await state.get_data()
    product_id = data.get('product_id')

    await state.clear()

    # Удаляем reply-клавиатуру
    await message.answer(
        "⏳ Обработка отмены...",
        reply_markup=ReplyKeyboardRemove()
    )

    if product_id:
        # Возвращаемся к товару
        from handlers.user.catalog import show_product
        # Создаем фейковый callback с правильным методом answer
        class FakeCallback:
            def __init__(self, message):
                self.message = message
                self.data = f"prod_{product_id}"

            async def answer(self, text=None, show_alert=False):
                pass

        fake_callback = FakeCallback(message)
        await show_product(fake_callback, session)
    else:
        # Если нет товара, возвращаемся в главное меню
        from keyboards.inline import main_menu_keyboard
        await message.answer(
            "❌ Оформление заказа отменено.\n\n"
            "🏠 <b>Главное меню</b>",
            reply_markup=main_menu_keyboard()
        )


@router.message(F.text == "🏠 Главное меню")
async def back_to_main_menu(message: Message, state: FSMContext, session: AsyncSession):
    """Возврат в главное меню"""
    await state.clear()

    # Удаляем reply-клавиатуру
    await message.answer(
        "⏳ Возврат в главное меню...",
        reply_markup=ReplyKeyboardRemove()
    )

    from keyboards.inline import main_menu_keyboard
    await message.answer(
        "🏠 <b>Главное меню</b>\n\nВыберите раздел:",
        reply_markup=main_menu_keyboard()
    )


@router.message(OrderStates.waiting_name)
async def process_order_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка имени в заказе"""
    if message.text == "❌ Отменить заказ":
        await cancel_order_form(message, state, session)
        return

    if message.text == "🏠 Главное меню":
        await back_to_main_menu(message, state, session)
        return

    name = message.text.strip()

    if len(name) < 2 or len(name) > 100:
        await message.answer(
            "❌ Имя должно быть от 2 до 100 символов.\n"
            "Пожалуйста, введите имя ещё раз:",
            reply_markup=order_cancel_keyboard()
        )
        return

    await state.update_data(full_name=name)
    logger.info(f"Имя сохранено: {name}, переходим к запросу телефона")

    await message.answer(
        "📞 <b>Введите ваш номер телефона</b>\n\n"
        "Формат: +7 XXX XXX-XX-XX или 8 XXX XXX-XX-XX\n\n"
        "Или нажмите кнопку ниже:",
        reply_markup=phone_keyboard()
    )

    await state.set_state(OrderStates.waiting_phone)


@router.message(OrderStates.waiting_phone, F.text == "◀️ Назад")
async def back_to_name_from_phone(message: Message, state: FSMContext, session: AsyncSession):
    """Возврат к вводу имени из ввода телефона"""
    # Удаляем текущую клавиатуру
    await message.answer(
        "⏳ Возврат...",
        reply_markup=ReplyKeyboardRemove()
    )

    # Возвращаемся к вводу имени
    await state.set_state(OrderStates.waiting_name)
    await message.answer(
        "📝 <b>Оформление заказа</b>\n\n"
        "Пожалуйста, введите ваше имя:\n"
        "(или нажмите кнопку ниже для отмены)",
        reply_markup=order_cancel_keyboard()
    )


@router.message(OrderStates.waiting_phone, F.contact)
async def process_order_phone_contact(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка контакта (номера телефона)"""
    if message.text == "❌ Отменить заказ":
        await cancel_order_form(message, state, session)
        return

    if message.text == "🏠 Главное меню":
        await back_to_main_menu(message, state, session)
        return

    phone = message.contact.phone_number

    if phone.startswith('7'):
        phone = '+' + phone
    elif phone.startswith('8'):
        phone = '+7' + phone[1:]

    formatted_phone = format_phone(phone)
    await state.update_data(phone=formatted_phone)

    await message.answer(
        f"✅ Номер получен: {formatted_phone}",
        reply_markup=ReplyKeyboardRemove()
    )

    await message.answer(
        "💬 Если хотите, добавьте комментарий к заказу\n"
        "(или отправьте \"-\" чтобы пропустить):"
    )
    await state.set_state(OrderStates.waiting_comment)


@router.message(OrderStates.waiting_phone)
async def process_order_phone_text(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка ручного ввода телефона"""
    if message.text == "❌ Отменить заказ":
        await cancel_order_form(message, state, session)
        return

    if message.text == "🏠 Главное меню":
        await back_to_main_menu(message, state, session)
        return

    if message.text == "◀️ Назад":
        await back_to_name_from_phone(message, state, session)
        return

    phone = message.text.strip()

    if not validate_phone(phone):
        await message.answer(
            "❌ Неверный формат номера.\n"
            "Используйте формат: +7XXXXXXXXXX или 8XXXXXXXXXX\n"
            "Попробуйте ещё раз:",
            reply_markup=phone_keyboard()
        )
        return

    formatted_phone = format_phone(phone)
    await state.update_data(phone=formatted_phone)

    await message.answer(
        f"✅ Номер принят: {formatted_phone}",
        reply_markup=ReplyKeyboardRemove()
    )

    await message.answer(
        "💬 Добавьте комментарий к заказу\n"
        "(или отправьте \"-\" чтобы пропустить):"
    )
    await state.set_state(OrderStates.waiting_comment)


@router.message(OrderStates.waiting_comment)
async def process_order_comment(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка комментария"""
    if message.text == "❌ Отменить заказ":
        await cancel_order_form(message, state, session)
        return

    if message.text == "🏠 Главное меню":
        await back_to_main_menu(message, state, session)
        return

    comment = message.text.strip()

    if comment == "-":
        comment = None

    await state.update_data(comment=comment)

    data = await state.get_data()

    text = (
        "📋 <b>Проверьте данные заказа:</b>\n\n"
        f"<b>Товар:</b> {data['product_name']}\n"
        f"<b>Имя:</b> {data['full_name']}\n"
        f"<b>Телефон:</b> {data['phone']}\n"
    )

    if data.get('comment'):
        text += f"<b>Комментарий:</b> {data['comment']}\n"

    text += "\n\n✅ Всё верно?"

    await message.answer(
        text,
        reply_markup=order_confirm_keyboard()
    )
    await state.set_state(OrderStates.confirmation)


@router.callback_query(OrderStates.confirmation, F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение и сохранение заказа"""
    data = await state.get_data()

    order = await create_order(
        session=session,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=data['full_name'],
        phone=data['phone'],
        product_id=data.get('product_id'),
        product_name=data['product_name'],
        comment=data.get('comment')
    )

    await callback.message.edit_text(
        "✅ <b>Заказ успешно оформлен!</b>\n\n"
        f"Номер вашего заказа: #{order.id}\n\n"
        "Наш менеджер свяжется с вами в ближайшее время.\n"
        "Спасибо за заказ! 🎉",
        reply_markup=None
    )

    if MANAGER_CHAT_ID:
        try:
            clean_phone = clean_phone_for_url(data['phone'])

            product_info = f"Товар: {order.product_name}"
            if data.get('product_id'):
                product_info += f"\nID товара: {data['product_id']}"

            manager_text = (
                "🆕 <b>НОВЫЙ ЗАКАЗ!</b>\n\n"
                f"<b>Заказ #{order.id}</b>\n"
                f"<b>Дата:</b> {order.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"<b>Клиент:</b>\n"
                f"Имя: {order.full_name}\n"
                f"Телефон: {order.phone}\n"
                f"Username: @{order.username if order.username else 'нет'}\n"
                f"User ID: {order.user_id}\n\n"
                f"<b>Заказ:</b>\n{product_info}\n"
            )

            if order.comment:
                manager_text += f"\n<b>Комментарий:</b>\n{order.comment}\n"

            reply_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📞 Позвонить клиенту", url=f"tel:{clean_phone}")],
                [InlineKeyboardButton(text="💬 Написать", url=f"tg://user?id={order.user_id}")]
            ])

            await callback.bot.send_message(
                MANAGER_CHAT_ID,
                manager_text,
                parse_mode="HTML",
                reply_markup=reply_keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления менеджеру: {e}")

    await state.clear()
    await safe_callback_answer(callback, "Заказ оформлен!")


@router.callback_query(F.data == "cancel_order")
async def cancel_order(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена оформления заказа через inline кнопку"""
    data = await state.get_data()
    product_id = data.get('product_id')

    await state.clear()

    # Убираем inline клавиатуру
    await callback.message.edit_text(
        "❌ Оформление заказа отменено.",
        reply_markup=None
    )

    if product_id:
        # Возвращаемся к товару
        await show_product(callback, session)
    else:
        # Если нет товара, возвращаемся в главное меню
        from keyboards.inline import main_menu_keyboard
        await callback.message.answer(
            "🏠 <b>Главное меню</b>\n\nВыберите раздел:",
            reply_markup=main_menu_keyboard()
        )

    await safe_callback_answer(callback)


# ============= КОНСУЛЬТАЦИЯ =============

@router.callback_query(F.data.startswith("consult_"))
async def start_consultation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Заказ консультации"""
    product_id = int(callback.data.split("_")[1])
    product = await get_product(session, product_id)

    if product:
        await state.update_data(
            product_id=product.id,
            product_name=product.name
        )

    await safe_delete_message(callback.message)

    await callback.message.answer(
        "📞 <b>Заказ консультации</b>\n\n"
        "Наш менеджер свяжется с вами для консультации.\n\n"
        "Введите ваше имя:\n"
        "(или нажмите кнопку ниже для отмены)",
        reply_markup=order_cancel_keyboard()
    )
    await state.set_state(ConsultationStates.waiting_name)
    await safe_callback_answer(callback)


@router.message(ConsultationStates.waiting_name)
async def process_consultation_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка имени для консультации"""
    if message.text == "❌ Отменить заказ":
        await cancel_order_form(message, state, session)
        return

    if message.text == "🏠 Главное меню":
        await back_to_main_menu(message, state, session)
        return

    name = message.text.strip()

    if len(name) < 2:
        await message.answer(
            "❌ Слишком короткое имя. Пожалуйста, введите ещё раз:",
            reply_markup=order_cancel_keyboard()
        )
        return

    await state.update_data(full_name=name)
    await message.answer(
        "📞 Введите ваш номер телефона:",
        reply_markup=phone_keyboard()
    )
    await state.set_state(ConsultationStates.waiting_phone)


@router.message(ConsultationStates.waiting_phone, F.text == "◀️ Назад")
async def back_to_name_from_consult_phone(message: Message, state: FSMContext, session: AsyncSession):
    """Возврат к вводу имени из ввода телефона для консультации"""
    # Удаляем текущую клавиатуру
    await message.answer(
        "⏳ Возврат...",
        reply_markup=ReplyKeyboardRemove()
    )

    # Возвращаемся к вводу имени
    await state.set_state(ConsultationStates.waiting_name)
    await message.answer(
        "📞 <b>Заказ консультации</b>\n\n"
        "Введите ваше имя:\n"
        "(или нажмите кнопку ниже для отмены)",
        reply_markup=order_cancel_keyboard()
    )


@router.message(ConsultationStates.waiting_phone, F.contact)
async def process_consultation_phone_contact(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка контакта для консультации"""
    if message.text == "❌ Отменить заказ":
        await cancel_order_form(message, state, session)
        return

    if message.text == "🏠 Главное меню":
        await back_to_main_menu(message, state, session)
        return

    phone = message.contact.phone_number

    if phone.startswith('7'):
        phone = '+' + phone
    elif phone.startswith('8'):
        phone = '+7' + phone[1:]

    formatted_phone = format_phone(phone)
    await state.update_data(phone=formatted_phone)

    await message.answer(
        f"✅ Номер получен: {formatted_phone}",
        reply_markup=ReplyKeyboardRemove()
    )

    await show_consultation_confirmation(message, state)


@router.message(ConsultationStates.waiting_phone)
async def process_consultation_phone_text(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка ручного ввода телефона для консультации"""
    if message.text == "❌ Отменить заказ":
        await cancel_order_form(message, state, session)
        return

    if message.text == "🏠 Главное меню":
        await back_to_main_menu(message, state, session)
        return

    if message.text == "◀️ Назад":
        await back_to_name_from_consult_phone(message, state, session)
        return

    phone = message.text.strip()

    if not validate_phone(phone):
        await message.answer(
            "❌ Неверный формат номера. Попробуйте ещё раз:",
            reply_markup=phone_keyboard()
        )
        return

    formatted_phone = format_phone(phone)
    await state.update_data(phone=formatted_phone)

    await message.answer(
        f"✅ Номер принят: {formatted_phone}",
        reply_markup=ReplyKeyboardRemove()
    )

    await show_consultation_confirmation(message, state)


async def show_consultation_confirmation(message: Message, state: FSMContext):
    """Показать подтверждение консультации"""
    data = await state.get_data()

    text = (
        "📋 <b>Запрос на консультацию:</b>\n\n"
        f"<b>Имя:</b> {data['full_name']}\n"
        f"<b>Телефон:</b> {data['phone']}\n"
    )

    if data.get('product_name'):
        text += f"<b>Товар:</b> {data['product_name']}\n"

    text += "\n\n✅ Отправить запрос?"

    await message.answer(
        text,
        reply_markup=order_confirm_keyboard()
    )
    await state.set_state(ConsultationStates.confirmation)


@router.callback_query(ConsultationStates.confirmation, F.data == "confirm_order")
async def confirm_consultation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Подтверждение консультации"""
    data = await state.get_data()

    consultation = await create_consultation(
        session=session,
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=data['full_name'],
        phone=data['phone'],
        product_id=data.get('product_id'),
        product_name=data.get('product_name')
    )

    await callback.message.edit_text(
        "✅ <b>Запрос на консультацию отправлен!</b>\n\n"
        "Наш менеджер свяжется с вами в ближайшее время.\n"
        f"Номер запроса: #{consultation.id}\n"
        "Спасибо за обращение! 📞",
        reply_markup=None
    )

    if MANAGER_CHAT_ID:
        try:
            clean_phone = clean_phone_for_url(data['phone'])

            reply_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📞 Связаться с клиентом",
                    url=f"tg://user?id={callback.from_user.id}"
                )],
                [InlineKeyboardButton(
                    text="📞 Позвонить",
                    url=f"tel:{clean_phone}"
                )],
                [InlineKeyboardButton(
                    text="✅ Отметить выполненной",
                    callback_data=f"consult_done_{consultation.id}"
                )],
                [InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data=f"consult_cancel_{consultation.id}"
                )]
            ])

            text = (
                "📞 <b>НОВЫЙ ЗАПРОС КОНСУЛЬТАЦИИ</b>\n\n"
                f"<b>Запрос #{consultation.id}</b>\n"
                f"<b>Дата:</b> {consultation.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"<b>Клиент:</b>\n"
                f"Имя: {consultation.full_name}\n"
                f"Телефон: {consultation.phone}\n"
                f"Username: @{consultation.username or 'нет'}\n"
                f"User ID: <code>{consultation.user_id}</code>\n\n"
            )

            if consultation.product_name:
                text += f"<b>Товар:</b> {consultation.product_name}\n"
                if consultation.product_id:
                    text += f"<b>ID товара:</b> {consultation.product_id}\n"

            await callback.bot.send_message(
                MANAGER_CHAT_ID,
                text,
                parse_mode="HTML",
                reply_markup=reply_keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления: {e}")

    await state.clear()
    await safe_callback_answer(callback)


# ============= ПРОСМОТР ЗАКАЗОВ =============

@router.callback_query(F.data == "my_orders")
async def show_my_orders(callback: CallbackQuery, session: AsyncSession):
    """Показать заказы пользователя"""
    result = await session.execute(
        select(Order)
        .where(Order.user_id == callback.from_user.id)
        .order_by(Order.created_at.desc())
    )
    orders = result.scalars().all()

    await safe_delete_message(callback.message)

    if not orders:
        await callback.message.answer(
            "🛒 У вас пока нет заказов.\n\n"
            "Перейдите в каталог и выберите понравившиеся товары!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🛏 В каталог", callback_data="back_to_main")]
            ])
        )
        await safe_callback_answer(callback)
        return

    text = "🛍 <b>Ваши заказы:</b>\n\n"
    await callback.message.answer(
        text,
        reply_markup=my_orders_keyboard(orders[:5], page=1, has_next=len(orders) > 5)
    )
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("view_order_"))
async def view_order_details(callback: CallbackQuery, session: AsyncSession):
    """Просмотр деталей заказа"""
    order_id = int(callback.data.split("_")[2])

    result = await session.execute(
        select(Order).where(Order.id == order_id, Order.user_id == callback.from_user.id)
    )
    order = result.scalar_one_or_none()

    if not order:
        await safe_callback_answer(callback, "Заказ не найден", True)
        return

    text = format_order_text(order)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к списку", callback_data="my_orders")]
    ])

    await safe_delete_message(callback.message)
    await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("my_orders_page_"))
async def my_orders_page(callback: CallbackQuery, session: AsyncSession):
    """Пагинация заказов пользователя"""
    page = int(callback.data.split("_")[3])
    limit = 5
    offset = (page - 1) * limit

    result = await session.execute(
        select(Order)
        .where(Order.user_id == callback.from_user.id)
        .order_by(Order.created_at.desc())
        .offset(offset)
        .limit(limit + 1)
    )
    orders = result.scalars().all()
    has_next = len(orders) > limit
    orders = orders[:limit]

    text = f"🛍 <b>Ваши заказы:</b> Страница {page}\n\n"

    await safe_delete_message(callback.message)
    await callback.message.answer(
        text,
        reply_markup=my_orders_keyboard(orders, page, has_next)
    )
    await safe_callback_answer(callback)


# ============= ПРЯМЫЕ ВЫЗОВЫ (ДЛЯ КОМАНД) =============

async def show_my_orders_direct(message: Message, session: AsyncSession):
    """Показать заказы пользователя (прямой вызов)"""
    result = await session.execute(
        select(Order)
        .where(Order.user_id == message.from_user.id)
        .order_by(Order.created_at.desc())
    )
    orders = result.scalars().all()

    if not orders:
        await message.answer(
            "🛒 У вас пока нет заказов.\n\n"
            "Перейдите в каталог и выберите понравившиеся товары!"
        )
        return

    text = "🛍 <b>Ваши заказы:</b>\n\n"
    await message.answer(
        text,
        reply_markup=my_orders_keyboard(orders[:5], page=1, has_next=len(orders) > 5)
    )