<?php
// Transforms prices.json [{cat, items:[{name,price}]}] into modal format
// Returns: {1: [{title, rows:[[name,sub,price],...], note?}], 2: [...], ...}

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

$raw = @file_get_contents('/home/gomoncli/private_data/prices.json');
if (!$raw) { echo '{}'; exit; }

$prices = @json_decode($raw, true);
if (!is_array($prices)) { echo '{}'; exit; }

// Keywords to match each service modal ID (1-6) to prices.json category names
$catMap = [
    1 => ['апаратна косметолог', 'апарат'],
    2 => ["ін'єкційна", 'ін єкційна', 'контурна', 'біоревіт', 'мезотер', 'ін`єкційна'],
    3 => ['доглядові', 'пілінг', 'карбокси', 'spa', 'спа-догляд', 'prx'],
    5 => ['корекція фігур', 'drumroll', 'пресотер', 'фігур', 'масаж'],
    6 => ['зуб', 'відбілюв', 'magic smile'],
];

$result = [];

foreach ($prices as $cat) {
    if (!is_array($cat)) continue;
    $catName = mb_strtolower($cat['cat'] ?? $cat['title'] ?? $cat['name'] ?? '', 'UTF-8');
    $items   = $cat['items'] ?? $cat['rows'] ?? $cat['services'] ?? [];

    $matchedId = null;
    foreach ($catMap as $serviceId => $keywords) {
        foreach ($keywords as $kw) {
            if (mb_strpos($catName, $kw) !== false) {
                $matchedId = $serviceId;
                break 2;
            }
        }
    }

    if ($matchedId === null) continue;

    $rows = [];
    foreach ($items as $item) {
        if (is_array($item)) {
            if (isset($item[0])) {
                // Already in [name, sub, price] format
                $rows[] = [
                    $item[0] ?? '',
                    $item[1] ?? '',
                    $item[2] ?? ''
                ];
            } else {
                $rows[] = [
                    $item['name'] ?? $item['service'] ?? '',
                    '',
                    $item['price'] ?? $item['cost'] ?? ''
                ];
            }
        }
    }

    if (!isset($result[$matchedId])) $result[$matchedId] = [];
    $entry = ['title' => $cat['cat'] ?? $cat['title'] ?? $cat['name'] ?? '', 'rows' => $rows];
    if (!empty($cat['note'])) $entry['note'] = $cat['note'];
    $result[$matchedId][] = $entry;
}

echo json_encode($result, JSON_UNESCAPED_UNICODE);
