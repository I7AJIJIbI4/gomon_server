#!/bin/bash
# git_fix_rebase.sh - Виправлення проблеми з rebase

echo "🔧 ВИПРАВЛЕННЯ ПРОБЛЕМИ З REBASE"
echo "================================"

log() {
    echo "[$(date '+%H:%M:%S')] $1"
}

log "📋 Поточний статус Git:"
git status

echo
log "💡 У вас є незакоммічені зміни. Варіанти:"
echo "1. Закоммітити зміни та продовжити rebase"
echo "2. Stash зміни (тимчасово сховати) та rebase"
echo "3. Скасувати всі незбережені зміни"
echo

read -p "Оберіть варіант (1/2/3): " -n 1 -r
echo

case $REPLY in
    1)
        log "💾 Коммітимо зміни..."
        git add .
        echo
        echo "Введіть повідомлення для коміту (або натисніть Enter для стандартного):"
        read -r commit_message
        
        if [[ -z "$commit_message" ]]; then
            commit_message="🔧 Apply fixes: wlaunch sync, webhook logic, and diagnostic tools"
        fi
        
        git commit -m "$commit_message"
        
        if [[ $? -eq 0 ]]; then
            log "✅ Зміни закоммічено"
            
            # Тепер робимо rebase
            log "🔄 Виконуємо rebase..."
            git pull --rebase origin main
            
            if [[ $? -eq 0 ]]; then
                log "✅ Rebase успішний"
                
                # Пушимо
                log "📤 Пушимо на GitHub..."
                git push origin main
                
                if [[ $? -eq 0 ]]; then
                    log "🎉 Все готово!"
                else
                    log "❌ Помилка при push"
                fi
            else
                log "❌ Конфлікти при rebase"
                echo "Перевірте файли з конфліктами та виконайте:"
                echo "git add ."
                echo "git rebase --continue"
                echo "git push origin main"
            fi
        else
            log "❌ Помилка при коміті"
        fi
        ;;
        
    2)
        log "📦 Ховаємо зміни в stash..."
        git stash push -m "WIP: fixes before rebase $(date)"
        
        if [[ $? -eq 0 ]]; then
            log "✅ Зміни сховано"
            
            # Робимо rebase
            log "🔄 Виконуємо rebase..."
            git pull --rebase origin main
            
            if [[ $? -eq 0 ]]; then
                log "✅ Rebase успішний"
                
                # Повертаємо зміни
                log "📦 Повертаємо зміни з stash..."
                git stash pop
                
                if [[ $? -eq 0 ]]; then
                    log "✅ Зміни повернуто"
                    echo
                    echo "Тепер закоммітьте зміни:"
                    echo "git add ."
                    echo "git commit -m 'Apply fixes'"
                    echo "git push origin main"
                else
                    log "❌ Конфлікти при поверненні stash"
                    echo "Вирішіть конфлікти та виконайте:"
                    echo "git add ."
                    echo "git stash drop"  # Видалити stash після вирішення
                fi
            else
                log "❌ Конфлікти при rebase"
                echo "Вирішіть конфлікти, потім:"
                echo "git add ."
                echo "git rebase --continue"
                echo "git stash pop"  # Повернути зміни після rebase
            fi
        else
            log "❌ Помилка при stash"
        fi
        ;;
        
    3)
        log "⚠️ УВАГА: Це видалить всі незбережені зміни!"
        read -p "Ви впевнені? Введіть 'YES' для підтвердження: " confirm
        
        if [[ "$confirm" == "YES" ]]; then
            log "🗑️ Скидаємо всі зміни..."
            git reset --hard HEAD
            git clean -fd
            
            # Тепер робимо rebase
            log "🔄 Виконуємо rebase..."
            git pull --rebase origin main
            
            if [[ $? -eq 0 ]]; then
                log "✅ Rebase успішний"
                git push origin main
                log "🎉 Синхронізація завершена"
            else
                log "❌ Помилка при rebase"
            fi
        else
            log "❌ Скасовано"
        fi
        ;;
        
    *)
        log "❌ Невірний вибір"
        exit 1
        ;;
esac

echo
log "📊 Фінальний статус:"
git status
