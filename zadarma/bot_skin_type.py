#!/usr/bin/env python3
"""Skin Type Quiz Bot (Bauman classification) — PTB v21, async."""
import os, sys, json, sqlite3, logging, logging.handlers, signal, atexit
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes,
)

# ── Config ──────────────────────────────────────────────────────────────────
from config import TG_SKINTYPE_TOKEN

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'users.db')
PID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skin_type_bot.pid')
LOG_PATH = '/var/log/gomon/skin_type_bot.log'

logger = logging.getLogger('skin_type_bot')
logger.setLevel(logging.INFO)
_handler = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logger.addHandler(_handler)

# ── PID ─────────────────────────────────────────────────────────────────────
def _create_pid():
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))
    atexit.register(lambda: os.path.exists(PID_FILE) and os.remove(PID_FILE))

# ── DB ──────────────────────────────────────────────────────────────────────
def _db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def _init_db():
    conn = _db()
    conn.execute("""CREATE TABLE IF NOT EXISTS skin_quiz_state (
        telegram_id INTEGER PRIMARY KEY,
        state_json TEXT NOT NULL,
        updated_at TEXT DEFAULT (datetime('now'))
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS skin_quiz_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL,
        username TEXT,
        first_name TEXT,
        skin_type TEXT NOT NULL,
        section_scores TEXT,
        completed_at TEXT DEFAULT (datetime('now'))
    )""")
    # Cleanup stale sessions (>24h)
    conn.execute("DELETE FROM skin_quiz_state WHERE updated_at < datetime('now', '-1 day')")
    conn.commit()
    conn.close()

def _save_state(tg_id, state):
    conn = _db()
    conn.execute(
        "INSERT OR REPLACE INTO skin_quiz_state (telegram_id, state_json, updated_at) VALUES (?,?,datetime('now'))",
        (tg_id, json.dumps(state, ensure_ascii=False)))
    conn.commit()
    conn.close()

def _load_state(tg_id):
    conn = _db()
    row = conn.execute("SELECT state_json FROM skin_quiz_state WHERE telegram_id=?", (tg_id,)).fetchone()
    conn.close()
    return json.loads(row[0]) if row else None

def _clear_state(tg_id):
    conn = _db()
    conn.execute("DELETE FROM skin_quiz_state WHERE telegram_id=?", (tg_id,))
    conn.commit()
    conn.close()

def _save_result(tg_id, username, first_name, skin_type, section_scores):
    conn = _db()
    conn.execute(
        "INSERT INTO skin_quiz_results (telegram_id, username, first_name, skin_type, section_scores) VALUES (?,?,?,?,?)",
        (tg_id, username, first_name, skin_type, json.dumps(section_scores)))
    conn.commit()
    conn.close()

# ── Conversation states ─────────────────────────────────────────────────────
SECTION, QUESTION, FINALIZE = range(3)

