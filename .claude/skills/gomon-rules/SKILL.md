---
name: gomon-rules
description: Поведінкові правила розробки для проєкту GomonClinic (gomon_server). Завантажуй на старті будь-якої сесії з gomon-кодом — кожне правило стосується конкретного класу багів які ми вже виправляли і не хочемо повторювати.
---

# Поведінкові правила розробки GomonClinic

Кожне правило виведено з попередньої сесії де ми вже спіткнулись на цьому. Не чекай нагадування — застосовуй проактивно.

## Auto-push: Mac ↔ сервер ↔ GitHub завжди в синку

Цей проєкт переопрацьовує універсальне правило «Never push without explicit per-action approval» з `~/.claude/CLAUDE.md`. Для `gomon_server` push робиться **без окремого підтвердження**: одразу після коміту (Mac або сервер) виконуй `git push origin main` і потім `git reset --hard origin/main` на сервері якщо коміт стартував з Mac. Мета — не накопичувати локальних дельт між трьома місцями.

**Why:** У сесії 2026-06-07 локальний коміт на сервері існував паралельно з різними станами Mac/GitHub. Коли потім запустили `git reset --hard origin/main` на сервері — він тихо знищив live-зміну `system_prompt.txt` яку я задеплоїв через `cat >`. Уникнути цього класу багів простіше за все правилом «push одразу після commit, sync server одразу після push».

**How to apply:**
- Звичайний commit + push — виконуй без `AskUserQuestion`
- Після `git push` з Mac — одразу `ssh ... 'git fetch && git reset --hard origin/main'` на сервері
- Універсальне правило про підтвердження ВСЕ ОДНО діє для:
  - `git push --force` / `--force-with-lease`
  - `git push` у не-`main` гілку чи на інший remote
  - Видалення гілок, тегів, релізів
  - Будь-що що міняє історію (rebase --root, push після interactive rebase)
- Якщо ризик невизначений — все-таки запитай.

## Push/TG/SMS — три незалежні канали

Push, TG і SMS — три повністю незалежні канали повідомлень. Push success НІКОЛИ не привід пропустити TG або SMS.

**Why:** Юзер прямо сказав «смс не скіпаєм, додаток і пуші ніяк не впливають на повідомлення в месенджерах і смс». Попередня версія коду пропускала SMS коли push успішний — це було неправильно.

**How to apply:** У `notify_client()`: завжди пробуй TG якщо `tg_id` існує, завжди fallback на SMS якщо TG fail/unavailable. Push — fire-and-forget паралельно з TG/SMS.

## CSS специфічність — `>tag` селектори перебивають класи дитини

Коли додаєш стилізований `<p>` з класом усередині `.auth-logo`, parent rule `.auth-logo>p` (specificity 0,1,1) перебиває `.auth-quote` (0,1,0). Треба `.auth-logo>p.auth-quote` щоб виграти.

**Why:** `.auth-logo>p` ставить `text-transform:uppercase`, `font-size:11px`, `color:var(--text3)` для лейбла «Черкаси» — це мовчки знищує будь-який `<p>` дитину з нижчою специфічністю класу.

**How to apply:** Коли додаєш стилізовані елементи всередину parent з `>tag` селекторами, завжди комбінуй parent+class: `.parent>tag.exception-class { ... }`.

## Auth-екран: layout через `margin:auto`

Auth-екран (`#screen-auth`) має 3 логічних блоки: logo group (верх), card (центр), bottom group (tg+ai).

**Робочий патерн:**
- `justify-content: flex-start` на контейнері
- `.auth-card { margin: auto 0 }` — займає рівний простір зверху і знизу
- `.auth-bottom { margin-top: auto }` — притискає до низу
- Усі не-card блоки: `flex-shrink: 0`

**Why:** `space-between` з 4+ items створює нерівномірні gaps. `margin:auto` на flex children розподіляє залишковий простір рівномірно.

**How to apply:** Коли розподіляєш вертикальний простір у flex column, віддавай перевагу `margin:auto` на «центральному» елементі замість `justify-content:space-between`.

