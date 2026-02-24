# states/order.py
from aiogram.fsm.state import State, StatesGroup

class OrderStates(StatesGroup):
    """Состояния для оформления заказа"""
    waiting_name = State()
    waiting_phone = State()
    waiting_product_selection = State()
    waiting_comment = State()
    confirmation = State()

class ConsultationStates(StatesGroup):
    """Состояния для заказа консультации"""
    waiting_name = State()
    waiting_phone = State()
    confirmation = State()

class SupportStates(StatesGroup):
    """Состояния для поддержки"""
    waiting_question = State()