# ── Questions (Bauman classification, 4 sections, 65 questions) ─────────────
questions = [
    {
        "section": "Жирна чи суха?",
        "description": "Ця секція оцінює продукцію шкірного сала та рівень зволоженості шкіри.",
        "questions": [
            {"number": 1, "question": "Після вмивання водою не використовуйте крем, тонік, пудру чи будь-який інший продукт. Через дві або три години погляньте в дзеркало при яскравому світлі. Ваше чоло та щоки виглядають або відчуваються:", "answers": [("А: Шершавими, що лущаться, або потрісканими", "A"), ("Б: Стягнутими", "B"), ("В: Добре зволоженими, без відбиття світла (матовими)", "C"), ("Г: Блискучими, що відбивають світло", "D")]},
            {"number": 2, "question": "На фотографіях ваше обличчя виглядає блискучим:", "answers": [("А: Ніколи, я ніколи не помічала блиску", "A"), ("Б: Іноді", "B"), ("В: Часто", "C"), ("Г: Завжди", "D")]},
            {"number": 3, "question": "Через два або три години після нанесення тональної основи, але не пудри, ваш макіяж виглядає:", "answers": [("А: Лущиться або висихає, підкреслюючи зморшки", "A"), ("Б: Рівним і гладким", "B"), ("В: Блискучим", "C"), ("Г: Розпливається і блищить", "D"), ("Д: Я не користуюся тональними основами", "E")]},
            {"number": 4, "question": "В умовах низької вологості, якщо ви не використовуєте крем, ваша шкіра на обличчі:", "answers": [("А: Відчувається дуже сухою або потрісканою", "A"), ("Б: Відчувається стягнутою", "B"), ("В: Відчувається нормальною", "C"), ("Г: Виглядає блискучою, або я ніколи не відчуваю потреби в кремі", "D"), ("Д: Не знаю", "E")]},
            {"number": 5, "question": "Погляньте в збільшувальне дзеркало. Скільки у вас великих пор, розміром з кінчик шпильки або більше?", "answers": [("А: Немає", "A"), ("Б: Кілька в Т-зоні (лоб і ніс)", "B"), ("В: Багато", "C"), ("Г: Тонни!", "D"), ("Д: Важко визначити — пори дуже дрібні або майже непомітні", "E")]},
            {"number": 6, "question": "Як би ви охарактеризували свою шкіру:", "answers": [("А: Суха", "A"), ("Б: Нормальна", "B"), ("В: Комбінована", "C"), ("Г: Жирна", "D")]},
            {"number": 7, "question": "Якщо ви використовуєте мило, що піниться і дає пишну піну, шкіра на вашому обличчі:", "answers": [("А: Відчувається сухою і потрісканою", "A"), ("Б: Відчувається трохи сухою, але не потрісканою", "B"), ("В: Відчувається нормальною", "C"), ("Г: Відчувається жирною", "D"), ("Д: Не використовую — шкіра від нього не пересихає", "E"), ("Е: Не використовую саме через те, що шкіра від нього пересихає", "A")]},
            {"number": 8, "question": "Якщо вашу шкіру на обличчі не зволожити, ви відчуваєте стягнутість:", "answers": [("А: Завжди", "A"), ("Б: Іноді", "B"), ("В: Рідко", "C"), ("Г: Ніколи", "D")]},
            {"number": 9, "question": "У вас є комедони (чорні точки та білі вугрі):", "answers": [("А: Ніколи", "A"), ("Б: Рідко", "B"), ("В: Іноді", "C"), ("Г: Завжди", "D")]},
            {"number": 10, "question": "Ваше обличчя жирне тільки в Т-зоні (лоб і ніс):", "answers": [("А: Ніколи", "A"), ("Б: Іноді", "B"), ("В: Часто", "C"), ("Г: Завжди", "D")]},
            {"number": 11, "question": "Через два або три години після застосування крему ваші щоки:", "answers": [("А: Шершаві, лущаться або потріскані", "A"), ("Б: Гладкі", "B"), ("В: Трохи блищать", "C"), ("Г: Блищать і лисніють, або я не використовую креми", "D")]},
        ]
    },
    {
        "section": "Чутлива чи стійка?",
        "description": "Ця секція вимірює тенденцію вашої шкіри до висипань, червоніння, а також свербіння.",
        "questions": [
            {"number": 12, "question": "У вас з'являються висипання на обличчі:", "answers": [("А: Ніколи", "A"), ("Б: Рідко", "B"), ("В: Як мінімум раз на місяць", "C"), ("Г: Як мінімум раз на тиждень", "D")]},
            {"number": 13, "question": "Засоби для догляду за шкірою викликають у вас червоніння, висипання, прищики або свербіння:", "answers": [("А: Ніколи", "A"), ("Б: Рідко", "B"), ("В: Часто", "C"), ("Г: Завжди", "D"), ("Д: Я не користуюсь косметикою", "E")]},
            {"number": 14, "question": "Вам коли-небудь ставили діагноз акне або розацеа?", "answers": [("А: Ні", "A"), ("Б: Знайомі помічали у мене подібне, але діагноз не ставили", "B"), ("В: Так", "C"), ("Г: Так, важка форма", "D"), ("Д: Не впевнена", "E")]},
            {"number": 15, "question": "Якщо ви носите прикраси не з 14-каратного золота, як часто від них з'являється висипання?", "answers": [("А: Ніколи", "A"), ("Б: Рідко", "B"), ("В: Часто", "C"), ("Г: Завжди", "D"), ("Д: Не впевнений", "E")]},
            {"number": 16, "question": "Сонцезахисні креми викликають у вас свербіння, печіння, висипання або червоніння:", "answers": [("А: Ніколи", "A"), ("Б: Рідко", "B"), ("В: Часто", "C"), ("Г: Завжди", "D"), ("Д: Я ніколи не користуюсь сонцезахисними засобами", "E")]},
            {"number": 17, "question": "Вам коли-небудь ставили діагноз атопічний дерматит, екзема або контактний дерматит?", "answers": [("А: Ні", "A"), ("Б: Знайомі помічали у мене подібне, але діагноз не ставили", "B"), ("В: Так", "C"), ("Г: Так, важка стадія", "D"), ("Д: Не впевнена", "E")]},
            {"number": 18, "question": "Як часто під кільцями з'являється почервоніння або висипання?", "answers": [("А: Ніколи", "A"), ("Б: Рідко", "B"), ("В: Часто", "C"), ("Г: Завжди", "D"), ("Д: Я не ношу кілець", "E")]},
            {"number": 19, "question": "Ароматизовані пінні ванни, масажні олії або лосьйони для тіла викликають у вас свербіння, висипання, червоніння або сильне відчуття сухості:", "answers": [("А: Ніколи", "A"), ("Б: Рідко", "B"), ("В: Часто", "C"), ("Г: Завжди", "D"), ("Д: Я ніколи не користуюсь такими продуктами", "E")]},
            {"number": 20, "question": "Чи можете ви користуватись милом з готелів на вашому тілі чи обличчі без будь-яких проблем?", "answers": [("А: Так", "A"), ("Б: Більшість часу у мене не виникає проблем", "B"), ("В: Ні, моя шкіра свербить, стає червоною або з'являються висипання", "C"), ("Г: Я віддаю перевагу не використовувати його, було багато проблем!", "D"), ("Д: Я беру косметику з собою, тому не впевнений(а)", "E")]},
            {"number": 21, "question": "У когось у вашій родині був діагностований атопічний дерматит, екзема, астма і/або алергія?", "answers": [("А: Ні", "A"), ("Б: Здається, один член сім'ї", "B"), ("В: Кілька членів сім'ї", "C"), ("Г: Багато членів моєї сім'ї", "D"), ("Д: Не впевнений(а)", "E")]},
            {"number": 22, "question": "Що відбувається, якщо ви користуєтеся сильно ароматизованим пральним порошком?", "answers": [("А: З моєю шкірою все добре", "A"), ("Б: Я відчуваю, що моя шкіра трохи суха", "B"), ("В: Моя шкіра свербить", "C"), ("Г: Моя шкіра свербить і з'являється висип", "D"), ("Д: Не впевнений(а), я ніколи їх не використовую", "E")]},
            {"number": 23, "question": "Як часто ваше обличчя або шия червоніють після помірного навантаження, стресу або сильних емоцій?", "answers": [("А: Ніколи", "A"), ("Б: Іноді", "B"), ("В: Часто", "C"), ("Г: Завжди", "D")]},
            {"number": 24, "question": "Як часто ви червонієте від вживання алкоголю?", "answers": [("А: Ніколи", "A"), ("Б: Іноді", "B"), ("В: Часто", "C"), ("Г: Завжди, я намагаюся не пити через цю проблему", "D"), ("Д: Я не п'ю алкоголь", "E")]},
            {"number": 25, "question": "Як часто ви червонієте від гострої або гарячої їжі чи напоїв?", "answers": [("А: Ніколи", "A"), ("Б: Іноді", "B"), ("В: Часто", "C"), ("Г: Завжди", "D"), ("Д: Я ніколи не їм гостру їжу", "E")]},
            {"number": 26, "question": "Як багато у вас видимих червоних або синіх судин чи судинних зірочок на обличчі і носі?", "answers": [("А: Немає", "A"), ("Б: Мало (1-3)", "B"), ("В: Кілька (4-6)", "C"), ("Г: Багато (7+)", "D")]},
            {"number": 27, "question": "Ваше обличчя виглядає червоним на фото:", "answers": [("А: Ніколи", "A"), ("Б: Іноді", "B"), ("В: Часто", "C"), ("Г: Завжди", "D")]},
            {"number": 28, "question": "Люди запитують, чи ви обгоріли, хоча ви не були під сонцем:", "answers": [("А: Ніколи", "A"), ("Б: Іноді", "B"), ("В: Часто", "C"), ("Г: Завжди", "D"), ("Д: Я завжди виглядаю, наче я обгорів(а) на сонці", "E")]},
            {"number": 29, "question": "У вас червоніння, свербіння або набряк від декоративної косметики, сонцезахисного крему або косметики по догляду?", "answers": [("А: Ніколи", "A"), ("Б: Іноді", "B"), ("В: Часто", "C"), ("Г: Завжди", "D"), ("Д: Я не використовую ці продукти", "E")]},
            {"number": 30, "question": "Чи вам коли-небудь ставив лікар діагноз акне, розацеа, контактний дерматит або екзема?", "answers": [("А: Так. Ставив діагноз дерматолог", "F"), ("Б: Так. Ставив діагноз терапевт", "B"), ("В: Ні", "G")]},
        ]
    },
    {
        "section": "Пігментована чи непігментована?",
        "description": "Ця секція вимірює тенденції вашої шкіри до продукування меланіну та появи пігментних плям.",
        "questions": [
            {"number": 31, "question": "Після прищика або врослого волосся залишається темнувата/темна пляма?", "answers": [("А: Ніколи", "A"), ("Б: Іноді", "B"), ("В: Часто", "C"), ("Г: Завжди", "D"), ("Д: У мене немає прищиків або врослих волосся", "E")]},
            {"number": 32, "question": "Після того як ви порізалися, як довго коричневий (не рожевий) слід залишається на шкірі?", "answers": [("А: У мене не залишається коричневого сліду", "A"), ("Б: Тиждень", "B"), ("В: Кілька тижнів", "C"), ("Г: Місяць", "D")]},
            {"number": 33, "question": "Скільки темних плям з'явилося на вашому обличчі під час вагітності, прийому оральних контрацептивів або гормональної замісної терапії?", "answers": [("А: Жодної", "A"), ("Б: Одне", "B"), ("В: Кілька", "C"), ("Г: Багато", "D"), ("Д: Питання не стосується мене", "E")]},
            {"number": 34, "question": "У вас є темні плями або точки над верхньою губою, щоках?", "answers": [("А: Ні", "A"), ("Б: Я не впевнена", "B"), ("В: Так, але ледь помітні", "C"), ("Г: Так, і дуже помітні", "D")]},
            {"number": 35, "question": "Чи темніють ваші пігментні плями, коли ви загораєте?", "answers": [("А: У мене немає пігментних плям", "A"), ("Б: Не впевнена", "B"), ("В: Трохи темніють", "C"), ("Г: Сильно темніють", "D"), ("Д: Я користуюсь сонцезахисним кремом кожен день і ніколи не загораю", "E")]},
            {"number": 36, "question": "Вам коли-небудь діагностували мелазму — плями на обличчі?", "answers": [("А: Ні", "A"), ("Б: Один раз, але я від них позбулася", "B"), ("В: Так", "C"), ("Г: Так, важка форма", "D"), ("Д: Не впевнена", "E")]},
            {"number": 37, "question": "У вас є маленькі коричневі плямки (веснянки або сонячні плями) на обличчі, грудях, спині або руках?", "answers": [("А: Ні", "A"), ("Б: Так, кілька (1-5)", "B"), ("В: Так, багато (6-15)", "C"), ("Г: Так, дуже багато (16+)", "D")]},
            {"number": 38, "question": "Якщо ви вперше за кілька місяців потрапляєте під сонце, ваша шкіра:", "answers": [("А: Тільки обгорає", "A"), ("Б: Спочатку обгорає, але потім засмагає", "B"), ("В: Засмагає", "C"), ("Г: Моя шкіра вже темна", "D")]},
            {"number": 39, "question": "Якщо ви кілька днів постійно перебуваєте під сонцем:", "answers": [("А: Я обгораю і лущуся, але шкіра не змінює кольору", "A"), ("Б: Моя шкіра стає трохи темнішою", "B"), ("В: Моя шкіра стає значно темнішою", "C"), ("Г: Моя шкіра вже темна", "D"), ("Д: Не впевнена", "E")]},
            {"number": 40, "question": "Коли ви перебуваєте під сонцем, у вас з'являються веснянки?", "answers": [("А: Ні, ніколи", "A"), ("Б: Кілька маленьких нових щороку", "B"), ("В: Часто з'являються", "C"), ("Г: Моя шкіра вже темна, не видно", "D"), ("Д: Я навмисно уникаю сонця", "E")]},
            {"number": 41, "question": "У когось з ваших батьків є веснянки?", "answers": [("А: Ні", "A"), ("Б: Кілька на обличчі", "B"), ("В: Багато на обличчі", "C"), ("Г: Багато на обличчі, грудях, шиї та плечах", "D"), ("Д: Не впевнена", "E")]},
            {"number": 42, "question": "Який ваш натуральний колір волосся?", "answers": [("А: Світле (блондинка)", "A"), ("Б: Каштанове / темно-русяве", "B"), ("В: Чорне", "C"), ("Г: Руде", "D")]},
            {"number": 43, "question": "Чи є у вас в історії життя меланома або у когось з ваших кровних родичів?", "answers": [("А: Ні", "A"), ("Б: Одна людина в родині", "B"), ("В: Більше ніж одна", "C"), ("Г: У мене була меланома", "D"), ("Д: Не впевнена", "E")]},
            {"number": 44, "question": "Чи є у вас пігментні плями на тих ділянках шкіри, які підлягають сонячному опроміненню?", "answers": [("А: Так", "F"), ("Б: Ні", "G")]},
        ]
    },
    {
        "section": "Зморшкувата чи пружна?",
        "description": "Ця секція вимірює тенденції вашої шкіри до формування зморшок.",
        "questions": [
            {"number": 45, "question": "У вас є зморшки на обличчі?", "answers": [("А: Ні, навіть коли я усміхаюся чи хмурюся", "A"), ("Б: Тільки під час мімічних рухів", "B"), ("В: Так, в русі і кілька в спокої", "C"), ("Г: Зморшки є навіть у спокої", "D")]},
            {"number": 46, "question": "Наскільки старо виглядає (виглядала) шкіра вашої матері?", "answers": [("А: На 5-10 років молодша її віку", "A"), ("Б: На свій вік", "B"), ("В: На 5 років старша", "C"), ("Г: На більше ніж 5 років старша", "D"), ("Д: Не можу відповісти", "E")]},
            {"number": 47, "question": "Наскільки старо виглядає (виглядала) шкіра вашого батька?", "answers": [("А: На 5-10 років молодша його віку", "A"), ("Б: На свій вік", "B"), ("В: На 5 років старша", "C"), ("Г: На більше ніж 5 років старша", "D"), ("Д: Не можу відповісти", "E")]},
            {"number": 48, "question": "Наскільки старо виглядає (виглядала) шкіра вашої бабусі по материнській лінії?", "answers": [("А: На 5-10 років молодша", "A"), ("Б: На свій вік", "B"), ("В: На 5 років старша", "C"), ("Г: На більше ніж 5 років старша", "D"), ("Д: Не можу відповісти", "E")]},
            {"number": 49, "question": "Наскільки старо виглядає (виглядала) шкіра вашого дідуся по материнській лінії?", "answers": [("А: На 5-10 років молодша", "A"), ("Б: На свій вік", "B"), ("В: На 5 років старша", "C"), ("Г: На більше ніж 5 років старша", "D"), ("Д: Не можу відповісти", "E")]},
            {"number": 50, "question": "Наскільки старо виглядає (виглядала) шкіра вашої бабусі по батьківській лінії?", "answers": [("А: На 5-10 років молодша", "A"), ("Б: На свій вік", "B"), ("В: На 5 років старша", "C"), ("Г: На більше ніж 5 років старша", "D"), ("Д: Не можу відповісти", "E")]},
            {"number": 51, "question": "Наскільки старо виглядає (виглядала) шкіра вашого дідуся по батьківській лінії?", "answers": [("А: На 5-10 років молодша", "A"), ("Б: На свій вік", "B"), ("В: На 5 років старша", "C"), ("Г: На більше ніж 5 років старша", "D"), ("Д: Не можу відповісти", "E")]},
            {"number": 52, "question": "Протягом вашого життя, чи засмагали ви постійно більше ніж два тижні на рік? Скільки загалом років?", "answers": [("А: Ніколи", "A"), ("Б: 1-5 років", "B"), ("В: 5-10 років", "C"), ("Г: Більше 10 років", "D")]},
            {"number": 53, "question": "Протягом вашого життя, чи захоплювалися ви сезонним загаром по два тижні за сезон чи рідше?", "answers": [("А: Ніколи", "A"), ("Б: 1-5 років", "B"), ("В: 5-10 років", "C"), ("Г: Більше 10 років", "D")]},
            {"number": 54, "question": "Виходячи з місця, де ви жили, скільки щоденного сонячного опромінення ви отримували в житті?", "answers": [("А: Мало — сіро і похмуро", "A"), ("Б: Трохи — змішаний клімат", "B"), ("В: Помірно — достатньо сонця", "C"), ("Г: Багато — тропіки або дуже сонячне місце", "D")]},
            {"number": 55, "question": "На який вік, на вашу думку, ви виглядаєте?", "answers": [("А: На 5-10 років молодша вашого віку", "A"), ("Б: На свій вік", "B"), ("В: На 5 років старша", "C"), ("Г: На більше ніж 5 років старша", "D")]},
            {"number": 56, "question": "Протягом останніх п'яти років, як часто ви дозволяли своїй шкірі засмагати?", "answers": [("А: Ніколи", "A"), ("Б: Один раз на місяць", "B"), ("В: Один раз на тиждень", "C"), ("Г: Щодня", "D")]},
            {"number": 57, "question": "Як часто ви обгорали під сонцем?", "answers": [("А: Ніколи", "A"), ("Б: 1-5 разів", "B"), ("В: 5-10 разів", "C"), ("Г: Багато разів", "D")]},
            {"number": 58, "question": "Протягом вашого життя, скільки сигарет ви викурили?", "answers": [("А: Жодної", "A"), ("Б: Кілька пачок", "B"), ("В: Декілька десятків пачок", "C"), ("Г: Я курю кожен день", "D"), ("Д: Я ніколи не курю, але живу з тими хто курить", "E")]},
            {"number": 59, "question": "Опишіть рівень забруднення повітря в місці, де ви живете:", "answers": [("А: Повітря свіже і чисте", "A"), ("Б: Частину року чисте", "B"), ("В: Трохи забруднене", "C"), ("Г: Дуже забруднене", "D")]},
            {"number": 60, "question": "Протягом якого часу ви використовували креми з ретиноїдами (Renova, Retin-A, Differin тощо)?", "answers": [("А: Багато років", "A"), ("Б: Від випадку до випадку", "B"), ("В: Один раз від акне", "C"), ("Г: Ніколи", "D")]},
            {"number": 61, "question": "Як часто ви зараз їсте фрукти і овочі?", "answers": [("А: З кожним прийомом їжі", "A"), ("Б: Один раз на день", "B"), ("В: Від випадку до випадку", "C"), ("Г: Ніколи", "D")]},
            {"number": 62, "question": "Протягом вашого життя, який відсоток раціону складали овочі і фрукти?", "answers": [("А: 75-100%", "A"), ("Б: 25-75%", "B"), ("В: 10-25%", "C"), ("Г: 0-10%", "D")]},
            {"number": 63, "question": "Який ваш натуральний колір шкіри (без засмаги)?", "answers": [("А: Темний", "A"), ("Б: Середній (смуглий)", "B"), ("В: Світлий", "C"), ("Г: Дуже світлий", "D")]},
            {"number": 64, "question": "Яка ваша етнічна приналежність?", "answers": [("А: Афро-американська", "A"), ("Б: Азіатська/індійська/середземноморська", "B"), ("В: Латиноамериканська/іспанська", "C"), ("Г: Європейська", "D")]},
            {"number": 65, "question": "Вам 65 років або більше?", "answers": [("А: Так", "F"), ("Б: Ні", "G")]},
        ]
    },
]

