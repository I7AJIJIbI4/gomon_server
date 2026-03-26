<?php
header('Content-Type: text/plain');

// Перевірка echo параметра для Zadarma
if (isset($_GET['zd_echo'])) {
    echo $_GET['zd_echo'];
    exit;
}

// Логування всіх запитів
$logFile = '/home/gomoncli/zadarma/webhook_simple.log';
$timestamp = date('Y-m-d H:i:s');
$data = file_get_contents('php://input');
$method = $_SERVER['REQUEST_METHOD'];

$logEntry = "[$timestamp] $method - Data: $data - GET: " . print_r($_GET, true) . "\n";
file_put_contents($logFile, $logEntry, FILE_APPEND | LOCK_EX);

echo "OK";
?>
