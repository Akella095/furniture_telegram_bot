# handlers/admin/consultations.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime

from filters.admin import is_admin_filter
from db.models import Consultation
from config import MANAGER_CHAT_ID
from logger import logger

router = Router(name="admin_consultations")
router.message.filter(is_admin_filter)
router.callback_query.filter(is_admin_filter)


# ============= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =============

async def safe_delete_message(message):
    """Безопасное удаление сообщения"""
    try:
        await message.delete()
        return True
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение: {e}")
        return False


async def safe_callback_answer(callback: CallbackQuery, text: str = None, show_alert: bool = False):
    """Безопасный ответ на callback"""
    try:
        if text:
            await callback.answer(text, show_alert=show_alert)
        else:
            await callback.answer()
    except Exception as e:
        logger.warning(f"Не удалось ответить на callback: {e}")


# ============= СПИСОК КОНСУЛЬТАЦИЙ =============

@router.callback_query(F.data == "admin_consultations")
async def list_consultations(callback: CallbackQuery, session: AsyncSession, page: int = 1):
    """Список запросов на консультацию"""
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    limit = 5
    offset = (page - 1) * limit

    total_count = await session.scalar(select(func.count(Consultation.id)))
    total_pages = max(1, (total_count + limit - 1) // limit)

    result = await session.execute(
        select(Consultation)
        .order_by(desc(Consultation.created_at))
        .offset(offset)
        .limit(limit)
    )
    consultations = result.scalars().all()

    text = f"📞 <b>Запросы на консультацию</b> (страница {page}/{total_pages})\n\n"

    if not consultations:
        text += "Нет запросов"
    else:
        for cons in consultations:
            status_emoji = {
                "новая": "🆕",
                "в работе": "🔄",
                "выполнена": "✅",
                "отменена": "❌"
            }.get(cons.status, "📞")

            username = f"@{cons.username}" if cons.username else f"ID: {cons.user_id}"
            date_str = cons.created_at.strftime('%d.%m.%Y %H:%M')

            text += f"{status_emoji} <b>#{cons.id}</b> от {username}\n"
            text += f"📞 {cons.phone}\n"
            if cons.product_name:
                text += f"📦 {cons.product_name}\n"
            text += f"📅 {date_str}\n\n"

    builder = InlineKeyboardBuilder()

    for cons in consultations:
        row = []
        row.append(InlineKeyboardButton(
            text=f"👁 #{cons.id}",
            callback_data=f"view_consult_{cons.id}"
        ))

        if cons.status == "новая":
            row.append(InlineKeyboardButton(
                text="📞 Ответить",
                callback_data=f"reply_consult_{cons.id}"
            ))

        builder.row(*row, width=2)

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"consult_page_{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="ignore"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"consult_page_{page + 1}"))
    if nav_row:
        builder.row(*nav_row)

    builder.row(
        InlineKeyboardButton(text="◀️ Назад в админку", callback_data="admin_back"),
        width=1
    )

    await safe_delete_message(callback.message)
    await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("consult_page_"))
async def consultations_page(callback: CallbackQuery, session: AsyncSession):
    """Пагинация консультаций"""
    page = int(callback.data.split("_")[2])
    await list_consultations(callback, session, page)


# ============= ПРОСМОТР КОНСУЛЬТАЦИИ =============

@router.callback_query(F.data.startswith("view_consult_"))
async def view_consultation(callback: CallbackQuery, session: AsyncSession):
    """Просмотр деталей консультации"""
    cons_id = int(callback.data.split("_")[2])

    result = await session.execute(
        select(Consultation).where(Consultation.id == cons_id)
    )
    cons = result.scalar_one_or_none()

    if not cons:
        await safe_callback_answer(callback, "Запрос не найден", True)
        return

    status_emoji = {
        "новая": "🆕",
        "в работе": "🔄",
        "выполнена": "✅",
        "отменена": "❌"
    }.get(cons.status, "📞")

    text = (
        f"📞 <b>Запрос на консультацию #{cons.id}</b>\n\n"
        f"<b>Статус:</b> {status_emoji} {cons.status}\n"
        f"<b>Дата:</b> {cons.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"<b>Клиент:</b>\n"
        f"Имя: {cons.full_name}\n"
        f"Телефон: {cons.phone}\n"
        f"Username: @{cons.username or 'нет'}\n"
        f"User ID: <code>{cons.user_id}</code>\n\n"
    )

    if cons.product_name:
        text += f"<b>Товар:</b> {cons.product_name}\n"

    if cons.processed_at:
        text += f"\n<b>Обработан:</b> {cons.processed_at.strftime('%d.%m.%Y %H:%M')}\n"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()

    if cons.status == "новая":
        # Вместо tel: ссылок используем текстовые кнопки
        builder.row(
            InlineKeyboardButton(text="📞 Показать номер", callback_data=f"show_phone_{cons.id}"),
            InlineKeyboardButton(text="💬 Написать", url=f"tg://user?id={cons.user_id}"),
            width=2
        )
        builder.row(
            InlineKeyboardButton(text="✅ Выполнена", callback_data=f"consult_done_{cons.id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"consult_cancel_{cons.id}"),
            width=2
        )

    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin_consultations"),
        width=1
    )

    await safe_delete_message(callback.message)
    await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await safe_callback_answer(callback)


