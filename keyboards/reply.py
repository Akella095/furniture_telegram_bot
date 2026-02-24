# keyboards/reply.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def remove_keyboard() -> ReplyKeyboardRemove:
    """Удалить клавиатуру"""
    return ReplyKeyboardRemove()


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню (Reply-клавиатура снизу)"""
    builder = ReplyKeyboardBuilder()

    # Основные разделы (2 кнопки в ряд)
    builder.row(
        KeyboardButton(text="🛏 Спальная мебель"),
        KeyboardButton(text="🍳 Кухонная мебель"),
        width=2
    )
    builder.row(
        KeyboardButton(text="🛋 Мягкая мебель"),
        KeyboardButton(text="🪑 Столы и стулья"),
        width=2
    )
    builder.row(
        KeyboardButton(text="🗄 Тумбы и комоды"),
        KeyboardButton(text="🛏 Матрасы"),
        width=2
    )
    builder.row(
        KeyboardButton(text="🚪 Шкафы"),
        width=1
    )

    # Разделитель
    builder.row(
        KeyboardButton(text="⭐ Сервис"),
        width=1
    )

    # Сервисные кнопки
    builder.row(
        KeyboardButton(text="🔍 Поиск"),
        KeyboardButton(text="📞 Поддержка"),
        width=2
    )
    builder.row(
        KeyboardButton(text="ℹ️ О нас"),
        KeyboardButton(text="🛒 Мои заказы"),
        width=2
    )

    # Кнопка главного меню
    builder.row(
        KeyboardButton(text="🏠 Главное меню"),
        width=1
    )

    return builder.as_markup(
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел или нажмите Главное меню..."
    )


def phone_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для отправки номера телефона с кнопкой НАЗАД"""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📱 Отправить номер телефона", request_contact=True))
    builder.row(KeyboardButton(text="◀️ Назад"))
    builder.row(KeyboardButton(text="❌ Отменить заказ"))
    builder.row(KeyboardButton(text="🏠 Главное меню"))
    return builder.as_markup(resize_keyboard=True)


def order_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для отмены заказа (ТОЛЬКО для заказов)"""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="❌ Отменить заказ"))
    builder.row(KeyboardButton(text="🏠 Главное меню"))
    return builder.as_markup(resize_keyboard=True)


def question_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для отмены вопроса (ТОЛЬКО для вопросов)"""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="❌ Отменить вопрос"))
    builder.row(KeyboardButton(text="🏠 Главное меню"))
    return builder.as_markup(resize_keyboard=True)


def back_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой назад"""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="◀️ Назад"))
    builder.row(KeyboardButton(text="❌ Отменить заказ"))
    builder.row(KeyboardButton(text="🏠 Главное меню"))
    return builder.as_markup(resize_keyboard=True)


def confirm_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура подтверждения"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="✅ Подтвердить"),
        KeyboardButton(text="❌ Отменить заказ"),
        width=2
    )
    builder.row(KeyboardButton(text="🏠 Главное меню"))
    return builder.as_markup(resize_keyboard=True)