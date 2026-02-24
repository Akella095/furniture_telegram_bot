# states/product.py
from aiogram.fsm.state import State, StatesGroup

class AddProductStates(StatesGroup):
    """Состояния для добавления товара админом"""
    waiting_name = State()
    waiting_category = State()
    waiting_country = State()
    waiting_dimensions = State()
    waiting_price = State()
    waiting_description = State()
    waiting_photos = State()
    confirmation = State()

class EditProductStates(StatesGroup):
    """Состояния для редактирования товара"""
    waiting_field_value = State()
    waiting_category = State()
    waiting_photos = State()