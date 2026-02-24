# handlers/admin/products.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging
from typing import List
from datetime import datetime

from filters.admin import is_admin_filter
from db.models import Product, Category, ProductPhoto
from db.queries import (
    get_product, create_product, update_product, delete_product,
    add_product_photos, delete_product_photo, get_products_by_category,
    get_category, get_root_categories, get_subcategories
)
from keyboards.admin import (
    admin_products_keyboard, admin_product_actions_keyboard,
    admin_product_edit_keyboard, admin_confirm_keyboard,
    admin_photos_management_keyboard
)
from keyboards.inline import categories_keyboard
from states.product import AddProductStates, EditProductStates
from utils.helpers import format_product_caption, format_price
from logger import logger

router = Router(name="admin_products")
router.message.filter(is_admin_filter)
router.callback_query.filter(is_admin_filter)


# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============

async def safe_callback_answer(callback: CallbackQuery, text: str = None, show_alert: bool = False):
    """Безопасный ответ на callback с обработкой ошибок"""
    try:
        if text:
            await callback.answer(text, show_alert=show_alert)
        else:
            await callback.answer()
    except Exception as e:
        logger.warning(f"Не удалось ответить на callback: {e}")


async def safe_delete_message(message):
    """Безопасное удаление сообщения"""
    try:
        await message.delete()
        return True
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
        return False


# ============= ПРЯМЫЕ ФУНКЦИИ ДЛЯ ОТОБРАЖЕНИЯ =============

async def admin_products_list_direct(callback: CallbackQuery, session: AsyncSession, page: int = 1):
    """Прямой показ списка товаров без попытки редактирования"""
    limit = 10
    offset = (page - 1) * limit

    result = await session.execute(
        select(Product)
        .options(selectinload(Product.category))
        .order_by(Product.created_at.desc())
        .offset(offset)
        .limit(limit + 1)
    )
    products = result.scalars().all()
    has_next = len(products) > limit
    products = products[:limit]

    text = f"📦 <b>Управление товарами</b>\n\n"

    if not products:
        text += "В каталоге пока нет товаров."
    else:
        text += f"Всего товаров: {len(products)} (страница {page})\n\n"

        for product in products:
            price_text = f" - {format_price(product.price)}" if product.price else ""
            status = "✅" if product.is_active else "❌"
            category_name = product.category.name if product.category else 'Не указана'

            text += f"{status} <b>{product.name}</b>{price_text}\n"
            text += f"ID: {product.id} | Категория: {category_name}\n\n"

    builder = InlineKeyboardBuilder()

    for product in products:
        builder.row(
            InlineKeyboardButton(
                text=f"📦 {product.name[:30]}...",
                callback_data=f"admin_view_product_{product.id}"
            ),
            width=1
        )

    if page > 1 or has_next:
        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton(text="◀️ Пред.", callback_data=f"admin_products_page_{page - 1}"))
        if has_next:
            nav_row.append(InlineKeyboardButton(text="След. ▶️", callback_data=f"admin_products_page_{page + 1}"))
        builder.row(*nav_row)

    builder.row(
        InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add_product"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад в админку", callback_data="admin_back"),
        width=1
    )

    await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


async def admin_products_page_direct(callback: CallbackQuery, session: AsyncSession, page: int):
    """Прямой показ страницы товаров"""
    limit = 10
    offset = (page - 1) * limit

    result = await session.execute(
        select(Product)
        .options(selectinload(Product.category))
        .order_by(Product.created_at.desc())
        .offset(offset)
        .limit(limit + 1)
    )
    products = result.scalars().all()
    has_next = len(products) > limit
    products = products[:limit]

    text = f"📦 <b>Управление товарами</b>\n\nСтраница {page}\n\n"

    for product in products:
        price_text = f" - {format_price(product.price)}" if product.price else ""
        status = "✅" if product.is_active else "❌"
        category_name = product.category.name if product.category else 'Не указана'

        text += f"{status} <b>{product.name}</b>{price_text}\n"
        text += f"ID: {product.id} | Категория: {category_name}\n\n"

    builder = InlineKeyboardBuilder()

    for product in products:
        builder.row(
            InlineKeyboardButton(
                text=f"📦 {product.name[:30]}...",
                callback_data=f"admin_view_product_{product.id}"
            ),
            width=1
        )

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️ Пред.", callback_data=f"admin_products_page_{page - 1}"))
    if has_next:
        nav_row.append(InlineKeyboardButton(text="След. ▶️", callback_data=f"admin_products_page_{page + 1}"))
    if nav_row:
        builder.row(*nav_row)

    builder.row(
        InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add_product"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад в админку", callback_data="admin_back"),
        width=1
    )

    await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


