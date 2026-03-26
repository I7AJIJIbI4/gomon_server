<?php
// Unified webhook - створено автоматично
require_once __DIR__ . '/webhook_functions.php';

$data = json_decode(file_get_contents('php://input'), true) ?: $_POST;
$event = $data['event'] ?? '';

if (isBotCallback($data)) {
    // Bot callback - передаємо в Python
    processBotCallback($data);
} else {
    // IVR дзвінок - обробляємо в PHP
    processIVRCall($data);
}
