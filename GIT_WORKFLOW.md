# Git Workflow & Version Control - GomonClinic Server

## 📋 Поточна конфігурація

### Git Repository
- **Location:** `/home/gomoncli` (home directory)
- **Remote:** https://github.com/I7AJIJIbI4/gomon_server.git
- **Branch:** main
- **User:** I7AJIJIbI4
- **Email:** samydoma@gmail.com

### Authentication
- **Method:** Personal Access Token (PAT)
- **Token:** Вбудовано в remote URL (приватний, не показувати!)
- **Формат URL:** `https://USERNAME:TOKEN@github.com/USER/REPO.git`

### Git версія
```bash
git --version
# git version 2.48.2
```

---

## 🚀 Базові команди

### Перевірка статусу
```bash
cd /home/gomoncli
git status
git status --short  # Короткий формат
```

### Перегляд змін
```bash
git diff                    # Unstaged зміни
git diff --staged           # Staged зміни
git diff HEAD               # Всі зміни
git log --oneline -10       # Останні 10 коммітів
git log --oneline --graph   # Граф коммітів
```

### Додавання файлів
```bash
# Конкретні файли
git add public_html/app/chat.php
git add zadarma/*.py

# Всі змінені файли
git add -u

# Всі файли (включно з новими)
git add .

# Інтерактивне додавання
git add -p
```

### Створення коміту
```bash
git commit -m "Короткий опис змін"

# Детальний коміт (відкриється редактор)
git commit

# Коміт з багаторядковим описом
git commit -m "feat: короткий заголовок

Детальний опис що змінилось:
- Пункт 1
- Пункт 2
- Пункт 3"
```

### Синхронізація з GitHub
```bash
# Отримати зміни з GitHub
git fetch origin
git pull origin main

# Відправити зміни на GitHub
git push origin main

# Force push (ОБЕРЕЖНО! Перезаписує історію)
git push origin main --force
```

---

## 📝 Конвенція коммітів

### Формат
```
<type>: <short description>

<optional detailed description>

<optional footer>
```

### Types
- **feat:** Нова функціональність
- **fix:** Виправлення бага
- **docs:** Оновлення документації
- **style:** Форматування, відступи (без змін функціональності)
- **refactor:** Рефакторинг коду
- **perf:** Оптимізація продуктивності
- **test:** Додавання/оновлення тестів
- **chore:** Технічні зміни (build, config, cron тощо)

### Приклади
```bash
git commit -m "feat: add PWA app recommendation to AI system prompt"
git commit -m "fix: resolve bold text rendering issue in widget"
git commit -m "docs: update deployment instructions"
git commit -m "chore: update Service Worker cache version"
```

---

## 🔄 Робочий процес (Workflow)

### 1. Перед початком роботи
```bash
cd /home/gomoncli

# Перевірити статус
git status

# Отримати останні зміни (якщо працюєш з декількох місць)
git pull origin main
```

### 2. Робота над змінами
```bash
# Редагуй файли...

# Перевіряй що змінилось
git status
git diff

# Додавай файли поступово
git add public_html/app/chat.php
git add zadarma/sync_appointments.py
```

### 3. Створення коміту
```bash
# Перевір що додано
git status

# Створи коміт
git commit -m "feat: hourly appointment sync system

- Created sync_appointments.py for optimized sync (7d back, 90d forward)
- Setup cron job for hourly execution
- Updated sync documentation"
```

### 4. Відправка на GitHub
```bash
# Спробуй звичайний push
git push origin main

# Якщо є конфлікти - отримай зміни
git pull origin main --rebase

# Відправ ще раз
git push origin main
```

---

## ⚠️ Troubleshooting

### Проблема 1: Resource temporarily unavailable
```
fatal: unable to create thread: Resource temporarily unavailable
fatal: the remote end hung up unexpectedly
```

**Причина:** Shared hosting має обмеження на процеси/пам'ять

**Рішення 1 - Clone на локальну машину:**
```bash
# На твоєму Mac/PC:
cd ~/Projects
git clone https://github.com/I7AJIJIbI4/gomon_server.git
cd gomon_server

# Додай server як remote
git remote add server ssh://gomoncli@31.131.18.79:21098/home/gomoncli

# Отримай зміни з сервера
git fetch server
git merge server/main

# Пуш на GitHub з локальної машини
git push origin main
```

**Рішення 2 - Збільшити buffer:**
```bash
git config http.postBuffer 1048576000
git config http.lowSpeedLimit 0
git config http.lowSpeedTime 999999
git push origin main
```

