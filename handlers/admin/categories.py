# handlers/admin/categories.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from logger import logger

from filters.admin import is_admin
from db.models import Category
from db.queries import (
    get_root_categories, get_subcategories, get_category,
    create_category, update_category, delete_category
)
from keyboards.admin import admin_categories_keyboard, admin_confirm_keyboard
from keyboards.inline import categories_keyboard

router = Router(name="admin_categories")
from filters.admin import is_admin_filter

router.message.filter(is_admin_filter)
router.callback_query.filter(is_admin_filter)

class CategoryStates(StatesGroup):
    waiting_name = State()
    waiting_parent = State()


@router.callback_query(F.data == "admin_categories")
async def admin_categories_list(callback: CallbackQuery, session: AsyncSession):
    """Управление категориями"""
    categories = await get_root_categories(session)

    text = "📁 <b>Управление категориями</b>\n\n"

    if not categories:
        text += "Нет корневых категорий."
    else:
        text += "Корневые категории:\n\n"
        for cat in categories:
            # Получаем количество подкатегорий
            subcats = await get_subcategories(session, cat.id)
            text += f"• {cat.name} (подкатегорий: {len(subcats)})\n"

    await callback.message.edit_text(
        text,
        reply_markup=admin_categories_keyboard(categories)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_cat_edit_"))
async def admin_cat_edit(callback: CallbackQuery, session: AsyncSession):
    """Редактирование категории"""
    category_id = int(callback.data.split("_")[3])
    category = await get_category(session, category_id)

    if not category:
        await callback.answer("Категория не найдена")
        return

    # Получаем подкатегории
    subcategories = await get_subcategories(session, category_id)

    text = (
        f"📁 <b>Категория: {category.name}</b>\n\n"
        f"ID: {category.id}\n"
        f"Родительская категория: {category.parent.name if category.parent else 'Корневая'}\n"
        f"Подкатегорий: {len(subcategories)}\n"
        f"Статус: {'Активна' if category.is_active else 'Неактивна'}\n"
        f"Порядок: {category.order}\n\n"
        f"Действия:"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"admin_cat_rename_{category_id}")],
        [InlineKeyboardButton(text="📁 Просмотр подкатегорий", callback_data=f"admin_cat_sub_{category_id}")],
        [InlineKeyboardButton(text="➕ Добавить подкатегорию", callback_data=f"admin_cat_create_{category_id}")],
        [InlineKeyboardButton(text="❌ Удалить категорию", callback_data=f"admin_cat_del_{category_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_categories")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_cat_rename_"))
async def admin_cat_rename(callback: CallbackQuery, state: FSMContext):
    """Переименование категории"""
    category_id = int(callback.data.split("_")[3])
    await state.update_data(category_id=category_id)

    await callback.message.edit_text(
        "✏️ Введите новое название категории:"
    )
    await state.set_state(CategoryStates.waiting_name)
    await callback.answer()


@router.message(CategoryStates.waiting_name)
async def admin_cat_rename_save(message: Message, state: FSMContext, session: AsyncSession):
    """Сохранение нового названия"""
    data = await state.get_data()
    category_id = data['category_id']
    new_name = message.text.strip()

    if len(new_name) < 2:
        await message.answer("❌ Название должно быть минимум 2 символа. Повторите:")
        return

    category = await update_category(session, category_id, name=new_name)

    if category:
        await message.answer(
            f"✅ Категория переименована в '{new_name}'",
            reply_markup=admin_categories_keyboard(await get_root_categories(session))
        )
    else:
        await message.answer("❌ Ошибка при переименовании")

    await state.clear()


@router.callback_query(F.data.startswith("admin_cat_sub_"))
async def admin_cat_subcategories(callback: CallbackQuery, session: AsyncSession):
    """Просмотр подкатегорий"""
    category_id = int(callback.data.split("_")[3])
    category = await get_category(session, category_id)
    subcategories = await get_subcategories(session, category_id)

    text = f"📁 <b>Подкатегории: {category.name}</b>\n\n"

    if not subcategories:
        text += "Нет подкатегорий."
    else:
        for cat in subcategories:
            text += f"• {cat.name}\n"

    await callback.message.edit_text(
        text,
        reply_markup=admin_categories_keyboard(subcategories, parent_id=category_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_cat_create_"))
async def admin_cat_create(callback: CallbackQuery, state: FSMContext):
    """Создание новой категории"""
    parent = callback.data.split("_")[3]

    if parent == "root":
        parent_id = None
    else:
        parent_id = int(parent)

    await state.update_data(parent_id=parent_id)

    await callback.message.edit_text(
        "➕ Введите название новой категории:"
    )
    await state.set_state(CategoryStates.waiting_name)
    await callback.answer()


@router.message(CategoryStates.waiting_name)
async def admin_cat_create_save(message: Message, state: FSMContext, session: AsyncSession):
    """Сохранение новой категории"""
    data = await state.get_data()
    parent_id = data.get('parent_id')
    name = message.text.strip()

    if len(name) < 2:
        await message.answer("❌ Название должно быть минимум 2 символа. Повторите:")
        return

    category = await create_category(session, name, parent_id)

    if category:
        await message.answer(
            f"✅ Категория '{name}' создана!",
            reply_markup=admin_categories_keyboard(
                await get_root_categories(session) if not parent_id else await get_subcategories(session, parent_id),
                parent_id=parent_id
            )
        )
    else:
        await message.answer("❌ Ошибка при создании категории")

    await state.clear()


@router.callback_query(F.data.startswith("admin_cat_del_"))
async def admin_cat_delete_confirm(callback: CallbackQuery):
    """Подтверждение удаления категории"""
    category_id = int(callback.data.split("_")[3])

    await callback.message.edit_text(
        "⚠️ <b>Вы уверены, что хотите удалить категорию?</b>\n\n"
        "Все подкатегории и товары в этой категории также будут удалены!\n"
        "Это действие необратимо!",
        reply_markup=admin_confirm_keyboard("delete_category", category_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_confirm_delete_category_"))
async def admin_cat_delete(callback: CallbackQuery, session: AsyncSession):
    """Удаление категории"""
    category_id = int(callback.data.split("_")[4])

    success = await delete_category(session, category_id)

    if success:
        await callback.message.edit_text(
            "✅ Категория удалена!",
            reply_markup=admin_categories_keyboard(await get_root_categories(session))
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка при удалении категории",
            reply_markup=admin_categories_keyboard(await get_root_categories(session))
        )

    await callback.answer()


@router.callback_query(F.data.startswith("admin_cat_back_"))
async def admin_cat_back(callback: CallbackQuery, session: AsyncSession):
    """Возврат к родительской категории"""
    category_id = int(callback.data.split("_")[3])
    category = await get_category(session, category_id)

    if category and category.parent_id:
        # Возвращаемся к родителю
        parent = await get_category(session, category.parent_id)
        subcategories = await get_subcategories(session, parent.id)

        await callback.message.edit_text(
            f"📁 <b>Подкатегории: {parent.name}</b>",
            reply_markup=admin_categories_keyboard(subcategories, parent_id=parent.id)
        )
    else:
        # Возвращаемся к корневым
        await admin_categories_list(callback, session)

    await callback.answer()