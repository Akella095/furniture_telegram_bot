# handlers/user/catalog.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import logging
from logger import logger
from db.models import Order
from db.queries import (
    get_root_categories, get_subcategories, get_category,
    get_products_by_category, get_product, get_category_path
)
from keyboards.inline import (
    categories_keyboard, products_keyboard, product_card_keyboard
)
from utils.helpers import format_product_caption
from logger import logger

router = Router(name="user_catalog")


async def safe_edit_message(callback: CallbackQuery, text: str, reply_markup=None):
    """Безопасное редактирование сообщения с проверкой на изменения"""
    try:
        # Проверяем, отличается ли новое сообщение от текущего
        current_text = callback.message.text or callback.message.caption or ""

        # Если текст отличается, редактируем
        if current_text != text:
            await callback.message.edit_text(text, reply_markup=reply_markup)
        else:
            # Если текст одинаковый, но клавиатура могла измениться
            await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception as e:
        if "message is not modified" not in str(e):
            logger.error(f"Ошибка при редактировании: {e}")
        await callback.answer()


@router.callback_query(F.data.startswith("cat_root_"))
async def show_root_category(callback: CallbackQuery, session: AsyncSession):
    """Показать корневую категорию"""
    category_id = int(callback.data.split("_")[2])

    # Получаем категорию
    category = await get_category(session, category_id)
    if not category:
        await callback.answer("Категория не найдена")
        return

    # Проверяем, есть ли подкатегории
    subcategories = await get_subcategories(session, category_id)

    if subcategories:
        # Показываем подкатегории
        text = f"📁 <b>{category.name}</b>\n\nВыберите подкатегорию:"
        kb = categories_keyboard(subcategories, parent_id=category_id)
        await safe_edit_message(callback, text, kb)
    else:
        # Сразу показываем товары
        await show_products(callback, session, category_id)

    await callback.answer()


@router.callback_query(F.data.startswith("cat_"))
async def show_category(callback: CallbackQuery, session: AsyncSession):
    """Показать категорию (обработчик для всех категорий)"""
    # Пропускаем cat_root_
    if callback.data.startswith("cat_root_"):
        return

    category_id = int(callback.data.split("_")[1])
    await show_products(callback, session, category_id)


@router.callback_query(F.data.startswith("prod_page_"))
async def products_page(callback: CallbackQuery, session: AsyncSession):
    """Пагинация товаров"""
    _, _, category_id, page = callback.data.split("_")
    category_id = int(category_id)
    page = int(page)

    products, has_next = await get_products_by_category(session, category_id, page)

    if not products:
        await callback.answer("Товары не найдены")
        return

    category = await get_category(session, category_id)

    text = f"📦 <b>{category.name}</b>\n\nСтраница {page}:\n"
    kb = products_keyboard(products, category_id, page, has_next)

    await safe_edit_message(callback, text, kb)
    await callback.answer()


async def show_products(callback: CallbackQuery, session: AsyncSession, category_id: int):
    """Показать товары категории"""
    products, has_next = await get_products_by_category(session, category_id, page=1)

    if not products:
        # Если товаров нет, проверяем подкатегории
        subcategories = await get_subcategories(session, category_id)
        if subcategories:
            category = await get_category(session, category_id)
            text = f"📁 <b>{category.name}</b>\n\nВыберите подкатегорию:"
            kb = categories_keyboard(subcategories, parent_id=category_id)
            await safe_edit_message(callback, text, kb)
        else:
            text = "😔 В этой категории пока нет товаров.\n\nВыберите другую категорию:"
            kb = categories_keyboard(await get_root_categories(session), show_back=False)
            await safe_edit_message(callback, text, kb)
        await callback.answer()
        return

    category = await get_category(session, category_id)

    text = f"📦 <b>{category.name}</b>\n\nВыберите товар:"
    kb = products_keyboard(products, category_id, page=1, has_next=has_next)

    await safe_edit_message(callback, text, kb)
    await callback.answer()


@router.callback_query(F.data.startswith("prod_"))
async def show_product(callback: CallbackQuery, session: AsyncSession):
    """Показать карточку товара"""
    product_id = int(callback.data.split("_")[1])
    product = await get_product(session, product_id)

    if not product:
        await callback.answer("Товар не найден")
        return

    # Формируем текст описания
    caption = format_product_caption(product)

    # Отправляем фото или просто текст
    if product.photos:
        # Отправляем первое фото с описанием
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=product.photos[0].file_id,
            caption=caption,
            parse_mode="HTML",
            reply_markup=product_card_keyboard(product.id)
        )
    else:
        # Нет фото, отправляем только текст
        await safe_edit_message(callback, caption, product_card_keyboard(product.id))

    await callback.answer()


@router.callback_query(F.data.startswith("back_to_products_"))
async def back_to_products(callback: CallbackQuery, session: AsyncSession):
    """Вернуться к списку товаров из карточки"""
    product_id = int(callback.data.split("_")[3])

    # Получаем товар, чтобы узнать его категорию
    product = await get_product(session, product_id)

    if not product:
        await callback.answer("Товар не найден")
        return

    category_id = product.category_id

    # Получаем товары этой категории
    products, has_next = await get_products_by_category(session, category_id, page=1)

    if not products:
        # Если товаров нет, возвращаемся в категорию
        await back_to_category(callback, session)
        return

    category = await get_category(session, category_id)
    text = f"📦 <b>{category.name}</b>\n\nВыберите товар:"
    kb = products_keyboard(products, category_id, page=1, has_next=has_next)

    # Удаляем текущее сообщение с фото и отправляем новый список
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")

    await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("back_to_cat_"))
async def back_to_category(callback: CallbackQuery, session: AsyncSession):
    """Вернуться к категории"""
    category_id = int(callback.data.split("_")[3])

    # Получаем категорию с явной загрузкой родителя
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select
    from db.models import Category

    result = await session.execute(
        select(Category)
        .where(Category.id == category_id)
        .options(selectinload(Category.parent))  # Явно загружаем родителя
    )
    category = result.scalar_one_or_none()

    if not category:
        await callback.answer("Категория не найдена")
        return

    # Получаем подкатегории родителя
    parent_id = category.parent_id
    if parent_id:
        categories = await get_subcategories(session, parent_id)
        parent = category.parent  # Уже загружено
        text = f"📁 <b>{parent.name}</b>"
    else:
        categories = await get_root_categories(session)
        text = "📁 <b>Категории</b>"

    text += "\n\nВыберите раздел:"
    kb = categories_keyboard(categories, parent_id=parent_id)

    # Безопасно удаляем и отправляем новое сообщение
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")

    await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


async def show_root_categories(message: Message, session: AsyncSession):
    """Показать корневые категории (прямой вызов)"""
    categories = await get_root_categories(session)
    text = "📋 <b>Каталог товаров</b>\n\nВыберите категорию:"
    await message.answer(text, reply_markup=categories_keyboard(categories))


async def show_root_categories(message: Message, session: AsyncSession):
    """Показать корневые категории (прямой вызов)"""
    from keyboards.inline import categories_keyboard
    from db.queries import get_root_categories

    categories = await get_root_categories(session)
    text = "📋 <b>Каталог товаров</b>\n\nВыберите категорию:"
    await message.answer(text, reply_markup=categories_keyboard(categories))

async def safe_delete_message(message):
    """Безопасное удаление сообщения без ошибок"""
    try:
        await message.delete()
        return True
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
        return False