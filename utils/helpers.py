# utils/helpers.py
import re
from typing import Tuple, Optional, List
from aiogram.types import CallbackQuery, Message
from logger import logger


def validate_phone(phone: str) -> bool:
    """
    Валидация номера телефона.
    Принимает форматы: +7XXXXXXXXXX, 8XXXXXXXXXX, 79XXXXXXXXX и т.д.
    """
    # Удаляем все нецифровые символы
    cleaned = re.sub(r'\D', '', phone)

    # Проверяем длину
    if len(cleaned) not in [10, 11]:
        return False

    # Проверяем начало
    if len(cleaned) == 11:
        return cleaned.startswith(('7', '8'))
    elif len(cleaned) == 10:
        return cleaned.startswith('9')

    return False


def format_phone(phone: str) -> str:
    """Форматирование номера телефона в читаемый вид"""
    cleaned = re.sub(r'\D', '', phone)

    if len(cleaned) == 11 and cleaned[0] in ('7', '8'):
        formatted = f"+7 ({cleaned[1:4]}) {cleaned[4:7]}-{cleaned[7:9]}-{cleaned[9:11]}"
    elif len(cleaned) == 10:
        formatted = f"+7 ({cleaned[0:3]}) {cleaned[3:6]}-{cleaned[6:8]}-{cleaned[8:10]}"
    else:
        formatted = phone

    return formatted


def parse_callback_data(callback_data: str) -> Tuple[str, ...]:
    """Парсинг callback_data с поддержкой сложных форматов"""
    parts = callback_data.split('_')
    return tuple(parts)


def split_text(text: str, max_length: int = 4000) -> List[str]:
    """Разделение длинного текста на части"""
    if len(text) <= max_length:
        return [text]

    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break

        # Ищем место для разрыва (конец предложения или пробел)
        split_pos = text.rfind('. ', 0, max_length)
        if split_pos == -1:
            split_pos = text.rfind(' ', 0, max_length)
        if split_pos == -1:
            split_pos = max_length

        parts.append(text[:split_pos + 1])
        text = text[split_pos + 1:].lstrip()

    return parts


def format_price(price: Optional[float]) -> str:
    """Форматирование цены"""
    if price is None:
        return "Цена не указана"
    return f"{price:,.0f} ₽".replace(",", " ")


def format_product_caption(product) -> str:
    """Формирование подписи к товару"""
    caption = f"<b>{product.name}</b>\n\n"

    if product.description:
        caption += f"{product.description}\n\n"

    if product.country:
        caption += f"🌍 Страна: {product.country}\n"

    if product.dimensions:
        caption += f"📏 Размеры: {product.dimensions}\n"

    if product.price:
        caption += f"💰 Цена: {format_price(product.price)}\n"

    return caption


def format_order_text(order) -> str:
    """Формирование текста заказа"""
    status_emoji = {
        "новая": "🆕",
        "в работе": "🔄",
        "выполнена": "✅",
        "отменена": "❌"
    }.get(order.status, "📦")

    text = (
        f"<b>Заказ #{order.id}</b>\n"
        f"Статус: {status_emoji} {order.status}\n"
        f"Дата: {order.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"<b>Клиент:</b>\n"
        f"Имя: {order.full_name}\n"
        f"Телефон: {order.phone}\n"
        f"Username: @{order.username if order.username else 'нет'}\n\n"
        f"<b>Товар:</b>\n"
        f"{order.product_name}\n"
    )

    if order.comment:
        text += f"\n<b>Комментарий:</b>\n{order.comment}\n"

    return text


def escape_markdown(text: str) -> str:
    """Экранирование спецсимволов для Markdown"""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)


def safe_str(value: Optional[str]) -> str:
    """Безопасное преобразование в строку"""
    return str(value) if value is not None else "Не указано"