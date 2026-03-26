#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
telegram_notifier.py - Покращений Telegram сповіщувач з інформацією про баланси
"""

import requests
import json
import logging
import os
from datetime import datetime
from config import TELEGRAM_TOKEN, ADMIN_USER_ID

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.token = TELEGRAM_TOKEN
        self.admin_id = ADMIN_USER_ID
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        # Використовуємо відносний шлях
        self.state_file = "api_states.json"
    
    def send_message(self, message, parse_mode="HTML"):
        """Відправити повідомлення адміністратору"""
        try:
            url = f"{self.api_url}/sendMessage"
            data = {
                'chat_id': self.admin_id,
                'text': message,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, json=data, timeout=10)
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Помилка відправки Telegram: {e}")
            return False
    
    def load_previous_states(self):
        """Завантажити попередні стани API"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    return json.load(f)
        except:
            pass
        return {}
    
    def save_states(self, states):
        """Зберегти поточні стани API"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(states, f)
        except Exception as e:
            logger.error(f"Помилка збереження станів: {e}")
    
    def notify_critical_error(self, api_name, error_message):
        """Критична помилка API"""
        message = f"""
🚨 <b>КРИТИЧНА ПОМИЛКА API</b>

📡 <b>API:</b> {api_name.upper()}
❌ <b>Помилка:</b> {error_message}
🕐 <b>Час:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

⚡ <b>Потрібна негайна увага!</b>
        """
        return self.send_message(message.strip())
    
    def notify_api_recovery(self, api_name):
        """API відновлено"""
        message = f"""
✅ <b>API ВІДНОВЛЕНО</b>

📡 <b>API:</b> {api_name.upper()}
🕐 <b>Час:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

😊 Все працює нормально!
        """
        return self.send_message(message.strip())
    
    def notify_regular_error(self, api_name, error_message):
        """Звичайна помилка API"""
        message = f"""
⚠️ <b>Помилка API</b>

