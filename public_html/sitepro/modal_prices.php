<?php
// Transforms prices.json [{cat, items:[{name,price}]}] into modal format
// Returns: {1: [{title, rows:[[name,sub,price],...], note?}], 2: [...], ...}

$allowed = ['gomonclinic.com', 'www.gomonclinic.com', 'drgomon.beauty', 'www.drgomon.beauty'];
$origin  = $_SERVER['HTTP_ORIGIN']  ?? '';
$referer = $_SERVER['HTTP_REFERER'] ?? '';

$origin_host = parse_url($origin, PHP_URL_HOST) ?: '';
$referer_host = parse_url($referer, PHP_URL_HOST) ?: '';
$host = $_SERVER['HTTP_HOST'] ?? '';
// Allow: same host, whitelisted Origin, or whitelisted Referer
$is_allowed = in_array($host, $allowed) || in_array($origin_host, $allowed) || in_array($referer_host, $allowed);
if (!$is_allowed) {
    http_response_code(403);
    exit;
}

if (in_array($origin_host, $allowed)) {
    header("Access-Control-Allow-Origin: $origin");
}
header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('X-Robots-Tag: noindex, nofollow');
header('Cache-Control: no-store');

$raw = @file_get_contents('/home/gomoncli/private_data/prices.json');
if (!$raw) { echo '{}'; exit; }

$prices = @json_decode($raw, true);
if (!is_array($prices)) { echo '{}'; exit; }

// Keywords to match each service modal ID (1-6) to prices.json category names.
// ORDER MATTERS: more specific checks must come before broader ones.
// Service 3 is before 2 so "Пілінги-біоревіталізанти" matches 'пілінг' (→3) not 'біоревіт' (→2).
$catMap = [
    // Апаратна косметологія: WOW-чистка, Киснева терапія, Дермапен, etc.
    1 => ['wow', 'киснев', 'дермапен', 'скрабінг', 'гідропілінг'],
    // Доглядові процедури та пілінги — перевіряємо ДО ін'єкційної (пілінги-біоревіталізанти)
    3 => ['доглядові', 'пілінг', 'карбокси', 'prx', 'kemikum', 'spa'],
    // Ін'єкційна косметологія: ботулін, контурна пластика, біоревіт, мезотерапія, etc.
    2 => ['ботулін', "ін'єкційна", 'контурна', 'біоревіталізація', 'мезотер', 'ферментотер', 'біорепар'],
    // Апаратна корекція фігури: DrumRoll, пресотерапія
    5 => ['drumroll', 'пресотер', 'лімфодренаж'],
    // Косметичне відбілювання зубів
    6 => ['відбілюв', 'зуб', 'magic smile'],
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