# ── Scoring ──────────────────────────────────────────────────────────────────
SCORE_MAP = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 2.5, 'F': 5, 'G': 0}
CYRILLIC_TO_LATIN = {'А': 'A', 'Б': 'B', 'В': 'C', 'Г': 'D', 'Д': 'E', 'Е': 'F', 'Ж': 'G'}

def _score(answer):
    return SCORE_MAP.get(answer, 0)

def _determine_type(score, section_idx):
    if section_idx == 0:  # O/D
        if score >= 27: return "O", "Жирна шкіра"
        return "D", "Суха шкіра"
    elif section_idx == 1:  # S/R
        if score >= 30: return "S", "Чутлива шкіра"
        return "R", "Стійка шкіра"
    elif section_idx == 2:  # P/N
        if score >= 29: return "P", "Пігментована шкіра"
        return "N", "Непігментована шкіра"
    elif section_idx == 3:  # W/T
        if score >= 41: return "W", "Зморшкувата шкіра"
        return "T", "Пружна шкіра"
    return "?", "Невизначено"

SKIN_TYPE_DESC = {
    "DRNT": "суха, стійка, непігментована, пружна",
    "DRNW": "суха, стійка, непігментована, схильна до зморшок",
    "DRPT": "суха, стійка, пігментована, пружна",
    "DRPW": "суха, стійка, пігментована, схильна до зморшок",
    "DSNT": "суха, чутлива, непігментована, пружна",
    "DSNW": "суха, чутлива, непігментована, схильна до зморшок",
    "DSPT": "суха, чутлива, пігментована, пружна",
    "DSPW": "суха, чутлива, пігментована, схильна до зморшок",
    "ORNT": "жирна, стійка, непігментована, пружна",
    "ORNW": "жирна, стійка, непігментована, схильна до зморшок",
    "ORPT": "жирна, стійка, пігментована, пружна",
    "ORPW": "жирна, стійка, пігментована, схильна до зморшок",
    "OSNT": "жирна, чутлива, непігментована, пружна",
    "OSNW": "жирна, чутлива, непігментована, схильна до зморшок",
    "OSPT": "жирна, чутлива, пігментована, пружна",
    "OSPW": "жирна, чутлива, пігментована, схильна до зморшок",
}

