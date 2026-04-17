#!/usr/bin/env python3
"""One-time script to sync WLaunch branch services with prices.json."""
import requests, json, time, sys
sys.path.insert(0, '/home/gomoncli/zadarma')
from config import WLAUNCH_API_URL, COMPANY_ID
from wlaunch_api import get_branch_id, HEADERS

bid = get_branch_id()
h = dict(HEADERS, **{'Content-Type': 'application/json'})

# Get branch services
url = "{}/company/{}/branch/{}/service".format(WLAUNCH_API_URL, COMPANY_ID, bid)
resp = requests.get(url, headers=HEADERS, params={"page": 0, "size": 500}, timeout=10)
bsvc = {s["name"]: s for s in resp.json().get("content", [])}

# Mapping: existing_wl_name -> (new_name_or_None, duration_seconds) or None to deactivate
RENAME_MAP = {
    # Already correct name — just activate
    "WOW-чистка обличчя":          (None, 4800),
    "Ботулінотерапія":              (None, 1800),
    "Контурна пластика губ":        (None, 1800),
    "Контурна пластика обличчя":    (None, 1800),
    "Мезотерапія":                  (None, 1800),
    "Ліполіз (ліполітики)":         (None, 1800),
    "Корекція ботулотоксину":       (None, 900),
    "Корекція філера":              (None, 900),
    "Лікування гіпергідрозу (Botox)": (None, 1800),
    "Карбокситерапія":              (None, 1800),
    "Ліполітики (обличчя, 4 мл)":   (None, 1800),

    # Rename to match prices.json
    "Гіалуронідаза":                ("Гіалуронідаза (розчинення філера)", 1800),
    "Fill up":                      ("Fill Up", 1800),
    "Plinest one (4 ml)":           ("Plinest One (4 ml)", 1800),
    "Біорепарація шкіри Rejuran HB": ("Rejuran HB", 1800),
    "Біорепарація шкіри Rejuran I":  ("Rejuran I", 1800),
    "Біорепарація шкіри Rejuran S":  ("Rejuran S", 1800),
    'Біорепарація шкіри Екзосоми (Exoxe) 2,5 ml': ("Екзосоми (Exoxe) 2.5 ml", 1800),
    "Smart Біоревіталізація":       ("Smart-біоревіталізація", 1800),
    "Neauvia hydro deluxe":         ("Neauvia Hydro Deluxe", 1800),
    'Мезоботокс "Монако" (4ml)':    ("Мезоботокс «Монако» (4 ml)", 1800),
    "Пілінг Біоревіталізант PRX T-33": ("PRX-T33", 2700),
    'SPA-догляд від Christina "Оновлення та сяяння"': ("SPA-догляд від Christina", 2700),
    "DrumRoll всього тіла":         ("Моделювання всього тіла", 2700),
    "DrumRoll окремої зони":        ("Моделювання окремої ділянки", 1800),
    'Відбілювання зубів "Light"':   ("Light", 1800),
    'Відбілювання зубів "Maximum"': ("Maximum", 4500),
    'Відбілювання зубів "Medium"':  ("Medium", 3600),

    # Reuse unused branch slots for new prices.json services
    "Азелаїновий пілінг":           ("Азелаїновий / Мигдальний / Феруловий", 1800),
    "Комбінована чистка обличчя":   ("WOW-чистка «Сяяння»", 5400),
    "Лікування акне":               ("Підліткова делікатна чистка", 4800),
    "Киснева мезотерапія":          ("Кисневий догляд Glow Skin", 3600),
    "Косметичний масаж обличчя":    ("Загальний релакс-масаж всього тіла", 3600),
    "Лімфодренажний масаж обличчя": ("Пресотерапія «Легкість тіла»", 1800),
    "Ін'єкції Ботокса для обличчя ↓": ("1 зона", 1800),
    "Ботокс в міжбрів'я":          ("2 зони", 1800),
    "Ботокс навколо очей":          ("3 зони", 1800),
    "Ботокс губ":                   ("Full Face", 1800),
    "Заповнення зморшок":           ("Ліфтинг Ніфертіті (платизма)", 1800),
    "Аугментація вилиць":           ("Neuramis Deep", 1800),
    "Контурна пластика носа":       ("Saypha Filler", 1800),
    "Контурна пластика підборіддя": ("Perfecta", 1800),
    "Корекція носослізних борізд":  ("Genyal / Xcelence 3", 1800),
    "PRX-пілінг":                   ("PRX-T33 + мікронідлінг", 2700),
    "Гліколевий пілінг":            ("KEMIKUM", 1800),
    "Мигдальний пілінг":            ("KEMIKUM + мікронідлінг", 2700),
    "Саліциловий пілінг":           ("Neuramis Volume", 1800),
    "Ензимний пілінг":              ("Saypha Volume", 1800),
    "Молочний пілінг":              ("Neauvia Stimulate", 1800),
    "Іспанський масаж обличчя":     ("Neauvia Intense Lips", 1800),
    "Альгінатна маска":             ("Skin Booster", 1800),
    "Вакуумна чистка обличчя":      ("Vitaran Tox & Eye", 1800),
    "Маски для обличчя":            ("Hair Loss / Hair Vital", 1800),
    "Мезотерапія шкіри голови":     ("Ліполітики (тіло, 10 мл)", 1800),
    "RRS long lasting":             ("Офлайн-консультація", 1800),
    "Peptydial HX":                 ("Онлайн-консультація", 1800),

    # Deactivate (typo/obsolete)
    'Карбокситеріпая "72 години зволоження"': None,
    "Чистка обличчя":                None,
    "Ін'єкційна косметологія":       None,
    "Процедури для тіла":            None,
    "DrumRoll":                      None,
}

