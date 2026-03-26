<?php
$allowed = ['gomonclinic.com', 'www.gomonclinic.com'];
$origin  = $_SERVER['HTTP_ORIGIN']  ?? '';
$referer = $_SERVER['HTTP_REFERER'] ?? '';

$ok = false;
foreach ($allowed as $host) {
    if (str_contains($origin, $host) || str_contains($referer, $host)) {
        $ok = true;
        break;
    }
}

if (!$ok) {
    http_response_code(403);
    exit;
}

header('Content-Type: application/json; charset=utf-8');
header('X-Robots-Tag: noindex, nofollow');
header('Cache-Control: no-store');
readfile('/home/gomoncli/private_data/promos.json');
