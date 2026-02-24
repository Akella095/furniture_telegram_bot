# handlers/admin/orders.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from logger import logger

from filters.admin import is_admin_filter
from db.models import Order
from db.queries import get_orders, get_order, update_order_status
from keyboards.admin import admin_orders_keyboard, admin_order_actions_keyboard
from utils.helpers import format_order_text


router = Router(name="admin_orders")
router.message.filter(is_admin_filter)
router.callback_query.filter(is_admin_filter)


@router.callback_query(F.data == "admin_orders")
async def admin_orders_list(callback: CallbackQuery, session: AsyncSession):
    """Список заказов для админа"""
    orders, has_next = await get_orders(session, page=1, limit=10)

    text = "📋 <b>Управление заказами (лидами)</b>\n\n"

    if not orders:
        text += "Нет заказов."
    else:
        text += f"Всего заказов на странице: {len(orders)}\n\n"

        for order in orders:
            status_emoji = {
                "новая": "🆕",
                "в работе": "🔄",
                "выполнена": "✅",
                "отменена": "❌"
            }.get(order.status, "📦")

            text += f"{status_emoji} <b>Заказ #{order.id}</b>\n"
            text += f"👤 {order.full_name}\n"
            text += f"📞 {order.phone}\n"
            text += f"📦 {order.product_name[:30]}...\n"
            text += f"📅 {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            text += f"Статус: {order.status}\n\n"

    await callback.message.edit_text(
        text,
        reply_markup=admin_orders_keyboard(page=1, has_next=has_next)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_orders_filter_"))
async def admin_orders_filter(callback: CallbackQuery, session: AsyncSession):
    """Фильтрация заказов по статусу"""
    status = callback.data.split("_")[3]

    if status == "все":
        status_filter = None
    else:
        status_filter = status

    orders, has_next = await get_orders(session, status=status_filter, page=1, limit=10)

    text = f"📋 <b>Заказы: {status if status != 'все' else 'все'}</b>\n\n"

    if not orders:
        text += "Нет заказов с таким статусом."
    else:
        for order in orders:
            status_emoji = {
                "новая": "🆕",
                "в работе": "🔄",
                "выполнена": "✅",
                "отменена": "❌"
            }.get(order.status, "📦")

            text += f"{status_emoji} <b>Заказ #{order.id}</b>\n"
            text += f"👤 {order.full_name}\n"
            text += f"📞 {order.phone}\n"
            text += f"📦 {order.product_name[:30]}...\n"
            text += f"📅 {order.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"

    await callback.message.edit_text(
        text,
        reply_markup=admin_orders_keyboard(status=status, page=1, has_next=has_next)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_orders_page_"))
async def admin_orders_page(callback: CallbackQuery, session: AsyncSession):
    """Пагинация заказов"""
    parts = callback.data.split("_")
    status = parts[3]
    page = int(parts[4])

    if status == "все":
        status_filter = None
    else:
        status_filter = status

    orders, has_next = await get_orders(session, status=status_filter, page=page, limit=10)

    text = f"📋 <b>Заказы: {status if status != 'все' else 'все'}</b> | Страница {page}\n\n"

    if not orders:
        text += "Нет заказов с таким статусом."
    else:
        for order in orders:
            status_emoji = {
                "новая": "🆕",
                "в работе": "🔄",
                "выполнена": "✅",
                "отменена": "❌"
            }.get(order.status, "📦")

            text += f"{status_emoji} <b>Заказ #{order.id}</b>\n"
            text += f"👤 {order.full_name}\n"
            text += f"📞 {order.phone}\n"
            text += f"📦 {order.product_name[:30]}...\n\n"

    await callback.message.edit_text(
        text,
        reply_markup=admin_orders_keyboard(status=status, page=page, has_next=has_next)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_view_order_"))
async def admin_view_order(callback: CallbackQuery, session: AsyncSession):
    """Просмотр деталей заказа"""
    order_id = int(callback.data.split("_")[3])
    order = await get_order(session, order_id)

    if not order:
        await callback.answer("Заказ не найден")
        return

    text = format_order_text(order)

    await callback.message.edit_text(
        text,
        reply_markup=admin_order_actions_keyboard(order_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_order_status_"))
async def admin_order_status_change(callback: CallbackQuery, session: AsyncSession):
    """Изменение статуса заказа"""
    _, _, _, order_id, status = callback.data.split("_", 4)
    order_id = int(order_id)

    order = await update_order_status(session, order_id, status)

    if order:
        await callback.answer(f"Статус изменен на '{status}'")

        # Отправляем уведомление клиенту
        try:
            status_emoji = {
                "новая": "🆕",
                "в работе": "🔄",
                "выполнена": "✅",
                "отменена": "❌"
            }.get(status, "📦")

            await callback.bot.send_message(
                order.user_id,
                f"🔄 <b>Статус вашего заказа #{order.id} изменен</b>\n\n"
                f"Новый статус: {status_emoji} {status}\n\n"
                f"Спасибо, что выбираете нас! 🪑",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление клиенту: {e}")

        # Обновляем отображение
        await admin_view_order(callback, session)
    else:
        await callback.answer("Ошибка при изменении статуса")


@router.callback_query(F.data.startswith("admin_order_contact_"))
async def admin_order_contact(callback: CallbackQuery, session: AsyncSession):
    """Показать контактную информацию клиента"""
    order_id = int(callback.data.split("_")[3])
    order = await get_order(session, order_id)

    if not order:
        await callback.answer("Заказ не найден")
        return

    text = (
        f"📞 <b>Контакт клиента</b>\n\n"
        f"Заказ #{order.id}\n\n"
        f"<b>Имя:</b> {order.full_name}\n"
        f"<b>Телефон:</b> {order.phone}\n"
        f"<b>Username:</b> @{order.username if order.username else 'нет'}\n"
        f"<b>User ID:</b> <code>{order.user_id}</code>\n\n"
        f"<b>Товар:</b> {order.product_name}\n"
    )

    if order.comment:
        text += f"\n<b>Комментарий:</b> {order.comment}\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к заказу", callback_data=f"admin_view_order_{order_id}")]
    ])

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()