# ============= ОСНОВНЫЕ ОБРАБОТЧИКИ =============

@router.callback_query(F.data == "admin_products")
async def admin_products_list(callback: CallbackQuery, session: AsyncSession):
    """Список всех товаров для админа"""
    await safe_delete_message(callback.message)
    await admin_products_list_direct(callback, session, 1)
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("admin_products_page_"))
async def admin_products_page(callback: CallbackQuery, session: AsyncSession):
    """Пагинация списка товаров"""
    page = int(callback.data.split("_")[3])
    await safe_delete_message(callback.message)
    await admin_products_page_direct(callback, session, page)
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("admin_view_product_"))
async def admin_view_product(callback: CallbackQuery, session: AsyncSession):
    """Просмотр товара админом"""
    product_id = int(callback.data.split("_")[3])
    product = await get_product(session, product_id)

    if not product:
        await safe_callback_answer(callback, "Товар не найден", True)
        return

    caption = format_product_caption(product)
    caption += f"\n<b>Статус:</b> {'✅ Активен' if product.is_active else '❌ Неактивен'}"
    caption += f"\n<b>Дата добавления:</b> {product.created_at.strftime('%d.%m.%Y %H:%M')}"
    caption += f"\n<b>ID:</b> {product.id}"

    await safe_delete_message(callback.message)

    if product.photos:
        await callback.message.answer_photo(
            photo=product.photos[0].file_id,
            caption=caption,
            parse_mode="HTML",
            reply_markup=admin_product_actions_keyboard(product.id)
        )
    else:
        await callback.message.answer(
            caption,
            reply_markup=admin_product_actions_keyboard(product.id),
            parse_mode="HTML"
        )

    await safe_callback_answer(callback)


# ============= ДОБАВЛЕНИЕ ТОВАРА =============

@router.callback_query(F.data == "admin_add_product")
async def admin_add_product_start(callback: CallbackQuery, state: FSMContext):
    """Начать добавление товара"""
    await safe_delete_message(callback.message)
    await callback.message.answer(
        "➕ <b>Добавление нового товара</b>\n\n"
        "Введите название товара:"
    )
    await state.set_state(AddProductStates.waiting_name)
    await safe_callback_answer(callback)


@router.message(AddProductStates.waiting_name)
async def admin_add_product_name(message: Message, state: FSMContext, session: AsyncSession):
    """Ввод названия товара"""
    name = message.text.strip()

    if len(name) < 3:
        await message.answer("❌ Название должно быть минимум 3 символа. Повторите ввод:")
        return

    await state.update_data(name=name)

    categories = await get_root_categories(session)
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.row(InlineKeyboardButton(
            text=f"📁 {cat.name}",
            callback_data=f"admin_cat_{cat.id}"
        ))

    await message.answer(
        "📁 <b>Выберите категорию</b>\n\nНажмите на кнопку с категорией:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(AddProductStates.waiting_category)


@router.callback_query(AddProductStates.waiting_category, F.data.startswith("admin_cat_"))
async def admin_add_product_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Выбор категории для товара"""
    category_id = int(callback.data.split("_")[2])
    category = await get_category(session, category_id)

    if not category:
        await safe_callback_answer(callback, "Категория не найдена", True)
        return

    subcategories = await get_subcategories(session, category_id)

    if subcategories:
        text = f"📁 <b>{category.name}</b>\n\nВыберите подкатегорию:"
        builder = InlineKeyboardBuilder()

        for subcat in subcategories:
            builder.row(InlineKeyboardButton(
                text=f"📁 {subcat.name}",
                callback_data=f"admin_cat_{subcat.id}"
            ))

        builder.row(InlineKeyboardButton(
            text="✅ Выбрать эту категорию",
            callback_data=f"admin_select_cat_{category_id}"
        ))

        if category.parent_id:
            builder.row(InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=f"admin_back_to_cat_{category.parent_id}"
            ))

        await safe_delete_message(callback.message)
        await callback.message.answer(text, reply_markup=builder.as_markup())
        await safe_callback_answer(callback)
        return

    await select_category(callback, state, session, category_id, category.name)


@router.callback_query(AddProductStates.waiting_category, F.data.startswith("admin_select_cat_"))
async def admin_select_current_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Выбрать текущую категорию"""
    category_id = int(callback.data.split("_")[3])
    category = await get_category(session, category_id)

    if category:
        await select_category(callback, state, session, category_id, category.name)
    else:
        await safe_callback_answer(callback, "Категория не найдена", True)


async def select_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession, category_id: int,
                          category_name: str):
    """Общая функция для выбора категории"""
    await state.update_data(category_id=category_id, category_name=category_name)

    await safe_delete_message(callback.message)
    await callback.message.answer(
        f"✅ Категория: {category_name}\n\n"
        "🌍 Введите страну производства (или отправьте \"-\" чтобы пропустить):"
    )
    await state.set_state(AddProductStates.waiting_country)
    await safe_callback_answer(callback)


