# bot.py
import asyncio
import sys
import socks
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

from config import BOT_TOKEN, YOUR_ADMIN_ID, ADMIN_IDS
from db.session import init_db, close_db
from logger import logger

from handlers.user import start, catalog, orders, search, support
from handlers.admin import panel, products, categories, orders as admin_orders, support as admin_support, \
    consultations as admin_consultations
from handlers.common import back
from middlewares.db import DbSessionMiddleware
from middlewares.support import SupportMiddleware


async def set_bot_commands(bot: Bot):
    """Установка меню команд"""

    # Команды для обычных пользователей
    user_commands = [
        BotCommand(command="start", description="🚀 Запустить бота"),
        BotCommand(command="catalog", description="📋 Открыть каталог"),
        BotCommand(command="search", description="🔍 Поиск товаров"),
        BotCommand(command="orders", description="📦 Мои заказы"),
        BotCommand(command="support", description="📞 Поддержка"),
        BotCommand(command="about", description="ℹ️ О компании")
    ]

    # Команды для администратора (с /admin)
    admin_commands = [
        BotCommand(command="start", description="🚀 Запустить бота"),
        BotCommand(command="admin", description="👨‍💼 Админ-панель"),
        BotCommand(command="catalog", description="📋 Каталог"),
        BotCommand(command="orders", description="📦 Мои заказы"),
        BotCommand(command="support", description="📞 Поддержка"),
        BotCommand(command="about", description="ℹ️ О компании")
    ]

    # Устанавливаем команды для всех пользователей
    await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())

    # Для администратора устанавливаем отдельные команды (используем YOUR_ADMIN_ID из config)
    if YOUR_ADMIN_ID:
        await bot.set_my_commands(
            admin_commands,
            scope=BotCommandScopeChat(chat_id=YOUR_ADMIN_ID)
        )
        logger.info(f"Админ-команды установлены для пользователя {YOUR_ADMIN_ID}")

    # Также устанавливаем для всех админов из списка (на случай если их несколько)
    for admin_id in ADMIN_IDS:
        if admin_id != YOUR_ADMIN_ID:  # Пропускаем основного админа, уже установили
            try:
                await bot.set_my_commands(
                    admin_commands,
                    scope=BotCommandScopeChat(chat_id=admin_id)
                )
                logger.info(f"Админ-команды установлены для пользователя {admin_id}")
            except Exception as e:
                logger.error(f"Не удалось установить команды для админа {admin_id}: {e}")


async def on_startup(bot: Bot):
    """Действия при запуске"""
    await init_db()
    await set_bot_commands(bot)
    logger.info("База данных инициализирована")
    logger.info("Команды бота установлены")

    # Уведомление админов о запуске
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "✅ Бот запущен и готов к работе!")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")


async def on_shutdown(bot: Bot):
    """Действия при остановке"""
    logger.info("Бот останавливается...")
    await close_db()
    logger.info("База данных закрыта")
    logger.info("Бот успешно остановлен")


async def main():

    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())



    # Middleware
    dp.update.middleware(DbSessionMiddleware())
    dp.message.middleware(SupportMiddleware(bot))
    dp.callback_query.middleware(SupportMiddleware(bot))

    # Регистрация роутеров
    dp.include_router(start.router)
    dp.include_router(catalog.router)
    dp.include_router(orders.router)
    dp.include_router(search.router)
    dp.include_router(support.router)
    dp.include_router(back.router)

    # Админские роутеры
    dp.include_router(panel.router)
    dp.include_router(products.router)
    dp.include_router(categories.router)
    dp.include_router(admin_orders.router)
    dp.include_router(admin_support.router)
    dp.include_router(admin_consultations.router)

    # Регистрация функций запуска/остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Удаляем вебхук перед запуском
    await bot.delete_webhook(drop_pending_updates=True)

    # Обработка сигналов для graceful shutdown
    try:
        logger.info("Бот запущен. Нажмите Ctrl+C для остановки.")
        await dp.start_polling(bot)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Получен сигнал остановки...")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
    finally:
        # Закрываем сессию бота
        await bot.session.close()
        logger.info("Сессия бота закрыта")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем (Ctrl+C)")
        sys.exit(0)