<?php
// Перевірка налаштування Zadarma webhook
header('Content-Type: text/html; charset=utf-8');

// ОБОВ'ЯЗКОВИЙ код для Zadarma
if (isset($_GET['zd_echo'])) {
    exit($_GET['zd_echo']);
}

echo "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Zadarma Webhook Check</title></head><body>";
echo "<h1>🔍 Перевірка Zadarma Webhook</h1>";

$webhook_url = 'https://gomonclinic.com/zadarma_ivr_webhook.php';

echo "<h2>✅ Налаштування для Zadarma:</h2>";
echo "<table border='1' style='border-collapse:collapse;'>";
echo "<tr><th>Параметр</th><th>Значення</th></tr>";
echo "<tr><td><strong>URL для дзвінків АТС</strong></td><td><code>$webhook_url</code></td></tr>";
echo "<tr><td><strong>URL для подій</strong></td><td><code>$webhook_url</code></td></tr>";
echo "<tr><td><strong>Validation код</strong></td><td>✅ Присутній</td></tr>";
echo "</table>";

echo "<h2>🧪 Тести:</h2>";

// Тест 1: Validation
echo "<h3>1. Zadarma Validation Test:</h3>";
$test_url = $webhook_url . '?zd_echo=validation_12345';
$result = @file_get_contents($test_url);
echo "URL: <code>$test_url</code><br>";
echo "Результат: <strong>" . ($result === 'validation_12345' ? '✅ УСПІХ' : '❌ ПОМИЛКА') . "</strong><br>";

// Тест 2: Status
echo "<h3>2. Webhook Status:</h3>";
$status = @file_get_contents($webhook_url);
echo "<pre style='background:#f5f5f5;padding:10px;'>$status</pre>";

// Тест 3: POST Internal 102 (Ворота)
echo "<h3>3. Тест воріт (internal 102):</h3>";
$gate_data = [
    'event' => 'NOTIFY_INTERNAL',
    'caller_id' => '380933297777',
    'internal' => '102',
    'call_start' => date('Y-m-d H:i:s')
];

$context = stream_context_create([
    'http' => [
        'method' => 'POST',
        'header' => 'Content-Type: application/json',
        'content' => json_encode($gate_data)
    ]
]);

$gate_result = @file_get_contents($webhook_url, false, $context);
echo "Запит: <pre>" . json_encode($gate_data, JSON_PRETTY_PRINT) . "</pre>";
echo "Результат: <pre>$gate_result</pre>";

// Тест 4: POST Internal 101 (Хвіртка)  
echo "<h3>4. Тест хвіртки (internal 101):</h3>";
$door_data = [
    'event' => 'NOTIFY_INTERNAL',
    'caller_id' => '380933297777', 
    'internal' => '101',
    'call_start' => date('Y-m-d H:i:s')
];

$context = stream_context_create([
    'http' => [
        'method' => 'POST',
        'header' => 'Content-Type: application/json',
        'content' => json_encode($door_data)
    ]
]);

$door_result = @file_get_contents($webhook_url, false, $context);
echo "Запит: <pre>" . json_encode($door_data, JSON_PRETTY_PRINT) . "</pre>";
echo "Результат: <pre>$door_result</pre>";

// Логи
echo "<h2>📝 Останні логи:</h2>";
$log_file = '/home/gomoncli/zadarma/ivr_webhook.log';
if (file_exists($log_file)) {
    $logs = file_get_contents($log_file);
    $lines = explode("\n", trim($logs));
    $last_lines = array_slice($lines, -25);
    echo "<pre style='background:#f0f0f0;padding:15px;height:300px;overflow-y:auto;'>";
    echo implode("\n", $last_lines);
    echo "</pre>";
} else {
    echo "<p>❌ Лог файл не знайдено</p>";
}

echo "<h2>📋 Інструкції для Zadarma:</h2>";
echo "<ol>";
echo "<li>Особистий кабінет → Налаштування → Інтеграції та API</li>";
echo "<li>У розділі 'Повідомлення про події':</li>";
echo "<li><strong>Про дзвінки в АТС:</strong> <code>$webhook_url</code></li>";
echo "<li><strong>Про події:</strong> <code>$webhook_url</code></li>";
echo "<li>Увімкніть потрібні події</li>";
echo "<li>Натисніть 'Зберегти'</li>";
echo "</ol>";

echo "<p><em>Останнє оновлення: " . date('Y-m-d H:i:s') . "</em></p>";
echo "</body></html>";
?>
