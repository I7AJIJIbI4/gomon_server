<?php
date_default_timezone_set('Europe/Kyiv');
header('Content-Type: application/json; charset=utf-8');

// IP-based access logging for audit (WLaunch webhook lacks custom header support)
// TODO: Add shared secret via X-Webhook-Token header when WLaunch API supports it
$webhook_ip = $_SERVER['HTTP_X_REAL_IP'] ?? $_SERVER['REMOTE_ADDR'] ?? 'unknown';

// Log all incoming webhooks
$raw = file_get_contents('php://input');
$log = date('Y-m-d H:i:s') . ' [IP:' . $webhook_ip . '] ' . $raw . "
";
file_put_contents('/var/log/gomon/wlaunch_webhook.log', $log, FILE_APPEND);

$data = json_decode($raw, true);
if (!$data || empty($data['appointment'])) {
    echo json_encode(['ok' => false, 'error' => 'no data']);
    exit;
}

$appt = $data['appointment'] ?? [];
$client = $data['client'] ?? [];
$services = $data['services'] ?? [];
$resources = $data['resources'] ?? [];

$status = $appt['status'] ?? '';
$appt_id = $appt['id'] ?? '';
$start_time = $appt['start_time'] ?? '';
$duration = $appt['duration'] ?? '';
$price = $appt['price'] ?? '';
$client_name = $client['full_name'] ?? '';
$client_phone = $client['phone'] ?? '';
$service_names = implode(', ', array_map(function($s) { return $s['name'] ?? ''; }, $services));
$specialist_names = implode(', ', array_map(function($r) { return $r['full_name'] ?? ''; }, $resources));

// Forward to Flask API for notification handling
$ch = curl_init('http://127.0.0.1:5001/api/webhook/wlaunch');
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST => true,
    CURLOPT_TIMEOUT => 10,
    CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
    CURLOPT_POSTFIELDS => json_encode([
        'appt_id' => $appt_id,
        'status' => $status,
        'start_time' => $start_time,
        'duration' => $duration,
        'price' => $price,
        'client_name' => $client_name,
        'client_phone' => $client_phone,
        'services' => $service_names,
        'specialist' => $specialist_names,
    ]),
]);
$result = curl_exec($ch);
$code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

echo json_encode(['ok' => true, 'forwarded' => $code]);