# ── Handlers ─────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    state = {'section': 0, 'question': 0, 'scores': [0, 0, 0, 0]}
    _save_state(tg_id, state)
    await update.message.reply_text(
        "Вітаємо у тесті на визначення типу шкіри за класифікацією Леслі Бауман (65 питань, 4 секції).\n\n"
        "Натисніть «Почати», щоб розпочати.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Почати", callback_data='start_section')]]))
    return SECTION


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    _clear_state(tg_id)
    await update.message.reply_text("Тест скасовано. /start щоб почати знову.")
    return ConversationHandler.END


async def show_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tg_id = query.from_user.id
    state = _load_state(tg_id)
    if not state:
        state = {'section': 0, 'question': 0, 'scores': [0, 0, 0, 0]}
        _save_state(tg_id, state)

    si = state['section']
    if si >= len(questions):
        return await _finalize(update, context)

    sec = questions[si]
    total_q = sum(len(s['questions']) for s in questions)
    done_q = sum(len(questions[i]['questions']) for i in range(si))
    await query.edit_message_text(
        "Секція {}/4: {}\n\n{}\n\nПрогрес: {}/{} питань".format(si + 1, sec['section'], sec['description'], done_q, total_q),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Продовжити", callback_data='continue_{}'.format(si))]]))
    return SECTION


async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tg_id = query.from_user.id
    state = _load_state(tg_id)
    if not state:
        await query.edit_message_text("Сесія закінчилась. /start щоб почати знову.")
        return ConversationHandler.END

    si = state['section']
    qi = state['question']
    sec = questions[si]
    q = sec['questions'][qi]

    total_q = sum(len(s['questions']) for s in questions)
    done_q = sum(len(questions[i]['questions']) for i in range(si)) + qi + 1

    text = "Питання {}/{}\n\n{}".format(done_q, total_q, q['question'])
    buttons = []
    for ans_text, ans_code in q['answers']:
        letter = ans_text[0]
        latin = CYRILLIC_TO_LATIN.get(letter, letter)
        buttons.append([InlineKeyboardButton(ans_text, callback_data='a_{}_{}'.format(si, latin))])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    return QUESTION


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tg_id = query.from_user.id
    state = _load_state(tg_id)
    if not state:
        await query.edit_message_text("Сесія закінчилась. /start щоб почати знову.")
        return ConversationHandler.END

    _, si_str, ans = query.data.split('_')
    si = int(si_str)
    state['scores'][si] += _score(ans)
    state['question'] += 1
    _save_state(tg_id, state)

    sec = questions[si]
    if state['question'] < len(sec['questions']):
        return await ask_question(update, context)

    # Section done — show section result
    section_score = state['scores'][si]
    stype, sdesc = _determine_type(section_score, si)

    state['section'] += 1
    state['question'] = 0
    _save_state(tg_id, state)

    if state['section'] >= len(questions):
        # All sections done
        return await _finalize(update, context)

    next_label = "Наступна секція" if state['section'] < len(questions) else "Результат"
    await query.edit_message_text(
        "Секція «{}» завершена!\n{:.0f} б. — {} ({})\n\nПереходимо до наступної секції.".format(
            sec['section'], section_score, stype, sdesc),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(next_label, callback_data='start_section')]]))
    return SECTION


