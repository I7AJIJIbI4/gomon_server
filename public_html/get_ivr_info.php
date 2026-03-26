<?php
/**
 * Скрипт для отримання поточних IVR налаштувань Zadarma
 */

// Конфігурація
$config = [
    'zadarma_key' => 'YOUR_ZADARMA_KEY',
    'zadarma_secret' => 'YOUR_ZADARMA_SECRET'
];

function makeZadarmaAPICall($method, $params = [], $requestType = 'GET', $config) {
    // Сортуємо параметри
    ksort($params);
    $paramsString = http_build_query($params);
    
    // Створюємо підпис (як у вашому робочому коді)
    $stringToSign = $method . $paramsString . md5($paramsString);
    $hmacHex = hash_hmac('sha1', $stringToSign, $config['zadarma_secret']);
    $signature = base64_encode($hmacHex);
    
    // Заголовки
    $headers = [
        'Authorization: ' . $config['zadarma_key'] . ':' . $signature,
        'Content-Type: application/x-www-form-urlencoded'
    ];
    
    // URL
    $url = 'https://api.zadarma.com' . $method;
    if ($requestType === 'GET' && $paramsString) {
        $url .= '?' . $paramsString;
    }
    
    echo "🔗 API URL: $url\n";
    echo "🔑 Signature: $signature\n\n";
    
    // CURL запит
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 30);
    
    if ($requestType === 'POST') {
        curl_setopt($ch, CURLOPT_POST, true);
        if ($paramsString) {
            curl_setopt($ch, CURLOPT_POSTFIELDS, $paramsString);
        }
    }
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $curlError = curl_error($ch);
    curl_close($ch);
    
    echo "📡 HTTP Code: $httpCode\n";
    if ($curlError) {
        echo "❌ CURL Error: $curlError\n";
    }
    
    echo "📄 Response: $response\n\n";
    
    if ($httpCode === 200) {
        return json_decode($response, true);
    }
    
    return false;
}

echo "=== ОТРИМАННЯ ПОТОЧНИХ IVR НАЛАШТУВАНЬ ===\n\n";

// 1. Отримуємо список IVR меню
echo "1️⃣ ОТРИМАННЯ СПИСКУ IVR МЕНЮ:\n";
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
$ivrs = makeZadarmaAPICall('/v1/pbx/ivr/', [], 'GET', $config);

if ($ivrs && isset($ivrs['ivrs'])) {
    echo "✅ Знайдено IVR меню:\n";
    foreach ($ivrs['ivrs'] as $ivr) {
        echo "  📋 Menu ID: {$ivr['menu_id']}\n";
        echo "  📝 Title: " . ($ivr['title'] ?: 'Без назви') . "\n";
        echo "  🔄 Status: {$ivr['status']}\n";
        echo "  ⏱️  Wait extension: {$ivr['waitexten']}\n";
        echo "  🎭 Type: {$ivr['type']}\n";
        
        if (isset($ivr['auto_responder'])) {
            echo "  📞 Auto responder: {$ivr['auto_responder']['status']}\n";
        }
        echo "  ────────────────────────────────────────────────\n";
        
        // 2. Для кожного меню отримуємо сценарії
        echo "\n2️⃣ СЦЕНАРІЇ ДЛЯ МЕНЮ {$ivr['menu_id']}:\n";
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
        
        $scenarios = makeZadarmaAPICall('/v1/pbx/ivr/scenario/', ['menu_id' => $ivr['menu_id']], 'GET', $config);
        
        if ($scenarios && isset($scenarios['scenarios'])) {
            echo "✅ Знайдено сценарії:\n";
            foreach ($scenarios['scenarios'] as $scenario) {
                echo "  🎯 Scenario ID: {$scenario['id']}\n";
                echo "  📝 Title: {$scenario['title']}\n";
                echo "  🔢 Push button: {$scenario['push_button']}\n";
                
                if (!empty($scenario['first_sips'])) {
                    echo "  📞 First SIPs: " . implode(', ', $scenario['first_sips']) . "\n";
                }
                if (!empty($scenario['second_sips'])) {
                    echo "  📞 Second SIPs: " . implode(', ', $scenario['second_sips']) . "\n";
                    echo "  ⏱️  Second delay: {$scenario['second_sips_delay']}s\n";
                }
                if (!empty($scenario['third_sips'])) {
                    echo "  📞 Third SIPs: " . implode(', ', $scenario['third_sips']) . "\n";
                    echo "  ⏱️  Third delay: {$scenario['third_sips_delay']}s\n";
                }
                echo "  ────────────────────────────────────────────────\n";
            }
        } else {
            echo "❌ Не вдалося отримати сценарії або вони відсутні\n";
        }
        echo "\n";
    }
} else {
    echo "❌ Не вдалося отримати IVR меню\n";
}

// 3. Отримуємо список звукових файлів
echo "\n3️⃣ ЗВУКОВІ ФАЙЛИ В СХОВИЩІ:\n";
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
$sounds = makeZadarmaAPICall('/v1/pbx/ivr/sounds/list', [], 'GET', $config);

if ($sounds) {
    echo "✅ Звукові файли:\n";
    if (isset($sounds['sounds']) && is_array($sounds['sounds'])) {
        foreach ($sounds['sounds'] as $sound) {
            echo "  🎵 ID: {$sound['id']}\n";
            echo "  📝 Name: {$sound['name']}\n";
            echo "  📏 Duration: {$sound['duration']}s\n";
            echo "  ────────────────────────────────────────────────\n";
        }
    } else {
        echo "  📭 Немає звукових файлів або інший формат відповіді\n";
    }
} else {
    echo "❌ Не вдалося отримати список звукових файлів\n";
}

echo "\n🎯 АНАЛІЗ ЗАВЕРШЕНО!\n";
echo "Тепер ви можете побачити повну конфігурацію вашого IVR\n";
?>