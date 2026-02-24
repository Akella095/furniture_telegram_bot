# keyboards/admin.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Optional
from db.models import Category, Product, Order


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Главное меню админ-панели"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📦 Управление товарами", callback_data="admin_products"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="📁 Управление категориями", callback_data="admin_categories"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="📋 Заказы (лиды)", callback_data="admin_orders"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="📞 Консультации", callback_data="admin_consultations"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="❓ Запросы в поддержку", callback_data="admin_support_requests"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add_product"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Выход", callback_data="back_to_main"),
        width=1
    )
    return builder.as_markup()


def admin_products_keyboard(page: int = 1, has_next: bool = False) -> InlineKeyboardMarkup:
    """Список товаров для админа"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add_product"),
        width=1
    )

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"admin_products_page_{page - 1}"))
    if has_next:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"admin_products_page_{page + 1}"))
    if nav_row:
        builder.row(*nav_row)

    builder.row(
        InlineKeyboardButton(text="◀️ Назад в админку", callback_data="admin_back"),
        width=1
    )

    return builder.as_markup()


def admin_product_actions_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """Клавиатура с действиями над товаром в админке"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✏️ Редактировать товар", callback_data=f"admin_edit_product_{product_id}"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="🖼 Управление фото", callback_data=f"admin_manage_photos_{product_id}"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="🟢 Активировать", callback_data=f"admin_toggle_status_{product_id}_active"),
        InlineKeyboardButton(text="🔴 Деактивировать", callback_data=f"admin_toggle_status_{product_id}_inactive"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="❌ Удалить", callback_data=f"admin_delete_product_{product_id}"),
        InlineKeyboardButton(text="◀️ Назад к списку", callback_data=f"admin_back_to_products_{product_id}"),
        width=2
    )

    return builder.as_markup()


def admin_product_edit_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для выбора поля редактирования"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✏️ Название", callback_data=f"admin_edit_field_{product_id}_name"),
        InlineKeyboardButton(text="📝 Описание", callback_data=f"admin_edit_field_{product_id}_description"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="🌍 Страна", callback_data=f"admin_edit_field_{product_id}_country"),
        InlineKeyboardButton(text="📏 Размеры", callback_data=f"admin_edit_field_{product_id}_dimensions"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="💰 Цена", callback_data=f"admin_edit_field_{product_id}_price"),
        InlineKeyboardButton(text="📁 Категория", callback_data=f"admin_edit_field_{product_id}_category"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад к товару", callback_data=f"admin_view_product_{product_id}"),
        width=1
    )

    return builder.as_markup()


def admin_photos_management_keyboard(product_id: int, photos: list) -> InlineKeyboardMarkup:
    """Клавиатура для управления фотографиями товара"""
    builder = InlineKeyboardBuilder()

    for i, photo in enumerate(photos, 1):
        builder.row(
            InlineKeyboardButton(
                text=f"🗑 Удалить фото {i}",
                callback_data=f"admin_delete_photo_{photo.id}"
            ),
            width=1
        )

    builder.row(
        InlineKeyboardButton(text="➕ Добавить фото", callback_data=f"admin_add_photo_{product_id}"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад к товару", callback_data=f"admin_view_product_{product_id}"),
        width=1
    )

    return builder.as_markup()


def admin_categories_keyboard(
        categories: List[Category],
        parent_id: Optional[int] = None
) -> InlineKeyboardMarkup:
    """Управление категориями для админа"""
    builder = InlineKeyboardBuilder()

    for cat in categories:
        builder.row(
            InlineKeyboardButton(
                text=f"📁 {cat.name}",
                callback_data=f"admin_cat_edit_{cat.id}"
            ),
            InlineKeyboardButton(
                text="❌",
                callback_data=f"admin_cat_del_{cat.id}"
            ),
            width=2
        )

    builder.row(
        InlineKeyboardButton(
            text="➕ Создать категорию",
            callback_data=f"admin_cat_create_{parent_id if parent_id else 'root'}"
        ),
        width=1
    )

    if parent_id:
        builder.row(
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_cat_back_{parent_id}"),
            width=1
        )
    else:
        builder.row(
            InlineKeyboardButton(text="◀️ Назад в админку", callback_data="admin_back"),
            width=1
        )

    return builder.as_markup()


# ============= ФУНКЦИИ ДЛЯ ЗАКАЗОВ =============

def admin_orders_keyboard(
        status: str = "all",
        page: int = 1,
        has_next: bool = False
) -> InlineKeyboardMarkup:
    """Фильтр и пагинация заказов для админа"""
    builder = InlineKeyboardBuilder()

    statuses = ["все", "новая", "в работе", "выполнена", "отменена"]
    status_row = []
    for s in statuses:
        emoji = "🆕" if s == "новая" else "🔄" if s == "в работе" else "✅" if s == "выполнена" else "❌" if s == "отменена" else "📋"
        callback = f"admin_orders_filter_{s}"
        text = f"{emoji} {s.capitalize()}"
        status_row.append(InlineKeyboardButton(text=text, callback_data=callback))
    builder.row(*status_row, width=2)

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"admin_orders_page_{status}_{page - 1}"))
    if has_next:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"admin_orders_page_{status}_{page + 1}"))
    if nav_row:
        builder.row(*nav_row)

    builder.row(
        InlineKeyboardButton(text="◀️ Назад в админку", callback_data="admin_back"),
        width=1
    )

    return builder.as_markup()


def admin_order_actions_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Действия с заказом для админа"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🔄 В работу", callback_data=f"admin_order_status_{order_id}_в работе"),
        InlineKeyboardButton(text="✅ Выполнен", callback_data=f"admin_order_status_{order_id}_выполнена"),
        width=2
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отменить", callback_data=f"admin_order_status_{order_id}_отменена"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="📞 Связаться", callback_data=f"admin_order_contact_{order_id}"),
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin_orders"),
        width=2
    )

    return builder.as_markup()


def admin_confirm_keyboard(action: str, item_id: int) -> InlineKeyboardMarkup:
    """Подтверждение действия (удаление и т.д.)"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"admin_confirm_{action}_{item_id}"),
        InlineKeyboardButton(text="❌ Нет, отмена", callback_data=f"admin_cancel_{action}_{item_id}"),
        width=2
    )
    return builder.as_markup()