async def _finalize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    tg_id = query.from_user.id
    state = _load_state(tg_id)
    if not state or len(state.get('scores', [])) < 4:
        await query.edit_message_text("Помилка: не всі секції завершені. /start")
        return ConversationHandler.END

    result_code = ''
    lines = []
    for idx in range(4):
        s = state['scores'][idx]
        stype, sdesc = _determine_type(s, idx)
        result_code += stype
        lines.append("{:.0f} б. — {} ({})".format(s, stype, sdesc))

    desc = SKIN_TYPE_DESC.get(result_code, '')

    text = "Ваш тип шкіри за класифікацією Леслі Бауман:\n\n"
    text += "{}  —  {}\n\n".format(result_code, desc)
    text += "\n".join(lines)
    text += "\n\nПоділіться результатами з вашим косметологом:"
    text += "\n[Instagram](https://ig.me/m/dr.gomon) | [Telegram](https://t.me/DrGomonCosmetology)"

    await query.edit_message_text(text, parse_mode='Markdown')

    # Save result
    user = query.from_user
    _save_result(tg_id, user.username, user.first_name, result_code, state['scores'])
    _clear_state(tg_id)

    logger.info('Quiz completed: tg_id={} type={} scores={}'.format(tg_id, result_code, state['scores']))
    return ConversationHandler.END


async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    logger.error('Bot error: {}'.format(context.error))


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    _create_pid()
    _init_db()

    app = Application.builder().token(TG_SKINTYPE_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SECTION: [
                CallbackQueryHandler(show_section, pattern=r'^start_section$'),
                CallbackQueryHandler(ask_question, pattern=r'^continue_\d+$'),
            ],
            QUESTION: [
                CallbackQueryHandler(handle_answer, pattern=r'^a_\d+_[A-G]$'),
            ],
            FINALIZE: [
                CallbackQueryHandler(show_section, pattern=r'^start_section$'),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
        per_user=True,
        per_chat=True,
    )
    app.add_handler(conv)
    app.add_error_handler(error_handler)

    logger.info('Skin type quiz bot started')
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
