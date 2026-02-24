from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import secrets
import string
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
import json
import re
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials

from config import db, logger
from models import (
    UserCreate, UserResponse, TestSubmit, UserLogin, 
    ScoreResult, ScaleType, SCALE_MAX_SCORES
)
from scoring import (
    calculate_score, 
    get_interpretation, 
    get_recommendation, 
    QUESTION_SCALES,
    INVERTED_QUESTIONS
)


# ЭТО Импорт тестовой оплаты - НЕ ИСПОЛЬЗОВАТЬ В ПРОДАКШЕНЕ
from payment import generate_test_qr, generate_users_after_payment
import uuid

app = FastAPI(
    title="PsychoTest API",
    description="Психологическое тестирование по методике 160 вопросов",
    version="1.0.0"
)

# CORS для React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== ИНИЦИАЛИЗАЦИЯ FIREBASE ADMIN SDK ==============
try:
    firebase_admin.get_app()
    logger.info("✅ Firebase Admin SDK уже инициализирован")
except ValueError:
    try:
        cred = credentials.Certificate("firebase-key.json")
        firebase_admin.initialize_app(cred)
        logger.info("✅ Firebase Admin SDK инициализирован из файла")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации Firebase Admin SDK: {e}")
        logger.warning("⚠️ Firebase Auth не будет работать без файла firebase-key.json")

# ============== ПРОВЕРКА FIREBASE ==============
@app.on_event("startup")
async def startup_event():
    if db is None:
        logger.error("❌ Firebase не инициализирован!")
    else:
        logger.info("✅ Firebase подключен успешно")
        try:
            questions_ref = db.collection("questions").limit(1).get()
            if not questions_ref:
                logger.warning("⚠️ Коллекция 'questions' пуста. Загрузите вопросы!")
        except Exception as e:
            logger.error(f"❌ Ошибка доступа к Firestore: {e}")

# ============== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==============
def generate_password(length: int = 8) -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def clean_filename(text: str) -> str:
    """Очистка имени файла - ТОЛЬКО ASCII"""
    if not text:
        return "user"
    numbers = re.findall(r'\d+', text)
    if numbers:
        return f"Test{numbers[0]}"
    return "user"

# ============== АДМИН РОУТЫ ==============
@app.post("/admin/generate-users", tags=["Admin"])
async def generate_users(data: UserCreate):
    try:
        logger.info(f"👤 Генерация {data.count} пользователей")
        
        # Получаем или создаем номер потока
        batch_ref = db.collection("batches").document("current")
        batch_data = batch_ref.get()
        
        if batch_data.exists:
            current_batch = batch_data.to_dict().get("batchNumber", 1)
        else:
            current_batch = 1
            batch_ref.set({"batchNumber": 1, "createdAt": datetime.now()})
        
        users = []
        batch = db.batch()
        users_ref = db.collection("users")
        
        # Считаем пользователей в текущем потоке
        existing = users_ref.where("batch", "==", current_batch).get()
        start_num = len(existing) + 1
        
        for i in range(data.count):
            login = f"Тестируемый{start_num + i}"
            password = generate_password(8)
            user_ref = db.collection("users").document()
            user_data = {
                "login": login,
                "password": password,
                "isCompleted": False,
                "completedAt": None,
                "createdAt": datetime.now(),
                "userId": user_ref.id,
                "batch": current_batch,  # 👈 НОМЕР ПОТОКА
                "paymentId": None
            }
            batch.set(user_ref, user_data)
            users.append({"login": login, "password": password})
        
        batch.commit()
        logger.info(f"✅ Создано {len(users)} пользователей в потоке {current_batch}")
        
        return JSONResponse({
            "success": True,
            "users": users,
            "count": len(users),
            "batch": current_batch
        })
            
    except Exception as e:
        logger.error(f"❌ Ошибка генерации пользователей: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/new-batch", tags=["Admin"])
