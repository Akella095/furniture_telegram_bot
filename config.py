# config.py
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else []

# SQLite для простоты
DATABASE_URL = "sqlite+aiosqlite:///furniture_bot.db"

# Настройки
PRODUCTS_PER_PAGE = 5
ORDERS_PER_PAGE = 10
SEARCH_RESULTS_PER_PAGE = 5

# ID чата менеджера для пересылки сообщений
MANAGER_CHAT_ID = ADMIN_IDS[0] if ADMIN_IDS else None

# ДОБАВЛЯЕМ ЭТУ СТРОКУ - ваш личный ID для удобства
YOUR_ADMIN_ID = ADMIN_IDS[0] if ADMIN_IDS else None