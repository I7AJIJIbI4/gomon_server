<?php
// test.php - Тестовий файл для перевірки webhook
header('Content-Type: application/json; charset=utf-8');

echo json_encode([
    'status' => 'working',
    'message' => 'Zadarma webhook тестовий файл працює!',
    'server_info' => [
        'php_version' => phpversion(),
        'server_time' => date('Y-m-d H:i:s'),
        'timezone' => date_default_timezone_get(),
        'curl_enabled' => function_exists('curl_init'),
        'json_enabled' => function_exists('json_encode'),
        'file_permissions' => is_writable(__DIR__ . '/logs/') ? 'OK' : 'ERROR'
    ],
    'urls' => [
        'webhook' => 'https://' . $_SERVER['HTTP_HOST'] . dirname($_SERVER['REQUEST_URI']) . '/webhook.php',
        'test' => 'https://' . $_SERVER['HTTP_HOST'] . $_SERVER['REQUEST_URI']
    ]
], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
?>
