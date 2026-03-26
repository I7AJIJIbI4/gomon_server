#!/bin/bash

echo "🎵 Перевірка звукових файлів в Zadarma..."

METHOD="/v1/pbx/ivr/sounds/list"
KEY="YOUR_ZADARMA_KEY"
SECRET="YOUR_ZADARMA_SECRET"

# Для GET запиту без параметрів
PARAMS=""
STRING_TO_SIGN="${METHOD}${PARAMS}$(echo -n "${PARAMS}" | md5sum | cut -d' ' -f1)"

echo "🔍 Debug підпису:"
echo "Method: $METHOD"
echo "Params: $PARAMS"
echo "String to sign: $STRING_TO_SIGN"

SIGNATURE=$(echo -n "$STRING_TO_SIGN" | openssl dgst -sha1 -hmac "$SECRET" -binary | base64)

echo "Signature: $SIGNATURE"
echo ""

echo "🔍 Отримуємо список файлів..."
RESPONSE=$(curl "https://api.zadarma.com${METHOD}" \
  -H "Authorization: ${KEY}:${SIGNATURE}" \
  -s)

echo "Response: $RESPONSE"

if echo "$RESPONSE" | grep -q '"status":"success"'; then
    echo ""
    echo "✅ Успішно! Форматуємо JSON:"
    echo "$RESPONSE" | python3 -m json.tool
    
    echo ""
    echo "🎯 Шукаємо файли Лаури:"
    echo "$RESPONSE" | grep -i "laura\|door\|gate\|telegram"
else
    echo ""
    echo "❌ Помилка API. Пробуємо альтернативний підпис..."
    
    # Альтернативний спосіб
    ALT_STRING="${METHOD}$(echo -n "" | md5sum | cut -d' ' -f1)"
    ALT_SIGNATURE=$(echo -n "$ALT_STRING" | openssl dgst -sha1 -hmac "$SECRET" -binary | base64)
    
    echo "Alternative signature: $ALT_SIGNATURE"
    
    ALT_RESPONSE=$(curl "https://api.zadarma.com${METHOD}" \
      -H "Authorization: ${KEY}:${ALT_SIGNATURE}" \
      -s)
    
    echo "Alternative response: $ALT_RESPONSE"
fi
