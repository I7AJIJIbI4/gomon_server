<?php
$allowed = ['gomonclinic.com', 'www.gomonclinic.com', 'drgomon.beauty', 'www.drgomon.beauty'];
$origin  = $_SERVER['HTTP_ORIGIN']  ?? '';
$referer = $_SERVER['HTTP_REFERER'] ?? '';

$origin_host = parse_url($origin, PHP_URL_HOST) ?: '';
$referer_host = parse_url($referer, PHP_URL_HOST) ?: '';
$host = $_SERVER['HTTP_HOST'] ?? '';
$is_allowed = in_array($host, $allowed) || in_array($origin_host, $allowed) || in_array($referer_host, $allowed);
if (!$is_allowed) {
    http_response_code(403);
    exit;
}

if (in_array($origin_host, $allowed)) {
    header("Access-Control-Allow-Origin: $origin");
}
header('Content-Type: application/json; charset=utf-8');
header('X-Robots-Tag: noindex, nofollow');
header('Cache-Control: no-store');
readfile('/home/gomoncli/private_data/promos.json');