@router.message(AddProductStates.waiting_country)
async def admin_add_product_country(message: Message, state: FSMContext):
    """Ввод страны производства"""
    country = message.text.strip()
    await state.update_data(country=None if country == "-" else country)

    await message.answer(
        "📏 Введите размеры товара (например: 200x150x80 см)\n"
        "или отправьте \"-\" чтобы пропустить:"
    )
    await state.set_state(AddProductStates.waiting_dimensions)


@router.message(AddProductStates.waiting_dimensions)
async def admin_add_product_dimensions(message: Message, state: FSMContext):
    """Ввод размеров"""
    dimensions = message.text.strip()
    await state.update_data(dimensions=None if dimensions == "-" else dimensions)

    await message.answer(
        "💰 Введите цену в рублях (только цифры)\n"
        "или отправьте \"-\" чтобы пропустить:"
    )
    await state.set_state(AddProductStates.waiting_price)


@router.message(AddProductStates.waiting_price)
async def admin_add_product_price(message: Message, state: FSMContext):
    """Ввод цены"""
    price_text = message.text.strip()

    if price_text == "-":
        price = None
    else:
        try:
            price_text = price_text.replace(" ", "").replace(",", ".")
            price = float(price_text)
            if price <= 0:
                raise ValueError
        except ValueError:
            await message.answer(
                "❌ Неверный формат цены. Введите число (например: 15000)\n"
                "или отправьте \"-\" чтобы пропустить:"
            )
            return

    await state.update_data(price=price)
    await message.answer(
        "📝 Введите описание товара\n"
        "или отправьте \"-\" чтобы пропустить:"
    )
    await state.set_state(AddProductStates.waiting_description)


@router.message(AddProductStates.waiting_description)
async def admin_add_product_description(message: Message, state: FSMContext):
    """Ввод описания"""
    description = message.text.strip()
    await state.update_data(description=None if description == "-" else description)

    await message.answer(
        "🖼 Загрузите фотографии товара (1-5 штук)\n"
        "Отправляйте фото по одному.\n\n"
        "Когда закончите, отправьте команду /done"
    )
    await state.set_state(AddProductStates.waiting_photos)
    await state.update_data(photos=[])


@router.message(AddProductStates.waiting_photos, F.photo)
async def admin_add_product_photo(message: Message, state: FSMContext):
    """Добавление фото товара"""
    data = await state.get_data()
    photos = data.get("photos", [])

    if len(photos) >= 5:
        await message.answer("❌ Максимум 5 фотографий. Отправьте /done для завершения")
        return

    file_id = message.photo[-1].file_id
    photos.append(file_id)
    await state.update_data(photos=photos)

    await message.answer(f"✅ Фото {len(photos)}/5 добавлено. Отправьте ещё или /done")


@router.message(AddProductStates.waiting_photos, F.text == "/done")
async def admin_add_product_done(message: Message, state: FSMContext, session: AsyncSession):
    """Завершение добавления фото и создание товара"""
    data = await state.get_data()

    product = await create_product(
        session=session,
        name=data['name'],
        category_id=data['category_id'],
        description=data.get('description'),
        country=data.get('country'),
        dimensions=data.get('dimensions'),
        price=data.get('price')
    )

    photos = data.get("photos", [])
    if photos:
        await add_product_photos(session, product.id, photos)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 К списку товаров", callback_data="admin_products")],
        [InlineKeyboardButton(text="➕ Добавить ещё товар", callback_data="admin_add_product")],
        [InlineKeyboardButton(text="🏠 В админку", callback_data="admin_back")],
    ])

    await message.answer(
        f"✅ <b>Товар успешно добавлен!</b>\n\n"
        f"ID: {product.id}\n"
        f"Название: {product.name}\n"
        f"Категория: {data['category_name']}\n"
        f"Фото: {len(photos)} шт.",
        reply_markup=kb
    )
    await state.clear()


