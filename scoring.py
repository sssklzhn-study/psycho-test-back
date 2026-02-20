from typing import List, Dict, Any, Optional
import logging
from models import ScaleType, SCALE_MAX_SCORES, INVERTED_QUESTIONS, ISK_SKIP_QUESTION_1
from config import db

logger = logging.getLogger(__name__)

# ============== ЭТАЛОННЫЕ ВОПРОСЫ ИЗ EXCEL ==============
# Это матрица принадлежности вопросов к шкалам
# Заполнено ПОЛНОСТЬЮ на основе листа "Шкала" в Excel
# 1 = вопрос относится к шкале, 0 = не относится

QUESTION_SCALES = {
    1:  {"Isk": 1, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},
    2:  {"Isk": 1, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},
    3:  {"Isk": 0, "Con": 0, "Ast": 1, "Ist": 0, "Psi": 0, "NPN": 0},
    4:  {"Isk": 0, "Con": 1, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 1},
    5:  {"Isk": 0, "Con": 0, "Ast": 1, "Ist": 0, "Psi": 0, "NPN": 0},
    6:  {"Isk": 1, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},
    7:  {"Isk": 0, "Con": 0, "Ast": 1, "Ist": 0, "Psi": 0, "NPN": 0},
    8:  {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    9:  {"Isk": 0, "Con": 0, "Ast": 1, "Ist": 0, "Psi": 0, "NPN": 0},
    10: {"Isk": 0, "Con": 0, "Ast": 1, "Ist": 0, "Psi": 0, "NPN": 1},
    11: {"Isk": 1, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},
    12: {"Isk": 0, "Con": 0, "Ast": 1, "Ist": 0, "Psi": 0, "NPN": 0},
    13: {"Isk": 0, "Con": 0, "Ast": 1, "Ist": 0, "Psi": 0, "NPN": 0},
    14: {"Isk": 0, "Con": 0, "Ast": 1, "Ist": 0, "Psi": 0, "NPN": 0},
    15: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    16: {"Isk": 0, "Con": 0, "Ast": 1, "Ist": 0, "Psi": 0, "NPN": 0},
    17: {"Isk": 0, "Con": 0, "Ast": 1, "Ist": 0, "Psi": 0, "NPN": 0},
    18: {"Isk": 1, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},
    19: {"Isk": 1, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},
    20: {"Isk": 0, "Con": 1, "Ast": 1, "Ist": 0, "Psi": 0, "NPN": 1},
    21: {"Isk": 0, "Con": 0, "Ast": 1, "Ist": 0, "Psi": 0, "NPN": 0},
    22: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    23: {"Isk": 1, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},
    24: {"Isk": 0, "Con": 0, "Ast": 1, "Ist": 0, "Psi": 0, "NPN": 0},
    25: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    26: {"Isk": 1, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},
    27: {"Isk": 1, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},
    28: {"Isk": 0, "Con": 0, "Ast": 1, "Ist": 0, "Psi": 0, "NPN": 0},
    29: {"Isk": 0, "Con": 0, "Ast": 1, "Ist": 0, "Psi": 0, "NPN": 0},
    30: {"Isk": 0, "Con": 1, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    31: {"Isk": 1, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},
    32: {"Isk": 0, "Con": 0, "Ast": 1, "Ist": 0, "Psi": 0, "NPN": 1},
    33: {"Isk": 0, "Con": 0, "Ast": 1, "Ist": 0, "Psi": 0, "NPN": 1},
    34: {"Isk": 1, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},
    35: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},  # КРАСНЫЙ
    36: {"Isk": 0, "Con": 1, "Ast": 1, "Ist": 0, "Psi": 0, "NPN": 1},
    37: {"Isk": 0, "Con": 0, "Ast": 1, "Ist": 0, "Psi": 0, "NPN": 1},
    38: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    39: {"Isk": 1, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},
    40: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    41: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    42: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},  # КРАСНЫЙ
    43: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},  # КРАСНЫЙ
    44: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    45: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    46: {"Isk": 1, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},
    47: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    48: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    49: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    50: {"Isk": 0, "Con": 1, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    51: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    52: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    53: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    54: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},  # НЕТ В ШКАЛАХ
    55: {"Isk": 1, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},
    56: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    57: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    58: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    59: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},  # НЕТ В ШКАЛАХ
    60: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 1},
    61: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},  # НЕТ В ШКАЛАХ
    62: {"Isk": 1, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},
    63: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    64: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    65: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    66: {"Isk": 1, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},
    67: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    68: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    69: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    70: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},  # НЕТ В ШКАЛАХ
    71: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},  # КРАСНЫЙ
    72: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    73: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    74: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    75: {"Isk": 0, "Con": 1, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    76: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    77: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    78: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},  # НЕТ В ШКАЛАХ
    79: {"Isk": 1, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},
    80: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    81: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    82: {"Isk": 0, "Con": 1, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    83: {"Isk": 0, "Con": 1, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    84: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    85: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    86: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    87: {"Isk": 0, "Con": 1, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    88: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    89: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    90: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},  # НЕТ В ШКАЛАХ
    91: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    92: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    93: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    94: {"Isk": 0, "Con": 1, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    95: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    96: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    97: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 1, "Psi": 0, "NPN": 0},
    98: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    99: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},  # НЕТ В ШКАЛАХ
    100: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 0},
    101: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 0},
    102: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    103: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    104: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 0},
    105: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 0},
    106: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    107: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    108: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 0},
    109: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 0},
    110: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},  # КРАСНЫЙ
    111: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    112: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 0},
    113: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 0},
    114: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    115: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    116: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 0},
    117: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 0},
    118: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    119: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    120: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 0},
    121: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 0},
    122: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    123: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    124: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 0},
    125: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 1},
    126: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},  # НЕТ В ШКАЛАХ
    127: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    128: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 1},
    129: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 1},
    130: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},  # НЕТ В ШКАЛАХ
    131: {"Isk": 0, "Con": 1, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    132: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 0},
    133: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 1},
    134: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},  # НЕТ В ШКАЛАХ
    135: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    136: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 1},
    137: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 1},
    138: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 1},
    139: {"Isk": 0, "Con": 1, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    140: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    141: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 0},
    142: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 0},
    143: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},  # НЕТ В ШКАЛАХ
    144: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},  # НЕТ В ШКАЛАХ
    145: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 1},
    146: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 1},
    147: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},  # НЕТ В ШКАЛАХ
    148: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    149: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 0},
    150: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 0},
    151: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    152: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    153: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 0},  # КРАСНЫЙ
    154: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 1},
    155: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    156: {"Isk": 0, "Con": 1, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    157: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 1, "NPN": 0},  # КРАСНЫЙ
    158: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},  # НЕТ В ШКАЛАХ
    159: {"Isk": 0, "Con": 1, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 1},
    160: {"Isk": 0, "Con": 0, "Ast": 0, "Ist": 0, "Psi": 0, "NPN": 0},  # НЕТ В ШКАЛАХ
}