dry_run = '--dry-run' in sys.argv
ok = err = skip = 0

for wl_name, mapping in sorted(RENAME_MAP.items()):
    s = bsvc.get(wl_name)
    if not s:
        print("? NOT FOUND: {}".format(wl_name))
        skip += 1
        continue
    sid = s["id"]

    if mapping is None:
        if dry_run:
            print("[DRY] ✗ DEACTIVATE: {}".format(wl_name))
            ok += 1
            continue
        try:
            r = requests.post("{}/company/{}/service/{}".format(WLAUNCH_API_URL, COMPANY_ID, sid),
                headers=h, json={"company_service": {"active": False}}, timeout=10)
            print("✗ DEACTIVATED: {} [{}]".format(wl_name, r.status_code))
            ok += 1 if r.status_code == 200 else 0
            err += 0 if r.status_code == 200 else 1
        except Exception as e:
            print("! ERROR: {} {}".format(wl_name, e))
            err += 1
        time.sleep(0.15)
        continue

    new_name, dur = mapping
    update = {"active": True, "duration": dur}
    if new_name:
        update["name"] = new_name

    label = "→ " + new_name if new_name else "(keep name)"
    if dry_run:
        print("[DRY] ✓ {}: {} {}min".format(wl_name[:40], label, dur // 60))
        ok += 1
        continue

    try:
        r = requests.post("{}/company/{}/service/{}".format(WLAUNCH_API_URL, COMPANY_ID, sid),
            headers=h, json={"company_service": update}, timeout=10)
        print("✓ {}: {} {} [{}]".format(r.status_code, wl_name[:40], label, dur // 60))
        if r.status_code != 200:
            print("  WARN:", r.text[:100])
            err += 1
        else:
            ok += 1
    except Exception as e:
        print("! ERROR: {} {}".format(wl_name, e))
        err += 1
    time.sleep(0.15)

# Deactivate remaining active services not in our map and not "Консультація"
KEEP_ACTIVE = {"Консультація"}
for name in RENAME_MAP:
    m = RENAME_MAP[name]
    if m is not None:
        KEEP_ACTIVE.add(m[0] if m[0] else name)

for name, s in sorted(bsvc.items()):
    if s.get("active") and name not in KEEP_ACTIVE and name not in RENAME_MAP:
        sid = s["id"]
        if dry_run:
            print("[DRY] ✗ EXTRA DEACTIVATE: {}".format(name))
            ok += 1
            continue
        try:
            r = requests.post("{}/company/{}/service/{}".format(WLAUNCH_API_URL, COMPANY_ID, sid),
                headers=h, json={"company_service": {"active": False}}, timeout=10)
            print("✗ EXTRA DEACTIVATED: {} [{}]".format(name, r.status_code))
            ok += 1
        except Exception as e:
            print("! EXTRA ERROR: {} {}".format(name, e))
            err += 1
        time.sleep(0.15)

print()
print("=== DONE: ok={} errors={} skipped={} ===".format(ok, err, skip))
