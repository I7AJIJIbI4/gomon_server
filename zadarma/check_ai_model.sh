#!/bin/bash
# check_ai_model.sh — перевіряє доступність моделі Claude, оновлює кеш

CACHE_FILE="/home/gomoncli/private_data/active_model.txt"
LOG="/home/gomoncli/zadarma/check_model.log"
TG_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
TG_CHAT="573368771"
API_KEY="YOUR_ANTHROPIC_API_KEY"

MODELS=(
  "claude-sonnet-4-6"
  "claude-sonnet-4-5"
  "claude-3-5-sonnet-20241022"
  "claude-haiku-4-5-20251001"
)

tg() {
  curl -s -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
    -d "chat_id=${TG_CHAT}" -d "text=$1" -d "parse_mode=HTML" > /dev/null
}

test_model() {
  local model="$1"
  local resp=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "https://api.anthropic.com/v1/messages" \
    -H "Content-Type: application/json" \
    -H "x-api-key: ${API_KEY}" \
    -H "anthropic-version: 2023-06-01" \
    -d "{\"model\":\"${model}\",\"max_tokens\":10,\"messages\":[{\"role\":\"user\",\"content\":\"Hi\"}]}" \
    --max-time 15)
  echo "$resp"
}

CURRENT=$(cat "$CACHE_FILE" 2>/dev/null || echo "${MODELS[0]}")
DATE=$(date '+%Y-%m-%d %H:%M')

# Перевіряємо поточну модель
CODE=$(test_model "$CURRENT")

if [ "$CODE" = "200" ]; then
  echo "$DATE OK: $CURRENT" >> "$LOG"
  exit 0
fi

# Поточна не працює — шукаємо першу робочу
echo "$DATE WARN: $CURRENT повернула $CODE, шукаємо альтернативу..." >> "$LOG"

for MODEL in "${MODELS[@]}"; do
  [ "$MODEL" = "$CURRENT" ] && continue
  CODE2=$(test_model "$MODEL")
  if [ "$CODE2" = "200" ]; then
    echo "$MODEL" > "$CACHE_FILE"
    echo "$DATE UPDATED: $CURRENT → $MODEL" >> "$LOG"
    tg "⚠️ <b>GomonAI: модель оновлено</b>%0A$CURRENT → <b>$MODEL</b>%0AПричина: HTTP $CODE"
    exit 0
  fi
done

# Жодна не працює
echo "$DATE ERROR: всі моделі недоступні" >> "$LOG"
tg "🚨 <b>GomonAI: всі моделі недоступні!</b>%0AОстання спроба: $CURRENT (HTTP $CODE)"