# Инвертированные вопросы (красные в Excel)
INVERTED_QUESTIONS = {35, 42, 43, 71, 110, 153, 157}

def calculate_score(answers: List[Dict], questions_map: Dict[int, Dict]) -> Dict[str, int]:
    """
    ТОЧНЫЙ ПОДСЧЕТ ПО МЕТОДИКЕ EXCEL с использованием данных из БД
    """
    
    # Инициализируем баллы
    scores = {
        "Isk": 0,
        "Con": 0, 
        "Ast": 0,
        "Ist": 0,
        "Psi": 0,
        "NPN": 0
    }
    
    logger.info(f"📊 НАЧАЛО ПОДСЧЕТА: получено {len(answers)} ответов")
    
    for answer_item in answers:
        q_num = answer_item["question_number"]
        answer_bool = answer_item["answer"]  # True = Да, False = Нет
        
        # Получаем матрицу принадлежности для этого вопроса
        if q_num not in QUESTION_SCALES:
            logger.warning(f"⚠️ Вопрос {q_num} не найден в матрице, пропускаем")
            continue
            
        scale_map = QUESTION_SCALES[q_num]
        
        # ОПРЕДЕЛЯЕМ БАЛЛ ЗА ОТВЕТ из БД (если есть) или используем старую логику
        if q_num in INVERTED_QUESTIONS:
            score = 0 if answer_bool else 1
        else:
            score = 1 if answer_bool else 0
        
        # ДОБАВЛЯЕМ БАЛЛЫ ВО ВСЕ ШКАЛЫ, К КОТОРЫМ ОТНОСИТСЯ ВОПРОС
        for scale, belongs in scale_map.items():
            if belongs == 1:
                # ОСОБЫЙ СЛУЧАЙ: Вопрос 1 НЕ УЧИТЫВАЕТСЯ в Isk
                if scale == "Isk" and q_num == 1:
                    logger.debug(f"    🚫 Пропускаем вопрос 1 для Isk (по методике)")
                    continue
                    
                scores[scale] += score
                logger.debug(f"    ✅ +{score} к {scale}, теперь {scores[scale]}")
    
    # Проверка: максимальные баллы должны совпадать с Excel
    logger.info(f"📈 ИТОГОВЫЕ БАЛЛЫ:")
    for scale, max_score in SCALE_MAX_SCORES.items():
        logger.info(f"  {scale}: {scores[scale.value]}/{max_score}")
    
    return scores


