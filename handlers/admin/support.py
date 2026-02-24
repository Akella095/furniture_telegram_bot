# handlers/admin/support.py
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, desc
from datetime import datetime
import logging

from filters.admin import is_admin_filter
from db.models import SupportRequest
from db.session import get_session
from config import MANAGER_CHAT_ID
from logger import logger

router = Router(name="admin_support")
router.message.filter(is_admin_filter)
router.callback_query.filter(is_admin_filter)


class ReplyToUserStates(StatesGroup):
    waiting_reply = State()


# ==================== СПИСОК ЗАПРОСОВ ====================

@router.callback_query(F.data == "admin_support_requests")
async def list_support_requests(callback: CallbackQuery, session: AsyncSession):
    """Список всех запросов в поддержку"""
    await list_support_requests_page(callback, session, 1)


async def list_support_requests_page(callback: CallbackQuery, session: AsyncSession, page: int = 1):
    """Список запросов с пагинацией"""
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    limit = 5  # Запросов на странице
    offset = (page - 1) * limit

    # Получаем общее количество запросов
    total_count = await session.scalar(select(func.count(SupportRequest.id)))
    total_pages = max(1, (total_count + limit - 1) // limit)

    # Получаем запросы с пагинацией
    result = await session.execute(
        select(SupportRequest)
        .order_by(desc(SupportRequest.created_at))
        .offset(offset)
        .limit(limit)
    )
    requests = result.scalars().all()

    text = f"📋 <b>Последние запросы в поддержку</b> (страница {page}/{total_pages})\n\n"

    if not requests:
        text += "Нет запросов"
    else:
        for req in requests:
            status = "✅" if req.is_resolved else "🆕"
            username = f"@{req.username}" if req.username else f"ID: {req.user_id}"
            date_str = req.created_at.strftime('%d.%m.%Y %H:%M')

            text += f"{status} <b>#{req.id}</b> от {username}\n"
            text += f"📝 {req.message[:50]}...\n"
            text += f"📅 {date_str}\n"

            if req.is_resolved and req.resolved_at:
                text += f"✅ Решено {req.resolved_at.strftime('%d.%m.%Y')}\n"
            text += "\n"

    # Создаем клавиатуру
    builder = InlineKeyboardBuilder()

    # Кнопки для каждого запроса
    for req in requests:
        row = []
        # Кнопка просмотра
        row.append(InlineKeyboardButton(
            text=f"👁 #{req.id}",
            callback_data=f"view_request_{req.id}"
        ))

        # Если не решено - кнопка ответа
        if not req.is_resolved:
            row.append(InlineKeyboardButton(
                text="✍️ Ответить",
                callback_data=f"reply_to_user_{req.id}"
            ))

        # Кнопка удалить (для всех)
        row.append(InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=f"delete_request_{req.id}"
        ))

        builder.row(*row, width=3 if len(row) == 3 else 2)

    # Пагинация
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"support_page_{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="ignore"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"support_page_{page + 1}"))
    if nav_row:
        builder.row(*nav_row)

    # Кнопка назад
    builder.row(
        InlineKeyboardButton(text="◀️ Назад в админку", callback_data="admin_back"),
        width=1
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("support_page_"))
async def support_page(callback: CallbackQuery, session: AsyncSession):
    """Пагинация запросов поддержки"""
    page = int(callback.data.split("_")[2])
    await list_support_requests_page(callback, session, page)


# ==================== ПРОСМОТР ЗАПРОСА ====================

