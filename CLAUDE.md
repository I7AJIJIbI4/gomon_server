# GomonClinic Server — Правила роботи

## Документування змін

**Кожна зміна коду має бути задокументована перед пушем у git.**

### Що документувати

Для кожної зміни вказати:
- **Що змінено** — файл, функція, endpoint
- **Чому** — яка проблема була, що не працювало
- **Як виправлено** — суть рішення

### Де документувати

1. **Git commit message** — обов'язково. Формат:
   ```
   fix/feat/refactor: коротка суть (до 72 символів)

   - Bug: опис проблеми
   - Fix: що зроблено
   - Files: які файли змінено
   ```

2. **GitHub PR** — для кожного набору змін відкривати PR з описом:
   - Список багів/задач
   - Що і чому змінено по кожному файлу
   - Як перевірити що працює

3. **CHANGELOG.md** (у корені репо) — для значних змін додавати запис.

### Приклад хорошого commit message

```
fix: appointment cancel + enhanced conversions + chat tracking

- Bug: parse_services не повертав appt_id → кнопка скасування не працювала
- Bug: відсутній endpoint /api/me/appointments/cancel → 404
- Bug: r.ok перевіряв JSON замість HTTP статусу
- Fix: додано cancel endpoint, виправлено parse_services та перевірку r.ok
- Fix: allow_enhanced_conversions для Google Ads (4 попередження)
- Fix: gtag conversion для GomonAI чату (WaavCKa45JAcELuXlNcC)
```

### Що НЕ допускається

- Пуш без commit message або з повідомленням типу fix, update, changes
- Зміни напряму в main без PR (для нетривіальних змін)
- Зміни на сервері без синхронізації з git ( + On branch main
Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   README.md

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	.CFUserTextEncoding
	.DS_Store
	.cache/
	.claude.json
	.claude.json.backup
	.claude/
	.codex/
	.config/
	.copilot/
	.cursor/
	.docker/
	.dotnet/
	.gitconfig
	.gitconfig-work
	.idlerc/
	.lesshst
	.local/
	.npm/
	.nuget/
	.nvm/
	.remember/
	.rest-client/
	.snipaste/
	.ssh/
	.swiftpm/
	.viminfo
	.vscode/
	.zcompdump
	.zsh_history
	.zsh_sessions/
	.zshrc
	Applications/
	Desktop/
	Documents/
	Downloads/
	Library/
	Movies/
	Music/
	Pictures/
	Projects/
	Public/
	Samsung/
	avatarmy-internal/
	ivan.pavlovskyi@masterofcode.com - Google Drive
	node_modules/
	package-lock.json
	package.json
	samydoma@gmail.com - Google Drive

no changes added to commit (use "git add" and/or "git commit -a") + )

## Структура проекту

-  — Flask API для PWA (порт 5001, 127.0.0.1)
-  — PWA фронтенд
-  — AI чат-віджет
-  — основний сайт gomonclinic.com
-  — інтеграція з Zadarma (дзвінки, вебхуки)

## Git workflow

```bash
cd /home/gomoncli
git checkout -b fix/назва-задачі   # нова гілка
# ... вносимо зміни ...
git add <файли>
git commit -m fix: опис
git push origin fix/назва-задачі
# відкрити PR на GitHub
```