def get_interpretation(scale: str, score: int) -> str:
    """
    Интерпретация результатов ПО ТЗ И EXCEL
    Формат: "норма (X)", "условно рекомендован (X)", "не рекомендован (X)", "ретест"
    """
    
    if scale == "Isk":  # Достоверность
        if score <= 6:
            return f"норма ({score} из 15)"
        else:
            return f"ретест ({score} из 15)"
    
    elif scale == "Con":  # Аутоагрессия
        if score <= 6:
            return f"норма ({score} из 14)"
        elif score <= 8:
            return f"условно рекомендован ({score} из 14)"
        else:
            return f"не рекомендован ({score} из 14)"
    
    elif scale == "NPN":  # Нервно-психическая устойчивость
        if score <= 23:
            return f"норма ({score} из 67)"
        elif score <= 30:
            return f"условно рекомендован ({score} из 67)"
        else:
            return f"не рекомендован ({score} из 67)"
    
    elif scale == "Psi":  # Психопатическая реакция
        if score <= 13:
            return f"норма ({score} из 30)"
        else:
            return f"не рекомендован ({score} из 30)"
    
    elif scale == "Ist":  # Истероидные проявления
        if score <= 27:
            return f"норма ({score} из 30)"
        else:
            return f"не рекомендован ({score} из 30)"
    
    elif scale == "Ast":  # Ранимость, чувствительность
        if score <= 15:
            return f"норма ({score} из 19)"
        else:
            return f"условно рекомендован ({score} из 19)"
    
    return f"{score} баллов"


def get_recommendation(scores: Dict[str, int]) -> str:
    """
    Итоговая рекомендация на основе всех шкал
    Приоритет: нерекомендован > ретест > условно > рекомендован
    """
    
    isk_score = scores.get("Isk", 0)
    con_score = scores.get("Con", 0)
    npn_score = scores.get("NPN", 0)
    psi_score = scores.get("Psi", 0)
    ist_score = scores.get("Ist", 0)
    ast_score = scores.get("Ast", 0)
    
    # Проверяем наихудший сценарий
    if con_score > 8 or npn_score > 30 or psi_score > 13 or ist_score > 27:
        return "не рекомендован"
    
    if isk_score > 6:
        return "ретест"
    
    if (7 <= con_score <= 8) or (24 <= npn_score <= 30) or (ast_score > 15):
        return "условно рекомендован"
    
    return "рекомендован"