# ============= ПОКАЗАТЬ НОМЕР ТЕЛЕФОНА =============

@router.callback_query(F.data.startswith("show_phone_"))
async def show_phone_number(callback: CallbackQuery, session: AsyncSession):
    """Показать номер телефона для копирования"""
    cons_id = int(callback.data.split("_")[2])

    result = await session.execute(
        select(Consultation).where(Consultation.id == cons_id)
    )
    cons = result.scalar_one_or_none()

    if not cons:
        await safe_callback_answer(callback, "Запрос не найден", True)
        return

    text = (
        f"📞 <b>Номер телефона клиента</b>\n\n"
        f"<b>Клиент:</b> {cons.full_name}\n"
        f"<b>Телефон:</b> <code>{cons.phone}</code>\n\n"
        f"<i>Вы можете скопировать номер и позвонить вручную</i>"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"view_consult_{cons.id}"),
        width=1
    )

    await safe_delete_message(callback.message)
    await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await safe_callback_answer(callback)


# ============= ОТВЕТ НА КОНСУЛЬТАЦИЮ =============

@router.callback_query(F.data.startswith("reply_consult_"))
async def reply_to_consultation(callback: CallbackQuery, session: AsyncSession):
    """Быстрый ответ на консультацию"""
    cons_id = int(callback.data.split("_")[2])

    result = await session.execute(
        select(Consultation).where(Consultation.id == cons_id)
    )
    cons = result.scalar_one_or_none()

    if not cons:
        await safe_callback_answer(callback, "Запрос не найден", True)
        return

    text = (
        f"📞 <b>Ответ на консультацию #{cons_id}</b>\n\n"
        f"<b>Клиент:</b> {cons.full_name}\n"
        f"<b>Телефон:</b> {cons.phone}\n\n"
        f"<i>Вы можете:</i>\n"
        f"• Нажать кнопку ниже чтобы написать клиенту\n"
        f"• Скопировать номер телефона\n"
        f"• Отметить статус в меню"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💬 Написать клиенту", url=f"tg://user?id={cons.user_id}"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="📞 Показать номер", callback_data=f"show_phone_{cons.id}"),
        width=1
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"view_consult_{cons.id}"),
        width=1
    )

    await safe_delete_message(callback.message)
    await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await safe_callback_answer(callback)


# ============= ОБРАБОТКА СТАТУСОВ =============

@router.callback_query(F.data.startswith("consult_done_"))
async def consultation_done(callback: CallbackQuery, session: AsyncSession):
    """Отметить консультацию как выполненную"""
    cons_id = int(callback.data.split("_")[2])

    from db.queries import update_consultation_status

    consultation = await update_consultation_status(
        session=session,
        consultation_id=cons_id,
        status="выполнена",
        processed_by=callback.from_user.id
    )

    if consultation:
        await safe_delete_message(callback.message)
        await callback.message.answer(
            f"✅ <b>Консультация #{cons_id} отмечена как выполненная</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ К списку", callback_data="admin_consultations")]
            ])
        )

        try:
            await callback.bot.send_message(
                consultation.user_id,
                "✅ <b>Статус вашей консультации обновлен</b>\n\n"
                "Ваш запрос на консультацию обработан. Менеджер свяжется с вами в ближайшее время!"
            )
        except:
            pass
    else:
        await callback.message.answer("❌ Ошибка при обновлении")

    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("consult_cancel_"))
async def consultation_cancel(callback: CallbackQuery, session: AsyncSession):
    """Отменить консультацию"""
    cons_id = int(callback.data.split("_")[2])

    from db.queries import update_consultation_status

    consultation = await update_consultation_status(
        session=session,
        consultation_id=cons_id,
        status="отменена",
        processed_by=callback.from_user.id
    )

    if consultation:
        await safe_delete_message(callback.message)
        await callback.message.answer(
            f"❌ <b>Консультация #{cons_id} отменена</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ К списку", callback_data="admin_consultations")]
            ])
        )
    else:
        await callback.message.answer("❌ Ошибка при обновлении")

    await safe_callback_answer(callback)