## SW cache bump на кожному frontend deploy

Кожна зміна `index.html` / `gomon-chat.js` / `gomon-widget.js` ОБОВ'ЯЗКОВО має бампити версію `CACHE` у `sw.js`, інакше браузер показує stale контент.

Формат: `gomon-YYYY-MM-DDx` де `x` — літера a-z. Обидва файли деплояться разом.

**Why:** SW кешує `index.html` — без cache bump activate event ніколи не fired і старий HTML лишається в кеші назавжди.

**How to apply:** Після БУДЬ-якої зміни `index.html`, `gomon-chat.js` чи `gomon-widget.js` — інкрементуй літеру в `CACHE` константі `sw.js` перед deploy. Якщо змінювався тільки JS — також додай `?v=YYYYMMDDx` у тег `<script src>`.

## Calendar click debug — try/catch структура в PTR IIFE

Коли клики по записах у календарі перестають працювати — перевір структуру `try { if/else if chain } catch` у `doRefresh()` всередині PTR IIFE.

**Root cause приклад:** Admin `else if` блоки були вставлені ПІСЛЯ closing `}` if-chain клієнта, але ПЕРЕД `catch`, ламаючи `try { ... } catch`. Це викликало `SyntaxError: Missing catch or finally after try` що вбивало ВСЬОГО JS нижче, включно з `_fmtDateStr` що використовувся в `openApptAction`.

**Why:** `doRefresh()` всередині PTR IIFE внизу файлу. Функції визначені після нього (як `_fmtDateStr`) у global scope і залежать від парсингу IIFE. Syntax error в IIFE заважає parser дійти до тих function declarations.

**How to apply:** Перед deploy будь-яких змін у `doRefresh()` (рядки ~5230-5295) перевіряй у browser console на SyntaxErrors.

**Related guard:** Phone display regex `/^38/` → `/^380/` (інакше `380...` стає `00...` замість `0...`). Calendar `onclick` — завжди передавай ID як string: `openApptAction('id')` зі `String(x.id) === String(id)` (manual IDs числові, WLaunch — string).

## Валідація нових input-ів на етапі кодування

При додаванні нових phone numbers, PINs чи інших ідентифікаторів у config — ЗАВЖДИ перевіряй що вони проходять існуючу frontend і backend валідацію ПЕРЕД deploy.

**Why:** Superadmin phone `03751840375` (11 цифр) був відхилений PWA auth input який мав max-length чи format validation для UA phones (10 цифр з 0, чи 12 цифр з 380). Фічу задеплоїли — не працювала бо телефон не можна було ввести у форму логіну.

**How to apply:** Перед додаванням нового phone/credential:
1. Перевір `formatPhone()` / `sendOtp()` JS validation в `index.html`
2. Перевір `norm_phone()` Python validation в `pwa_api.py`
3. Перевір input field constraints (`maxlength`, `pattern`, `type`)
4. Перевір весь auth flow вручну перед «готово».

## Заборона слова «клініка» в клієнтських текстах

Ніколи не використовувати слово «клініка» в текстах для клієнтів.

**Why:** Це косметологічний простір, не клініка. Юзер прямо попросив замінити скрізь.

**How to apply:** У `system_prompt.txt`, відповідях бота, chat context — замість «клініка Dr. Gomon» писати «Dr. Gomon Cosmetology», «простір Dr. Gomon», «студія», або просто «ми»/«у нас». Правило прописане у `system_prompt.txt` рядок 8. Перевіряти `grep -i "клінік"` перед deploy.

## Crontab: змінні середовища — ТІЛЬКИ вгорі файлу

При будь-якій зміні crontab (`crontab -e` або `crontab <file>`) — змінні `APP=`, `VENV=`, `PATH=` та інші **мають стояти вище ВСІХ job-рядків** у файлі.

