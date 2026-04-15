<?php
$allowed = ['gomonclinic.com', 'www.gomonclinic.com', 'drgomon.beauty', 'www.drgomon.beauty'];
$origin  = $_SERVER['HTTP_ORIGIN']  ?? '';
$referer = $_SERVER['HTTP_REFERER'] ?? '';

$origin_host = parse_url($origin, PHP_URL_HOST) ?: '';
$referer_host = parse_url($referer, PHP_URL_HOST) ?: '';
if (!in_array($origin_host, $allowed) && !in_array($referer_host, $allowed)) {
    http_response_code(403);
    exit;
}

header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('X-Robots-Tag: noindex, nofollow');
header('Cache-Control: no-store');
readfile('/home/gomoncli/private_data/prices.json');
