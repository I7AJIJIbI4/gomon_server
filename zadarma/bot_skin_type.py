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
IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skin_type_imgs')
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
        "description": "Ця секція оцінює жирність та зволоженість вашої шкіри.",
        "questions": [
            {"number": 1, "question": "Уявіть: ви вмилися водою і 2-3 години нічого не наносили на обличчя. Ваше чоло та щоки виглядають або відчуваються:", "answers": [("Шершавими, лущаться або потріскані", "A"), ("Стягнутими", "B"), ("Добре зволоженими, матовими", "C"), ("Блискучими, відбивають світло", "D")]},
            {"number": 2, "question": "На фотографіях ваше обличчя виглядає блискучим:", "answers": [("Ніколи", "A"), ("Іноді", "B"), ("Часто", "C"), ("Завжди", "D")]},
            {"number": 3, "question": "Через 2-3 години після нанесення тональної основи (без пудри) ваш макіяж виглядає:", "answers": [("Лущиться, підкреслює зморшки", "A"), ("Рівним і гладким", "B"), ("Блискучим", "C"), ("Розпливається і блищить", "D"), ("Я не користуюся тональними основами", "E")]},
            {"number": 4, "question": "В умовах низької вологості, без крему, ваша шкіра на обличчі:", "answers": [("Дуже суха або потріскана", "A"), ("Стягнута", "B"), ("Нормальна", "C"), ("Блискуча, крем не потрібен", "D"), ("Не знаю", "E")]},
            {"number": 5, "question": "Погляньте в збільшувальне дзеркало. Скільки у вас великих пор?", "answers": [("Немає", "A"), ("Кілька в Т-зоні (лоб і ніс)", "B"), ("Багато", "C"), ("Дуже багато по всьому обличчю", "D"), ("Важко визначити, пори дрібні", "E")]},
            {"number": 6, "question": "Як би ви охарактеризували свою шкіру:", "answers": [("Суха", "A"), ("Нормальна", "B"), ("Комбінована", "C"), ("Жирна", "D")]},
            {"number": 7, "question": "Після використання мила, що піниться, шкіра на обличчі:", "answers": [("Суха і потріскана", "A"), ("Трохи суха, але не потріскана", "B"), ("Нормальна", "C"), ("Жирна", "D"), ("Не використовую, шкіра не пересихає", "E"), ("Не використовую, бо шкіра пересихає", "A")]},
            {"number": 8, "question": "Якщо шкіру на обличчі не зволожити, ви відчуваєте стягнутість:", "answers": [("Завжди", "A"), ("Іноді", "B"), ("Рідко", "C"), ("Ніколи", "D")]},
            {"number": 9, "question": "У вас є комедони (чорні точки та білі вугрі):", "answers": [("Ніколи", "A"), ("Рідко", "B"), ("Іноді", "C"), ("Завжди", "D")]},
            {"number": 10, "question": "Ваше обличчя жирне тільки в Т-зоні (лоб і ніс):", "answers": [("Ніколи", "A"), ("Іноді", "B"), ("Часто", "C"), ("Завжди", "D")]},
            {"number": 11, "question": "Через 2-3 години після нанесення крему ваші щоки:", "answers": [("Шершаві, лущаться", "A"), ("Гладкі", "B"), ("Трохи блищать", "C"), ("Блищать і лисніють", "D")]},
        ]
    },
    {
        "section": "Чутлива чи стійка?",
        "description": "Ця секція оцінює схильність шкіри до висипань, червоніння та свербіння.",
        "questions": [
            {"number": 12, "question": "У вас з'являються висипання на обличчі:", "answers": [("Ніколи", "A"), ("Рідко", "B"), ("Мінімум раз на місяць", "C"), ("Мінімум раз на тиждень", "D")]},
            {"number": 13, "question": "Засоби для догляду за шкірою викликають червоніння, висипання або свербіння:", "answers": [("Ніколи", "A"), ("Рідко", "B"), ("Часто", "C"), ("Завжди", "D"), ("Не користуюся косметикою", "E")]},
            {"number": 14, "question": "Вам коли-небудь ставили діагноз акне або розацеа?", "answers": [("Ні", "A"), ("Знайомі помічали, але діагноз не ставили", "B"), ("Так", "C"), ("Так, важка форма", "D"), ("Не впевнена", "E")]},
            {"number": 15, "question": "Якщо ви носите прикраси не з 14-каратного золота, як часто від них з'являється висипання?", "answers": [("Ніколи", "A"), ("Рідко", "B"), ("Часто", "C"), ("Завжди", "D"), ("Не впевнена", "E")]},
            {"number": 16, "question": "Сонцезахисні креми викликають свербіння, печіння або червоніння:", "answers": [("Ніколи", "A"), ("Рідко", "B"), ("Часто", "C"), ("Завжди", "D"), ("Не користуюся сонцезахисними", "E")]},
            {"number": 17, "question": "Вам ставили діагноз атопічний дерматит, екзема або контактний дерматит?", "answers": [("Ні", "A"), ("Знайомі помічали, але діагноз не ставили", "B"), ("Так", "C"), ("Так, важка стадія", "D"), ("Не впевнена", "E")]},
            {"number": 18, "question": "Як часто під кільцями з'являється почервоніння або висипання?", "answers": [("Ніколи", "A"), ("Рідко", "B"), ("Часто", "C"), ("Завжди", "D"), ("Не ношу кілець", "E")]},
            {"number": 19, "question": "Ароматизовані засоби (пінні ванни, масажні олії, лосьйони) викликають свербіння або червоніння:", "answers": [("Ніколи", "A"), ("Рідко", "B"), ("Часто", "C"), ("Завжди", "D"), ("Не користуюся такими продуктами", "E")]},
            {"number": 20, "question": "Чи можете ви користуватись милом з готелів без проблем?", "answers": [("Так", "A"), ("Зазвичай проблем немає", "B"), ("Ні, шкіра свербить і червоніє", "C"), ("Не використовую, було багато проблем", "D"), ("Беру з собою, тому не знаю", "E")]},
            {"number": 21, "question": "У когось у вашій родині є атопічний дерматит, екзема, астма або алергія?", "answers": [("Ні", "A"), ("Один член сім'ї", "B"), ("Кілька членів сім'ї", "C"), ("Багато членів сім'ї", "D"), ("Не впевнена", "E")]},
            {"number": 22, "question": "Що відбувається від сильно ароматизованого прального порошку?", "answers": [("Все добре", "A"), ("Шкіра трохи суха", "B"), ("Шкіра свербить", "C"), ("Свербить і з'являється висип", "D"), ("Не знаю, не використовую", "E")]},
            {"number": 23, "question": "Як часто обличчя або шия червоніють після стресу чи сильних емоцій?", "answers": [("Ніколи", "A"), ("Іноді", "B"), ("Часто", "C"), ("Завжди", "D")]},
            {"number": 24, "question": "Як часто ви червонієте від алкоголю?", "answers": [("Ніколи", "A"), ("Іноді", "B"), ("Часто", "C"), ("Завжди, намагаюся не пити", "D"), ("Не п'ю алкоголь", "E")]},
            {"number": 25, "question": "Як часто ви червонієте від гострої або гарячої їжі?", "answers": [("Ніколи", "A"), ("Іноді", "B"), ("Часто", "C"), ("Завжди", "D"), ("Не їм гостру їжу", "E")]},
            {"number": 26, "question": "Скільки у вас видимих судин або судинних зірочок на обличчі і носі?", "answers": [("Немає", "A"), ("Мало (1-3)", "B"), ("Кілька (4-6)", "C"), ("Багато (7+)", "D")]},
            {"number": 27, "question": "Ваше обличчя виглядає червоним на фото:", "answers": [("Ніколи", "A"), ("Іноді", "B"), ("Часто", "C"), ("Завжди", "D")]},
            {"number": 28, "question": "Люди запитують, чи ви обгоріли, хоча ви не були під сонцем:", "answers": [("Ніколи", "A"), ("Іноді", "B"), ("Часто", "C"), ("Завжди", "D"), ("Я завжди виглядаю так", "E")]},
            {"number": 29, "question": "Від косметики або сонцезахисного крему у вас червоніння, свербіння чи набряк:", "answers": [("Ніколи", "A"), ("Іноді", "B"), ("Часто", "C"), ("Завжди", "D"), ("Не використовую ці продукти", "E")]},
            {"number": 30, "question": "Чи ставив лікар діагноз акне, розацеа, контактний дерматит або екзема?", "answers": [("Так, дерматолог", "F"), ("Так, терапевт", "B"), ("Ні", "G")]},
        ]
    },
    {
        "section": "Пігментована чи непігментована?",
        "description": "Ця секція оцінює схильність шкіри до появи пігментних плям, веснянок та нерівного тону.",
        "questions": [
            {"number": 31, "question": "Після прищика або врослого волосся залишається темна пляма?", "answers": [("Ніколи", "A"), ("Іноді", "B"), ("Часто", "C"), ("Завжди", "D"), ("У мене цього не буває", "E")]},
            {"number": 32, "question": "Після порізу, як довго коричневий (не рожевий) слід залишається на шкірі?", "answers": [("Не залишається", "A"), ("Тиждень", "B"), ("Кілька тижнів", "C"), ("Місяць", "D")]},
            {"number": 33, "question": "Скільки темних плям з'явилося під час вагітності, прийому контрацептивів або гормональної терапії?", "answers": [("Жодної", "A"), ("Одна", "B"), ("Кілька", "C"), ("Багато", "D"), ("Питання не стосується мене", "E")]},
            {"number": 34, "question": "У вас є темні плями над верхньою губою або на щоках?", "answers": [("Ні", "A"), ("Не впевнена", "B"), ("Так, ледь помітні", "C"), ("Так, дуже помітні", "D")]},
            {"number": 35, "question": "Чи темніють пігментні плями, коли ви загораєте?", "answers": [("У мене немає плям", "A"), ("Не впевнена", "B"), ("Трохи темніють", "C"), ("Сильно темніють", "D"), ("Завжди з SPF, ніколи не загораю", "E")]},
            {"number": 36, "question": "Вам діагностували мелазму (плями на обличчі)?", "answers": [("Ні", "A"), ("Так, але позбулася", "B"), ("Так", "C"), ("Так, важка форма", "D"), ("Не впевнена", "E")]},
            {"number": 37, "question": "У вас є веснянки або сонячні плями на обличчі, грудях, спині, руках?", "answers": [("Ні", "A"), ("Кілька (1-5)", "B"), ("Багато (6-15)", "C"), ("Дуже багато (16+)", "D")]},
            {"number": 38, "question": "Якщо вперше за кілька місяців потрапляєте під сонце, шкіра:", "answers": [("Тільки обгорає", "A"), ("Спочатку обгорає, потім засмагає", "B"), ("Засмагає", "C"), ("Шкіра вже темна", "D")]},
            {"number": 39, "question": "Якщо кілька днів постійно під сонцем:", "answers": [("Обгораю, але колір не змінюється", "A"), ("Стає трохи темнішою", "B"), ("Стає значно темнішою", "C"), ("Шкіра вже темна", "D"), ("Не впевнена", "E")]},
            {"number": 40, "question": "Під сонцем у вас з'являються веснянки?", "answers": [("Ніколи", "A"), ("Кілька нових щороку", "B"), ("Часто з'являються", "C"), ("Шкіра темна, не видно", "D"), ("Навмисно уникаю сонця", "E")]},
            {"number": 41, "question": "У когось з ваших батьків є веснянки?", "answers": [("Ні", "A"), ("Кілька на обличчі", "B"), ("Багато на обличчі", "C"), ("Багато: обличчя, груди, шия, плечі", "D"), ("Не впевнена", "E")]},
            {"number": 42, "question": "Який ваш натуральний колір волосся?", "answers": [("Світле (блонд)", "A"), ("Каштанове / темно-русяве", "B"), ("Чорне", "C"), ("Руде", "D")]},
            {"number": 43, "question": "Чи була меланома у вас або кровних родичів?", "answers": [("Ні", "A"), ("У одного родича", "B"), ("У кількох родичів", "C"), ("У мене особисто", "D"), ("Не впевнена", "E")]},
            {"number": 44, "question": "Чи є пігментні плями на ділянках шкіри, що бувають на сонці?", "answers": [("Так", "F"), ("Ні", "G")]},
        ]
    },
    {
        "section": "Зморшкувата чи пружна?",
        "description": "Ця секція оцінює схильність шкіри до формування зморшок та ознак старіння.",
        "questions": [
            {"number": 45, "question": "У вас є зморшки на обличчі?", "answers": [("Ні, навіть при мімічних рухах", "A"), ("Тільки при усмішці чи хмуренні", "B"), ("В русі і кілька в спокої", "C"), ("Є навіть у спокої", "D")]},
            {"number": 46, "question": "Наскільки старо виглядає (виглядала) шкіра вашої мами?", "answers": [("На 5-10 років молодша", "A"), ("На свій вік", "B"), ("На 5 років старша", "C"), ("На 5+ років старша", "D"), ("Не можу відповісти", "E")]},
            {"number": 47, "question": "Наскільки старо виглядає (виглядала) шкіра вашого тата?", "answers": [("На 5-10 років молодша", "A"), ("На свій вік", "B"), ("На 5 років старша", "C"), ("На 5+ років старша", "D"), ("Не можу відповісти", "E")]},
            {"number": 48, "question": "Шкіра вашої бабусі по мамі:", "answers": [("На 5-10 років молодша", "A"), ("На свій вік", "B"), ("На 5 років старша", "C"), ("На 5+ років старша", "D"), ("Не можу відповісти", "E")]},
            {"number": 49, "question": "Шкіра вашого дідуся по мамі:", "answers": [("На 5-10 років молодша", "A"), ("На свій вік", "B"), ("На 5 років старша", "C"), ("На 5+ років старша", "D"), ("Не можу відповісти", "E")]},
            {"number": 50, "question": "Шкіра вашої бабусі по татові:", "answers": [("На 5-10 років молодша", "A"), ("На свій вік", "B"), ("На 5 років старша", "C"), ("На 5+ років старша", "D"), ("Не можу відповісти", "E")]},
            {"number": 51, "question": "Шкіра вашого дідуся по татові:", "answers": [("На 5-10 років молодша", "A"), ("На свій вік", "B"), ("На 5 років старша", "C"), ("На 5+ років старша", "D"), ("Не можу відповісти", "E")]},
            {"number": 52, "question": "Скільки років ви регулярно засмагали (більше 2 тижнів на рік)?", "answers": [("Ніколи", "A"), ("1-5 років", "B"), ("5-10 років", "C"), ("Більше 10 років", "D")]},
            {"number": 53, "question": "Скільки років ви засмагали сезонно (до 2 тижнів за сезон)?", "answers": [("Ніколи", "A"), ("1-5 років", "B"), ("5-10 років", "C"), ("Більше 10 років", "D")]},
            {"number": 54, "question": "Скільки сонця ви отримували протягом життя?", "answers": [("Мало, жила в похмурому кліматі", "A"), ("Трохи, змішаний клімат", "B"), ("Помірно, достатньо сонця", "C"), ("Багато, сонячний або тропічний клімат", "D")]},
            {"number": 55, "question": "На який вік, на вашу думку, ви виглядаєте?", "answers": [("На 5-10 років молодша", "A"), ("На свій вік", "B"), ("На 5 років старша", "C"), ("На 5+ років старша", "D")]},
            {"number": 56, "question": "За останні 5 років, як часто ви засмагали?", "answers": [("Ніколи", "A"), ("Раз на місяць", "B"), ("Раз на тиждень", "C"), ("Щодня", "D")]},
            {"number": 57, "question": "Скільки разів за життя ви обгорали на сонці?", "answers": [("Ніколи", "A"), ("1-5 разів", "B"), ("5-10 разів", "C"), ("Багато разів", "D")]},
            {"number": 58, "question": "Скільки сигарет ви викурили за життя?", "answers": [("Жодної", "A"), ("Кілька пачок", "B"), ("Декілька десятків пачок", "C"), ("Курю щодня", "D"), ("Не курю, але живу з курцями", "E")]},
            {"number": 59, "question": "Рівень забруднення повітря де ви живете:", "answers": [("Свіже і чисте", "A"), ("Частину року чисте", "B"), ("Трохи забруднене", "C"), ("Дуже забруднене", "D")]},
            {"number": 60, "question": "Чи використовували ви креми з ретиноїдами (Renova, Retin-A, Differin)?", "answers": [("Багато років", "A"), ("Від випадку до випадку", "B"), ("Один раз від акне", "C"), ("Ніколи", "D")]},
            {"number": 61, "question": "Як часто ви зараз їсте фрукти і овочі?", "answers": [("З кожним прийомом їжі", "A"), ("Раз на день", "B"), ("Від випадку до випадку", "C"), ("Ніколи", "D")]},
            {"number": 62, "question": "Який відсоток вашого раціону складали овочі та фрукти протягом життя?", "answers": [("75-100%", "A"), ("25-75%", "B"), ("10-25%", "C"), ("0-10%", "D")]},
            {"number": 63, "question": "Ваш натуральний колір шкіри (без засмаги):", "answers": [("Темний", "A"), ("Середній (смуглий)", "B"), ("Світлий", "C"), ("Дуже світлий", "D")]},
            {"number": 64, "question": "Ваша етнічна приналежність (для більшості українців - європейська):", "answers": [("Афро-американська", "A"), ("Азіатська / індійська / середземноморська", "B"), ("Латиноамериканська", "C"), ("Європейська", "D")]},
            {"number": 65, "question": "Вам 65 років або більше?", "answers": [("Так", "F"), ("Ні", "G")]},
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

    letters = ['А', 'Б', 'В', 'Г', 'Д', 'Е']
    answer_lines = []
    buttons = []
    for i, (ans_text, ans_code) in enumerate(q['answers']):
        letter = letters[i] if i < len(letters) else chr(ord('А') + i)
        latin = CYRILLIC_TO_LATIN.get(letter, 'A')
        answer_lines.append("{}) {}".format(letter, ans_text))
        buttons.append([InlineKeyboardButton(letter, callback_data='a_{}_{}'.format(si, latin))])
    text = "Питання {}/{}\n\n{}\n\n{}".format(done_q, total_q, q['question'], "\n".join(answer_lines))

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

    img_path = os.path.join(IMG_DIR, '{}.png'.format(result_code))
    if os.path.exists(img_path):
        # Replace the buttons message with a photo carrying the result as caption.
        # edit_message_text can't change a text message into a photo, so delete + send_photo.
        try:
            await query.message.delete()
        except Exception as e:
            logger.warning('delete quiz message failed: {}'.format(e))
        with open(img_path, 'rb') as f:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=f,
                caption=text,
                parse_mode='Markdown',
            )
    else:
        logger.warning('skin_type image missing for {}, falling back to text'.format(result_code))
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
        per_message=False,
    )
    app.add_handler(conv)
    app.add_error_handler(error_handler)

    logger.info('Skin type quiz bot started')
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