**Why:** 16 червня 2026, коміт `dac30dd` додав рядок `anthropic_health` у crontab. Під час редагування змінні `APP=`, `VENV=`, `PATH=` опинились внизу, після всіх job-рядків. У Vixie cron (Ubuntu) змінні, визначені після job-рядків, не застосовуються до них. Всі команди що містили `$APP`/`$VENV` отримували порожній рядок — `cd $APP` переходив у `/root/`, `$VENV script.py` ставав просто `script.py` і Shell видавав `not found`. Збій тривав 6 днів: не було sync з WLaunch, TG/SMS/push нагадувань клієнтам, брифінгів спеціалістам, нарахування кешбеку, Drive папок.

**How to apply:**
- Перед будь-яким редагуванням crontab: `crontab -l | head -5` — перевір що перші рядки — це `APP=`, `VENV=`, `PATH=`
- Після редагування: `crontab -l | grep -n "^APP=\|^VENV=\|^PATH="` — номери рядків мають бути < 10 і < першого job-рядка
- Якщо вони внизу — виправити: `crontab -l | grep -E "^(APP|PATH|VENV)=" > /tmp/vars.txt && crontab -l | grep -v "^APP=\|^PATH=\|^VENV=" > /tmp/jobs.txt && cat /tmp/vars.txt /tmp/jobs.txt | crontab -`
- Для нового job — додавати тільки новий рядок у потрібне місце, не перетасовувати існуючі блоки

## Instagram OAuth — правильна конфігурація

При проблемах з Instagram авторизацією або після закінчення токену — перевіряй ці параметри.

**Правильний стек (станом на 22.06.2026):**
- `IG_APP_ID = '847955297878760'` — Instagram App ID (НЕ Facebook App ID `1138101513882406`)
- `IG_APP_SECRET = '21203d69a19930315c00b8681d2036bd'` — секрет Instagram App
- OAuth URL: `https://www.instagram.com/oauth/authorize` (Business Login, НЕ `api.instagram.com`)
- `IG_REDIRECT_URI = 'https://drgomon.beauty/messenger/'`

**Де зареєстрований redirect URI:** Meta Console → app `gomonclinic.com` (ID: 1138101513882406) → Сценарії використання → Manage messaging & content on Instagram → Step 4 "Set up Instagram business login" → кнопка "Business login settings".

**Why:** Є два окремих App ID: Facebook App `1138101513882406` і Instagram App `847955297878760` (підпродукт). OAuth через `www.instagram.com` використовує Instagram App ID. `api.instagram.com` — для застарілого Basic Display API (не наш випадок). Redirect URI реєструється в Instagram Business Login settings, НЕ в "Facebook Login for Business" Valid OAuth Redirect URIs.

**Найшвидший спосіб оновити токен (~кожні 60 днів):**
Meta Console → Сценарії використання → Manage messaging & content on Instagram → Step 2 "Generate access tokens" → dr.gomon → "Generate token" → скопіювати → записати в `/opt/gomon/app/private_data/ig_token.txt`.

**How to apply:** Якщо Instagram AI перестав відповідати або лог показує 401 → перевір дату генерації токену (токен живе ~60 днів). Виконай renewal через Meta Console, не через OAuth flow у браузері.

## Carousel реалізація — `children[1]` як активний

Site deals carousel у `sitepro/a188dd94d37a0374c81c636d09cd1f05.php` використовує DOM rotation + translateX.

**Робочий підхід:**
- Active tile = `children[1]` (другий у DOM), `children[0]` завжди прихований ліворуч
- Base position: `translateX(-step)` — ховає перший child
- `slideNext`: анімує до `-2*step`, потім rotate first→end, reset до `-step`
- `slidePrev`: анімує до `0` (ліва tile з'їжджає в), потім rotate last→front, reset до `-step`
- Обидва напрямки симетричні — завжди 1 tile видима з кожного боку

**Why:** Простий `overflow: hidden` + DOM rotation ламає backward slide бо tile яку треба показати, не існує у visible area. `children[0]` завжди ліворуч вирішує це.

**How to apply:** Ніколи не використовуй `void offsetWidth` + immediate transition для backward slide — нестабільно. Тримай buffer tile завжди present на лівому боці.

**Dots navigation:** `goTo` обирає найкоротший напрямок (forward vs backward), instant-rotates n-1 tiles, анімує останній крок.
