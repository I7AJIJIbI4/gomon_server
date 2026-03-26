#!/usr/bin/env python3  
# -*- coding: utf-8 -*-
"""
api_monitor.py - Повний моніторинг всіх API сервісів (ФІНАЛЬНА ВЕРСІЯ)
"""

import requests
import json
import logging
import time
from config import (
    ZADARMA_API_KEY, ZADARMA_API_SECRET,
    WLAUNCH_API_KEY, COMPANY_ID
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class APIMonitor:
    def __init__(self):
        self.results = {}
    
    def test_zadarma_api(self):
        """Тестування Zadarma API"""
        try:
            from zadarma_api import test_zadarma_auth
            if test_zadarma_auth():
                self.results['zadarma'] = {'status': 'OK', 'message': 'API працює'}
                return True
            else:
                self.results['zadarma'] = {'status': 'ERROR', 'message': 'Помилка авторизації'}
                return False
        except Exception as e:
            self.results['zadarma'] = {'status': 'ERROR', 'message': str(e)}
            return False
    
    def test_wlaunch_api(self):
        """Тестування WLaunch API з правильним endpoint"""
        try:
            # Правильний endpoint згідно документації
            url = f"https://api.wlaunch.net/v1/company/{COMPANY_ID}/branch/"
            params = {
                'active': 'true',
                'sort': 'ordinal',
                'page': '0',
                'size': '20'
            }
            headers = {
                'Authorization': f'Bearer {WLAUNCH_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'content' in data:
                    branches = len(data['content'])
                    total = data.get('page', {}).get('total_elements', 0)
                    branch_name = data['content'][0]['name'] if data['content'] else 'Unknown'
                    self.results['wlaunch'] = {
                        'status': 'OK', 
                        'message': f'API працює, філій: {branches} ({branch_name})'
                    }
                    return True
            
            self.results['wlaunch'] = {
                'status': 'ERROR', 
                'message': f'HTTP {response.status_code}'
            }
            return False
            
        except Exception as e:
            self.results['wlaunch'] = {'status': 'ERROR', 'message': str(e)}
            return False
    
    def test_sms_fly_api(self):
        """Тестування SMS Fly API v2"""
        try:
            # Використовуємо SMS_FLY_PASSWORD як API key для v2
            try:
                from config import SMS_FLY_PASSWORD
            except ImportError:
                self.results['sms_fly'] = {'status': 'NOT_CONFIGURED', 'message': 'SMS Fly не налаштовано'}
                return None
            
            url = "https://sms-fly.ua/api/v2/api.php"
            headers = {'Content-Type': 'application/json'}
            
            payload = {
                "auth": {
                    "key": SMS_FLY_PASSWORD
                },
                "action": "GETBALANCE",
                "data": {}
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('success') == 1:
                        balance = data.get('data', {}).get('balance', 'невідомо')
                        self.results['sms_fly'] = {'status': 'OK', 'message': f'Баланс: {balance} грн (v2)'}
                        return True
                    else:
                        error_info = data.get('error', {})
                        error_code = error_info.get('code', 'Unknown')
                        self.results['sms_fly'] = {'status': 'ERROR', 'message': f'API помилка: {error_code}'}
                        return False
                except json.JSONDecodeError:
                    self.results['sms_fly'] = {'status': 'ERROR', 'message': 'Некоректна JSON відповідь'}
                    return False
            
            self.results['sms_fly'] = {'status': 'ERROR', 'message': f'HTTP {response.status_code}'}
            return False
            
        except Exception as e:
            self.results['sms_fly'] = {'status': 'ERROR', 'message': str(e)}
            return False
    
    def test_telegram_api(self):
        """Тестування Telegram Bot API"""
        try:
            from config import TELEGRAM_TOKEN
            
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    bot_info = data['result']
                    self.results['telegram'] = {'status': 'OK', 'message': f'Бот: {bot_info["first_name"]}'}
                    return True
            
            self.results['telegram'] = {'status': 'ERROR', 'message': f'HTTP {response.status_code}'}
            return False
            
        except Exception as e:
            self.results['telegram'] = {'status': 'ERROR', 'message': str(e)}
            return False
    
    def run_all_tests(self):
        """Запуск всіх тестів API"""
        logger.info("🔍 Початок тестування всіх API...")
        
        tests = [
            ('Zadarma API', self.test_zadarma_api),
            ('WLaunch API', self.test_wlaunch_api),
            ('SMS Fly API', self.test_sms_fly_api),
            ('Telegram API', self.test_telegram_api)
        ]
        
        for name, test_func in tests:
            logger.info(f"🧪 Тестування {name}...")
            try:
                test_func()
            except Exception as e:
                logger.error(f"❌ Помилка тестування {name}: {e}")
                self.results[name.lower().replace(' ', '_')] = {'status': 'ERROR', 'message': str(e)}
        
        return self.results
    
    def get_summary(self):
        """Отримати підсумок тестування"""
        if not self.results:
            return "❓ Тестування не проводилось"
        
        ok_count = sum(1 for r in self.results.values() if r['status'] == 'OK')
        error_count = sum(1 for r in self.results.values() if r['status'] == 'ERROR')
        not_configured = sum(1 for r in self.results.values() if r['status'] == 'NOT_CONFIGURED')
        
        total = len(self.results)
        
        if error_count == 0 and ok_count == total:
            return f"🏆 ВСІ API ПРАЦЮЮТЬ ІДЕАЛЬНО! ({ok_count}/{total})"
        elif error_count == 0:
            return f"✅ Всі налаштовані API працюють ({ok_count}/{total})"
        elif error_count <= 1:
            return f"⚠️ Незначні проблеми з API ({ok_count}/{total} працюють)"
        else:
            return f"❌ Серйозні проблеми з API ({error_count}/{total} не працюють)"
    
    def get_detailed_report(self):
        """Детальний звіт по кожному API"""
        if not self.results:
            return "Немає результатів тестування"
        
        report = []
        for api_name, result in self.results.items():
            status_emoji = {
                'OK': '✅',
                'ERROR': '❌', 
                'NOT_CONFIGURED': '⚙️'
            }.get(result['status'], '❓')
            
            report.append(f"{status_emoji} {api_name.upper()}: {result['message']}")
        
        return "\n".join(report)

def main():
    """Головна функція для CLI використання"""
    monitor = APIMonitor()
    results = monitor.run_all_tests()
    
    print("\n📊 РЕЗУЛЬТАТИ ТЕСТУВАННЯ API:")
    print("=" * 50)
    print(monitor.get_detailed_report())
    print("=" * 50)
    print(monitor.get_summary())
    print("=" * 50)
    
    # Повертаємо код виходу
    error_count = sum(1 for r in results.values() if r['status'] == 'ERROR')
    return min(error_count, 10)  # Максимум 10 для exit code

if __name__ == "__main__":
    exit(main())
