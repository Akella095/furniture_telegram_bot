# handlers/user/start.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from keyboards.inline import main_menu_keyboard, about_keyboard, support_keyboard, contacts_keyboard, \
    categories_keyboard
from keyboards.reply import main_menu_keyboard as reply_main_menu
from db.queries import get_root_categories, is_admin
from db.models import Order
from states.search import SearchStates
from config import YOUR_ADMIN_ID
from logger import logger

router = Router(name="user_start")


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    """Обработчик команды /start"""
    await state.clear()

    welcome_text = (
        "🏠 <b>Добро пожаловать в магазин мебели!</b>\n\n"
        "📋 <b>Главное меню:</b>\n"
        "• Просмотр каталога мебели\n"
        "• Узнать характеристики товаров\n"
        "• Заказать консультацию\n"
        "• Оформить заказ\n\n"
        "Выберите интересующий раздел ниже:"
    )

    await message.answer(welcome_text, reply_markup=main_menu_keyboard())

    # Показываем админ-панель только вам
    if YOUR_ADMIN_ID and message.from_user.id == YOUR_ADMIN_ID:
        from keyboards.admin import admin_panel_keyboard
        await message.answer(
            "👨‍💼 <b>Панель администратора</b>\n\n"
            "У вас есть права доступа к управлению магазином.",
            reply_markup=admin_panel_keyboard()
        )

    logger.info(f"Пользователь {message.from_user.id} (@{message.from_user.username}) запустил бота")


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат в главное меню"""
    await state.clear()

    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")

    text = "🏠 <b>Главное меню</b>\n\nВыберите раздел:"
    await callback.message.answer(text, reply_markup=main_menu_keyboard())

    try:
        await callback.answer()
    except:
        pass


@router.callback_query(F.data == "about")
async def show_about(callback: CallbackQuery):
    """Информация о компании"""
    text = (
        "🏢 <b>О нашей компании</b>\n\n"
        "Мы работаем на рынке мебели более 10 лет.\n"
        "Наша миссия — создавать уют в вашем доме!\n\n"
        "📍 <b>Адрес:</b> г. Грозный, ул. Сайханова, д. 1\n"
        "🕒 <b>Режим работы:</b> Пн-Вс 10:00 - 21:00\n"
        "📞 <b>Телефон:</b> 8 (928) 555-55-55\n"
        "📧 <b>Email:</b> info@furniture.ru\n"
        "🌐 <b>Сайт:</b> www.furniture.ru\n\n"
        "<i>Выберите интересующий раздел:</i>"
    )

    await callback.message.edit_text(text, reply_markup=about_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "support")
async def show_support(callback: CallbackQuery):
    """Страница поддержки"""
    text = (
        "📞 <b>Служба поддержки</b>\n\n"
        "Если у вас возникли вопросы:\n\n"
        "• Нажмите «Задать вопрос» и напишите нам\n"
        "• Позвоните по телефону\n"
        "• Напишите на email\n"
        "• Посетите наш магазин\n\n"
        "Мы всегда рады помочь!"
    )

    await callback.message.edit_text(text, reply_markup=support_keyboard())
    await callback.answer()


@router.callback_query(F.data == "address")
async def show_address(callback: CallbackQuery):
    """Показать адрес на карте"""
    text = (
        "📍 <b>Наш адрес:</b>\n"
        "г. Грозный, ул. Сайханова, д. 1\n\n"
        "🚇 Ближайшая остановка: «Сайханова»\n"
        "🚗 Парковка: бесплатная на территории"
    )

    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "show_contacts")
async def show_contacts(callback: CallbackQuery):
    """Показать контакты"""
    text = (
        "📞 <b>Наши контакты</b>\n\n"
        "Выберите, что хотите узнать:\n\n"
        "• 📞 Телефон\n"
        "• 📧 Email\n"
        "• 📍 Адрес магазина"
    )

    await callback.message.edit_text(text, reply_markup=contacts_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "show_phone")
async def show_phone(callback: CallbackQuery):
    """Показать номер телефона"""
    text = (
        "📞 <b>Наш телефон</b>\n\n"
        "8 (928) 555-55-55\n\n"
        "<i>Вы можете скопировать номер и позвонить нам в рабочее время.</i>\n\n"
        "🕒 Режим работы: Пн-Вс 10:00 - 21:00"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к контактам", callback_data="show_contacts")]
    ])

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "show_email")
async def show_email(callback: CallbackQuery):
    """Показать email"""
    text = (
        "📧 <b>Наш email</b>\n\n"
        "info@furniture.ru\n\n"
        "<i>Напишите нам, и мы ответим в ближайшее время!</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к контактам", callback_data="show_contacts")]
    ])

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "show_address_text")
async def show_address_text(callback: CallbackQuery):
    """Показать адрес"""
    text = (
        "📍 <b>Наш адрес</b>\n\n"
        "г. Грозный, ул. Сайханова, д. 1\n\n"
        "🚇 Ближайшая остановка: «Сайханова»\n"
        "🚗 Парковка: бесплатная на территории\n\n"
        "<i>Ждем вас в гости!</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к контактам", callback_data="show_contacts")]
    ])

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "working_hours")
async def show_working_hours(callback: CallbackQuery):
    """Показать режим работы"""
    text = (
        "🕒 <b>Режим работы</b>\n\n"
        "🟢 <b>Будние дни:</b> 10:00 - 21:00\n"
        "🟢 <b>Суббота:</b> 10:00 - 20:00\n"
        "🟡 <b>Воскресенье:</b> 11:00 - 19:00\n\n"
        "📍 г. Грозный, ул. Сайханова, д. 1\n"
        "📞 8 (928) 555-55-55\n\n"
        "<i>Ждем вас в гости!</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="about")]
    ])

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ==================== ОБРАБОТЧИКИ КОМАНД ====================

@router.message(Command("catalog"))
async def cmd_catalog(message: Message, session: AsyncSession):
    """Обработчик команды /catalog"""
    from handlers.user.catalog import show_root_categories
    await show_root_categories(message, session)


@router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext):
    """Обработчик команды /search"""
    await message.answer(
        "🔍 <b>Поиск товаров</b>\n\n"
        "Введите название товара, страну или описание для поиска:"
    )
    await state.set_state(SearchStates.waiting_query)


@router.message(Command("orders"))
async def cmd_orders(message: Message, session: AsyncSession):
    """Обработчик команды /orders"""
    from handlers.user.orders import show_my_orders_direct
    await show_my_orders_direct(message, session)



@router.message(Command("support"))
async def cmd_support(message: Message):
    """Обработчик команды /support"""
    text = (
        "📞 <b>Служба поддержки</b>\n\n"
        "Если у вас возникли вопросы:\n\n"
        "• Нажмите «Задать вопрос» и напишите нам\n"
        "• Позвоните по телефону\n"
        "• Напишите на email\n"
        "• Посетите наш магазин\n\n"
        "Мы всегда рады помочь!"
    )

    await message.answer(text, reply_markup=support_keyboard())


@router.message(Command("about"))
async def cmd_about(message: Message):
    """Обработчик команды /about"""
    text = (
        "🏢 <b>О нашей компании</b>\n\n"
        "Мы работаем на рынке мебели более 10 лет.\n"
        "Наша миссия — создавать уют в вашем доме!\n\n"
        "📍 Адрес: г. Грозный, ул. Сайханова, д. 1\n"
        "🕒 Режим работы: Пн-Вс 10:00 - 21:00\n"
        "📞 Телефон: 8 (928) 555-55-55\n\n"
        "👇 Нажмите «Показать контакты» для связи"
    )

    await message.answer(text, reply_markup=about_keyboard())


@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession):
    """Обработчик команды /admin"""
    from handlers.admin.panel import admin_panel_direct
    from config import YOUR_ADMIN_ID

    if YOUR_ADMIN_ID and message.from_user.id != YOUR_ADMIN_ID:
        await message.answer("⛔ У вас нет прав доступа к админ-панели.")
        return

    await admin_panel_direct(message, session)


@router.message(F.text == "🏠 Главное меню")
async def reply_main_menu(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик нажатия на кнопку Главное меню в reply-клавиатуре"""
    await state.clear()

    try:
        await message.delete()
    except:
        pass

    text = "🏠 <b>Главное меню</b>\n\nВыберите раздел:"
    await message.answer(text, reply_markup=main_menu_keyboard())