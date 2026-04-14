<?php
// PHP proxy до Flask PWA API на 127.0.0.1:5001
$flask_base = 'http://127.0.0.1:5001';

// Визначити підшлях: /api/health → /api/health
$request_uri = $_SERVER['REQUEST_URI'];
// Прибрати query string з URI для побудови URL
$path = strtok($request_uri, '?');
$query = $_SERVER['QUERY_STRING'] ?? '';
$url = $flask_base . $path . ($query ? '?' . $query : '');

$method = $_SERVER['REQUEST_METHOD'];
$body = file_get_contents('php://input');
$headers_in = getallheaders();

$ch = curl_init($url);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT        => 15,
    CURLOPT_CUSTOMREQUEST  => $method,
]);

// Прокинути заголовки (Content-Type, Authorization)
$fwd_headers = [];
foreach ($headers_in as $k => $v) {
    $lk = strtolower($k);
    if (in_array($lk, ['content-type', 'authorization', 'accept'])) {
        $fwd_headers[] = $k . ': ' . $v;
    }
}
if ($fwd_headers) {
    curl_setopt($ch, CURLOPT_HTTPHEADER, $fwd_headers);
}

// Тіло для POST/PUT
if ($body && in_array($method, ['POST', 'PUT', 'PATCH'])) {
    curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
}

$response = curl_exec($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$content_type = curl_getinfo($ch, CURLINFO_CONTENT_TYPE);
curl_close($ch);

http_response_code($http_code ?: 502);
header('Content-Type: ' . ($content_type ?: 'application/json'));

// CORS — restricted to known origins
$allowed_hosts = ['gomonclinic.com', 'www.gomonclinic.com', 'drgomon.beauty', 'www.drgomon.beauty'];
$origin = $_SERVER['HTTP_ORIGIN'] ?? '';
if ($origin) {
    $host = parse_url($origin, PHP_URL_HOST) ?? '';
    if (in_array($host, $allowed_hosts, true)) {
        header("Access-Control-Allow-Origin: $origin");
    }
} else {
    // Same-origin requests (no Origin header) — allow
    header('Access-Control-Allow-Origin: https://drgomon.beauty');
}
header('Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS');
header('Access-Control-Allow-Headers: Authorization, Content-Type');

if ($method === 'OPTIONS') { exit; }
echo $response;