# ============= РЕДАКТИРОВАНИЕ ТОВАРА =============

@router.callback_query(F.data.startswith("admin_edit_product_"))
async def admin_edit_product(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начать редактирование товара"""
    product_id = int(callback.data.split("_")[3])
    product = await get_product(session, product_id)

    if not product:
        await safe_callback_answer(callback, "Товар не найден", True)
        return

    await state.update_data(product_id=product_id)

    await safe_delete_message(callback.message)
    await callback.message.answer(
        f"✏️ <b>Редактирование товара</b>\n\n"
        f"<b>{product.name}</b>\n\n"
        f"Выберите поле для редактирования:",
        reply_markup=admin_product_edit_keyboard(product_id)
    )

    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("admin_edit_field_"))
async def admin_edit_field_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начать редактирование поля товара"""
    _, _, _, product_id, field = callback.data.split("_")
    product_id = int(product_id)

    field_names = {
        "name": "название",
        "description": "описание",
        "country": "страну производства",
        "dimensions": "размеры",
        "price": "цену",
        "category": "категорию"
    }

    field_name = field_names.get(field, field)

    await state.update_data(product_id=product_id, field=field)

    product = await get_product(session, product_id)

    current_value = ""
    if product:
        if field == "name":
            current_value = product.name
        elif field == "description":
            current_value = product.description or "не указано"
        elif field == "country":
            current_value = product.country or "не указана"
        elif field == "dimensions":
            current_value = product.dimensions or "не указаны"
        elif field == "price":
            current_value = f"{product.price} ₽" if product.price else "не указана"

    await safe_delete_message(callback.message)
    await callback.message.answer(
        f"✏️ <b>Редактирование {field_name}</b>\n\n"
        f"<b>Текущее значение:</b> {current_value}\n\n"
        f"Введите новое значение для поля '{field_name}':\n"
        f"(Отправьте /cancel для отмены)"
    )

    if field == "category":
        await state.set_state(EditProductStates.waiting_category)
        categories = await get_root_categories(session)
        builder = InlineKeyboardBuilder()
        for cat in categories:
            builder.row(InlineKeyboardButton(
                text=f"📁 {cat.name}",
                callback_data=f"admin_cat_{cat.id}"
            ))
        await callback.message.answer(
            "📁 Выберите новую категорию:",
            reply_markup=builder.as_markup()
        )
    else:
        await state.set_state(EditProductStates.waiting_field_value)

    await safe_callback_answer(callback)


@router.message(EditProductStates.waiting_field_value)
async def admin_edit_field_save(message: Message, state: FSMContext, session: AsyncSession):
    """Сохранить отредактированное поле"""
    data = await state.get_data()
    product_id = data['product_id']
    field = data['field']
    value = message.text.strip()

    if field == "price":
        try:
            value = float(value.replace(" ", "").replace(",", "."))
            if value <= 0:
                raise ValueError
        except ValueError:
            await message.answer(
                "❌ Неверный формат цены. Введите число (например: 15000)\n"
                "или отправьте /cancel для отмены:"
            )
            return

    elif field == "name" and len(value) < 3:
        await message.answer(
            "❌ Название должно быть минимум 3 символа. Повторите ввод:"
        )
        return

    product = await update_product(session, product_id, **{field: value})

    if product:
        await message.answer(
            f"✅ <b>Поле успешно обновлено!</b>\n\n"
            f"<b>Поле:</b> {field}\n"
            f"<b>Новое значение:</b> {value}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👁 Посмотреть товар", callback_data=f"admin_view_product_{product_id}")],
                [InlineKeyboardButton(text="📦 К списку товаров", callback_data="admin_products")]
            ])
        )
    else:
        await message.answer("❌ Ошибка при обновлении товара")

    await state.clear()


