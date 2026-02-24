# filters/admin.py
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from db.queries import is_admin
from db.session import get_session
from config import YOUR_ADMIN_ID
import logging

logger = logging.getLogger(__name__)


class IsAdminFilter(BaseFilter):
    """Фильтр для проверки прав администратора"""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id

        # Проверяем по вашему ID из конфига
        if YOUR_ADMIN_ID and user_id == YOUR_ADMIN_ID:
            logger.info(f"Доступ разрешен для администратора {user_id}")
            return True

        logger.info(f"Доступ запрещен для пользователя {user_id}")
        return False


# Создаем экземпляр фильтра
is_admin_filter = IsAdminFilter()