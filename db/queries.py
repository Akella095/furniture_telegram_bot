# db/queries.py
from datetime import datetime

from sqlalchemy import select, update, delete, and_, or_, func
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Tuple, Dict, Any
from db.models import Category, Product, ProductPhoto, Order, Admin, SupportRequest, Consultation
from logger import logger


# ========== КАТЕГОРИИ ==========

async def get_root_categories(session: AsyncSession) -> List[Category]:
    """Получить корневые категории"""
    result = await session.execute(
        select(Category)
        .where(Category.parent_id.is_(None), Category.is_active)
        .order_by(Category.order, Category.id)
    )
    return result.scalars().all()


async def get_subcategories(session: AsyncSession, parent_id: int) -> List[Category]:
    """Получить дочерние категории"""
    result = await session.execute(
        select(Category)
        .where(Category.parent_id == parent_id, Category.is_active)
        .order_by(Category.order, Category.id)
    )
    return result.scalars().all()


async def get_category(session: AsyncSession, category_id: int) -> Optional[Category]:
    """Получить категорию по ID"""
    return await session.get(Category, category_id)


async def get_category_path(session: AsyncSession, category_id: int) -> List[Category]:
    """Получить путь до категории (для кнопки Назад)"""
    path = []
    current = await get_category(session, category_id)
    while current:
        path.append(current)
        if current.parent_id:
            current = await get_category(session, current.parent_id)
        else:
            break
    return list(reversed(path))


async def create_category(session: AsyncSession, name: str, parent_id: Optional[int] = None) -> Category:
    """Создать категорию (для админа)"""
    category = Category(name=name, parent_id=parent_id)
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


async def update_category(session: AsyncSession, category_id: int, **kwargs) -> Optional[Category]:
    """Обновить категорию"""
    await session.execute(
        update(Category)
        .where(Category.id == category_id)
        .values(**kwargs)
    )
    await session.commit()
    return await get_category(session, category_id)


async def delete_category(session: AsyncSession, category_id: int) -> bool:
    """Удалить категорию"""
    result = await session.execute(
        delete(Category).where(Category.id == category_id)
    )
    await session.commit()
    return result.rowcount > 0


# ========== ТОВАРЫ ==========

async def get_products_by_category(
        session: AsyncSession,
        category_id: int,
        page: int = 1,
        limit: int = 5
) -> Tuple[List[Product], bool]:
    """Получить товары категории с пагинацией"""
    offset = (page - 1) * limit
    result = await session.execute(
        select(Product)
        .where(Product.category_id == category_id, Product.is_active)
        .options(selectinload(Product.photos))
        .order_by(Product.id)
        .offset(offset)
        .limit(limit + 1)
    )
    items = result.scalars().all()
    has_next = len(items) > limit
    return items[:limit], has_next


async def get_product(session: AsyncSession, product_id: int) -> Optional[Product]:
    """Получить товар по ID"""
    return await session.get(
        Product,
        product_id,
        options=[
            selectinload(Product.photos),
            selectinload(Product.category)
        ]
    )


async def search_products(
        session: AsyncSession,
        query: str,
        page: int = 1,
        limit: int = 5
) -> Tuple[List[Product], bool, int]:
    """Поиск товаров по названию и описанию"""
    offset = (page - 1) * limit
    search_pattern = f"%{query}%"

    # Сначала считаем общее количество
    count_result = await session.execute(
        select(func.count(Product.id))
        .where(
            Product.is_active,
            or_(
                Product.name.ilike(search_pattern),
                Product.description.ilike(search_pattern),
                Product.country.ilike(search_pattern)
            )
        )
    )
    total = count_result.scalar() or 0

    # Получаем товары
    result = await session.execute(
        select(Product)
        .where(
            Product.is_active,
            or_(
                Product.name.ilike(search_pattern),
                Product.description.ilike(search_pattern),
                Product.country.ilike(search_pattern)
            )
        )
        .options(selectinload(Product.photos))
        .order_by(Product.id)
        .offset(offset)
        .limit(limit + 1)
    )
    items = result.scalars().all()
    has_next = len(items) > limit

    return items[:limit], has_next, total


