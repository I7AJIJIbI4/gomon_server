<?php
// Симуляція POST запиту до IVR webhook
$_POST = array(
    'event' => 'NOTIFY_INTERNAL',
    'call_start' => '2025-08-05 15:30:00',
    'pbx_call_id' => 'test_123',
    'caller_id' => '380933297777',
    'called_did' => '380733103110',
    'internal' => '102',
    'calltype' => 'normal'
);

echo "🧪 ТЕСТУВАННЯ IVR WEBHOOK\n";
echo "POST data: " . json_encode($_POST) . "\n";
echo "=================================\n";

// Включити IVR webhook
include __DIR__ . '/webhooks/zadarma_ivr_webhook.php';

echo "\n=== РЕЗУЛЬТАТ ===\n";
if (file_exists('/tmp/pending_ivr_calls.json')) {
    echo "✅ Pending calls файл створено\n";
    echo file_get_contents('/tmp/pending_ivr_calls.json');
} else {
    echo "❌ Pending calls файл НЕ створено\n";
}
?>
