# states/search.py
from aiogram.fsm.state import State, StatesGroup

class SearchStates(StatesGroup):
    """Состояния для поиска"""
    waiting_query = State()