async def create_product(
        session: AsyncSession,
        name: str,
        category_id: int,
        description: Optional[str] = None,
        country: Optional[str] = None,
        dimensions: Optional[str] = None,
        price: Optional[float] = None
) -> Product:
    """Создать товар"""
    product = Product(
        name=name,
        category_id=category_id,
        description=description,
        country=country,
        dimensions=dimensions,
        price=price
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product


async def update_product(session: AsyncSession, product_id: int, **kwargs) -> Optional[Product]:
    """Обновить товар"""
    await session.execute(
        update(Product)
        .where(Product.id == product_id)
        .values(**kwargs)
    )
    await session.commit()
    return await get_product(session, product_id)


async def delete_product(session: AsyncSession, product_id: int) -> bool:
    """Удалить товар"""
    result = await session.execute(
        delete(Product).where(Product.id == product_id)
    )
    await session.commit()
    return result.rowcount > 0


# ========== ФОТО ==========

async def add_product_photos(
        session: AsyncSession,
        product_id: int,
        file_ids: List[str]
) -> List[ProductPhoto]:
    """Добавить фото к товару"""
    photos = []
    for order, file_id in enumerate(file_ids):
        photo = ProductPhoto(
            product_id=product_id,
            file_id=file_id,
            order=order
        )
        session.add(photo)
        photos.append(photo)
    await session.commit()
    return photos


async def delete_product_photo(session: AsyncSession, photo_id: int) -> bool:
    """Удалить фото товара"""
    result = await session.execute(
        delete(ProductPhoto).where(ProductPhoto.id == photo_id)
    )
    await session.commit()
    return result.rowcount > 0


# ========== ЗАКАЗЫ ==========

async def create_order(
        session: AsyncSession,
        user_id: int,
        full_name: str,
        phone: str,
        product_name: str,
        username: Optional[str] = None,
        product_id: Optional[int] = None,
        comment: Optional[str] = None
) -> Order:
    """Создать заказ"""
    order = Order(
        user_id=user_id,
        username=username,
        full_name=full_name,
        phone=phone,
        product_id=product_id,
        product_name=product_name,
        comment=comment,
        status="новая"
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


async def get_orders(
        session: AsyncSession,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 10
) -> Tuple[List[Order], bool]:
    """Получить заказы с пагинацией"""
    offset = (page - 1) * limit
    query = select(Order).options(selectinload(Order.product)).order_by(Order.created_at.desc())

    if status:
        query = query.where(Order.status == status)

    query = query.offset(offset).limit(limit + 1)
    result = await session.execute(query)
    items = result.scalars().all()
    has_next = len(items) > limit

    return items[:limit], has_next


async def get_order(session: AsyncSession, order_id: int) -> Optional[Order]:
    """Получить заказ по ID"""
    return await session.get(
        Order,
        order_id,
        options=[selectinload(Order.product)]
    )


async def update_order_status(session: AsyncSession, order_id: int, status: str) -> Optional[Order]:
    """Обновить статус заказа"""
    await session.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(status=status)
    )
    await session.commit()
    return await get_order(session, order_id)


# ========== АДМИНЫ ==========

async def is_admin(session: AsyncSession, user_id: int) -> bool:
    """Проверить, является ли пользователь админом"""
    result = await session.execute(
        select(Admin).where(Admin.user_id == user_id, Admin.is_active)
    )
    return result.scalar_one_or_none() is not None


async def get_all_admins(session: AsyncSession) -> List[Admin]:
    """Получить всех админов"""
    result = await session.execute(
        select(Admin).where(Admin.is_active)
    )
    return result.scalars().all()


# ========== ПОДДЕРЖКА ==========

async def create_support_request(
    session: AsyncSession,
    user_id: int,
    message: str,
    username: Optional[str] = None,
    full_name: Optional[str] = None
) -> SupportRequest:
    """Создать запрос в поддержку"""
    request = SupportRequest(
        user_id=user_id,
        username=username,
        full_name=full_name,
        message=message
    )
    session.add(request)
    await session.commit()
    await session.refresh(request)
    return request


async def update_support_request(
        session: AsyncSession,
        request_id: int,
        reply_to_message_id: int
) -> Optional[SupportRequest]:
    """Обновить запрос поддержки (ID ответного сообщения)"""
    await session.execute(
        update(SupportRequest)
        .where(SupportRequest.id == request_id)
        .values(reply_to_message_id=reply_to_message_id, is_resolved=True)
    )
    await session.commit()
    return await session.get(SupportRequest, request_id)


async def create_consultation(
        session: AsyncSession,
        user_id: int,
        full_name: str,
        phone: str,
        username: Optional[str] = None,
        product_id: Optional[int] = None,
        product_name: Optional[str] = None
) -> Consultation:
    """Создать запрос на консультацию"""
    consultation = Consultation(
        user_id=user_id,
        username=username,
        full_name=full_name,
        phone=phone,
        product_id=product_id,
        product_name=product_name,
        status="новая"
    )
    session.add(consultation)
    await session.commit()
    await session.refresh(consultation)
    return consultation


async def get_consultations(
        session: AsyncSession,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 10
) -> Tuple[List[Consultation], bool]:
    """Получить список консультаций"""
    offset = (page - 1) * limit
    query = select(Consultation).order_by(Consultation.created_at.desc())

    if status:
        query = query.where(Consultation.status == status)

    query = query.offset(offset).limit(limit + 1)
    result = await session.execute(query)
    items = result.scalars().all()
    has_next = len(items) > limit

    return items[:limit], has_next


async def update_consultation_status(
        session: AsyncSession,
        consultation_id: int,
        status: str,
        processed_by: Optional[int] = None,
        comment: Optional[str] = None
) -> Optional[Consultation]:
    """Обновить статус консультации"""
    values = {"status": status}
    if processed_by:
        values["processed_by"] = processed_by
    if comment:
        values["comment"] = comment
    if status in ["выполнена", "отменена"]:
        values["processed_at"] = datetime.utcnow()

    await session.execute(
        update(Consultation)
        .where(Consultation.id == consultation_id)
        .values(**values)
    )
    await session.commit()
    return await session.get(Consultation, consultation_id)