@router.callback_query(F.data.startswith("view_request_"))
async def view_request(callback: CallbackQuery, session: AsyncSession):
    """Просмотр деталей запроса"""
    request_id = int(callback.data.split("_")[2])

    result = await session.execute(
        select(SupportRequest).where(SupportRequest.id == request_id)
    )
    req = result.scalar_one_or_none()

    if not req:
        await callback.answer("Запрос не найден")
        return

    status = "✅ Решен" if req.is_resolved else "🆕 Новый"
    username = f"@{req.username}" if req.username else "Нет username"

    text = (
        f"📋 <b>Запрос #{req.id}</b>\n\n"
        f"<b>Статус:</b> {status}\n"
        f"<b>От:</b> {req.full_name or 'Имя не указано'} ({username})\n"
        f"<b>User ID:</b> <code>{req.user_id}</code>\n"
        f"<b>Дата:</b> {req.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"<b>Вопрос:</b>\n{req.message}\n\n"
    )

    if req.is_resolved and req.resolved_at:
        resolver = f" (админ ID: {req.resolved_by})" if req.resolved_by else ""
        text += f"<b>Решено:</b> {req.resolved_at.strftime('%d.%m.%Y %H:%M')}{resolver}\n"

    # Создаем клавиатуру
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()

    if not req.is_resolved:
        builder.row(InlineKeyboardButton(
            text="✍️ Ответить",
            callback_data=f"reply_to_user_{req.id}"
        ))

    builder.row(
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_request_{req.id}"),
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin_support_requests"),
        width=2
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


# ==================== ОТВЕТ НА ЗАПРОС ====================

# В функции start_reply_to_user убедитесь, что состояние установлено правильно
@router.callback_query(F.data.startswith("reply_to_user_"))
async def start_reply_to_user(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начать ответ пользователю"""
    request_id = int(callback.data.split("_")[3])

    # Получаем запрос из БД
    result = await session.execute(
        select(SupportRequest).where(SupportRequest.id == request_id)
    )
    support_request = result.scalar_one_or_none()

    if not support_request:
        await callback.answer("Запрос не найден")
        return

    # Сохраняем данные в состояние
    await state.update_data(
        request_id=request_id,
        user_id=support_request.user_id,
        user_message=support_request.message,
        username=support_request.username
    )

    # Показываем информацию о запросе
    text = (
        f"✍️ <b>Ответ пользователю</b>\n\n"
        f"<b>Запрос #{request_id}</b>\n"
        f"<b>Вопрос:</b>\n{support_request.message}\n\n"
        f"<b>От:</b> @{support_request.username if support_request.username else 'нет'}\n"
        f"<b>ID:</b> <code>{support_request.user_id}</code>\n\n"
        f"<i>Введите ваш ответ. Отправьте /cancel для отмены.</i>"
    )

    await callback.message.edit_text(text, parse_mode="HTML")

    # ВАЖНО: устанавливаем состояние
    await state.set_state(ReplyToUserStates.waiting_reply)
    logger.info(f"Установлено состояние ReplyToUserStates:waiting_reply для админа {callback.from_user.id}")

    await callback.answer()


@router.message(ReplyToUserStates.waiting_reply, F.text == "/cancel")
async def cancel_reply(message: Message, state: FSMContext):
    """Отмена ответа"""
    await message.answer(
        "❌ Ответ отменен",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 К списку запросов", callback_data="admin_support_requests")]
        ])
    )
    await state.clear()


@router.message(ReplyToUserStates.waiting_reply)
async def send_reply_to_user(message: Message, state: FSMContext, session: AsyncSession):
    """Отправить ответ пользователю"""
    # Логируем начало отправки
    logger.info(f"=== НАЧАЛО ОТПРАВКИ ОТВЕТА ===")
    logger.info(f"Админ {message.from_user.id} (@{message.from_user.username}) отправляет ответ")
    logger.info(f"Текст ответа: {message.text[:50]}...")

    data = await state.get_data()
    logger.info(f"Данные из state: {data}")

    request_id = data['request_id']
    user_id = data['user_id']
    original_question = data['user_message']
    username = data.get('username', 'пользователь')

    reply_text = message.text.strip()
    logger.info(f"ID запроса: {request_id}")
    logger.info(f"ID пользователя: {user_id}")
    logger.info(f"Username пользователя: @{username}")

    if len(reply_text) < 2:
        logger.warning(f"Слишком короткий ответ: {len(reply_text)} символов")
        await message.answer("❌ Слишком короткий ответ. Введите ответ ещё раз (или /cancel для отмены):")
        return

    try:
        # Отправляем ответ пользователю с цитированием его вопроса
        logger.info(f"Попытка отправки сообщения пользователю {user_id}...")

        await message.bot.send_message(
            user_id,
            f"📨 <b>Ответ от поддержки</b>\n\n"
            f"<b>Ваш вопрос:</b>\n{original_question}\n\n"
            f"<b>Ответ:</b>\n{reply_text}\n\n"
            f"<i>Если у вас остались вопросы, напишите снова!</i>",
            parse_mode="HTML"
        )

        logger.info(f"✅ Сообщение успешно отправлено пользователю {user_id}")

        # Отмечаем запрос как решенный
        logger.info(f"Отмечаем запрос #{request_id} как решенный...")

        result = await session.execute(
            select(SupportRequest).where(SupportRequest.id == request_id)
        )
        support_request = result.scalar_one_or_none()

        if support_request:
            support_request.is_resolved = True
            support_request.resolved_at = datetime.utcnow()
            support_request.resolved_by = message.from_user.id
            await session.commit()

            logger.info(f"✅ Запрос #{request_id} отмечен как решенный")
            logger.info(f"Решен администратором: {message.from_user.id}")
            logger.info(f"Время решения: {support_request.resolved_at}")
        else:
            logger.error(f"❌ Запрос #{request_id} не найден в БД")

        # Отправляем подтверждение админу
        await message.answer(
            f"✅ <b>Ответ отправлен! Запрос #{request_id} отмечен как решенный.</b>\n\n"
            f"<b>Кому:</b> @{username}\n"
            f"<b>Ваш ответ:</b>\n{reply_text}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 К списку запросов", callback_data="admin_support_requests")]
            ]),
            parse_mode="HTML"
        )

        logger.info(f"✅ Подтверждение отправлено админу")

        # Обновляем исходное сообщение в чате менеджера (убираем кнопки)
        if support_request and support_request.reply_message_id:
            try:
                logger.info(f"Обновляем сообщение менеджера (ID: {support_request.reply_message_id})...")
                await message.bot.edit_message_reply_markup(
                    chat_id=MANAGER_CHAT_ID,
                    message_id=support_request.reply_message_id,
                    reply_markup=None
                )
                logger.info(f"✅ Сообщение менеджера обновлено")
            except Exception as e:
                logger.error(f"❌ Не удалось обновить сообщение менеджера: {e}")

    except Exception as e:
        logger.error(f"❌ ОШИБКА при отправке ответа: {e}")
        logger.error(f"Тип ошибки: {type(e).__name__}")

        # Определяем тип ошибки для пользователя
        error_text = str(e)
        if "bot was blocked by the user" in error_text:
            user_error = "Пользователь заблокировал бота"
        elif "chat not found" in error_text:
            user_error = "Пользователь не найден (возможно, удалил чат)"
        elif "Forbidden" in error_text:
            user_error = "Бот заблокирован пользователем"
        else:
            user_error = f"Техническая ошибка: {error_text[:100]}"

        await message.answer(
            f"❌ <b>Ошибка при отправке ответа</b>\n\n"
            f"{user_error}\n\n"
            f"Запрос #{request_id} остался в статусе 'новый'.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 К списку запросов", callback_data="admin_support_requests")]
            ]),
            parse_mode="HTML"
        )

    logger.info(f"=== КОНЕЦ ОТПРАВКИ ОТВЕТА ===")
    await state.clear()


# ==================== УДАЛЕНИЕ ЗАПРОСА ====================

@router.callback_query(F.data.startswith("delete_request_"))
async def delete_request_confirm(callback: CallbackQuery):
    """Подтверждение удаления запроса"""
    request_id = int(callback.data.split("_")[2])

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{request_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"view_request_{request_id}"),
        width=2
    )

    await callback.message.edit_text(
        f"❓ <b>Вы уверены, что хотите удалить запрос #{request_id}?</b>\n\n"
        "Это действие необратимо!",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete_"))
async def delete_request(callback: CallbackQuery, session: AsyncSession):
    """Удаление запроса"""
    request_id = int(callback.data.split("_")[2])

    try:
        # Удаляем запрос
        await session.execute(
            delete(SupportRequest).where(SupportRequest.id == request_id)
        )
        await session.commit()

        logger.info(f"Запрос #{request_id} удален администратором {callback.from_user.id}")

        await callback.message.edit_text(
            f"✅ <b>Запрос #{request_id} успешно удален</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 К списку запросов", callback_data="admin_support_requests")]
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка при удалении запроса #{request_id}: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка при удалении запроса</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_support_requests")]
            ]),
            parse_mode="HTML"
        )

    await callback.answer()


# ==================== ОТМЕТИТЬ КАК РЕШЕННЫЙ ====================

@router.callback_query(F.data.startswith("resolve_request_"))
async def resolve_request(callback: CallbackQuery, session: AsyncSession):
    """Отметить запрос как решенный без ответа"""
    request_id = int(callback.data.split("_")[2])

    result = await session.execute(
        select(SupportRequest).where(SupportRequest.id == request_id)
    )
    support_request = result.scalar_one_or_none()

    if support_request:
        support_request.is_resolved = True
        support_request.resolved_at = datetime.utcnow()
        support_request.resolved_by = callback.from_user.id
        await session.commit()

        await callback.message.edit_text(
            f"✅ <b>Запрос #{request_id} отмечен как решенный</b>\n\n"
            f"Вопрос: {support_request.message[:100]}...",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 К списку запросов", callback_data="admin_support_requests")]
            ]),
            parse_mode="HTML"
        )

        # Убираем кнопки с исходного сообщения, если оно было в чате менеджера
        if support_request.reply_message_id:
            try:
                await callback.bot.edit_message_reply_markup(
                    chat_id=MANAGER_CHAT_ID,
                    message_id=support_request.reply_message_id,
                    reply_markup=None
                )
            except Exception as e:
                logger.error(f"Не удалось обновить сообщение менеджера: {e}")
    else:
        await callback.answer("Запрос не найден")

    await callback.answer()