@router.callback_query(F.data.startswith("admin_cat_"))
async def admin_edit_category_select(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Выбор категории при редактировании"""
    category_id = int(callback.data.split("_")[2])
    category = await get_category(session, category_id)

    if not category:
        await safe_callback_answer(callback, "Категория не найдена", True)
        return

    subcategories = await get_subcategories(session, category_id)

    if subcategories:
        text = f"📁 <b>{category.name}</b>\n\nВыберите подкатегорию:"
        builder = InlineKeyboardBuilder()

        for subcat in subcategories:
            builder.row(InlineKeyboardButton(
                text=f"📁 {subcat.name}",
                callback_data=f"admin_cat_{subcat.id}"
            ))

        builder.row(InlineKeyboardButton(
            text="✅ Выбрать эту категорию",
            callback_data=f"admin_edit_select_cat_{category_id}"
        ))

        if category.parent_id:
            builder.row(InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=f"admin_edit_back_to_cat_{category.parent_id}"
            ))

        await safe_delete_message(callback.message)
        await callback.message.answer(text, reply_markup=builder.as_markup())
        await safe_callback_answer(callback)
        return

    await admin_edit_select_category(callback, state, session, category_id)


@router.callback_query(F.data.startswith("admin_edit_select_cat_"))
async def admin_edit_select_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Выбрать категорию при редактировании"""
    category_id = int(callback.data.split("_")[4])

    data = await state.get_data()
    product_id = data['product_id']

    product = await update_product(session, product_id, category_id=category_id)

    if product:
        category = await get_category(session, category_id)
        await safe_delete_message(callback.message)
        await callback.message.answer(
            f"✅ <b>Категория изменена на '{category.name}'</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👁 Посмотреть товар", callback_data=f"admin_view_product_{product_id}")],
                [InlineKeyboardButton(text="📦 К списку товаров", callback_data="admin_products")]
            ])
        )
    else:
        await callback.message.answer("❌ Ошибка при обновлении категории")

    await state.clear()
    await safe_callback_answer(callback)


# ============= УПРАВЛЕНИЕ ФОТО =============

@router.callback_query(F.data.startswith("admin_manage_photos_"))
async def admin_manage_photos(callback: CallbackQuery, session: AsyncSession):
    """Управление фотографиями товара"""
    product_id = int(callback.data.split("_")[3])
    product = await get_product(session, product_id)

    if not product:
        await safe_callback_answer(callback, "Товар не найден", True)
        return

    if not product.photos:
        await safe_delete_message(callback.message)
        await callback.message.answer(
            f"📷 <b>У товара '{product.name}' нет фотографий</b>\n\n"
            "Нажмите кнопку ниже, чтобы добавить фото:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить фото", callback_data=f"admin_add_photo_{product_id}")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_view_product_{product_id}")]
            ])
        )
        await safe_callback_answer(callback)
        return

    await safe_delete_message(callback.message)
    await callback.message.answer(
        f"📷 <b>Управление фотографиями товара '{product.name}'</b>\n\n"
        f"Всего фото: {len(product.photos)}/5\n\n"
        "Выберите фото для удаления:",
        reply_markup=admin_photos_management_keyboard(product_id, product.photos)
    )
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("admin_add_photo_"))
async def admin_add_photo(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Добавление фото к товару"""
    product_id = int(callback.data.split("_")[3])
    product = await get_product(session, product_id)

    if not product:
        await safe_callback_answer(callback, "Товар не найден", True)
        return

    if len(product.photos) >= 5:
        await safe_callback_answer(callback, "Максимум 5 фотографий!", True)
        return

    await state.update_data(product_id=product_id, photos=list(product.photos))

    await safe_delete_message(callback.message)
    await callback.message.answer(
        f"🖼 Добавление фото к товару '{product.name}'\n"
        f"Текущих фото: {len(product.photos)}/5\n\n"
        "Отправьте фото или /cancel для отмены:"
    )
    await state.set_state(EditProductStates.waiting_photos)
    await safe_callback_answer(callback)


@router.message(EditProductStates.waiting_photos, F.photo)
async def admin_add_photo_handler(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка добавления фото"""
    data = await state.get_data()
    product_id = data['product_id']

    file_id = message.photo[-1].file_id
    await add_product_photos(session, product_id, [file_id])

    await message.answer(f"✅ Фото добавлено! Отправьте ещё фото или /done для завершения")


@router.message(EditProductStates.waiting_photos, F.text == "/done")
async def admin_add_photo_done(message: Message, state: FSMContext):
    """Завершение добавления фото"""
    await message.answer("✅ Добавление фото завершено")
    await state.clear()


@router.message(EditProductStates.waiting_photos, F.text == "/cancel")
async def admin_add_photo_cancel(message: Message, state: FSMContext):
    """Отмена добавления фото"""
    await message.answer("❌ Добавление фото отменено")
    await state.clear()


@router.callback_query(F.data.startswith("admin_delete_photo_"))
async def admin_delete_photo(callback: CallbackQuery, session: AsyncSession):
    """Удаление фото товара"""
    photo_id = int(callback.data.split("_")[3])

    # Получаем фото чтобы узнать product_id
    result = await session.execute(
        select(ProductPhoto).where(ProductPhoto.id == photo_id)
    )
    photo = result.scalar_one_or_none()

    if not photo:
        await safe_callback_answer(callback, "Фото не найдено", True)
        return

    product_id = photo.product_id
    success = await delete_product_photo(session, photo_id)

    if success:
        await safe_delete_message(callback.message)
        await callback.message.answer(
            "✅ Фото удалено",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад к товару", callback_data=f"admin_view_product_{product_id}")]
            ])
        )
    else:
        await safe_callback_answer(callback, "❌ Ошибка при удалении", True)

    await safe_callback_answer(callback)


