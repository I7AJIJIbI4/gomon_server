<?php
/**
 * TG Business bot media proxy
 * GET /app/tg_media.php?fid=xxx
 */
require_once __DIR__ . '/config.php';

$fid = $_GET['fid'] ?? '';
if (!$fid || !preg_match('/^[A-Za-z0-9_-]+$/', $fid)) {
    http_response_code(403);
    exit;
}

$token = TG_BIZ_TOKEN;

// Get file path from TG
$ch = curl_init("https://api.telegram.org/bot{$token}/getFile?" . http_build_query(['file_id' => $fid]));
curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 5]);
$r = json_decode(curl_exec($ch), true);
curl_close($ch);

$fp = $r['result']['file_path'] ?? '';
if (!$fp) { http_response_code(404); exit; }

// Download file
$ch2 = curl_init("https://api.telegram.org/file/bot{$token}/{$fp}");
curl_setopt_array($ch2, [CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 15]);
$data = curl_exec($ch2);
curl_close($ch2);

if (!$data) { http_response_code(502); exit; }

// Determine content type from file path extension
$ext = strtolower(pathinfo($fp, PATHINFO_EXTENSION));
$type_map = [
    'jpg' => 'image/jpeg', 'jpeg' => 'image/jpeg', 'png' => 'image/png',
    'gif' => 'image/gif', 'webp' => 'image/webp',
    'mp4' => 'video/mp4', 'mov' => 'video/quicktime',
    'ogg' => 'audio/ogg', 'oga' => 'audio/ogg', 'webm' => 'audio/webm',
    'mp3' => 'audio/mpeg', 'wav' => 'audio/wav',
];
$ct = $type_map[$ext] ?? 'application/octet-stream';
// Fallback: detect from magic bytes
if ($ct === 'application/octet-stream') {
    $head = substr($data, 0, 4);
    if ($head === "\xff\xd8\xff\xe0" || $head === "\xff\xd8\xff\xe1") $ct = 'image/jpeg';
    elseif (substr($data, 0, 8) === "\x89PNG\r\n\x1a\n") $ct = 'image/png';
    elseif (substr($data, 0, 4) === "RIFF" && substr($data, 8, 4) === "WEBP") $ct = 'image/webp';
    elseif (substr($data, 0, 3) === "GIF") $ct = 'image/gif';
    elseif (substr($data, 4, 4) === "ftyp") $ct = 'video/mp4';
    elseif (substr($data, 0, 4) === "OggS") $ct = 'audio/ogg';
}
header('Content-Type: ' . $ct);
header('Cache-Control: public, max-age=86400');
echo $data;
