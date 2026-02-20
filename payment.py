# ЭТОТ ФАЙЛ ТЕСТОВАЯ ОПЛАТА ПО ВАРИАНТУ 1, НЕ ИСПОЛЬЗОВАТЬ В ПРОДАКШЕНЕ
import qrcode
import io
import base64
import uuid
import random
import string
from datetime import datetime

def generate_password(length: int = 8) -> str:
    """Генерация случайного пароля"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(random.choice(alphabet) for _ in range(length))

def generate_test_qr(amount: float, order_id: str) -> str:
    """
    Генерация ТЕСТОВОГО Kaspi QR кода
    В реальности: https://kaspi.kz/pay/{merchant_id}/{order_id}/{amount}
    Для теста: просто текст с суммой
    """
    # Тестовые данные Kaspi (предоставленные заказчиком)
    kaspi_merchant_id = "TEST_MERCHANT_123"
    
    # Формируем тестовую ссылку
    qr_data = f"https://test.kaspi.kz/pay/{kaspi_merchant_id}/{order_id}/{amount}"
    
    # Генерируем QR код
    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=5
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Конвертируем в base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return f"data:image/png;base64,{img_str}"

def generate_users_after_payment(count: int = 1) -> list:
    """Генерация пользователей после оплаты"""
    users = []
    for i in range(count):
        login = f"Тестируемый{random.randint(1000, 9999)}"
        password = generate_password(8)
        users.append({
            "login": login,
            "password": password
        })
    return users