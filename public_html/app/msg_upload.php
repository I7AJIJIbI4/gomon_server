<?php
/**
 * Media upload proxy for admin messenger
 * Forwards file to Flask API /api/admin/messages/upload
 */
header('Content-Type: application/json; charset=utf-8');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'method_not_allowed']);
    exit;
}

$auth = $_SERVER['HTTP_AUTHORIZATION'] ?? '';
if (!$auth) {
    http_response_code(401);
    echo json_encode(['error' => 'unauthorized']);
    exit;
}

if (!isset($_FILES['file'])) {
    http_response_code(400);
    echo json_encode(['error' => 'no_file']);
    exit;
}

$f = $_FILES['file'];
if ($f['error'] !== UPLOAD_ERR_OK) {
    http_response_code(400);
    echo json_encode(['error' => 'upload_error', 'code' => $f['error']]);
    exit;
}

// Forward to Flask API
$ch = curl_init('http://127.0.0.1:5001/api/admin/messages/upload');
$cfile = new CURLFile($f['tmp_name'], $f['type'], $f['name']);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST => true,
    CURLOPT_POSTFIELDS => ['file' => $cfile],
    CURLOPT_HTTPHEADER => ['Authorization: ' . $auth],
    CURLOPT_TIMEOUT => 30,
]);
$response = curl_exec($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

http_response_code($http_code);
echo $response;
