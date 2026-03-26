<?php
/**
 * МОДИФІКАЦІЯ ІСНУЮЧИХ IVR СЦЕНАРІЇВ ZADARMA
 * Зміна поточних сценаріїв для прямих callback'ів
 */

// Конфігурація
$config = [
    'zadarma_key' => 'YOUR_ZADARMA_KEY',
    'zadarma_secret' => 'YOUR_ZADARMA_SECRET'
];

function makeZadarmaAPICall($method, $params = [], $requestType = 'GET', $config) {
    ksort($params);
    $paramsString = http_build_query($params);
    
    $stringToSign = $method . $paramsString . md5($paramsString);
    $hmacHex = hash_hmac('sha1', $stringToSign, $config['zadarma_secret']);
    $signature = base64_encode($hmacHex);
    
    $headers = [
        'Authorization: ' . $config['zadarma_key'] . ':' . $signature,
        'Content-Type: application/x-www-form-urlencoded'
    ];
    
    $url = 'https://api.zadarma.com' . $method;
    if ($requestType === 'GET' && $paramsString) {
        $url .= '?' . $paramsString;
    }
    
    echo "🔗 API URL: $url\n";
    echo "🔑 Signature: " . substr($signature, 0, 20) . "...\n\n";
    
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
    } elseif ($requestType === 'PUT') {
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'PUT');
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($params));
        curl_setopt($ch, CURLOPT_HTTPHEADER, array_merge($headers, ['Content-Type: application/json']));
    } elseif ($requestType === 'DELETE') {
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'DELETE');
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

// ========================================
// ВАРІАНТ 1: ПРЯМІ CALLBACK'И (РЕКОМЕНДУЮ)
// ========================================

function createDirectCallbackScenarios() {
    global $config;
    
    echo "=== СТВОРЕННЯ ПРЯМИХ CALLBACK СЦЕНАРІЇВ ===\n\n";
    
    // Спочатку видаляємо старі сценарії
    $oldScenarios = [
        '687a97edd0c7d2d570050659', // hvirtka
        '687a97edd0c7d2d570050657', // Vorota  
        '687a97edd0c7d2d570050658'  // SMS
    ];
    
    foreach ($oldScenarios as $scenarioId) {
        echo "🗑️ Видалення старого сценарія: $scenarioId\n";
        $result = makeZadarmaAPICall('/v1/pbx/ivr/scenario/delete/', ['scenario_id' => $scenarioId], 'DELETE', $config);
    }
    
    // Створюємо нові сценарії з прямими callback'ами
    $newScenarios = [
        [
            'push_button' => 1,
            'title' => 'Хвіртка - прямий callback',
            'extension' => '0637442017', // Прямий номер хвіртки
            'menu_id' => 1
        ],
        [
            'push_button' => 2, 
            'title' => 'Ворота - прямий callback',
            'extension' => '0930063585', // Прямий номер воріт
            'menu_id' => 1
        ],
        [
            'push_button' => 3,
            'title' => 'SMS через webhook',
            'extension' => 'webhook', // Спеціальний обробник для SMS
            'menu_id' => 1
        ]
    ];
    
    foreach ($newScenarios as $scenario) {
        echo "➕ Створення нового сценарія: {$scenario['title']}\n";
        $result = makeZadarmaAPICall('/v1/pbx/ivr/scenario/create/', $scenario, 'POST', $config);
        
        if ($result && isset($result['scenario_id'])) {
            echo "✅ Сценарій створено з ID: {$result['scenario_id']}\n\n";
        } else {
            echo "❌ Помилка створення сценарія\n\n";
        }
    }
}

// ========================================
// ВАРІАНТ 2: МОДИФІКАЦІЯ ІСНУЮЧИХ
// ========================================

function modifyExistingScenarios() {
    global $config;
    
    echo "=== МОДИФІКАЦІЯ ІСНУЮЧИХ СЦЕНАРІЇВ ===\n\n";
    
    // Використовуємо PUT запити для зміни існуючих сценаріїв
    $scenarios = [
        [
            'id' => '687a97edd0c7d2d570050659', // hvirtka
            'title' => 'Хвіртка оптимізована',
            'queue_strategy' => 'off',
            'queue_announce_position' => 0,
            'numbers' => [
                [
                    'number' => '0637442017', // Прямий номер замість 101
                    'delay' => 0,
                    'duration' => 30
                ]
            ]
        ],
        [
            'id' => '687a97edd0c7d2d570050657', // Vorota
            'title' => 'Ворота оптимізовані',
            'queue_strategy' => 'off', 
            'queue_announce_position' => 0,
            'numbers' => [
                [
                    'number' => '0930063585', // Прямий номер замість 102
                    'delay' => 0,
                    'duration' => 30
                ]
            ]
        ],
        [
            'id' => '687a97edd0c7d2d570050658', // SMS
            'title' => 'SMS оптимізований',
            'queue_strategy' => 'off',
            'queue_announce_position' => 0,
            'numbers' => [
                [
                    'number' => 'webhook', // Webhook обробник
                    'delay' => 0,
                    'duration' => 5
                ]
            ]
        ]
    ];
    
    foreach ($scenarios as $scenario) {
        echo "🔧 Модифікація сценарія: {$scenario['title']} (ID: {$scenario['id']})\n";
        $result = makeZadarmaAPICall('/v1/pbx/ivr/scenario/edit/', $scenario, 'PUT', $config);
        
        if ($result && isset($result['status']) && $result['status'] === 'success') {
            echo "✅ Сценарій успішно оновлено\n\n";
        } else {
            echo "❌ Помилка оновлення сценарія\n\n";
        }
    }
}

