# Оновлення на сервері — інструкцію перенесено

Тут раніше було оновлення через `update.sh` і ручний варіант із `git reset --hard origin/main`, `pkill` та `run_script.sh` для старого shared-хостингу. На поточному VPS (`45.94.157.127`, systemd) це шкідливо: `reset --hard` стирає незакомічені зміни на сервері, а запуск `bot.py` поза systemd дає другий екземпляр бота. Детальніше — у `QUICK_DEPLOY.md`.

## Актуальний процес

Скіл `.claude/skills/gomon-deploy/SKILL.md` і розділ «Deploy Flow» у `CLAUDE.md`. Пуш і деплой — лише з явного дозволу на кожну дію.

Що змінилось порівняно зі старою інструкцією:

- **Бекап `config.py` і `users.db` перед оновленням не потрібен.** `config.py`, `config.php`, `prices.json`, `promos.json` і бази поза git, тож `git pull` їх не чіпає. Бази й так щодня бекапляться о 02:50 Києва в `/opt/gomon/backups/` (14 днів).
- **Бот не зупиняють руками.** Сервіси `gomon-api`, `gomon-bot`, `gomon-tgbiz` перезапускаються через `systemctl restart` і лише ті, чий код змінився.
- **Залежності** — у venv `/opt/gomon/venv`: `/opt/gomon/venv/bin/pip install -r requirements.txt`, якщо змінився `requirements.txt`.
- **Перевірка:** `curl -s https://drgomon.beauty/api/health`, `systemctl is-active gomon-api gomon-bot gomon-tgbiz`, `journalctl -u <сервіс> -n 20`.

## Відкат

Не `reset --hard` на сервері. Відкотити коміт локально через `git revert <hash>`, запушити (з дозволу), на сервері `git pull` і перезапустити те, що змінилось. Дані — з `/opt/gomon/backups/`.