📡 <b>API:</b> {api_name.upper()}
❌ <b>Помилка:</b> {error_message}
🕐 <b>Час:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        return self.send_message(message.strip())
    
    def send_daily_summary(self, results):
        """Покращений щоденний звіт з балансами"""
        ok_count = sum(1 for r in results.values() if r['status'] == 'OK')
        total = len(results)
        
        status_emoji = "✅" if ok_count == total else "⚠️" if ok_count >= total//2 else "❌"
        
        message = f"""
📊 <b>ЩОДЕННИЙ ЗВІТ API</b>

{status_emoji} <b>Загальний статус:</b> {ok_count}/{total} API працюють

<b>📡 Детально по API:</b>
"""
        
        # Спочатку показуємо всі API
        for api_name, result in results.items():
            emoji = "✅" if result['status'] == 'OK' else "❌" if result['status'] == 'ERROR' else "⚙️"
            message += f"{emoji} <b>{api_name.upper()}:</b> {result['message']}\n"
        
        # Додаємо фінансову секцію
        financial_info = []
        
        # Zadarma баланс
        if 'zadarma' in results and results['zadarma']['status'] == 'OK':
            zadarma_data = results['zadarma']
            if 'balance' in zadarma_data:
                balance = zadarma_data['balance']
                currency = zadarma_data.get('currency', '')
                
                # Додаємо попередження для низького балансу
                try:
                    balance_float = float(balance)
                    if balance_float < 50:
                        warning = " ⚠️ <i>Низький баланс!</i>"
                    else:
                        warning = ""
                except:
                    warning = ""
                
                financial_info.append(f"📞 <b>Zadarma:</b> {balance} {currency}{warning}")
        
        # SMS Fly баланс
        if 'sms_fly' in results and results['sms_fly']['status'] == 'OK':
            sms_data = results['sms_fly']
            if 'balance' in sms_data:
                balance = sms_data['balance']
                currency = sms_data.get('currency', '')
                
                # Додаємо попередження для низького балансу
                try:
                    balance_float = float(balance)
                    if balance_float < 10:
                        warning = " ⚠️ <i>Критично низький!</i>"
                    elif balance_float < 50:
                        warning = " ⚠️ <i>Низький баланс!</i>"
                    else:
                        warning = ""
                except:
                    warning = ""
                
                financial_info.append(f"📱 <b>SMS Fly:</b> {balance} {currency}{warning}")
        
        # Додаємо фінансову інформацію якщо є
        if financial_info:
            message += f"\n💰 <b>БАЛАНСИ:</b>\n"
            for info in financial_info:
                message += f"{info}\n"
        
        # Додаємо додаткову інформацію
        message += f"\n🕐 <b>Час звіту:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Додаємо рекомендації якщо є проблеми
        if ok_count < total:
            message += f"\n\n💡 <b>Рекомендації:</b> Перевірте проблемні API та поповніть баланси при необхідності."
        
        return self.send_message(message.strip())
    
    def notify_low_balance(self, api_name, balance, currency, threshold=50):
        """Сповіщення про низький баланс"""
        message = f"""
⚠️ <b>ПОПЕРЕДЖЕННЯ: НИЗЬКИЙ БАЛАНС</b>

💰 <b>API:</b> {api_name.upper()}
💳 <b>Поточний баланс:</b> {balance} {currency}
📉 <b>Поріг:</b> {threshold} {currency}
🕐 <b>Час:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

💡 <b>Рекомендація:</b> Поповніть баланс для безперебійної роботи сервісу.
        """
        return self.send_message(message.strip())
    
    def process_api_results(self, current_results):
        """Обробити результати API та відправити сповіщення"""
        previous_states = self.load_previous_states()
        notifications_sent = []
        
        critical_apis = ['zadarma', 'telegram']
        
        for api_name, result in current_results.items():
            current_status = result['status']
            previous_status = previous_states.get(api_name, 'UNKNOWN')
            
            # Сповіщення про нові помилки
            if current_status == 'ERROR' and previous_status != 'ERROR':
                if api_name in critical_apis:
                    self.notify_critical_error(api_name, result['message'])
                    notifications_sent.append(f"CRITICAL: {api_name}")
                else:
                    self.notify_regular_error(api_name, result['message'])
                    notifications_sent.append(f"ERROR: {api_name}")
            
            # Сповіщення про відновлення
            elif current_status == 'OK' and previous_status == 'ERROR':
                self.notify_api_recovery(api_name)
                notifications_sent.append(f"RECOVERY: {api_name}")
            
            # Перевірка низьких балансів (тільки якщо API працює)
            elif current_status == 'OK' and 'balance' in result:
                try:
                    balance = float(result['balance'])
                    currency = result.get('currency', '')
                    
                    # Різні пороги для різних API
                    thresholds = {
                        'zadarma': 50,    # UAH
                        'sms_fly': 10     # грн
                    }
                    
                    threshold = thresholds.get(api_name, 50)
                    
                    # Перевіряємо чи баланс став низьким
                    previous_balance = previous_states.get(f"{api_name}_balance", float('inf'))
                    
                    if balance < threshold and previous_balance >= threshold:
                        self.notify_low_balance(api_name, balance, currency, threshold)
                        notifications_sent.append(f"LOW_BALANCE: {api_name}")
                    
                    # Зберігаємо поточний баланс для майбутніх перевірок
                    previous_states[f"{api_name}_balance"] = balance
                    
                except (ValueError, TypeError):
                    pass  # Ігноруємо якщо баланс не число
        
        # Зберегти поточні стани (включаючи баланси)
        current_states = {api: result['status'] for api, result in current_results.items()}
        current_states.update({k: v for k, v in previous_states.items() if k.endswith('_balance')})
        self.save_states(current_states)
        
        return notifications_sent

def test_notifier():
    """Тест сповіщувача з демонстрацією нових можливостей"""
    notifier = TelegramNotifier()
    
    # Тестові дані з балансами
    test_results = {
        'zadarma': {'status': 'OK', 'message': 'Баланс: 85.94 UAH', 'balance': '85.94', 'currency': 'UAH'},
        'sms_fly': {'status': 'OK', 'message': 'Баланс: 15.5 грн', 'balance': '15.5', 'currency': 'грн'},
        'wlaunch': {'status': 'OK', 'message': 'Філій: 1 (1 активних)'},
        'telegram': {'status': 'OK', 'message': 'Бот: DrGomonConcierge (@your_bot)'}
    }
    
    success = notifier.send_daily_summary(test_results)
    return success

if __name__ == "__main__":
    print("🧪 Тестування покращеного Telegram сповіщувача...")
    success = test_notifier()
    print("✅ Успішно відправлено!" if success else "❌ Помилка відправки!")