**Рішення 3 - Пакетний push (малими коммітами):**
Якщо initial commit дуже великий, можна розділити файли на частини.

### Проблема 2: Rejected push (diverged branches)
```
! [rejected]        main -> main (fetch first)
error: failed to push some refs
```

**Рішення:**
```bash
# Варіант A - Rebase (якщо немає важливих змін на GitHub)
git fetch origin
git rebase origin/main
# Розв'язати конфлікти якщо є
git push origin main

# Варіант B - Merge
git pull origin main
# Розв'язати конфлікти якщо є
git push origin main

# Варіант C - Force push (ТІЛЬКИ якщо впевнений!)
git push origin main --force
```

### Проблема 3: Merge conflicts
```
CONFLICT (content): Merge conflict in file.php
```

**Рішення:**
```bash
# 1. Перевір які файли в конфлікті
git status

# 2. Відкрий файл і знайди маркери конфлікту:
# <<<<<<< HEAD
# твій код
# =======
# чужий код
# >>>>>>> origin/main

# 3. Відредагуй файл, видали маркери, залиш потрібний код

# 4. Додай розв'язаний файл
git add file.php

# 5. Продовж merge/rebase
git rebase --continue
# або
git merge --continue

# Щоб скасувати merge/rebase:
git rebase --abort
git merge --abort
```

### Проблема 4: Accidentally committed wrong files
```bash
# Видалити файл з останнього коміту (але залишити в робочій директорії)
git reset HEAD~1 file.txt

# Змінити останній коміт (додати/видалити файли)
git add forgotten_file.php
git commit --amend --no-edit

# Скасувати останній коміт повністю
git reset --soft HEAD~1  # Зміни залишаться в staging
git reset --hard HEAD~1  # Зміни будуть видалені (ОБЕРЕЖНО!)
```

---

## 📂 .gitignore - Що ігнорується

### Категорії ігнорованих файлів:

1. **Секрети і конфіги:**
   - `.env`, `config.py`, `*.pem`, `*.key`
   - `private_data/`

2. **Бази даних:**
   - `*.db`, `*.sqlite`

3. **Системні директорії хостингу:**
   - `.ssh/`, `.cpanel/`, `logs/`, `mail/`, `backup/`

4. **Backup файли:**
   - `*.backup`, `*.bak`
   - `*.backup_[0-9]*` (timestamp backups)
   - `*_backup_*.py`

5. **Runtime файли:**
   - `*.log`, `*.pid`, `__pycache__/`, `*.pyc`

6. **Медіа файли:**
   - `public_html/sitepro/gallery/`
   - `public_html/sitepro/gallery_gen/`

7. **Тимчасові:**
   - `tmp/`, `.DS_Store`

### Додати нові правила:
```bash
echo "new_folder/" >> .gitignore
git add .gitignore
git commit -m "chore: update gitignore"
```

---

## 🔐 Оновлення токену (PAT)

Якщо токен застарів або треба змінити:

### 1. Створити новий PAT на GitHub
1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token
3. Scope: `repo` (full control)
4. Скопіюй токен (показується тільки раз!)

### 2. Оновити remote URL
```bash
cd /home/gomoncli

# Видалити старий remote
git remote remove origin

# Додати новий з новим токеном
git remote add origin https://USERNAME:NEW_TOKEN@github.com/I7AJIJIbI4/gomon_server.git

# Перевірити
git remote -v
```

### 3. Або змінити існуючий
```bash
git remote set-url origin https://USERNAME:NEW_TOKEN@github.com/I7AJIJIbI4/gomon_server.git
```

---

## 📊 Корисні команди

### Перегляд історії
```bash
# Детальна історія з diffstat
git log --stat

# Історія з графом
git log --oneline --graph --all --decorate

# Пошук по коммітам
git log --grep="widget"
git log --author="I7AJIJIbI4"

# Файли змінені в коміті
git show <commit-hash>
git show HEAD
```

### Порівняння
```bash
# Порівняти з попереднім коммітом
git diff HEAD~1

# Порівняти дві гілки
git diff main origin/main

# Показати що змінилось у файлі
git log -p public_html/app/chat.php
```

### Скасування змін
```bash
# Відкинути зміни в робочій директорії
git restore file.php
git checkout -- file.php

# Відкинути зміни в staging
git restore --staged file.php
git reset HEAD file.php

# Повернутись до певного коміту
git reset --hard <commit-hash>
```