async def create_new_batch():
    """Создание нового потока тестируемых"""
    try:
        batch_ref = db.collection("batches").document("current")
        batch_data = batch_ref.get()
        
        if batch_data.exists:
            current_batch = batch_data.to_dict().get("batchNumber", 1)
            new_batch = current_batch + 1
        else:
            new_batch = 1
        
        batch_ref.set({
            "batchNumber": new_batch,
            "createdAt": datetime.now()
        })
        
        logger.info(f"✅ Создан новый поток #{new_batch}")
        
        return {
            "success": True,
            "batch": new_batch,
            "message": f"Поток #{new_batch} создан"
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания потока: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/batches", tags=["Admin"])
async def get_batches():
    """Получение списка всех потоков"""
    try:
        users_ref = db.collection("users").get()
        
        # Группируем пользователей по потокам
        batches = {}
        for user in users_ref:
            user_data = user.to_dict()
            if user_data.get("login") == "admin":
                continue
                
            batch = user_data.get("batch", 1)
            if batch not in batches:
                batches[batch] = {
                    "batchNumber": batch,
                    "total": 0,
                    "completed": 0,
                    "pending": 0
                }
            
            batches[batch]["total"] += 1
            if user_data.get("isCompleted"):
                batches[batch]["completed"] += 1
            else:
                batches[batch]["pending"] += 1
        
        # Сортируем по номеру потока
        result = sorted(batches.values(), key=lambda x: x["batchNumber"])
        
        return {"batches": result}
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения потоков: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/users/{user_id}", tags=["Admin"])
async def get_user(user_id: str):
    """Получение данных конкретного пользователя"""
    try:
        user_ref = db.collection("users").document(user_id).get()
        if not user_ref.exists:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        user_data = user_ref.to_dict()
        user_data["id"] = user_ref.id
        return user_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка получения пользователя: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/user/{user_id}/history", tags=["User"])
async def get_user_history(user_id: str):
    """Получение истории тестирований пользователя"""
    try:
        # Ищем все результаты этого пользователя
        results_ref = db.collection("results").where("userId", "==", user_id).get()
        
        history = []
        for res in results_ref:
            res_data = res.to_dict()
            history.append({
                "completedAt": res_data.get("completedAt"),
                "scores": res_data.get("scores"),
                "recommendation": res_data.get("recommendation")
            })
        
        # Сортируем по дате (сначала новые)
        history.sort(key=lambda x: x.get("completedAt", ""), reverse=True)
        
        return {"history": history}
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения истории: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/export/users-pdf", tags=["Admin"])
async def export_users_pdf(request: Request):
    try:
        data = await request.json()
        users = data.get('users', [])
        
        if not users:
            users_ref = db.collection("users").get()
            users = []
            for user in users_ref:
                user_data = user.to_dict()
                if user_data.get("login") != "admin":
                    users.append({
                        "login": user_data.get("login"),
                        "password": user_data.get("password", "********")
                    })
        
        # PDF теперь генерируется на фронтенде
        file_bytes = b"PDF generation moved to frontend"
        return Response(
            content=file_bytes,
            media_type="text/plain; charset=ascii",
            headers={
                "Content-Disposition": f"attachment; filename=users_{datetime.now().strftime('%Y%m%d')}.txt"
            }
        )
    except Exception as e:
        logger.error(f"❌ Ошибка генерации списка: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/export/summary", tags=["Admin"])
async def export_summary_pdf():
    try:
        results_ref = db.collection("results")
        results = results_ref.get()
        result_list = []
        
        for res in results:
            res_data = res.to_dict()
            user_ref = db.collection("users").document(res.id).get()
            if user_ref.exists:
                user_data = user_ref.to_dict()
                res_data["user"] = {"login": user_data.get("login")}
            result_list.append(res_data)
        
        # PDF теперь генерируется на фронтенде
        file_bytes = b"PDF generation moved to frontend"
        return Response(
            content=file_bytes,
            media_type="text/plain; charset=ascii",
            headers={
                "Content-Disposition": f"attachment; filename=summary_{datetime.now().strftime('%Y%m%d')}.txt"
            }
        )
    except Exception as e:
        logger.error(f"❌ Ошибка генерации ведомости: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/export/user/{user_id}", tags=["Admin"])
async def export_individual_pdf(user_id: str):
    try:
        user_ref = db.collection("users").document(user_id).get()
        if not user_ref.exists:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        user_data = user_ref.to_dict()
        user_data["id"] = user_ref.id
        
        results_ref = db.collection("results").document(user_id).get()
        if results_ref.exists:
            user_data["results"] = results_ref.to_dict()
        
        # PDF теперь генерируется на фронтенде
        file_bytes = b"PDF generation moved to frontend"
        
        filename = clean_filename(user_data.get('login', 'user'))
        
        return Response(
            content=file_bytes,
            media_type="text/plain; charset=ascii",
            headers={
                "Content-Disposition": f"attachment; filename={filename}_{datetime.now().strftime('%Y%m%d')}.txt"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка генерации отчета: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/users", tags=["Admin"])
async def get_all_users():
    try:
        users_ref = db.collection("users")
        users = users_ref.get()
        result = []
        for user in users:
            user_data = user.to_dict()
            user_data["id"] = user.id
            results_ref = db.collection("results").document(user.id).get()
            if results_ref.exists:
                user_data["results"] = results_ref.to_dict()
            result.append(user_data)
        return {"users": result}
    except Exception as e:
        logger.error(f"❌ Ошибка получения пользователей: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/results", tags=["Admin"])
async def get_all_results():
    try:
        results_ref = db.collection("results")
        results = results_ref.get()
        result_list = []
        for res in results:
            res_data = res.to_dict()
            user_ref = db.collection("users").document(res.id).get()
            if user_ref.exists:
                user_data = user_ref.to_dict()
                res_data["user"] = {
                    "login": user_data.get("login"),
                    "completedAt": user_data.get("completedAt")
                }
            result_list.append(res_data)
        return {"results": result_list}
    except Exception as e:
        logger.error(f"❌ Ошибка получения результатов: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============== FIREBASE AUTH РОУТЫ ==============
# @app.post("/auth/firebase-login", tags=["Auth"])
# async def firebase_login(request: Request):
#     try:
#         data = await request.json()
#         id_token = data.get('idToken')
#         login = data.get('login')
#         password = data.get('password')
        
#         logger.info(f"🔐 Firebase вход: {login}")
        
#         try:
#             decoded_token = firebase_auth.verify_id_token(id_token)
#             firebase_uid = decoded_token['uid']
#             logger.info(f"✅ Firebase токен верифицирован: {firebase_uid}")
#         except Exception as e:
#             logger.error(f"❌ Ошибка верификации токена: {e}")
#             raise HTTPException(status_code=401, detail="Недействительный токен")
        
#         users_ref = db.collection("users").where("login", "==", login).get()
        
#         if not users_ref:
#             logger.warning(f"❌ Пользователь {login} не найден в БД")
#             raise HTTPException(status_code=401, detail="Неверный логин или пароль")
        
#         user = users_ref[0]
#         user_data = user.to_dict()
        
#         if user_data.get("password") != password:
#             logger.warning(f"❌ Неверный пароль для {login}")
#             raise HTTPException(status_code=401, detail="Неверный логин или пароль")
        
#         db.collection("users").document(user.id).update({
#             "firebaseUid": firebase_uid,
#             "lastLoginAt": datetime.now()
#         })
        
#         logger.info(f"✅ Успешный Firebase вход: {login}")
        
#         return {
#             "success": True,
#             "userId": user.id,
#             "login": user_data.get("login"),
#             "isCompleted": user_data.get("isCompleted", False)
#         }
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"❌ Ошибка Firebase авторизации: {e}")
#         raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
import asyncio  # 👈 ДОБАВЬ ЭТОТ ИМПОРТ В НАЧАЛО ФАЙЛА

@app.post("/auth/firebase-login", tags=["Auth"])
async def firebase_login(request: Request):
    try:
        data = await request.json()
        id_token = data.get('idToken')
        login = data.get('login')
        password = data.get('password')
        
        logger.info(f"🔐 Firebase вход: {login}")
        
        # 👇 RETRY МЕХАНИЗМ ДЛЯ ОШИБКИ ВРЕМЕНИ
        max_retries = 3
        decoded_token = None
        firebase_uid = None
        email_from_token = None
        
        for attempt in range(max_retries):
            try:
                decoded_token = firebase_auth.verify_id_token(id_token)
                firebase_uid = decoded_token['uid']
                email_from_token = decoded_token.get('email', '')
                logger.info(f"✅ Firebase токен верифицирован: {firebase_uid}, email: {email_from_token}")
                break
            except Exception as e:
                error_str = str(e)
                if "Token used too early" in error_str and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 1  # 1, 2, 3 секунды
                    logger.warning(f"⏰ Ошибка времени (попытка {attempt + 1}/{max_retries}), ожидание {wait_time}с...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"❌ Ошибка верификации токена: {e}")
                    raise HTTPException(status_code=401, detail="Недействительный токен")
        
        # Ищем пользователя по логину или email
        users_ref = db.collection("users").where("login", "==", login).get()
        
        if not users_ref and '@' in login:
            users_ref = db.collection("users").where("email", "==", login).get()
            logger.info(f"📝 Поиск по email: {login}, найдено: {len(users_ref)}")
        
        if not users_ref:
            logger.warning(f"❌ Пользователь {login} не найден в БД")
            raise HTTPException(status_code=401, detail="Неверный логин или пароль")
        
        user = users_ref[0]
        user_data = user.to_dict()
        
        # Для зарегистрированных через email пароль не проверяем
        if user_data.get("password") and user_data.get("password") != password:
            logger.warning(f"❌ Неверный пароль для {login}")
            raise HTTPException(status_code=401, detail="Неверный логин или пароль")
        
        db.collection("users").document(user.id).update({
            "firebaseUid": firebase_uid,
            "lastLoginAt": datetime.now()
        })
        
        logger.info(f"✅ Успешный Firebase вход: {user_data.get('login')}")
        
        # 👇 ВАЖНО: ВОЗВРАЩАЕМ ВСЕ ПОЛЯ!
        return {
            "success": True,
            "userId": user.id,
            "login": user_data.get("login"),        # 👈 ЭТО ПОЛЕ НУЖНО!
            "userLogin": user_data.get("login"),    # 👈 ДУБЛИРУЕМ ДЛЯ НАДЕЖНОСТИ
            "isCompleted": user_data.get("isCompleted", False)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка Firebase авторизации: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
@app.post("/auth/firebase-admin", tags=["Auth"])
async def firebase_admin_login(request: Request):
    try:
        data = await request.json()
        id_token = data.get('idToken')
        
        logger.info(f"🔐 Firebase вход администратора")
        
        try:
            decoded_token = firebase_auth.verify_id_token(id_token)
            firebase_uid = decoded_token['uid']
            email = decoded_token.get('email', '')
            logger.info(f"✅ Firebase токен верифицирован: {firebase_uid}, email: {email}")
        except Exception as e:
            logger.error(f"❌ Ошибка верификации токена: {e}")
            raise HTTPException(status_code=401, detail="Недействительный токен")
        
        users_ref = db.collection("users").where("login", "==", "admin").where("isAdmin", "==", True).get()
        
        if not users_ref:
            logger.warning(f"❌ Администратор не найден в БД")
            raise HTTPException(status_code=401, detail="Администратор не найден")
        
        user = users_ref[0]
        
        db.collection("users").document(user.id).update({
            "firebaseUid": firebase_uid,
            "lastLoginAt": datetime.now()
        })
        
        logger.info(f"✅ Успешный Firebase вход администратора")
        
        return {
            "success": True,
            "userId": user.id,
            "login": "admin",
            "isAdmin": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка Firebase админ-авторизации: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

# ============== СТАРЫЕ РОУТЫ АВТОРИЗАЦИИ ==============
# @app.post("/auth/login", tags=["Auth"])
# async def login(credentials: UserLogin):
#     try:
#         users_ref = db.collection("users").where("login", "==", credentials.login).get()
#         if not users_ref:
#             raise HTTPException(status_code=401, detail="Неверный логин или пароль")
        
#         user = users_ref[0]
#         user_data = user.to_dict()
        
#         if user_data.get("password") != credentials.password:
#             raise HTTPException(status_code=401, detail="Неверный логин или пароль")
        
#         if user_data.get("isCompleted"):
#             return {
#                 "success": True,
#                 "userId": user.id,
#                 "login": user_data.get("login"),
#                 "isCompleted": True,
#                 "message": "Вы уже прошли тестирование"
#             }
        
#         return {
#             "success": True,
#             "userId": user.id,
#             "login": user_data.get("login"),
#             "isCompleted": False
#         }
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"❌ Ошибка авторизации: {e}")
#         raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@app.post("/auth/login", tags=["Auth"])
async def login(credentials: UserLogin):
    try:
        logger.info(f"🔐 Попытка входа: login='{credentials.login}'")
        
        # Получаем текущий активный поток
        batch_ref = db.collection("batches").document("current")
        batch_data = batch_ref.get()
        current_batch = batch_data.to_dict().get("batchNumber", 1) if batch_data.exists else 1
        
        logger.info(f"📊 Текущий поток: {current_batch}")
        
        # Ищем пользователя с таким логином И в текущем потоке
        users_ref = db.collection("users")\
            .where("login", "==", credentials.login)\
            .where("batch", "==", current_batch)\
            .get()
        
        logger.info(f"📊 Найдено пользователей в потоке {current_batch}: {len(users_ref)}")
        
        if not users_ref:
            # Если не нашли в текущем потоке, пробуем найти в любом (для старых пользователей)
            logger.info(f"📊 Пользователь не найден в потоке {current_batch}, ищем во всех...")
            users_ref = db.collection("users").where("login", "==", credentials.login).get()
            
            if not users_ref:
                raise HTTPException(status_code=401, detail="Неверный логин или пароль")
            
            logger.info(f"📊 Найдено пользователей всего: {len(users_ref)}")
            
            # Если несколько - берем последнего по дате
            users_list = []
            for user_doc in users_ref:
                user_data = user_doc.to_dict()
                created_at = user_data.get("createdAt")
                users_list.append({
                    "id": user_doc.id,
                    "data": user_data,
                    "createdAt": created_at,
                    "batch": user_data.get("batch")
                })
            
            users_list.sort(key=lambda x: x.get("createdAt") or datetime.min, reverse=True)
            latest_user = users_list[0]
            logger.info(f"👤 Выбран пользователь из потока {latest_user['batch']}")
        else:
            # Нашли в текущем потоке
            user_doc = users_ref[0]
            latest_user = {
                "id": user_doc.id,
                "data": user_doc.to_dict()
            }
        
        user_id = latest_user["id"]
        user_data = latest_user["data"]
        
        # Проверка пароля
        stored_password = user_data.get("password")
        
        if stored_password != credentials.password:
            logger.warning(f"❌ Неверный пароль для {credentials.login}")
            raise HTTPException(status_code=401, detail="Неверный логин или пароль")
        
        # Остальной код...
        
        return {
            "success": True,
            "userId": user_id,
            "login": user_data.get("login"),
            "isCompleted": user_data.get("isCompleted", False),
            "batch": user_data.get("batch")  # Добавим batch в ответ
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка авторизации: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@app.post("/auth/admin-login", tags=["Auth"])
async def admin_login(credentials: UserLogin):
    try:
        users_ref = db.collection("users").where("login", "==", credentials.login).where("isAdmin", "==", True).get()
        if not users_ref:
            raise HTTPException(status_code=401, detail="Неверный логин или пароль")
        
        user = users_ref[0]
        user_data = user.to_dict()
        
        if user_data.get("password") != credentials.password:
            raise HTTPException(status_code=401, detail="Неверный логин или пароль")
        
        return {
            "success": True,
            "userId": user.id,
            "login": user_data.get("login"),
            "isAdmin": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка авторизации администратора: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

# ============== ОПЛАТА ==============
# @app.post("/payment/create-order", tags=["Payment"])
# async def create_payment_order(request: Request):
#     try:
#         data = await request.json()
#         amount = data.get('amount', 1000)
#         test_count = data.get('count', 1)
        
#         order_id = str(uuid.uuid4())
        
#         db.collection("payments").document(order_id).set({
#             "orderId": order_id,
#             "amount": amount,
#             "testCount": test_count,
#             "status": "pending",
#             "createdAt": datetime.now(),
#             "users": []
#         })
        
#         qr_code = generate_test_qr(amount, order_id)
        
#         return {
#             "success": True,
#             "orderId": order_id,
#             "qrCode": qr_code,
#             "amount": amount,
#             "testCount": test_count
#         }
        
#     except Exception as e:
#         logger.error(f"❌ Ошибка создания заказа: {e}")
#         raise HTTPException(status_code=500, detail=str(e))
@app.post("/payment/create-order", tags=["Payment"])
async def create_payment_order(request: Request):
    try:
        data = await request.json()
        amount = data.get('amount', 1000)
        test_count = data.get('count', 1)
        buyer_user_id = data.get('userId')  # 👈 ПОЛУЧАЕМ ID ПОКУПАТЕЛЯ
        
        logger.info(f"💳 Создание заказа: amount={amount}, count={test_count}, buyer={buyer_user_id}")
        
        order_id = str(uuid.uuid4())
        
        # Сохраняем в Firebase с информацией о покупателе
        db.collection("payments").document(order_id).set({
            "orderId": order_id,
            "amount": amount,
            "testCount": test_count,
            "status": "pending",
            "createdAt": datetime.now(),
            "users": [],
            "buyerUserId": buyer_user_id  # 👈 СОХРАНЯЕМ КТО КУПИЛ
        })
        
        qr_code = generate_test_qr(amount, order_id)
        
        return {
            "success": True,
            "orderId": order_id,
            "qrCode": qr_code,
            "amount": amount,
            "testCount": test_count
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания заказа: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# @app.post("/payment/check/{order_id}", tags=["Payment"])
# async def check_payment(order_id: str):
#     try:
#         payment_ref = db.collection("payments").document(order_id).get()
        
#         if not payment_ref.exists:
#             raise HTTPException(status_code=404, detail="Заказ не найден")
        
#         payment_data = payment_ref.to_dict()
#         current_status = payment_data.get("status", "pending")
        
#         if current_status == "pending":
#             db.collection("payments").document(order_id).update({
#                 "status": "paid",
#                 "paidAt": datetime.now()
#             })
            
#             users = generate_users_after_payment(payment_data.get("testCount", 1))
            
#             batch = db.batch()
#             generated_users = []
            
#             # Получаем текущий номер потока
#             batch_ref = db.collection("batches").document("current")
#             batch_data = batch_ref.get()
#             if batch_data.exists:
#                 current_batch = batch_data.to_dict().get("batchNumber", 1)
#             else:
#                 current_batch = 1
            
#             for user_data in users:
#                 user_ref = db.collection("users").document()
#                 user_data_db = {
#                     "login": user_data["login"],
#                     "password": user_data["password"],
#                     "isCompleted": False,
#                     "completedAt": None,
#                     "createdAt": datetime.now(),
#                     "userId": user_ref.id,
#                     "paymentId": order_id,
#                     "batch": current_batch
#                 }
#                 batch.set(user_ref, user_data_db)
#                 generated_users.append({
#                     "login": user_data["login"],
#                     "password": user_data["password"]
#                 })
            
#             batch.commit()
            
#             db.collection("payments").document(order_id).update({
#                 "users": generated_users,
#                 "status": "completed"
#             })
            
#             return {
#                 "success": True,
#                 "status": "paid",
#                 "paid": True,
#                 "users": generated_users
#             }
        
#         return {
#             "success": True,
#             "status": current_status,
#             "paid": current_status == "paid"
#         }
        
#     except Exception as e:
#         logger.error(f"❌ Ошибка проверки оплаты: {e}")
#         raise HTTPException(status_code=500, detail=str(e))
@app.post("/payment/check/{order_id}", tags=["Payment"])
async def check_payment(order_id: str):
    try:
        payment_ref = db.collection("payments").document(order_id).get()
        
        if not payment_ref.exists:
            raise HTTPException(status_code=404, detail="Заказ не найден")
        
        payment_data = payment_ref.to_dict()
        current_status = payment_data.get("status", "pending")
        buyer_user_id = payment_data.get("buyerUserId")  # 👈 КТО КУПИЛ
        
        if current_status == "pending":
            # Имитация оплаты (для теста)
            db.collection("payments").document(order_id).update({
                "status": "paid",
                "paidAt": datetime.now()
            })
            
            users = generate_users_after_payment(payment_data.get("testCount", 1))
            
            batch = db.batch()
            generated_users = []
            
            # Получаем текущий номер потока
            batch_ref = db.collection("batches").document("current")
            batch_data = batch_ref.get()
            if batch_data.exists:
                current_batch = batch_data.to_dict().get("batchNumber", 1)
            else:
                current_batch = 1
            
            for user_data in users:
                user_ref = db.collection("users").document()
                user_data_db = {
                    "login": user_data["login"],
                    "password": user_data["password"],
                    "isCompleted": False,
                    "completedAt": None,
                    "createdAt": datetime.now(),
                    "userId": user_ref.id,
                    "paymentId": order_id,
                    "batch": current_batch,
                    "purchasedBy": buyer_user_id  # 👈 КТО КУПИЛ (ОЧЕНЬ ВАЖНО!)
                }
                batch.set(user_ref, user_data_db)
                generated_users.append({
                    "userId": user_ref.id,  # 👈 ДОБАВЛЯЕМ userId
                    "login": user_data["login"],
                    "password": user_data["password"]
                })
            
            batch.commit()
            
            db.collection("payments").document(order_id).update({
                "users": generated_users,
                "status": "completed"
            })
            
            return {
                "success": True,
                "status": "paid",
                "paid": True,
                "users": generated_users
            }
        
        return {
            "success": True,
            "status": current_status,
            "paid": current_status == "paid"
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки оплаты: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============== ТЕСТИРОВАНИЕ ==============
@app.get("/questions", tags=["Test"])
async def get_questions(request: Request):
    try:
        lang = request.headers.get("Accept-Language", "ru")
        if lang.startswith("kk"):
            lang = "kz"
        else:
            lang = "ru"
        
        logger.info(f"📝 Запрос вопросов на языке: {lang}")
        
        questions_ref = db.collection("questions").order_by("number").get()
        
        questions = []
        for q in questions_ref:
            q_data = q.to_dict()
            text_field = "text_ru" if lang == "ru" else "text_kz"
            
            questions.append({
                "id": q.id,
                "number": q_data.get("number"),
                "text": q_data.get(text_field, q_data.get("text_ru", "Вопрос")),
                "types": q_data.get("types", []),
                "is_inverted": q_data.get("is_inverted", False)
            })
        
        logger.info(f"✅ Загружено {len(questions)} вопросов на языке {lang}")
        return {"questions": questions}
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения вопросов: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# @app.post("/test/submit", tags=["Test"])
# async def submit_test(test_data: TestSubmit, request: Request):
#     try:
#         user_id = request.headers.get("X-User-Id")
#         user_ref = db.collection("users").document(user_id).get()
        
#         if not user_ref.exists:
#             raise HTTPException(status_code=404, detail="Пользователь не найден")
        
#         user_data = user_ref.to_dict()
        
#         if user_data.get("isCompleted"):
#             raise HTTPException(status_code=400, detail="Тест уже пройден")
        
#         answers_ref = db.collection("users").document(user_id).collection("answers")
#         batch = db.batch()
        
#         questions_ref = db.collection("questions").get()
#         questions_dict = {}
#         for q in questions_ref:
#             q_data = q.to_dict()
#             questions_dict[q_data.get('number')] = q_data

#         for answer in test_data.answers:
#             answer_doc = answers_ref.document()
#             question_ref = db.collection("questions").document(answer.question_id).get()
            
#             q_number = 0
#             points = 0
            
#             if question_ref.exists:
#                 q_data = question_ref.to_dict()
#                 q_number = q_data.get("number", 0)
#                 if answer.answer:
#                     points = q_data.get('pointsIfYes', 1)
#                 else:
#                     points = q_data.get('pointsIfNo', 0)
            
#             answer_data = {
#                 "questionId": answer.question_id,
#                 "questionNumber": q_number,
#                 "answer": answer.answer,
#                 "points": points,
#                 "submittedAt": datetime.now()
#             }
#             batch.set(answer_doc, answer_data)
        
#         batch.commit()
        
#         answers_for_scoring = []
#         for answer in test_data.answers:
#             question_ref = db.collection("questions").document(answer.question_id).get()
#             q_number = 0
#             if question_ref.exists:
#                 q_data = question_ref.to_dict()
#                 q_number = q_data.get("number", 0)
            
#             answers_for_scoring.append({
#                 "question_number": q_number,
#                 "answer": answer.answer
#             })
        
#         scores = calculate_score(answers_for_scoring, {})
        
#         interpretations = {}
#         for scale in ["Isk", "Con", "Ast", "Ist", "Psi", "NPN"]:
#             interpretations[scale] = get_interpretation(scale, scores.get(scale, 0))
        
#         recommendation = get_recommendation(scores)
        
#         result_data = {
#             "userId": user_id,
#             "scores": scores,
#             "interpretations": interpretations,
#             "recommendation": recommendation,
#             "completedAt": datetime.now(),
#             "maxScores": {k: v for k, v in SCALE_MAX_SCORES.items()}
#         }
        
#         db.collection("results").document(user_id).set(result_data)
#         db.collection("users").document(user_id).update({
#             "isCompleted": True,
#             "completedAt": datetime.now()
#         })
        
#         return {
#             "success": True,
#             "scores": scores,
#             "interpretations": interpretations,
#             "recommendation": recommendation,
#             "maxScores": SCALE_MAX_SCORES
#         }
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"❌ Ошибка при отправке теста: {e}")
#         raise HTTPException(status_code=500, detail=str(e))
@app.post("/test/submit", tags=["Test"])
async def submit_test(test_data: TestSubmit, request: Request):
    """
    Отправка ответов и подсчет результатов
    """
    try:
        user_id = request.headers.get("X-User-Id")
        logger.info(f"📝 Получена отправка теста от user_id: {user_id}")
        logger.info(f"📦 Количество ответов: {len(test_data.answers)}")
        
        # Проверяем существование пользователя
        user_ref = db.collection("users").document(user_id).get()
        
        if not user_ref.exists:
            logger.error(f"❌ Пользователь {user_id} не найден")
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        user_data = user_ref.to_dict()
        
        if user_data.get("isCompleted"):
            logger.warning(f"⚠️ Пользователь {user_id} уже прошел тест")
            raise HTTPException(status_code=400, detail="Тест уже пройден")
        
        # ============== СОХРАНЕНИЕ ОТВЕТОВ ==============
        # Получаем ссылку на подколлекцию answers
        answers_ref = db.collection("users").document(user_id).collection("answers")
        batch = db.batch()
        
        # Загружаем все вопросы для быстрого доступа
        questions_ref = db.collection("questions").get()
        questions_dict = {}
        for q in questions_ref:
            q_data = q.to_dict()
            questions_dict[q.id] = q_data
            questions_dict[q_data.get('number')] = q_data  # Также по номеру

        saved_count = 0
        for answer in test_data.answers:
            # Создаем новый документ в подколлекции answers
            answer_doc = answers_ref.document()
            
            # Получаем данные вопроса
            question_data = questions_dict.get(answer.question_id, {})
            q_number = question_data.get("number", 0)
            
            # Вычисляем баллы за ответ
            if answer.answer:  # ответ Да
                points = question_data.get('pointsIfYes', 1)
                answer_text = "Да"
            else:  # ответ Нет
                points = question_data.get('pointsIfNo', 0)
                answer_text = "Нет"
            
            # Данные для сохранения
            answer_data = {
                "questionId": answer.question_id,
                "questionNumber": q_number,
                "answer": answer.answer,          # true/false
                "answerText": answer_text,        # "Да"/"Нет"
                "points": points,                  # баллы за ответ
                "submittedAt": datetime.now()      # время ответа
            }
            
            # Добавляем в batch
            batch.set(answer_doc, answer_data)
            saved_count += 1
        
        # Сохраняем все ответы одной транзакцией
        batch.commit()
        logger.info(f"✅ Сохранено {saved_count} ответов в коллекцию answers")
        
        # ============== ПОДСЧЕТ БАЛЛОВ ==============
        answers_for_scoring = []
        for answer in test_data.answers:
            question_data = questions_dict.get(answer.question_id, {})
            q_number = question_data.get("number", 0)
            
            answers_for_scoring.append({
                "question_number": q_number,
                "answer": answer.answer
            })
        
        scores = calculate_score(answers_for_scoring, {})
        
        interpretations = {}
        for scale in ["Isk", "Con", "Ast", "Ist", "Psi", "NPN"]:
            interpretations[scale] = get_interpretation(scale, scores.get(scale, 0))
        
        recommendation = get_recommendation(scores)
        
        # ============== СОХРАНЕНИЕ РЕЗУЛЬТАТОВ ==============
        result_data = {
            "userId": user_id,
            "scores": scores,
            "interpretations": interpretations,
            "recommendation": recommendation,
            "completedAt": datetime.now(),
            "maxScores": {k: v for k, v in SCALE_MAX_SCORES.items()}
        }
        
        db.collection("results").document(user_id).set(result_data)
        
        # Обновляем статус пользователя
        db.collection("users").document(user_id).update({
            "isCompleted": True,
            "completedAt": datetime.now()
        })
        
        logger.info(f"✅ Тест завершен. Рекомендация: {recommendation}")
        
        return {
            "success": True,
            "scores": scores,
            "interpretations": interpretations,
            "recommendation": recommendation,
            "maxScores": SCALE_MAX_SCORES
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке теста: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/auth/register", tags=["Auth"])
async def register(request: Request):
    """
    Регистрация нового пользователя
    """
    try:
        data = await request.json()
        id_token = data.get('idToken')
        email = data.get('email')
        login = data.get('login', email.split('@')[0])
        
        logger.info(f"📝 Регистрация нового пользователя: {email}")
        
        # 1. Верифицируем Firebase токен
        try:
            decoded_token = firebase_auth.verify_id_token(id_token)
            firebase_uid = decoded_token['uid']
            logger.info(f"✅ Firebase токен верифицирован: {firebase_uid}")
        except Exception as e:
            logger.error(f"❌ Ошибка верификации токена: {e}")
            raise HTTPException(status_code=401, detail="Недействительный токен")
        
        # 2. Проверяем, нет ли уже такого email в Firestore
        existing = db.collection("users").where("email", "==", email).get()
        if existing:
            logger.warning(f"❌ Email {email} уже зарегистрирован")
            raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
        
        # 3. Создаем пользователя в Firestore
        user_ref = db.collection("users").document()
        
        # Генерируем уникальный логин
        base_login = login
        counter = 1
        while True:
            existing_login = db.collection("users").where("login", "==", base_login).get()
            if not existing_login:
                break
            base_login = f"{login}{counter}"
            counter += 1
        
        # Получаем текущий номер потока
        batch_ref = db.collection("batches").document("current")
        batch_data = batch_ref.get()
        if batch_data.exists:
            current_batch = batch_data.to_dict().get("batchNumber", 1)
        else:
            current_batch = 1
        
        user_data = {
            "login": base_login,
            "email": email,
            "firebaseUid": firebase_uid,
            "isCompleted": False,
            "completedAt": None,
            "createdAt": datetime.now(),
            "userId": user_ref.id,
            "isAdmin": False,
            "batch": current_batch,
            "emailVerified": False,
            "password": None  # Пароль хранится только в Firebase Auth
        }
        
        user_ref.set(user_data)
        
        logger.info(f"✅ Пользователь создан в Firestore: {base_login}")
        
        return {
            "success": True,
            "userId": user_ref.id,
            "login": base_login,
            "message": "Пользователь успешно зарегистрирован"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка регистрации: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test/result/{user_id}", tags=["Test"])
async def get_result(user_id: str):
    try:
        result_ref = db.collection("results").document(user_id).get()
        if not result_ref.exists:
            raise HTTPException(status_code=404, detail="Результаты не найдены")
        
        result_data = result_ref.to_dict()
        user_ref = db.collection("users").document(user_id).get()
        if user_ref.exists:
            user_data = user_ref.to_dict()
            result_data["login"] = user_data.get("login")
        
        return result_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка получения результатов: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/user/profile/{user_id}", tags=["User"])
async def get_user_profile(user_id: str):
    """Получение профиля пользователя со всей историей"""
    try:
        # Данные пользователя
        user_ref = db.collection("users").document(user_id).get()
        if not user_ref.exists:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        user_data = user_ref.to_dict()
        
        # Все результаты пользователя (история тестов)
        results_ref = db.collection("results").where("userId", "==", user_id).get()
        history = []
        for res in results_ref:
            res_data = res.to_dict()
            history.append({
                "completedAt": res_data.get("completedAt"),
                "scores": res_data.get("scores"),
                "interpretations": res_data.get("interpretations"),
                "recommendation": res_data.get("recommendation")
            })
        
        # Сортируем по дате (сначала новые)
        history.sort(key=lambda x: x.get("completedAt", ""), reverse=True)
        
        # Статистика
        stats = {
            "totalTests": len(history),
            "lastTestDate": history[0].get("completedAt") if history else None,
            "lastRecommendation": history[0].get("recommendation") if history else None,
            "recommended": len([h for h in history if h.get("recommendation") == "рекомендован"]),
            "conditional": len([h for h in history if h.get("recommendation") == "условно рекомендован"]),
            "notRecommended": len([h for h in history if h.get("recommendation") == "не рекомендован"]),
            "retest": len([h for h in history if h.get("recommendation") == "ретест"])
        }
        
        return {
            "userId": user_id,
            "login": user_data.get("login"),
            "createdAt": user_data.get("createdAt"),
            "stats": stats,
            "history": history
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения профиля: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# @app.get("/user/accesses/{user_id}", tags=["User"])
# async def get_user_accesses(user_id: str):
#     """Получение всех логинов/паролей пользователя (если покупал несколько)"""
#     try:
#         # Ищем все аккаунты, связанные с этим пользователем по email или firebaseUid
#         user_ref = db.collection("users").document(user_id).get()
#         if not user_ref.exists:
#             raise HTTPException(status_code=404, detail="Пользователь не найден")
        
#         user_data = user_ref.to_dict()
#         firebase_uid = user_data.get("firebaseUid")
        
#         # Ищем все аккаунты с этим же firebaseUid
#         accesses = []
#         if firebase_uid:
#             accounts = db.collection("users").where("firebaseUid", "==", firebase_uid).get()
#             for acc in accounts:
#                 acc_data = acc.to_dict()
#                 accesses.append({
#                     "userId": acc.id,
#                     "login": acc_data.get("login"),
#                     "password": acc_data.get("password"),
#                     "isCompleted": acc_data.get("isCompleted"),
#                     "completedAt": acc_data.get("completedAt"),
#                     "paymentId": acc_data.get("paymentId")
#                 })
        
#         return {"accesses": accesses}
        
#     except Exception as e:
#         logger.error(f"❌ Ошибка получения доступов: {e}")
#         raise HTTPException(status_code=500, detail=str(e))
@app.get("/user/accesses/{user_id}", tags=["User"])
async def get_user_accesses(user_id: str):
    """Получение всех логинов/паролей, купленных пользователем"""
    try:
        logger.info(f"🔑 Запрос доступов для пользователя: {user_id}")
        
        # Ищем все аккаунты, купленные этим пользователем
        accounts = db.collection("users").where("purchasedBy", "==", user_id).get()
        
        logger.info(f"📊 Найдено доступов: {len(accounts)}")
        
        accesses = []
        for acc in accounts:
            acc_data = acc.to_dict()
            accesses.append({
                "userId": acc.id,
                "login": acc_data.get("login"),
                "password": acc_data.get("password"),
                "isCompleted": acc_data.get("isCompleted", False),
                "completedAt": acc_data.get("completedAt"),
                "paymentId": acc_data.get("paymentId")
            })
        
        return {"accesses": accesses}
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения доступов: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/user-answers/{user_id}", tags=["Admin"])
async def get_user_answers(user_id: str):
    """
    Получение всех ответов пользователя (для админа)
    """
    try:
        # Проверяем существование пользователя
        user_ref = db.collection("users").document(user_id).get()
        if not user_ref.exists:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Получаем все ответы из подколлекции
        answers_ref = db.collection("users").document(user_id).collection("answers")
        answers = answers_ref.order_by("questionNumber").get()
        
        result = []
        for ans in answers:
            ans_data = ans.to_dict()
            result.append({
                "questionNumber": ans_data.get("questionNumber"),
                "answer": ans_data.get("answer"),
                "answerText": ans_data.get("answerText", "Да" if ans_data.get("answer") else "Нет"),
                "points": ans_data.get("points", 0),
                "submittedAt": ans_data.get("submittedAt")
            })
        
        # Получаем результаты пользователя
        results_ref = db.collection("results").document(user_id).get()
        results_data = results_ref.to_dict() if results_ref.exists else None
        
        return {
            "userId": user_id,
            "userLogin": user_ref.to_dict().get("login"),
            "answers": result,
            "totalAnswers": len(result),
            "results": results_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка получения ответов: {e}")
        raise HTTPException(status_code=500, detail=str(e))
# ============== ЗАГРУЗКА ВОПРОСОВ ==============
@app.post("/admin/load-questions", tags=["Admin"])
async def load_questions_from_excel():
    try:
        questions_ref = db.collection("questions")
        old_questions = questions_ref.get()
        batch = db.batch()
        for q in old_questions:
            batch.delete(q.reference)
        batch.commit()
        
        batch = db.batch()
        questions_list = []
        
        question_texts = {
            1: "Иногда мне в голову приходят такие мысли, что лучше никому о них не рассказывать.",
            2: "Я охотно принимаю участие во всех собраниях и других общественных мероприятиях.",
        }
        
        for q_num in range(1, 161):
            if q_num in QUESTION_SCALES:
                scale_map = QUESTION_SCALES[q_num]
                types = [scale for scale, val in scale_map.items() if val == 1]
                
                q_ref = questions_ref.document(f"q_{q_num}")
                q_data = {
                    "number": q_num,
                    "text": question_texts.get(q_num, f"Вопрос {q_num}"),
                    "types": types,
                    "is_inverted": q_num in INVERTED_QUESTIONS,
                    "pointsIfYes": 0 if q_num in INVERTED_QUESTIONS else 1,
                    "pointsIfNo": 1 if q_num in INVERTED_QUESTIONS else 0,
                    "created_at": datetime.now()
                }
                
                batch.set(q_ref, q_data)
                questions_list.append(q_data)
        
        batch.commit()
        logger.info(f"✅ Загружено {len(questions_list)} вопросов")
        return {"success": True, "count": len(questions_list)}
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки вопросов: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, log_level="info")