# handlers/user/search.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from db.queries import search_products, get_product
from keyboards.inline import products_keyboard, search_keyboard
from utils.helpers import format_product_caption
from logger import logger

router = Router(name="user_search")


class SearchStates(StatesGroup):
    """Состояния поиска"""
    waiting_query = State()


# Функция для безопасного удаления и отправки нового сообщения
async def safe_delete_and_answer(callback: CallbackQuery, text: str, reply_markup=None):
    """Безопасное удаление сообщения и отправка нового"""
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")

    await callback.message.answer(text, reply_markup=reply_markup)
    await callback.answer()


@router.callback_query(F.data == "search")
async def start_search(callback: CallbackQuery, state: FSMContext):
    """Начать поиск"""
    await safe_delete_and_answer(
        callback,
        "🔍 <b>Поиск товаров</b>\n\nВведите название товара, страну или описание для поиска:"
    )
    await state.set_state(SearchStates.waiting_query)


@router.callback_query(F.data.startswith("search_cat_"))
async def search_in_category(callback: CallbackQuery, state: FSMContext):
    """Поиск в конкретной категории"""
    category_id = callback.data.split("_")[2]
    if category_id == "root":
        await state.update_data(search_category=None)
    else:
        await state.update_data(search_category=int(category_id))

    await safe_delete_and_answer(
        callback,
        f"🔍 <b>Поиск в категории</b>\n\nВведите название товара для поиска:"
    )
    await state.set_state(SearchStates.waiting_query)


@router.message(SearchStates.waiting_query)
async def process_search(
        message: Message,
        state: FSMContext,
        session: AsyncSession
):
    """Обработка поискового запроса"""
    query = message.text.strip()

    if len(query) < 2:
        await message.answer(
            "❌ Слишком короткий запрос. Минимум 2 символа.\n"
            "Попробуйте ещё раз:"
        )
        return

    # Ищем товары
    products, has_next, total = await search_products(session, query, page=1)

    if not products:
        await message.answer(
            "😔 По вашему запросу ничего не найдено.\n\n"
            "Попробуйте изменить запрос:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Новый поиск", callback_data="search")],
                [InlineKeyboardButton(text="◀️ В каталог", callback_data="back_to_main")]
            ])
        )
        await state.clear()
        return

    # Сохраняем запрос для пагинации
    await state.update_data(search_query=query)

    text = (
        f"🔍 <b>Результаты поиска:</b> \"{query}\"\n"
        f"Найдено: {total} товаров\n\n"
        f"Страница 1:"
    )

    await message.answer(
        text,
        reply_markup=products_keyboard(products, 0, page=1, has_next=has_next)
    )
    await state.clear()


@router.callback_query(F.data.startswith("search_page_"))
async def search_page(callback: CallbackQuery, session: AsyncSession):
    """Пагинация результатов поиска"""
    parts = callback.data.split("_")
    page = int(parts[-1])
    query_parts = parts[2:-1]
    query = "_".join(query_parts).replace("_", " ")

    products, has_next, total = await search_products(session, query, page)

    if not products:
        await callback.answer("Страница не найдена")
        return

    text = (
        f"🔍 <b>Результаты поиска:</b> \"{query}\"\n"
        f"Найдено: {total} товаров\n\n"
        f"Страница {page}:"
    )

    # Вместо edit_text используем delete + answer
    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")

    await callback.message.answer(
        text,
        reply_markup=products_keyboard(products, 0, page, has_next)
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def back_from_search(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню из поиска"""
    await state.clear()

    from keyboards.inline import main_menu_keyboard
    text = "🏠 <b>Главное меню</b>\n\nВыберите раздел:"

    # Используем safe_delete_and_answer вместо edit_text
    await safe_delete_and_answer(callback, text, main_menu_keyboard())


@router.callback_query(F.data.startswith("back_to_cat_"))
async def back_to_category_from_search(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к категории из поиска"""
    await state.clear()

    category_id = int(callback.data.split("_")[3])

    from db.queries import get_category, get_subcategories
    from keyboards.inline import categories_keyboard

    category = await get_category(session, category_id)

    if category:
        # Получаем подкатегории
        subcategories = await get_subcategories(session, category_id)

        if subcategories:
            text = f"📁 <b>{category.name}</b>\n\nВыберите подкатегорию:"
            kb = categories_keyboard(subcategories, parent_id=category_id)
        else:
            # Если нет подкатегорий, показываем товары
            from handlers.user.catalog import show_products
            await show_products(callback, session, category_id)
            return

        # Удаляем текущее сообщение
        try:
            await callback.message.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")

        # Отправляем новое сообщение
        await callback.message.answer(text, reply_markup=kb)
    else:
        # Если категория не найдена, возвращаемся в главное меню
        from keyboards.inline import main_menu_keyboard
        text = "🏠 <b>Главное меню</b>\n\nВыберите раздел:"

        try:
            await callback.message.delete()
        except:
            pass

        await callback.message.answer(text, reply_markup=main_menu_keyboard())

    await callback.answer()



# Обработчик для поиска по кнопке (если используется reply-клавиатура)
@router.message(F.text == "🔍 Поиск")
async def search_button_handler(message: Message, state: FSMContext):
    """Обработка нажатия на кнопку поиска"""
    await message.answer(
        "🔍 <b>Поиск товаров</b>\n\n"
        "Введите название товара, страну или описание:"
    )
    await state.set_state(SearchStates.waiting_query)