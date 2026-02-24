# keyboards/inline.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Optional, Tuple
from db.models import Category, Product, Order
from logger import logger


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🛏 Спальная мебель", callback_data="cat_root_1"),
        InlineKeyboardButton(text="🍳 Кухонная мебель", callback_data="cat_root_2"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🛋 Мягкая мебель", callback_data="cat_root_3"),
        InlineKeyboardButton(text="🪑 Столы и стулья", callback_data="cat_root_4"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🗄 Тумбы и комоды", callback_data="cat_root_5"),
        InlineKeyboardButton(text="🛏 Матрасы", callback_data="cat_root_6"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🚪 Шкафы", callback_data="cat_root_7"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="ℹ️ О компании / Контакты", callback_data="about"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="🔍 Поиск товаров", callback_data="search"),
        InlineKeyboardButton(text="📞 Поддержка", callback_data="support"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🛒 Мои заказы", callback_data="my_orders"),
        width=1
    )
    return builder.as_markup()


def categories_keyboard(
        categories: List[Category],
        parent_id: Optional[int] = None,
        show_back: bool = True,
        page: int = 1,
        total_pages: int = 1
) -> InlineKeyboardMarkup:
    """Клавиатура категорий"""
    builder = InlineKeyboardBuilder()

    # Добавляем категории
    for cat in categories:
        builder.row(
            InlineKeyboardButton(
                text=f"📁 {cat.name}",
                callback_data=f"cat_{cat.id}"
            ),
            width=1
        )

    # Пагинация для категорий
    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"cat_page_{parent_id}_{page - 1}"))
        nav_row.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="ignore"))
        if page < total_pages:
            nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"cat_page_{parent_id}_{page + 1}"))
        builder.row(*nav_row)

    # Кнопка поиска по категории (если есть родитель)
    if parent_id:
        builder.row(
            InlineKeyboardButton(text="🔍 Искать в этой категории", callback_data=f"search_cat_{parent_id}"),
            width=1
        )

    # Кнопки навигации
    nav_buttons = []

    # Кнопка "Назад" (если есть родительская категория)
    if show_back and parent_id:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_to_cat_{parent_id}"))

    # КНОПКА "ГЛАВНОЕ МЕНЮ" - ВСЕГДА ПОКАЗЫВАЕМ
    nav_buttons.append(InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main"))

    # Добавляем кнопки навигации
    if nav_buttons:
        builder.row(*nav_buttons, width=len(nav_buttons))

    return builder.as_markup()


def products_keyboard(
        products: List[Product],
        category_id: int,
        page: int = 1,
        has_next: bool = False
) -> InlineKeyboardMarkup:
    """Клавиатура списка товаров"""
    builder = InlineKeyboardBuilder()

    for product in products:
        price_text = f" - {product.price:,.0f} ₽" if product.price else ""
        name = product.name[:35] + "..." if len(product.name) > 35 else product.name
        button_text = f"{name}{price_text}"

        builder.row(
            InlineKeyboardButton(text=button_text, callback_data=f"prod_{product.id}"),
            width=1
        )

    # Пагинация
    if page > 1 or has_next:
        nav_row = []
        if page > 1:
            nav_row.append(
                InlineKeyboardButton(text="◀️ Предыдущая", callback_data=f"prod_page_{category_id}_{page - 1}"))
        if has_next:
            nav_row.append(
                InlineKeyboardButton(text="Следующая ▶️", callback_data=f"prod_page_{category_id}_{page + 1}"))
        builder.row(*nav_row)

    # Кнопки навигации
    nav_buttons = []

    if category_id > 0:
        nav_buttons.append(InlineKeyboardButton(text="📁 К категориям", callback_data=f"back_to_cat_{category_id}"))

    nav_buttons.append(InlineKeyboardButton(text="🔍 Поиск", callback_data="search"))
    nav_buttons.append(InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main"))

    builder.row(*nav_buttons, width=len(nav_buttons))

    return builder.as_markup()


def product_card_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """Клавиатура карточки товара"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Оформить заказ", callback_data=f"order_{product_id}"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="📞 Заказать консультацию", callback_data=f"consult_{product_id}"),
        InlineKeyboardButton(text="❓ Задать вопрос", callback_data=f"ask_{product_id}"),
        width=2
    )

    builder.row(
        InlineKeyboardButton(text="🔸🔸🔸🔸🔸🔸🔸", callback_data="ignore"),
        width=1
    )

    # Всегда показываем кнопку "Главное меню"
    builder.row(
        InlineKeyboardButton(text="◀️ Назад к списку", callback_data=f"back_to_products_{product_id}"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main"),
        width=2
    )

    return builder.as_markup()


def order_phone_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для ввода телефона"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📱 Отправить контакт", callback_data="send_contact"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_product"),
        width=1
    )
    return builder.as_markup()


def order_confirm_keyboard() -> InlineKeyboardMarkup:
    """Подтверждение заказа"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_order"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_order"),
        width=2
    )
    return builder.as_markup()


def search_keyboard(page: int = 1, has_next: bool = False, query: str = "") -> InlineKeyboardMarkup:
    """Клавиатура для результатов поиска"""
    builder = InlineKeyboardBuilder()

    # Пагинация
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️ Пред.", callback_data=f"search_page_{query}_{page - 1}"))
    if has_next:
        nav_row.append(InlineKeyboardButton(text="След. ▶️", callback_data=f"search_page_{query}_{page + 1}"))
    if nav_row:
        builder.row(*nav_row)

    # Кнопки навигации
    builder.row(
        InlineKeyboardButton(text="🔄 Новый поиск", callback_data="search"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="📁 Каталог", callback_data="back_to_main"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main"),
        width=2
    )

    return builder.as_markup()


def support_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура поддержки"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 Задать вопрос", callback_data="ask_support"),
        width=1
    )
    # Убираем URL кнопки, оставляем только callback
    builder.row(
        InlineKeyboardButton(text="📞 Контакты", callback_data="show_contacts"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="📍 Адрес магазина", callback_data="address"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_main"),
        width=1
    )
    return builder.as_markup()


def about_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура 'О компании'"""
    builder = InlineKeyboardBuilder()

    # Информационные кнопки
    builder.row(
        InlineKeyboardButton(text="🕒 Режим работы", callback_data="working_hours"),
        InlineKeyboardButton(text="📍 Адрес", callback_data="address"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="📞 Контакты", callback_data="show_contacts"),
        InlineKeyboardButton(text="🌐 Сайт", url="https://www.furniture.ru"),
        width=2
    )

    # Кнопка "Назад" в главное меню
    builder.row(
        InlineKeyboardButton(text="◀️ Назад в главное меню", callback_data="back_to_main"),
        width=1
    )

    return builder.as_markup()


def my_orders_keyboard(orders: List[Order], page: int = 1, has_next: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура списка заказов пользователя"""
    builder = InlineKeyboardBuilder()

    for order in orders[:5]:  # Показываем максимум 5 заказов на странице
        status_emoji = {
            "новая": "🆕",
            "в работе": "🔄",
            "выполнена": "✅",
            "отменена": "❌"
        }.get(order.status, "📦")

        button_text = f"{status_emoji} Заказ #{order.id} - {order.product_name[:20]}"
        builder.row(InlineKeyboardButton(text=button_text, callback_data=f"view_order_{order.id}"))

    # Пагинация
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"my_orders_page_{page - 1}"))
    if has_next:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"my_orders_page_{page + 1}"))
    if nav_row:
        builder.row(*nav_row)

    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_main"))

    return builder.as_markup()


def contacts_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с контактами (без URL)"""
    builder = InlineKeyboardBuilder()

    # Убираем URL, делаем кнопки с callback
    builder.row(
        InlineKeyboardButton(text="📞 Показать номер", callback_data="show_phone"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="📧 Показать email", callback_data="show_email"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="📍 Показать адрес", callback_data="show_address_text"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="about"),
        width=1
    )
    return builder.as_markup()


async def safe_edit_or_delete(callback: CallbackQuery, text: str, reply_markup=None):
    """Безопасно редактирует или удаляет и создает новое сообщение"""
    try:
        # Пробуем отредактировать
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception as e:
        # Если не получается (например, сообщение с фото), удаляем и создаем новое
        logger.warning(f"Не удалось отредактировать: {e}")
        try:
            await callback.message.delete()
        except:
            pass
        await callback.message.answer(text, reply_markup=reply_markup)

    await callback.answer()