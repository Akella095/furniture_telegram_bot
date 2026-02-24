# db/session.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from config import DATABASE_URL
from db.base import Base
from db.models import Category, Admin
import logging
from logger import logger

# Создаем асинхронный движок для SQLite
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    """Инициализация базы данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Создаем начальные категории
    await create_initial_categories()

    # Добавляем админов из .env в БД
    from config import ADMIN_IDS
    async for session in get_session():
        for admin_id in ADMIN_IDS:
            result = await session.execute(
                select(Admin).where(Admin.user_id == admin_id)
            )
            if not result.scalar_one_or_none():
                admin = Admin(user_id=admin_id)
                session.add(admin)
        await session.commit()


async def create_initial_categories():
    """Создание начальной структуры категорий"""
    async for session in get_session():
        # Проверяем, есть ли уже категории
        result = await session.execute(select(Category).limit(1))
        if result.scalar_one_or_none():
            return

        logger.info("Создание начальных категорий...")

        # Корневые категории
        root_cats = {}
        for name in ["Спальная мебель", "Кухонная мебель", "Мягкая мебель",
                     "Столы и стулья", "Тумбы и комоды", "Матрасы", "Шкафы"]:
            cat = Category(name=name, parent_id=None)
            session.add(cat)
            await session.flush()
            root_cats[name] = cat.id

        # Спальная мебель
        bedroom = root_cats["Спальная мебель"]
        russian_bed = Category(name="Российская", parent_id=bedroom)
        turkish_bed = Category(name="Турецкая", parent_id=bedroom)
        beds = Category(name="Кровати", parent_id=bedroom)
        session.add_all([russian_bed, turkish_bed, beds])
        await session.flush()

        # Кухонная мебель
        kitchen = root_cats["Кухонная мебель"]
        straight = Category(name="Прямая", parent_id=kitchen)
        corner = Category(name="Угловая", parent_id=kitchen)
        session.add_all([straight, corner])
        await session.flush()

        # Мягкая мебель
        soft = root_cats["Мягкая мебель"]
        russian_soft = Category(name="Российская", parent_id=soft)
        turkish_soft = Category(name="Турецкая", parent_id=soft)
        session.add_all([russian_soft, turkish_soft])
        await session.flush()

        # Подкатегории для Российской мягкой мебели
        soft_straight = Category(name="Прямая", parent_id=russian_soft.id)
        soft_corner = Category(name="Угловая", parent_id=russian_soft.id)
        session.add_all([soft_straight, soft_corner])

        await session.commit()
        logger.info("Начальные категории созданы")


async def get_session():
    """Генератор сессий БД"""
    async with AsyncSessionLocal() as session:
        yield session


async def close_db():
    """Закрытие соединения с БД"""
    await engine.dispose()