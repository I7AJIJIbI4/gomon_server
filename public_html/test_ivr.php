<?php
/**
 * ШВИДКИЙ ТЕСТ МОДИФІКАЦІЇ IVR
 * Мінімальний код для тестування
 */

// Конфігурація
$config = [
    'zadarma_key' => 'YOUR_ZADARMA_KEY',
    'zadarma_secret' => 'YOUR_ZADARMA_SECRET'
];

function makeZadarmaAPICall($method, $params = [], $requestType = 'PUT', $config) {
    ksort($params);
    $paramsString = http_build_query($params);
    
    $stringToSign = $method . $paramsString . md5($paramsString);
    $hmacHex = hash_hmac('sha1', $stringToSign, $config['zadarma_secret']);
    $signature = base64_encode($hmacHex);
    
    $headers = [
        'Authorization: ' . $config['zadarma_key'] . ':' . $signature,
        'Content-Type: application/json'
    ];
    
    $url = 'https://api.zadarma.com' . $method;
    
    echo "🔗 URL: $url\n";
    echo "🔑 Signature: " . substr($signature, 0, 20) . "...\n";
    
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, 30);
    curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'PUT');
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($params));
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    echo "📡 HTTP: $httpCode\n";
    echo "📄 Response: $response\n\n";
    
    return ($httpCode === 200) ? json_decode($response, true) : false;
}

// ТЕСТ: Змінюємо тільки сценарій хвіртки
echo "🧪 ТЕСТОВА МОДИФІКАЦІЯ СЦЕНАРІЯ ХВІРТКИ\n";
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";

$testScenario = [
    'id' => '687a97edd0c7d2d570050659', // ID вашого hvirtka сценарія
    'title' => 'Хвіртка - прямий callback',
    'queue_strategy' => 'off',
    'queue_announce_position' => 0,
    'numbers' => [
        [
            'number' => '0637442017', // Прямий номер хвіртки
            'delay' => 0,
            'duration' => 30
        ]
    ]
];

$result = makeZadarmaAPICall('/v1/pbx/ivr/scenario/edit/', $testScenario, 'PUT', $config);

if ($result && isset($result['status']) && $result['status'] === 'success') {
    echo "✅ УСПІХ! Сценарій хвіртки змінено на прямий callback\n\n";
    echo "🔬 ТЕПЕР ПРОТЕСТУЙТЕ:\n";
    echo "1. Подзвоніть на 0733103110\n";
    echo "2. Натисніть кнопку 1 (хвіртка)\n";
    echo "3. Перевірте швидкість відкриття\n";
    echo "4. Порівняйте з попередньою швидкістю\n\n";
    echo "📞 Якщо працює швидше - система оптимізована!\n";
    echo "📞 Якщо НЕ працює - повертайте старі налаштування\n";
} else {
    echo "❌ ПОМИЛКА! Сценарій не змінено\n";
    echo "Перевірте API ключі та права доступу\n";
}

echo "\n🔄 Для повернення до старих налаштувань:\n";
echo "Замініть 'number' => '0637442017' на 'number' => 101\n";

?>