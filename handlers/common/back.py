# handlers/common/back.py
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from db.queries import get_root_categories, get_category, get_subcategories
from keyboards.inline import categories_keyboard, main_menu_keyboard

router = Router(name="common_back")


@router.callback_query(F.data.startswith("back_to_cat_"))
async def back_to_category(callback: CallbackQuery, session: AsyncSession):
    """Возврат к категории"""
    category_id = int(callback.data.split("_")[3])

    category = await get_category(session, category_id)
    if not category:
        await callback.answer("Категория не найдена")
        return

    parent_id = category.parent_id
    categories = await get_subcategories(session, parent_id) if parent_id else await get_root_categories(session)

    text = "📁 <b>Категории</b>\n\nВыберите раздел:" if not parent_id else f"📁 <b>{category.parent.name if category.parent else 'Категории'}</b>"

    await callback.message.delete()
    await callback.message.answer(
        text,
        reply_markup=categories_keyboard(categories, parent_id=parent_id)
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    await callback.message.delete()

    text = "🏠 <b>Главное меню</b>\n\nВыберите раздел:"
    await callback.message.answer(text, reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "back_to_product")
async def back_to_product(callback: CallbackQuery, state: FSMContext):
    """Возврат к товару из формы"""
    await state.clear()

    # Пытаемся получить product_id из данных состояния
    data = await state.get_data()
    product_id = data.get('product_id')

    if product_id:
        # Создаём callback для показа товара
        new_callback = callback
        new_callback.data = f"prod_{product_id}"

        from handlers.user.catalog import show_product
        await show_product(new_callback, callback.message.conf)
    else:
        await back_to_main(callback, state)