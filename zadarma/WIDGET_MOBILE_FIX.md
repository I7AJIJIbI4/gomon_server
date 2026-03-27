# Виправлення мобільного віджета - 27.03.2026

## Проблеми, що були виправлені:

### 1. Неклікабельні посилання на додаток
**Проблема:** AI асистент на сайті не згадував мобільний додаток (PWA) взагалі

**Виправлення:**
- Додано розділ "Мобільний додаток клініки" в system_prompt.txt
- AI тепер знає про додаток за адресою https://www.gomonclinic.com.ua/app/
- AI буде рекомендувати додаток у відповідних ситуаціях:
  - Коли клієнт питає про записи/історію візитів
  - Коли клієнт хоче push-сповіщення
  - Постійним клієнтам для зручності

**Приклад відповіді AI:**
"Ви можете переглянути свою історію візитів та майбутні записи в нашому [мобільному додатку](https://www.gomonclinic.com.ua/app/) — там також є зручні нагадування про процедури"

### 2. Покращені touch targets для мобільних пристроїв
**Проблема:** Посилання були малими і важко натискалися на Android

**Виправлення в gomon-widget.js (CSS для .gw-bubble-ai a):**
```css
display: inline-block;           /* Робить посилання блоковим елементом */
padding: 2px 0;                  /* Додає вертикальний відступ */
min-height: 44px;                /* Apple HIG рекомендація для touch targets */
line-height: 1.8;                /* Більша висота рядка для легшого натискання */
touch-action: manipulation;      /* Оптимізує touch взаємодію */
-webkit-tap-highlight-color: rgba(212, 176, 122, 0.2);  /* Підсвічування при натисканні */
```

**Також додано:**
- `:active` стан для кращого feedback при натисканні (колір #c9a76a)

### 3. Картка процедури з кнопкою запису
**Статус:** Вже реалізовано і працює!

Віджет вже має повний функціонал procedure card з:
- Назвою процедури
- Кнопкою копіювання назви
- Кнопкою "Написати лікарю в Instagram" з прямим посиланням

AI буде показувати цю картку коли:
- Клієнт хоче записатись
- Процедура зрозуміла з контексту або історії
- Використовується тег `<PROCEDURE>Назва процедури</PROCEDURE>`

## Файли, що були змінені:

1. `/home/gomoncli/public_html/app/system_prompt.txt`
   - Додано розділ про мобільний додаток
   - Backup: `system_prompt.txt.backup_20260327_*`

2. `/home/gomoncli/public_html/gomon-widget.js`
   - Покращено CSS для посилань (мобільні touch targets)
   - Backup: `gomon-widget.js.backup_20260327_*`

## Що тестувати на Android:

1. **Відкрийте сайт gomonclinic.com.ua на Android**

2. **Запитайте AI про записи або історію візитів**
   - AI повинен запропонувати мобільний додаток
   - Посилання має бути підкреслене і клікабельне

3. **Перевірте клікабельність посилань:**
   - Натисніть на посилання пальцем
   - Має бути видно підсвічування при натисканні
   - Посилання має відкриватися в новій вкладці

4. **Запитайте про конкретну процедуру та попросіть записати:**
   - AI повинен показати procedure card
   - Картка має містити кнопку "Написати лікарю в Instagram"
   - Кнопка має відкривати Instagram Direct

## Технічні деталі:

**Мінімальний touch target:** 44px (Apple HIG / Google Material Design рекомендація)

**Touch optimization:**
- `touch-action: manipulation` - швидша відповідь на дотик (без затримки 300ms)
- Tap highlight - візуальний feedback на Android

**Модель AI:** Sonnet 4.6 (змінено раніше для кращих відповідей)

## Що далі:

Після тестування на реальному Android пристрої:
- Якщо посилання ще не клікаються - перевірити чи немає JavaScript overlay поверх тексту
- Якщо AI не згадує додаток - можливо потрібно очистити кеш сесії
- Якщо procedure card не з'являється - перевірити чи AI генерує тег `<PROCEDURE>`

## Резервні копії:

Всі оригінальні файли збережено з timestamp:
```bash
ls -la /home/gomoncli/public_html/app/system_prompt.txt.backup_*
ls -la /home/gomoncli/public_html/gomon-widget.js.backup_*
```

Для відкату змін:
```bash
# System prompt
cp /home/gomoncli/public_html/app/system_prompt.txt.backup_TIMESTAMP /home/gomoncli/public_html/app/system_prompt.txt

# Widget
cp /home/gomoncli/public_html/gomon-widget.js.backup_TIMESTAMP /home/gomoncli/public_html/gomon-widget.js
```
