<?php
// Тест нових IVR функцій
require_once 'webhooks/zadarma_ivr_webhook.php';

echo "🧪 ТЕСТУВАННЯ IVR TRACKING ФУНКЦІЙ\n";
echo "=" * 40 . "\n";

// Симулювати pending call
$test_data = [
    'call_id' => 'test_123',
    'target_number' => '0930063585', 
    'caller_id' => '380933297777',
    'action_type' => 'vorota',
    'timestamp' => time(),
    'status' => 'pending'
];

file_put_contents('/tmp/pending_ivr_calls.json', json_encode([$test_data], JSON_PRETTY_PRINT));
echo "✅ Створено тестовий pending call\n";

// Тестувати пошук
$found = getPendingCallByTarget('0930063585');
if ($found) {
    echo "✅ Знайдено pending call: " . $found['call_id'] . "\n";
} else {
    echo "❌ Pending call не знайдено\n";
}

// Тестувати оновлення статусу
$updated = updatePendingCallStatus('test_123', 'success');
echo $updated ? "✅ Статус оновлено\n" : "❌ Помилка оновлення\n";

// Показати результат
$content = file_get_contents('/tmp/pending_ivr_calls.json');
echo "📋 Поточний стан файлу:\n$content\n";

echo "🎯 Тест завершено!\n";
?>
