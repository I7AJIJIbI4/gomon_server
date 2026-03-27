# Покращення мобільного віджета та PWA - Завершено 27.03.2026

## Виконані зміни:

### 1. ✅ Виправлено рендеринг жирного тексту (**текст**)

**Проблема:** Markdown **текст** не перетворювався на жирний в повідомленнях асистента

**Рішення:**
- Змінено regex з `/\*\*(.+?)\*\*/g` на `/\*\*([\s\S]+?)\*\*/g`
- `[\s\S]` захоплює будь-які символи включно з переносами рядків
- Змінено `<b>` на `<strong>` для семантично правильного HTML

**Файл:** `gomon-widget.js` (рядок 433)

**До:**
```javascript
.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
```

**Після:**
```javascript
.replace(/\*\*([\s\S]+?)\*\*/g, '<strong>$1</strong>')
```

---

### 2. ✅ Зроблено модалку фулскрін без скролу сайту

**Проблема:** 
- На десктопі модалка була малою (700px) з великими відступами
- Сайт під модалкою був видимим і міг скролитися

**Рішення:**

**A. Збільшено модалку:**
- Висота: `86vh` → `96vh` (майже весь екран)
- Ширина: `max-width: 900px` → `1000px`
- Padding overlay: `24px 20px` → `12px` (менші відступи)
- Background: `rgba(11,10,8,0.72)` → `0.85` (більш темний)

**B. На мобільних (100% екрану):**
- Висота: `91dvh` → `100vh`
- Padding: `0`
- Border-radius: `0` (без закруглень)
- `align-items: stretch` (розтягнути на весь екран)

**C. Заборона скролу:**
- Код вже був реалізований у функціях `openModal()` та `closeModal()`
- `document.body.style.overflow = 'hidden'` при відкритті
- `document.body.style.overflow = ''` при закритті

**Файл:** `gomon-widget.js` (рядки 30-79, 605, 613)

---

### 3. ✅ Покращено touch targets для мобільних посилань

**Проблема:** Посилання важко натискати на Android (малий target)

**Рішення:** Додано CSS для `.gw-bubble-ai a`:
```css
display: inline-block;
padding: 2px 0;
min-height: 44px;                    /* Apple HIG стандарт */
line-height: 1.8;
touch-action: manipulation;           /* Оптимізація touch */
-webkit-tap-highlight-color: rgba(212, 176, 122, 0.2);  /* Підсвічування */
```

Також додано `:active` стан для feedback при натисканні.

**Файл:** `gomon-widget.js` (рядки 150-163)

---

### 4. ✅ Додано інформацію про PWA додаток в system prompt

**Проблема:** AI не знав про існування мобільного додатку

**Рішення:** Додано розділ "Мобільний додаток клініки" в system prompt з:
- URL додатку: https://www.gomonclinic.com.ua/app/
- Коли рекомендувати (записи, історія, push-сповіщення)
- Як згадувати (markdown формат посилань)
- Приклади використання

**Файл:** `/home/gomoncli/public_html/app/system_prompt.txt` (рядки 171-190)

**Приклад:**
> "Ви можете переглянути свою історію візитів та майбутні записи в нашому [мобільному додатку](https://www.gomonclinic.com.ua/app/)"

---

### 5. ✅ Замінено емоджі копіювання на золотисту SVG іконку

**Проблема:** В PWA додатку використовувалась емоджі 📋 замість гарної іконки

**Рішення:**

**A. Замінено кнопку копіювання:**
```html
<!-- Було -->
<button class="gc-copy-btn" title="Скопіювати назву">📋</button>

<!-- Стало -->
<button class="gc-copy-btn" title="Скопіювати назву">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" 
       stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
    <rect x="9" y="9" width="13" height="13" rx="2"/>
    <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
  </svg>
</button>
```

**B. Оновлено JavaScript логіку:**
- Створено константи `copySvg` та `checkSvg`
- Замінено `textContent` на `innerHTML` для SVG
- Success стан: ✅ → зелена галочка SVG

**Файл:** `/home/gomoncli/public_html/app/gomon-chat.js` (рядки 564, 594-603)

**Іконки тепер однакові в:**
- ✅ Віджеті на сайті (gomon-widget.js)
- ✅ PWA додатку (gomon-chat.js)

**SVG використовує `stroke="currentColor"`** - колір визначається CSS класу `.gc-copy-btn` 
Золотистий колір: `#d4b07a` (як Instagram і Telegram кнопки)

---

## Резюме змін по файлах:

### 📄 `/home/gomoncli/public_html/gomon-widget.js`
1. ✅ Виправлено bold markdown rendering
2. ✅ Модалка 96vh (desktop) / 100vh (mobile)
3. ✅ Touch targets 44px для посилань
4. ✅ Заборона скролу body (вже було)

### 📄 `/home/gomoncli/public_html/app/gomon-chat.js`
1. ✅ Емоджі 📋 → золотиста SVG іконка копіювання
2. ✅ Емоджі ✅ → зелена SVG галочка success

