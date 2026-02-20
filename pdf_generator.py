from datetime import datetime
import logging
from typing import List, Dict
import re

logger = logging.getLogger(__name__)

def extract_test_number(login: str) -> str:
    """Извлекает номер из логина и возвращает TestN"""
    if not login:
        return "Unknown"
    numbers = re.findall(r'\d+', login)
    if numbers:
        return f"Test{numbers[0]}"
    return "Unknown"

def generate_individual_pdf(user_data: Dict) -> bytes:
    """Генерация отчета - ТОЛЬКО ASCII, ГАРАНТИЯ РАБОТЫ"""
    try:
        # БЕРЕМ ТОЛЬКО НОМЕР ИЗ ЛОГИНА
        login = extract_test_number(user_data.get('login', ''))
        
        results = user_data.get('results', {})
        scores = results.get('scores', {})
        
        recommendation = results.get('recommendation', '')
        if 'не рекомендован' in recommendation:
            rec_text = 'NOT RECOMMENDED'
        elif 'рекомендован' in recommendation:
            rec_text = 'RECOMMENDED'
        elif 'условно' in recommendation:
            rec_text = 'CONDITIONALLY RECOMMENDED'
        elif 'ретест' in recommendation:
            rec_text = 'RETEST REQUIRED'
        else:
            rec_text = 'UNKNOWN'
        
        now = datetime.now()
        date_str = now.strftime('%d.%m.%Y %H:%M')
        datetime_str = now.strftime('%d.%m.%Y %H:%M:%S')
        
        # ФОРМИРУЕМ БАЙТЫ
        output = []
        output.append(b'============================================================')
        output.append(b'INDIVIDUAL TEST REPORT')
        output.append(b'============================================================')
        output.append(b'')
        output.append(f'Login: {login}'.encode('ascii'))
        output.append(f'Date: {date_str}'.encode('ascii'))
        output.append(b'')
        output.append(b'TEST RESULTS:')
        output.append(b'----------------------------------------')
        output.append(f'Isk (Truthfulness)     : {scores.get("Isk", 0)}/17'.encode('ascii'))
        output.append(f'Con (Autoaggression)  : {scores.get("Con", 0)}/14'.encode('ascii'))
        output.append(f'NPN (Neuro-psychic)   : {scores.get("NPN", 0)}/67'.encode('ascii'))
        output.append(f'Psi (Psychopathy)     : {scores.get("Psi", 0)}/30'.encode('ascii'))
        output.append(f'Ist (Hysteria)        : {scores.get("Ist", 0)}/30'.encode('ascii'))
        output.append(f'Ast (Sensitivity)     : {scores.get("Ast", 0)}/19'.encode('ascii'))
        output.append(b'')
        output.append(f'FINAL RECOMMENDATION: {rec_text}'.encode('ascii'))
        output.append(b'')
        output.append(b'============================================================')
        output.append(f'Generated: {datetime_str}'.encode('ascii'))
        output.append(b'PsychoTest System v1.0')
        
        return b'\n'.join(output)
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации отчета: {e}")
        return b'Error generating report'

def generate_users_pdf(users: List[Dict]) -> bytes:
    """Генерация списка пользователей - ТОЛЬКО ASCII"""
    try:
        now = datetime.now()
        date_str = now.strftime('%d.%m.%Y %H:%M')
        
        output = []
        output.append(b'============================================================')
        output.append(b'USERS LIST')
        output.append(b'============================================================')
        output.append(b'')
        output.append(f'Generated: {date_str}'.encode('ascii'))
        output.append(b'')
        output.append(b'------------------------------------------------------------')
        output.append(b'No.   Login                     Password')
        output.append(b'------------------------------------------------------------')
        
        for i, user in enumerate(users[:30], 1):
            login = extract_test_number(user.get('login', ''))
            password = user.get('password', '')
            
            line = f"{i:<5} {login[:25]:<25} {password[:25]:<25}"
            output.append(line.encode('ascii'))
        
        output.append(b'------------------------------------------------------------')
        return b'\n'.join(output)
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации списка: {e}")
        return b'Error generating list'

def generate_summary_pdf(results: List[Dict]) -> bytes:
    """Генерация общей ведомости - ТОЛЬКО ASCII"""
    try:
        now = datetime.now()
        date_str = now.strftime('%d.%m.%Y %H:%M')
        
        output = []
        output.append(b'================================================================================')
        output.append(b'TEST RESULTS SUMMARY')
        output.append(b'================================================================================')
        output.append(b'')
        output.append(f'Date: {date_str}'.encode('ascii'))
        output.append(b'')
        output.append(b'--------------------------------------------------------------------------------')
        output.append(b'Login           Isk   Con   NPN   Psi   Ist   Ast   Rec    ')
        output.append(b'--------------------------------------------------------------------------------')
        
        for res in results[:30]:
            user = res.get('user', {})
            login = user.get('login', '')
            if login == 'admin': 
                continue
            
            login = extract_test_number(login)
            scores = res.get('scores', {})
            
            rec = res.get('recommendation', '')
            if 'не рекомендован' in rec:
                rec_short = 'NO'
            elif 'рекомендован' in rec:
                rec_short = 'OK'
            elif 'условно' in rec:
                rec_short = 'MAYBE'
            elif 'ретест' in rec:
                rec_short = 'RETEST'
            else:
                rec_short = '?'
            
            line = f"{login[:15]:<15} {scores.get('Isk', 0):<6} {scores.get('Con', 0):<6} {scores.get('NPN', 0):<6} {scores.get('Psi', 0):<6} {scores.get('Ist', 0):<6} {scores.get('Ast', 0):<6} {rec_short:<8}"
            output.append(line.encode('ascii'))
        
        output.append(b'--------------------------------------------------------------------------------')
        return b'\n'.join(output)
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации ведомости: {e}")
        return b'Error generating summary'