### Теги (версії)
```bash
# Створити тег
git tag v1.0.0
git tag -a v1.0.0 -m "Version 1.0.0 - Initial release"

# Відправити теги на GitHub
git push origin --tags

# Показати теги
git tag
git show v1.0.0
```

---

## 🔄 Deployment Workflow

### Варіант 1: Прямо на сервері (поточний)
```bash
ssh -i ~/.ssh/id_rsa -p 21098 gomoncli@31.131.18.79

cd /home/gomoncli

# Редагуй файли...

git add .
git commit -m "feat: add new feature"

# Якщо push не працює через ресурси - clone локально (див. Troubleshooting)
```

### Варіант 2: Розробка локально + deploy (рекомендується)
```bash
# 1. На локальній машині
cd ~/Projects/gomon_server

# 2. Робота з кодом
# ... редагуй файли ...

git add .
git commit -m "feat: new feature"
git push origin main

# 3. Deploy на сервер через SSH
ssh -i ~/.ssh/id_rsa -p 21098 gomoncli@31.131.18.79 "cd /home/gomoncli && git pull origin main"

# 4. Перезапуск сервісів (якщо потрібно)
ssh -i ~/.ssh/id_rsa -p 21098 gomoncli@31.131.18.79 "cd /home/gomoncli/zadarma && ./check_flask.sh && ./check_and_run_bot.sh"
```

### Варіант 3: Automated deployment (майбутнє)
Можна налаштувати GitHub Actions або webhook для автоматичного deployment при push.

---

## 📈 Статистика

```bash
# Кількість коммітів
git rev-list --count HEAD

# Кількість коммітів по авторам
git shortlog -sn

# Розмір репозиторію
du -sh .git

# Найбільші файли в історії
git rev-list --objects --all | grep "$(git verify-pack -v .git/objects/pack/*.idx | sort -k 3 -n | tail -10 | awk '{print$1}')"
```

---

## 🎯 Best Practices

1. **Коммить часто** - маленькі, логічні зміни краще великих
2. **Описові повідомлення** - пиши чіткі commit messages
3. **Pull перед push** - завжди перевіряй чи є нові зміни
4. **Не коммить секрети** - перевіряй .gitignore перед commit
5. **Backup** - GitHub = автоматичний backup коду
6. **Теги для версій** - позначай важливі релізи тегами
7. **Branch для features** - великі зміни роби в окремих гілках

---

## 🆘 Швидка допомога

### Забув що робив
```bash
git status
git diff
git log --oneline -5
```

### Хочу скасувати все
```bash
git reset --hard HEAD
git clean -fd  # Видалити untracked файли
```

### Хочу подивитись старий код
```bash
git log --oneline
git checkout <commit-hash>
# Подивись код...
git checkout main  # Повернутись
```

### Видалити файл з Git (але залишити на диску)
```bash
git rm --cached file.txt
echo "file.txt" >> .gitignore
git commit -m "chore: remove file.txt from tracking"
```

### Перемістити останні N коммітів в нову гілку
```bash
git branch new-feature
git reset --hard HEAD~N
git checkout new-feature
```

---

## 📚 Ресурси

- **GitHub Repo:** https://github.com/I7AJIJIbI4/gomon_server
- **Git Docs:** https://git-scm.com/doc
- **Git Book:** https://git-scm.com/book/uk/v2

---

## 🚀 Швидкий старт для push з локальної машини

Через проблеми з ресурсами на shared hosting, рекомендується:

1. **Clone репозиторій локально:**
```bash
git clone https://github.com/I7AJIJIbI4/gomon_server.git
cd gomon_server
```

2. **Додати server як додатковий remote:**
```bash
git remote add server ssh://gomoncli@31.131.18.79:21098/home/gomoncli
```

3. **Синхронізація:**
```bash
# Отримати зміни з сервера
git fetch server
git merge server/main --allow-unrelated-histories

# Відправити на GitHub
git push origin main
```

4. **Оновити сервер з GitHub (коли потрібно):**
```bash
ssh -i ~/.ssh/id_rsa -p 21098 gomoncli@31.131.18.79 "cd /home/gomoncli && git pull origin main"
```

---

**Останнє оновлення:** 2026-03-27
**Коміт:** 0358750 - Major improvements (AI, sync, mobile widget)
**Status:** ✅ Git налаштовано, коміт створено, push потребує локальну машину
