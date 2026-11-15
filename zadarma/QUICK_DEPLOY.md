# Деплой — інструкцію перенесено

Тут раніше був опис деплою на старий shared-хостинг (`uashared35.ukraine.com.ua`) через скрипти `update.sh`, `quick_deploy.sh` і `deploy.sh`. З квітня 2026 проєкт працює на VPS `45.94.157.127` під systemd, тож ці скрипти **не запускати**:

- `update.sh` робить `git reset --hard origin/main` — стирає на сервері все незакомічене (так 07.06.2026 зникла жива правка `system_prompt.txt`);
- він же зупиняє бота через `pkill` і запускає `bot.py` через `nohup` поза systemd — виходить другий екземпляр поруч із `gomon-bot.service`;
- `deploy.sh` просто викликає `update.sh`.

## Актуальний процес

- **Скіл `.claude/skills/gomon-deploy/SKILL.md`** — що перезапускати після якої зміни, bump `sw.js` і `?v=` віджета, перевірки до й після.
- **Розділ «Deploy Flow» у `CLAUDE.md`** — загальна схема і доступ до сервера.

Пуш і деплой — лише з явного дозволу на кожну дію (`gomon-rules`).

Коротко:
```bash
ssh root@45.94.157.127 'cd /opt/gomon/app && git status --short'   # змінені відстежувані файли — зупинись
ssh root@45.94.157.127 'cd /opt/gomon/app && git pull'             # не reset --hard
ssh root@45.94.157.127 'systemctl restart gomon-api'               # лише те, що змінилось: див. gomon-deploy
curl -s https://drgomon.beauty/api/health
```
