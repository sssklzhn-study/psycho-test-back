from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum

# ============== ШКАЛЫ =======
class ScaleType(str, Enum):
    ISK = "Isk"  # Достоверность
    CON = "Con"  # Аутоагрессия
    AST = "Ast"  # Ранимость
    IST = "Ist"  # Истероидность
    PSI = "Psi"  # Психопатия
    NPN = "NPN"  # Нервно-психическая устойчивость

# Максимальные баллы по шкалам ИЗ EXCEL
SCALE_MAX_SCORES = {
    ScaleType.ISK: 17,   # Isk (но вопрос 1 не учитывается = 16 макс)
    ScaleType.CON: 14,   # Con
    ScaleType.AST: 19,   # Ast
    ScaleType.IST: 30,   # Ist
    ScaleType.PSI: 30,   # Psi
    ScaleType.NPN: 67,   # NPN
}

# ============== ИНВЕРТИРОВАННЫЕ ВОПРОСЫ (КРАСНЫЕ В EXCEL) ===
# Да = 0, Нет = 1
INVERTED_QUESTIONS = {35, 42, 43, 71, 110, 153, 157}

# Вопрос 1 НЕ УЧИТЫВАЕТСЯ в Isk
ISK_SKIP_QUESTION_1 = True

# ============== МОДЕЛИ ДАННЫХ ======
class Question(BaseModel):
    """Модель вопроса"""
    id: Optional[str] = None
    number: int  # номер вопроса (1-160)
    text: str
    types: List[str]  # ['Isk', 'Con', ...]
    is_inverted: bool = False  # True для красных вопросов

class UserCreate(BaseModel):
    """Создание пользователя админом"""
    count: int = 1

class UserResponse(BaseModel):
    """Ответ пользователя"""
    question_id: str
    answer: bool  # True = Да, False = Нет

class TestSubmit(BaseModel):
    """Отправка теста"""
    answers: List[UserResponse]

class UserLogin(BaseModel):
    """Логин пользователя"""
    login: str
    password: str

class ScoreResult(BaseModel):
    """Результаты подсчета"""
    scores: Dict[str, int]  # баллы по шкалам
    interpretations: Dict[str, str]  # текстовые интерпретации
    recommendation: str  # итоговая рекомендация
    max_scores: Dict[str, int]  # максимальные баллы