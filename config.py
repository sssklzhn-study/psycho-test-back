import firebase_admin
from firebase_admin import credentials, firestore, auth
import os
from dotenv import load_dotenv
import logging

# Логирование для отладки
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# ============== FIREBASE INIT ==============
def init_firebase():
    """Инициализация Firebase с проверкой ошибок"""
    try:
        # Проверяем, не инициализировано ли уже
        firebase_admin.get_app()
        logger.info("✅ Firebase уже инициализирован")
    except ValueError:
        # Ищем сервисный аккаунт
        cred_path = os.getenv("FIREBASE_CREDENTIALS", "firebase-key.json")
        
        if not os.path.exists(cred_path):
            logger.error(f"❌ Файл {cred_path} не найден!")
            logger.info("📌 Создайте firebase-key.json в папке backend")
            raise FileNotFoundError(f"Firebase key not found at {cred_path}")
        
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        logger.info("✅ Firebase инициализирован успешно")
    
    return firestore.client()

# Глобальные объекты БД
try:
    db = init_firebase()
except Exception as e:
    logger.error(f"❌ Ошибка Firebase: {e}")
    db = None