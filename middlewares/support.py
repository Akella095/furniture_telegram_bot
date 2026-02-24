# middlewares/support.py
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from config import MANAGER_CHAT_ID, ADMIN_IDS
from logger import logger


class SupportMiddleware(BaseMiddleware):
    """Middleware для пересылки сообщений в поддержку"""

    def __init__(self, bot: Bot):
        self.bot = bot
        super().__init__()

    async def __call__(
            self,
            handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
            event: Message | CallbackQuery,
            data: Dict[str, Any]
    ) -> Any:
        # Проверяем, что это сообщение и оно НЕ является командой
        if isinstance(event, Message) and event.text and not event.text.startswith('/'):
            # Получаем состояние из data
            state: FSMContext = data.get("state")
            user_id = event.from_user.id

            # ЕСЛИ ЭТО АДМИН - НИЧЕГО НЕ ПЕРЕСЫЛАЕМ
            if user_id in ADMIN_IDS:
                logger.debug(f"Админ {user_id} пишет сообщение - пропускаем без пересылки")
                return await handler(event, data)

            if state:
                current_state = await state.get_state()

                # СПИСОК СОСТОЯНИЙ, КОТОРЫЕ НЕ ДОЛЖНЫ ПЕРЕСЫЛАТЬСЯ МЕНЕДЖЕРУ
                skip_states = [
                    # Состояния добавления товара
                    "AddProductStates:waiting_name",
                    "AddProductStates:waiting_category",
                    "AddProductStates:waiting_country",
                    "AddProductStates:waiting_dimensions",
                    "AddProductStates:waiting_price",
                    "AddProductStates:waiting_description",
                    "AddProductStates:waiting_photos",

                    # Состояния редактирования товара
                    "EditProductStates:waiting_field_value",
                    "EditProductStates:waiting_category",
                    "EditProductStates:waiting_photos",

                    # Состояния заказа
                    "OrderStates:waiting_name",
                    "OrderStates:waiting_phone",
                    "OrderStates:waiting_product_selection",
                    "OrderStates:waiting_comment",
                    "OrderStates:confirmation",

                    # Состояния консультации
                    "ConsultationStates:waiting_name",
                    "ConsultationStates:waiting_phone",
                    "ConsultationStates:confirmation",

                    # Состояния поддержки (когда пользователь задает вопрос)
                    "SupportStates:waiting_question",

                    # Состояния категорий
                    "CategoryStates:waiting_name",
                    "CategoryStates:waiting_parent",

                    # Состояния поиска
                    "SearchStates:waiting_query",

                    # Состояния ответа админа
                    "ReplyToUserStates:waiting_reply"  # ДОБАВЛЯЕМ ЭТО СОСТОЯНИЕ
                ]

                # Если текущее состояние в списке пропускаемых - не пересылаем
                if current_state and current_state in skip_states:
                    logger.debug(f"Сообщение в состоянии {current_state} не пересылается менеджеру")
                    return await handler(event, data)

            # Если пользователь пишет в личку боту без команды и не в FSM,
            # пересылаем менеджеру (только если это не админ)
            if MANAGER_CHAT_ID and not event.text.startswith('/') and user_id not in ADMIN_IDS:
                try:
                    # Формируем сообщение для менеджера
                    user = event.from_user
                    forward_text = (
                        f"📨 <b>Сообщение от пользователя</b>\n"
                        f"ID: {user.id}\n"
                        f"Имя: {user.full_name}\n"
                        f"Username: @{user.username if user.username else 'нет'}\n\n"
                        f"Текст: {event.text}"
                    )

                    await self.bot.send_message(
                        MANAGER_CHAT_ID,
                        forward_text,
                        parse_mode="HTML"
                    )

                    # Отвечаем пользователю, что сообщение отправлено
                    await event.answer(
                        "✅ Ваше сообщение отправлено менеджеру. Ожидайте ответа!"
                    )
                    return  # Не передаем дальше в хендлеры
                except Exception as e:
                    logger.error(f"Ошибка пересылки сообщения: {e}")

        return await handler(event, data)