### 📄 `/home/gomoncli/public_html/app/system_prompt.txt`
1. ✅ Додано розділ про PWA додаток
2. ✅ Інструкції коли і як рекомендувати

---

## Резервні копії:

Всі оригінальні файли збережено:
```bash
/home/gomoncli/public_html/gomon-widget.js.backup_20260327_*
/home/gomoncli/public_html/app/gomon-chat.js.backup_20260327_*
/home/gomoncli/public_html/app/system_prompt.txt.backup_20260327_*
```

Для відкату:
```bash
# Widget
cp /home/gomoncli/public_html/gomon-widget.js.backup_TIMESTAMP /home/gomoncli/public_html/gomon-widget.js

# PWA chat
cp /home/gomoncli/public_html/app/gomon-chat.js.backup_TIMESTAMP /home/gomoncli/public_html/app/gomon-chat.js

# System prompt
cp /home/gomoncli/public_html/app/system_prompt.txt.backup_TIMESTAMP /home/gomoncli/public_html/app/system_prompt.txt
```

---

## Що тестувати:

### На Android/iOS:
1. **Відкрити сайт gomonclinic.com.ua**
   - Перевірити що віджет відкривається на весь екран
   - Сайт за модалкою не скролиться
   - Посилання на додаток клікабельні

2. **Запитати AI про записи/історію**
   - AI повинен запропонувати мобільний додаток
   - Посилання має відкриватися в новій вкладці

3. **Запитати про процедуру та попросіть записатися**
   - З'явиться procedure card
   - Іконка копіювання золотиста (SVG замість емоджі)
   - При натисканні змінюється на зелену галочку

4. **Відкрити PWA додаток** (https://www.gomonclinic.com.ua/app/)
   - Іконка копіювання тепер SVG (золотиста)
   - При копіюванні з'являється зелена галочка
   - Стиль однаковий з віджетом

5. **Перевірити жирний текст**
   - AI може використовувати **жирний текст** в відповідях
   - Має відображатися bold font

---

## Технічні деталі:

**Мінімальний touch target:** 44px (Apple HIG / Material Design)

**Touch optimization:**
- `touch-action: manipulation` - швидша відповідь без 300ms delay
- Tap highlight - візуальний feedback на Android

**SVG currentColor:**
- Іконки успадковують колір від батьківського CSS
- Золотистий: `#d4b07a`
- Success green: `#6fcf97`

**Fullscreen modal:**
- Desktop: 96vh (4vh margin for safety)
- Mobile: 100vh (справжній fullscreen)
- Body overflow hidden при відкритті

---

## Статус: ✅ Всі зміни застосовано і готові до тестування

Всі файли оновлено на сервері. Зміни вступають в силу відразу (можливо потрібно оновити кеш браузера Ctrl+F5).

---

## 🔄 Оновлення Service Worker кешу

**Оновлено:** 27.03.2026

### Зміни в `/home/gomoncli/public_html/app/sw.js`:

```javascript
// Було:
const CACHE = "gomon-2026-03-26e";

// Стало:
const CACHE = "gomon-2026-03-27";
```

### Що це означає:

**Service Worker кешує такі файли:**
- `/app/index.html`
- `/app/gomon-chat.js` ⭐ (змінений сьогодні)
- `/promos.php`
- `/app/manifest.json`
- Google Fonts

**Як працює оновлення:**

1. При наступному відвідуванні PWA додатку:
   - Браузер виявить новий `sw.js`
   - Запустить новий Service Worker
   - Видалить старий кеш `gomon-2026-03-26e`
   - Створить новий кеш `gomon-2026-03-27`
   - Завантажить свіжі версії всіх файлів

2. Користувачі автоматично отримають:
   - ✅ Нову золотисту SVG іконку копіювання
   - ✅ Виправлену логіку з checkmark SVG

3. **Не потрібно нічого робити вручну** - оновлення відбудеться автоматично при наступному візиті

### Для віджета на сайті (gomon-widget.js):

❌ **Service Worker не використовується** для основного сайту
✅ Браузерний кеш оновиться автоматично згідно HTTP headers
✅ Можна примусово оновити через Ctrl+F5 / Cmd+Shift+R

---

## 📦 Резервні копії (оновлено):

```bash
/home/gomoncli/public_html/gomon-widget.js.backup_20260327_*
/home/gomoncli/public_html/app/gomon-chat.js.backup_20260327_*
/home/gomoncli/public_html/app/system_prompt.txt.backup_20260327_*
/home/gomoncli/public_html/app/sw.js.backup_20260327_*  # NEW
```

---

## ✅ Фінальний чеклист:

- [x] Виправлено bold text rendering (widget)
- [x] Модалка fullscreen (desktop 96vh / mobile 100vh)
- [x] Покращено touch targets для посилань (44px)
- [x] Додано інформацію про PWA в system prompt
- [x] Замінено емоджі на SVG іконки в PWA
- [x] **Оновлено Service Worker cache version**

## 🚀 Готово до використання!

Всі зміни застосовано. PWA додаток автоматично оновиться при наступному відвідуванні користувачами.