// ========================================
// ВАРІАНТ 3: ПОЕТАПНА ЗМІНА
// ========================================

function stepByStepModification() {
    global $config;
    
    echo "=== ПОЕТАПНА МОДИФІКАЦІЯ (БЕЗПЕЧНО) ===\n\n";
    
    // Крок 1: Спочатку тестуємо на одному сценарії
    echo "📍 КРОК 1: Тестова модифікація сценарія хвіртки\n";
    
    $testScenario = [
        'id' => '687a97edd0c7d2d570050659', // hvirtka
        'title' => 'Хвіртка ТЕСТ',
        'queue_strategy' => 'off',
        'queue_announce_position' => 0,
        'numbers' => [
            [
                'number' => '0637442017', // Прямий callback
                'delay' => 0,
                'duration' => 30
            ]
        ]
    ];
    
    echo "🧪 Тестування зміни сценарія хвіртки...\n";
    $result = makeZadarmaAPICall('/v1/pbx/ivr/scenario/edit/', $testScenario, 'PUT', $config);
    
    if ($result && isset($result['status']) && $result['status'] === 'success') {
        echo "✅ ТЕСТ УСПІШНИЙ! Можна продовжувати\n\n";
        
        echo "📍 КРОК 2: Інструкції для тестування\n";
        echo "1. Подзвоніть на 0733103110\n";
        echo "2. Натисніть кнопку 1 (хвіртка)\n";
        echo "3. Перевірте чи відкривається хвіртка БЕЗ webhook'а\n";
        echo "4. Якщо працює - запустіть повну модифікацію\n\n";
        
        return true;
    } else {
        echo "❌ ТЕСТ НЕВДАЛИЙ! Перевірте параметри\n\n";
        return false;
    }
}

function completeModification() {
    echo "📍 КРОК 3: Повна модифікація всіх сценаріїв\n";
    echo "Запустіть modifyExistingScenarios() після успішного тесту\n\n";
}

// ========================================
// ПОРІВНЯННЯ ПІДХОДІВ
// ========================================

function compareApproaches() {
    echo "=== ПОРІВНЯННЯ ПІДХОДІВ ===\n\n";
    
    echo "🎯 ПОТОЧНА СХЕМА (що працює):\n";
    echo "   Кнопка → Internal 101/102/103 → NOTIFY_INTERNAL → Ваш webhook → API callback\n";
    echo "   ➕ Працює стабільно\n";
    echo "   ➕ Детальне логування\n";
    echo "   ➖ Додаткові webhook запити\n";
    echo "   ➖ Затримка через проміжні кроки\n\n";
    
    echo "🎯 НОВА СХЕМА (пряма):\n";
    echo "   Кнопка → Прямий callback на 0637442017/0930063585\n";
    echo "   ➕ Швидше спрацювання\n";
    echo "   ➕ Менше навантаження на сервер\n";
    echo "   ➕ Простіша логіка\n";
    echo "   ➖ Менше контролю над процесом\n";
    echo "   ➖ Складніше налаштувати додаткові функції\n\n";
    
    echo "🎯 ГІБРИДНА СХЕМА (рекомендую):\n";
    echo "   Кнопка 1,2 → Прямі callback'и (швидкість)\n";
    echo "   Кнопка 3 → Webhook для SMS (гнучкість)\n";
    echo "   ➕ Кращє з обох світів\n";
    echo "   ➕ SMS залишається гнучким\n";
    echo "   ➕ Ворота/хвіртка працюють швидше\n\n";
}

// ========================================
// ОСНОВНА ФУНКЦІЯ
// ========================================

function main() {
    echo "=== МОДИФІКАЦІЯ ZADARMA IVR СЦЕНАРІЇВ ===\n\n";
    
    compareApproaches();
    
    echo "🎮 ОБЕРІТЬ ВАРІАНТ ВИКОНАННЯ:\n";
    echo "1️⃣ Поетапна модифікація (безпечно)\n";
    echo "2️⃣ Повна модифікація існуючих\n";
    echo "3️⃣ Створення нових сценаріїв\n";
    echo "4️⃣ Тільки аналіз (без змін)\n\n";
    
    // За замовчуванням запускаємо безпечний тест
    echo "🧪 ЗАПУСК ТЕСТОВОЇ МОДИФІКАЦІЇ:\n";
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
    
    if (stepByStepModification()) {
        echo "✅ Готово до повної модифікації!\n";
        echo "Запустіть modifyExistingScenarios() для завершення\n";
    }
}

// Розкоментуйте для запуску:
main();

// Або запустіть окремі функції:
// stepByStepModification();        // Безпечний тест
// modifyExistingScenarios();       // Повна модифікація
// createDirectCallbackScenarios(); // Створення нових

?>

<!-- 
=== РЕКОМЕНДОВАНИЙ ПЛАН ===

1. ТЕСТ (5 хвилин):
   - Запустіть stepByStepModification()
   - Протестуйте хвіртку
   - Переконайтеся що працює

2. ПОВНА МОДИФІКАЦІЯ (якщо тест успішний):
   - Запустіть modifyExistingScenarios()
   - Протестуйте всі функції

3. РЕЗУЛЬТАТ:
   ✅ Швидше відкриття воріт/хвіртки
   ✅ Менше навантаження на сервер  
   ✅ SMS через webhook (гнучкість)
   ✅ Простіша архітектура
-->