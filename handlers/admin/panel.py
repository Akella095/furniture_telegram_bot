# handlers/admin/panel.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import logging

from filters.admin import is_admin_filter
from db.models import Product, Order, Category, Admin
from db.queries import get_all_admins
from keyboards.admin import admin_panel_keyboard
from config import ADMIN_IDS
from logger import logger

router = Router(name="admin_panel")
router.message.filter(is_admin_filter)
router.callback_query.filter(is_admin_filter)


@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession):
    """Обработчик команды /admin"""
    await show_admin_panel(message, session)


async def show_admin_panel(message: Message, session: AsyncSession):
    """Показать панель администратора"""
    # Проверяем, есть ли админ в БД, если нет - добавляем
    from db.models import Admin

    result = await session.execute(
        select(Admin).where(Admin.user_id == message.from_user.id)
    )
    admin = result.scalar_one_or_none()

    if not admin:
        admin = Admin(
            user_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name
        )
        session.add(admin)
        await session.commit()

    # Статистика
    products_count = await session.scalar(select(func.count(Product.id)))
    orders_count = await session.scalar(
        select(func.count(Order.id)).where(Order.status == "новая")
    )
    categories_count = await session.scalar(select(func.count(Category.id)))

    text = (
        "👨‍💼 <b>Панель администратора</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Товаров: {products_count or 0}\n"
        f"• Категорий: {categories_count or 0}\n"
        f"• Новых заказов: {orders_count or 0}\n\n"
        "Выберите действие:"
    )

    await message.answer(text, reply_markup=admin_panel_keyboard())


@router.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: CallbackQuery, session: AsyncSession):
    """Возврат в админ-панель через callback"""
    # Статистика
    products_count = await session.scalar(select(func.count(Product.id)))
    orders_count = await session.scalar(
        select(func.count(Order.id)).where(Order.status == "новая")
    )
    categories_count = await session.scalar(select(func.count(Category.id)))

    text = (
        "👨‍💼 <b>Панель администратора</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Товаров: {products_count or 0}\n"
        f"• Категорий: {categories_count or 0}\n"
        f"• Новых заказов: {orders_count or 0}\n\n"
        "Выберите действие:"
    )

    await callback.message.edit_text(text, reply_markup=admin_panel_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат в админ-панель"""
    await state.clear()
    await admin_panel_callback(callback, session)  # Вызываем callback версию


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery, session: AsyncSession):
    """Подробная статистика"""
    # Товары
    total_products = await session.scalar(select(func.count(Product.id)))
    active_products = await session.scalar(
        select(func.count(Product.id)).where(Product.is_active == True)
    )

    # Заказы по статусам
    new_orders = await session.scalar(
        select(func.count(Order.id)).where(Order.status == "новая")
    )
    work_orders = await session.scalar(
        select(func.count(Order.id)).where(Order.status == "в работе")
    )
    completed_orders = await session.scalar(
        select(func.count(Order.id)).where(Order.status == "выполнена")
    )
    cancelled_orders = await session.scalar(
        select(func.count(Order.id)).where(Order.status == "отменена")
    )

    # Категории
    total_categories = await session.scalar(select(func.count(Category.id)))

    # Админы
    admins = await get_all_admins(session)

    text = (
        "📊 <b>Детальная статистика</b>\n\n"
        f"<b>Товары:</b>\n"
        f"• Всего: {total_products or 0}\n"
        f"• Активных: {active_products or 0}\n"
        f"• Неактивных: {(total_products or 0) - (active_products or 0)}\n\n"
        f"<b>Заказы:</b>\n"
        f"• 🆕 Новые: {new_orders or 0}\n"
        f"• 🔄 В работе: {work_orders or 0}\n"
        f"• ✅ Выполнены: {completed_orders or 0}\n"
        f"• ❌ Отменены: {cancelled_orders or 0}\n\n"
        f"<b>Категории:</b> {total_categories or 0}\n"
        f"<b>Администраторы:</b> {len(admins)}\n"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# Добавляем функцию для прямого вызова (если нужно)
async def admin_panel_direct(message: Message, session: AsyncSession):
    """Прямой вызов админ-панели (для команд)"""
    await show_admin_panel(message, session)