<?php
/**
 * Wlaunch Webhook Proxy
 * Проксує запити від Wlaunch до локального webhook сервера
 */

header('Content-Type: application/json');

// Логування
$log_file = '/home/gomoncli/zadarma/wlaunch_webhook_proxy.log';
$timestamp = date('Y-m-d H:i:s');

// Отримуємо дані від Wlaunch
$method = $_SERVER['REQUEST_METHOD'];
$input = file_get_contents('php://input');

file_put_contents($log_file, "[{$timestamp}] {$method} request received\n", FILE_APPEND);
file_put_contents($log_file, "[{$timestamp}] Data: {$input}\n", FILE_APPEND);

if ($method === 'GET') {
    // Health check
    echo json_encode(['status' => 'ok', 'service' => 'wlaunch_webhook_proxy']);
    exit;
}

if ($method !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed']);
    exit;
}

// Проксуємо запит до локального сервера
$ch = curl_init('http://localhost:5003/webhook/wlaunch');
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, $input);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'Content-Type: application/json',
    'Content-Length: ' . strlen($input)
]);
curl_setopt($ch, CURLOPT_TIMEOUT, 30);

$response = curl_exec($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$error = curl_error($ch);
curl_close($ch);

if ($error) {
    file_put_contents($log_file, "[{$timestamp}] Error: {$error}\n", FILE_APPEND);
    http_response_code(500);
    echo json_encode(['error' => 'Proxy error', 'details' => $error]);
    exit;
}

file_put_contents($log_file, "[{$timestamp}] Response: {$response}\n", FILE_APPEND);

http_response_code($http_code);
echo $response;
