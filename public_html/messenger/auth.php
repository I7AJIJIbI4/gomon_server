<?php
/**
 * Facebook OAuth code → access_token exchange
 * POST /messenger/auth.php
 * Body: { "code": "..." }
 */
header('Content-Type: application/json; charset=utf-8');

define('APP_ID',     '1138101513882406');
define('APP_SECRET', '080b493fbebe441376ee4e1bf323c57b');
define('REDIRECT_URI', 'https://www.gomonclinic.com/messenger/');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed']);
    exit;
}

$raw  = file_get_contents('php://input');
$body = json_decode($raw, true);
$code = trim($body['code'] ?? '');

if (!$code) {
    http_response_code(400);
    echo json_encode(['error' => 'No code provided']);
    exit;
}

$url = 'https://graph.facebook.com/oauth/access_token?' . http_build_query([
    'client_id'     => APP_ID,
    'client_secret' => APP_SECRET,
    'redirect_uri'  => REDIRECT_URI,
    'code'          => $code,
]);

$ch = curl_init($url);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT        => 15,
    CURLOPT_SSL_VERIFYPEER => true,
]);
$response  = curl_exec($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$curl_err  = curl_error($ch);
curl_close($ch);

if ($curl_err) {
    http_response_code(502);
    echo json_encode(['error' => $curl_err]);
    exit;
}

http_response_code($http_code);
echo $response;
