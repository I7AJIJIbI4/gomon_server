<?php
/**
 * Instagram OAuth code → access_token exchange
 * POST /messenger/auth.php
 * Body: { "code": "..." }
 */
header('Content-Type: application/json; charset=utf-8');

require_once dirname(__DIR__) . '/app/config.php';

define('REDIRECT_URI', IG_REDIRECT_URI);

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

// Step 1: Exchange code for short-lived token
$ch = curl_init('https://api.instagram.com/oauth/access_token');
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST           => true,
    CURLOPT_POSTFIELDS     => http_build_query([
        'client_id'     => IG_APP_ID,
        'client_secret' => IG_APP_SECRET,
        'grant_type'    => 'authorization_code',
        'redirect_uri'  => REDIRECT_URI,
        'code'          => $code,
    ]),
    CURLOPT_TIMEOUT        => 15,
    CURLOPT_SSL_VERIFYPEER => true,
]);
$response  = curl_exec($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$curl_err  = curl_error($ch);
curl_close($ch);

if ($curl_err) {
    http_response_code(502);
    echo json_encode(['error' => 'cURL: ' . $curl_err]);
    exit;
}

$data = json_decode($response, true);

if ($http_code !== 200 || !isset($data['access_token'])) {
    http_response_code($http_code ?: 502);
    echo $response;
    exit;
}

$short_token = $data['access_token'];
$user_id     = $data['user_id'] ?? null;

// Step 2: Exchange short-lived token for long-lived token
$ll_url = 'https://graph.instagram.com/access_token?' . http_build_query([
    'grant_type'    => 'ig_exchange_token',
    'client_secret' => IG_APP_SECRET,
    'access_token'  => $short_token,
]);

$ch2 = curl_init($ll_url);
curl_setopt_array($ch2, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT        => 15,
    CURLOPT_SSL_VERIFYPEER => true,
]);
$ll_response  = curl_exec($ch2);
$ll_http_code = curl_getinfo($ch2, CURLINFO_HTTP_CODE);
curl_close($ch2);

$ll_data = json_decode($ll_response, true);

if ($ll_http_code === 200 && isset($ll_data['access_token'])) {
    echo json_encode([
        'access_token' => $ll_data['access_token'],
        'token_type'   => $ll_data['token_type'] ?? 'bearer',
        'expires_in'   => $ll_data['expires_in'] ?? 5184000,
        'user_id'      => $user_id,
    ]);
} else {
    echo json_encode([
        'access_token' => $short_token,
        'token_type'   => 'bearer',
        'expires_in'   => 3600,
        'user_id'      => $user_id,
    ]);
}
