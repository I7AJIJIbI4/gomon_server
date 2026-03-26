#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
api_monitor.py - Покращений моніторинг API з детальною інформацією про баланси
"""

import requests
import json
import logging
import time
from config import (
    ZADARMA_API_KEY, ZADARMA_API_SECRET,
    WLAUNCH_API_KEY, COMPANY_ID
)

# Імпортуємо Telegram сповіщувач
try:
    from telegram_notifier import TelegramNotifier
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("⚠️ Telegram сповіщення недоступні")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class APIMonitor:
    def __init__(self, enable_notifications=True):
        self.results = {}
        self.notifier = TelegramNotifier() if TELEGRAM_AVAILABLE and enable_notifications else None
    
    def test_zadarma_api(self):
        """Тестування Zadarma API з отриманням балансу"""
        try:
            # Використовуємо zadarma_api для отримання балансу
            from zadarma_api import zadarma_api
            
            response = zadarma_api.call('/v1/info/balance/', {}, 'GET')
            result = json.loads(response.text)
            
            if result.get("status") == "success":
                balance = result.get("balance", "невідомо")
                currency = result.get("currency", "")
                
                # Форматуємо повідомлення як у SMS Fly
                balance_msg = f"Баланс: {balance} {currency}" if currency else f"Баланс: {balance}"
                
                self.results['zadarma'] = {
                    'status': 'OK', 
                    'message': balance_msg,
                    'balance': balance,
                    'currency': currency
                }
                logger.info(f"✅ Zadarma API працює. {balance_msg}")
                return True
            else:
                error_msg = result.get("message", "Невідома помилка API")
                self.results['zadarma'] = {'status': 'ERROR', 'message': f'API помилка: {error_msg}'}
                logger.error(f"❌ Zadarma API помилка: {error_msg}")
                return False
                
        except Exception as e:
            error_msg = str(e)
            self.results['zadarma'] = {'status': 'ERROR', 'message': f'Помилка підключення: {error_msg}'}
            logger.error(f"❌ Zadarma API виключення: {error_msg}")
            return False
    
    def test_wlaunch_api(self):
        """Тестування WLaunch API з додатковою інформацією"""
        try:
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
                    
                    if data['content']:
                        branch_name = data['content'][0]['name']
                        # Додаємо інформацію про активність
                        active_branches = sum(1 for b in data['content'] if b.get('active', False))
                        
                        message = f"Філій: {branches} ({active_branches} активних) - {branch_name}"
                    else:
                        message = f"Філій: {branches} (порожній список)"
                    
                    self.results['wlaunch'] = {
                        'status': 'OK', 
                        'message': message,
                        'branches_count': branches,
                        'active_branches': active_branches if data['content'] else 0
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
        """Тестування SMS Fly API v2 з детальною інформацією"""
        try:
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
                        
                        # Додаємо інформацію про рівень балансу
                        try:
                            balance_float = float(balance)
                            if balance_float < 10:
                                balance_status = "⚠️ Низький баланс"
                            elif balance_float < 50:
                                balance_status = "🟡 Помірний баланс"
                            else:
                                balance_status = "✅ Достатній баланс"
                        except:
                            balance_status = ""
                        
                        message = f"Баланс: {balance} грн {balance_status}".strip()
                        
                        self.results['sms_fly'] = {
                            'status': 'OK', 
                            'message': message,
                            'balance': balance,
                            'currency': 'грн'
                        }
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
        """Тестування Telegram Bot API з додатковою інформацією"""
        try:
            from config import TELEGRAM_TOKEN
            
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    bot_info = data['result']
                    bot_name = bot_info.get("first_name", "Unknown")
                    username = bot_info.get("username", "")
                    
                    # Додаємо інформацію про username якщо є
                    if username:
                        message = f"Бот: {bot_name} (@{username})"
                    else:
                        message = f"Бот: {bot_name}"
                    
                    self.results['telegram'] = {
                        'status': 'OK', 
                        'message': message,
                        'bot_name': bot_name,
                        'username': username
                    }
                    return True
            
            self.results['telegram'] = {'status': 'ERROR', 'message': f'HTTP {response.status_code}'}
            return False
            
        except Exception as e:
            self.results['telegram'] = {'status': 'ERROR', 'message': str(e)}
            return False
    
    def get_financial_summary(self):
        """Отримати фінансовий підсумок балансів"""
        financial_info = []
        
        # Zadarma баланс
        if 'zadarma' in self.results and self.results['zadarma']['status'] == 'OK':
            zadarma_data = self.results['zadarma']
            if 'balance' in zadarma_data:
                balance = zadarma_data['balance']
                currency = zadarma_data.get('currency', '')
                financial_info.append(f"📞 Zadarma: {balance} {currency}")
        
        # SMS Fly баланс
        if 'sms_fly' in self.results and self.results['sms_fly']['status'] == 'OK':
            sms_data = self.results['sms_fly']
            if 'balance' in sms_data:
                balance = sms_data['balance']
                currency = sms_data.get('currency', '')
                financial_info.append(f"📱 SMS Fly: {balance} {currency}")
        
        if financial_info:
            return "💰 ФІНАНСОВИЙ СТАТУС:\n" + "\n".join(f"   {info}" for info in financial_info)
        
        return ""
    
    def run_all_tests(self, send_notifications=True):
        """Запуск всіх тестів API з сповіщеннями"""
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
        
        # Відправити Telegram сповіщення
        if send_notifications and self.notifier:
            try:
                notifications = self.notifier.process_api_results(self.results)
                if notifications:
                    logger.info(f"📱 Відправлено Telegram сповіщення: {', '.join(notifications)}")
            except Exception as e:
                logger.error(f"❌ Помилка Telegram сповіщень: {e}")
        
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
    
    # Додаємо фінансовий підсумок
    financial_summary = monitor.get_financial_summary()
    if financial_summary:
        print(financial_summary)
        print("=" * 50)
    
    print(monitor.get_summary())
    print("=" * 50)
    
    # Повертаємо код виходу
    error_count = sum(1 for r in results.values() if r['status'] == 'ERROR')
    return min(error_count, 10)

if __name__ == "__main__":
    exit(main())