# ============= УДАЛЕНИЕ ТОВАРА =============

@router.callback_query(F.data.startswith("admin_delete_product_"))
async def admin_delete_product_confirm(callback: CallbackQuery, session: AsyncSession):
    """Подтверждение удаления товара"""
    product_id = int(callback.data.split("_")[3])
    product = await get_product(session, product_id)

    if not product:
        await safe_callback_answer(callback, "Товар не найден", True)
        return

    await safe_delete_message(callback.message)
    await callback.message.answer(
        f"⚠️ <b>Вы уверены, что хотите удалить товар?</b>\n\n"
        f"<b>{product.name}</b>\n"
        f"ID: {product.id}\n\n"
        f"Это действие необратимо!",
        reply_markup=admin_confirm_keyboard("delete_product", product_id)
    )

    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("admin_confirm_delete_product_"))
async def admin_delete_product(callback: CallbackQuery, session: AsyncSession):
    """Удаление товара"""
    product_id = int(callback.data.split("_")[4])

    product = await get_product(session, product_id)
    product_name = product.name if product else "Товар"

    success = await delete_product(session, product_id)

    await safe_delete_message(callback.message)

    if success:
        await callback.message.answer(
            f"✅ <b>Товар успешно удален!</b>\n\n"
            f"{product_name} (ID: {product_id}) удален из каталога.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📦 К списку товаров", callback_data="admin_products")],
                [InlineKeyboardButton(text="🏠 В админку", callback_data="admin_back")]
            ])
        )
    else:
        await callback.message.answer(
            f"❌ <b>Ошибка при удалении товара</b>\n\n"
            f"Не удалось удалить товар {product_name}.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📦 К списку товаров", callback_data="admin_products")],
                [InlineKeyboardButton(text="🏠 В админку", callback_data="admin_back")]
            ])
        )

    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("admin_cancel_delete_product_"))
async def admin_cancel_delete(callback: CallbackQuery, session: AsyncSession):
    """Отмена удаления - возврат к просмотру товара"""
    product_id = int(callback.data.split("_")[4])
    await admin_view_product(callback, session)


# ============= НАВИГАЦИЯ =============

@router.callback_query(F.data.startswith("admin_back_to_products_"))
async def admin_back_to_products(callback: CallbackQuery, session: AsyncSession):
    """Вернуться к списку товаров из карточки товара"""
    await safe_delete_message(callback.message)
    await admin_products_list_direct(callback, session, 1)
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("admin_toggle_status_"))
async def admin_toggle_status(callback: CallbackQuery, session: AsyncSession):
    """Изменить статус товара (активен/неактивен)"""
    _, _, _, product_id, status = callback.data.split("_")
    product_id = int(product_id)

    is_active = (status == "active")

    product = await update_product(session, product_id, is_active=is_active)

    if product:
        status_text = "активирован" if is_active else "деактивирован"
        await safe_delete_message(callback.message)
        await callback.message.answer(
            f"✅ <b>Товар успешно {status_text}!</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👁 Посмотреть товар", callback_data=f"admin_view_product_{product_id}")],
                [InlineKeyboardButton(text="📦 К списку товаров", callback_data="admin_products")]
            ])
        )
    else:
        await callback.message.answer("❌ Ошибка при изменении статуса")

    await safe_callback_answer(callback)


# ============= ОТМЕНА =============

@router.message(F.text == "/cancel")
async def cancel_editing(message: Message, state: FSMContext):
    """Отмена редактирования"""
    current_state = await state.get_state()

    if current_state is None:
        return

    data = await state.get_data()
    product_id = data.get('product_id')

    await state.clear()

    if product_id:
        await message.answer(
            "❌ Редактирование отменено",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👁 Вернуться к товару", callback_data=f"admin_view_product_{product_id}")],
                [InlineKeyboardButton(text="📦 К списку товаров", callback_data="admin_products")]
            ])
        )
    else:
        await message.answer("❌ Редактирование отменено")