---
name: gomon-deploy
description: Деплой gomon_server на VPS 45.94.157.127 — що перезапускати після якої зміни, обов'язкові bump-и (sw.js CACHE, ?v= віджета), перевірки до і після. Використовуй, коли користувач просить задеплоїти, викотити зміни на сервер або питає, що потрібно перезапустити.
---

# Деплой GomonClinic

Код лежить на сервері в `/opt/gomon/app/` (git, remote по SSH). Деплой = `git pull` + перезапуск того, що змінилось. **Спершу визнач, що саме змінилось** (`git diff --stat <старий>..HEAD`), і бери лише потрібні рядки таблиці нижче.

Коміт, пуш і деплой — лише з явного дозволу на кожну дію (`gomon-rules` і `~/.claude/CLAUDE.md` тепер збігаються). Назви, що саме зробиш, і дочекайся «так». `git reset --hard`, force-push, видалення гілок і тегів — окремий явний дозвіл.

## 1. Перед деплоєм (локально)

1. `python -m pytest tests -q` — pre-push хук ганяє те саме, але краще знати до пушу.
2. `python -m py_compile` для змінених `.py`. Для PHP локально `php` може бути відсутній — перевіряй на сервері (крок 3).
3. Змінив JS у `index.html` / `gomon-*.js` — правила з CLAUDE.md: кожен виклик `renderXxx()` має існувати, кожен `getElementById` має елемент, кожен `fetch('/api/…')` має endpoint, `grep -n 'function _fmtDate'` без дублікатів.
4. Нічого з `config.py`, `config.php`, `prices.json`, `promos.json`, ключів у коміті — вони поза git.

## 2. Що перезапускати

| Змінилось | Дія |
|---|---|
| `pwa_api.py` (і модулі, які він імпортує) | `systemctl restart gomon-api`. Сам не перезавантажиться: `check_flask.sh` більше не в crontab |
| `bot.py` | `systemctl restart gomon-bot` |
| `tg_business_listener.py` | `systemctl restart gomon-tgbiz` |
| Спільні модулі (`notifier.py`, `user_db.py`, `tz_utils.py`, `loyalty.py`, `config.py`, `cashback_confirm.py`) | перезапусти **всі** сервіси, що їх імпортують: `gomon-api`, `gomon-bot`, `gomon-tgbiz` |
| Cron-скрипти (`appt_reminder`, `photo_reminder`, `sync_*`, `ig_health`, `wl_catalog`, `push_reminder`…) | нічого: крон візьме нову версію на наступному запуску. Де є `--dry-run`, запусти його вручну |
| `deploy/crontab` | окремий потік, див. нижче |
| PHP (`chat.php`, `send.php`, `modal_prices.php`…) | перезапуск не потрібен, діє одразу після pull. Спершу `php -l` на сервері |
| `index.html`, `gomon-chat.js`, `manifest.json`, `sw.js` | **обов'язково** bump `CACHE` у `sw.js` (`gomon-YYYY-MM-DDx`, наступна літера) і коміт `index.html` + `sw.js` разом |
| `gomon-widget.js` | bump `?v=YYYYMMDDx` у `a188dd94d37a0374c81c636d09cd1f05.php` (зараз ~рядок 1530) |

Додатково для видимих клієнту змін: оновити `google-play/PLAYSTORE-LISTING.md` (release notes) і CLAUDE.md, якщо змінились endpoints, схема БД, cron чи правила.

### Crontab
Джерело правди — `deploy/crontab`. Руками на сервері не правити. Нова джоба з фіксованою годиною: обидві UTC-години + `kyiv_gate.py`; `tests/test_crontab.py` скаже, якщо щось не так. Деплой із бекапом:
```bash
ssh root@45.94.157.127 'cd /opt/gomon/app && crontab -l > /opt/gomon/backups/crontab/crontab_$(date +%Y%m%d_%H%M).txt && crontab deploy/crontab'
ssh root@45.94.157.127 'cd /opt/gomon/app && crontab -l | diff - deploy/crontab && echo in-sync'
```

## 3. Деплой

```bash
ssh root@45.94.157.127 'cd /opt/gomon/app && git status --short'   # дивись перед pull
ssh root@45.94.157.127 'cd /opt/gomon/app && git pull'
```
- У `git status` невідстежені файли в `public_html/` (картинки, лого) — давні й безпечні. **Змінені відстежувані файли** — зупинись і спитай: колись живу правку `system_prompt.txt` на сервері знищив `reset --hard`. Файли на сервері руками не правити.
- `git pull`, а не `reset --hard`.
- Далі: `/opt/gomon/venv/bin/python -m py_compile <змінені .py>`, `php -l <змінені .php>`, потім рестарти з таблиці.

Особливі випадки:
- **Зміна ланцюжка моделей у `chat.php`**: видали `private_data/active_model.txt`, якщо там стара модель (кеш).
- **Нова модель Claude**: перевір реальним запитом і лише невеликою вибіркою (`agent_tester.py --sample N --seed S`). Довгий system prompt (~16K токенів) коштує: прогін на 15 кейсів ≈ 1 $, а 06.11.2026 баланс прод-ключа вичерпався, найімовірніше від таких тестів (клієнтські AI-чати лежали, доки його не поповнили). Перед прогоном спитай користувача. Sonnet 5.5 не приймає `temperature` і за замовчуванням повертає `thinking`-блок першим: бери текст з усіх `text`-блоків, а щоб не платити за думання, шли `thinking: {"type":"between_tools"}`.
- **Зміни в розсилках** (SMS/TG/push): спершу `--dry-run`. Запобіжник `send_guard` зупинить cron-розсилки на 30 відправках за запуск; прапорець `/opt/gomon/send_paused.flag`.

## 4. Після деплою

```bash
curl -s https://drgomon.beauty/api/health                       # ok:true, db:true
ssh root@45.94.157.127 'systemctl is-active gomon-api gomon-bot gomon-tgbiz'
ssh root@45.94.157.127 'journalctl -u gomon-api -u gomon-bot -u gomon-tgbiz -n 20 --no-pager'
curl -si https://drgomon.beauty/app/sw.js | grep CACHE          # має збігатись з sw.js у коміті
```
Для зміненого — точкова перевірка: TG Business — написати в DM, AI має відповісти; WLaunch — `python3 sync_appointments.py` без помилок; WayForPay — тестовий платіж; PHP — відкрити сторінку. У разі збою `journalctl` покаже причину; відкат — повернути попередній коміт на сервері й перезапустити сервіси (з дозволу користувача).

У фінальному звіті напиши чесно, що **перевірено** (health, active, dry-run), а що ні (реальний клієнтський сценарій, поки не було такого вхідного).
