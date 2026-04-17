<?php
date_default_timezone_set('Europe/Kyiv');
/**
 * Dr. Gomon Cosmetology — AI Chat Endpoint
 * Розмістити: /api/chat.php
 */

// ═══════════════════════════════════════════════════════════════
//  КОНФІГУРАЦІЯ — завантажується з config.php
// ═══════════════════════════════════════════════════════════════

// Завантажуємо конфігурацію з окремого файлу (не в Git)
require_once __DIR__ . '/config.php';

// Шлях до системного промпту — рекомендується вище webroot
define('SYSTEM_PROMPT_FILE', __DIR__ . '/system_prompt.txt');

// Дозволені origins (CORS)
$allowed_origins = [
    'https://gomonclinic.com',
    'https://www.gomonclinic.com',
    'https://drgomon.beauty',
    'https://www.drgomon.beauty',
];

// ═══════════════════════════════════════════════════════════════
//  CORS / PREFLIGHT
// ═══════════════════════════════════════════════════════════════

$origin = $_SERVER['HTTP_ORIGIN'] ?? '';
if (in_array($origin, $allowed_origins, true)) {
    header("Access-Control-Allow-Origin: $origin");
}
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
header('Content-Type: application/json; charset=utf-8');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST' && $_SERVER['REQUEST_METHOD'] !== 'GET') {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed']);
    exit;
}


// ═══════════════════════════════════════════════════════════════
//  ХЕЛПЕРИ ДЛЯ TELEGRAM
// ═══════════════════════════════════════════════════════════════

/**
 * Нормалізує телефон до формату 380XXXXXXXXX (як pwa_api.py::norm_phone).
 * Повертає рядок із тільки цифрами, або порожній рядок якщо невалідний.
 */
function normalize_phone(string $raw): string {
    $d = preg_replace('/[^\d]/', '', $raw);
    if (strlen($d) === 10 && $d[0] === '0') return '38' . $d;          // 0XXXXXXXXX
    if (strlen($d) === 11 && substr($d, 0, 2) === '80') return '3' . $d; // 80XXXXXXXXX
    if (strlen($d) === 12 && substr($d, 0, 3) === '380') return $d;      // 380XXXXXXXXX
    if (strlen($d) >= 7) return $d;   // міжнародний або невідомий — повертаємо digits
    return '';
}

function lookup_telegram_user(string $phone): ?array {
    $db_path = '/home/gomoncli/zadarma/users.db';
    if (!file_exists($db_path)) return null;
    try {
        $db = new SQLite3($db_path, SQLITE3_OPEN_READONLY);
        $norm = preg_replace('/[^\d]/', '', $phone);
        $last9 = substr($norm, -9);
        $stmt = $db->prepare(
            "SELECT telegram_id, username, first_name FROM users WHERE phone LIKE :p LIMIT 1"
        );
        $stmt->bindValue(':p', '%' . $last9, SQLITE3_TEXT);
        $res = $stmt->execute();
        $row = $res ? $res->fetchArray(SQLITE3_ASSOC) : null;
        $db->close();
        return $row ?: null;
    } catch (Exception $e) { return null; }
}

function format_phone_link(string $phone): string {
    $d = preg_replace('/[^\d]/', '', $phone);
    if (strlen($d) === 10) $d = '38' . $d;
    $e164 = '+' . $d;
    return '<a href="tel:' . $e164 . '">' . $e164 . '</a>';
}

function format_tg_link(?array $tg_user): string {
    if (!$tg_user) return '';
    if (!empty($tg_user['username'])) {
        $name = htmlspecialchars($tg_user['username'], ENT_XML1);
        return ' · <a href="https://t.me/' . $name . '">@' . $name . '</a>';
    }
    if (!empty($tg_user['telegram_id'])) {
        return ' · <a href="tg://user?id=' . (int)$tg_user['telegram_id'] . '">Telegram</a>';
    }
    return '';
}

// ═══════════════════════════════════════════════════════════════
//  ВХІДНІ ДАНІ
// ═══════════════════════════════════════════════════════════════

// GET — return chat history from DB
if ($_SERVER['REQUEST_METHOD'] === 'GET' && !empty($_GET['history'])) {
    $hist_phone = normalize_phone(trim($_GET['phone'] ?? ''));
    $hist_token = trim($_GET['token'] ?? '');
    if (!$hist_phone || !$hist_token) {
        echo json_encode(['messages' => []]);
        exit;
    }
    // Verify session token matches phone
    try {
        $sess_db = new SQLite3('/home/gomoncli/zadarma/otp_sessions.db');
        $sess_st = $sess_db->prepare('SELECT phone FROM sessions WHERE token=:t AND expires_at > :now LIMIT 1');
        $sess_st->bindValue(':t', $hist_token);
        $sess_st->bindValue(':now', time());
        $sess_row = $sess_st->execute()->fetchArray(SQLITE3_ASSOC);
        $sess_db->close();
        if (!$sess_row || substr(preg_replace('/\D/', '', $sess_row['phone']), -9) !== substr(preg_replace('/\D/', '', $hist_phone), -9)) {
            echo json_encode(['messages' => []]);
            exit;
        }
    } catch (Exception $e) {
        echo json_encode(['messages' => []]);
        exit;
    }
    $sess_key = 'phone_' . substr(preg_replace('/[^\d]/', '', $hist_phone), -9);
    try {
        $ai_db = new SQLite3('/home/gomoncli/zadarma/ai_chat.db');
        $ai_db->exec('PRAGMA journal_mode=WAL');
        $st = $ai_db->prepare('SELECT role, content FROM ai_messages WHERE session_key=:sk ORDER BY id DESC LIMIT 20');
        $st->bindValue(':sk', $sess_key);
        $res = $st->execute();
        $msgs = [];
        while ($row = $res->fetchArray(SQLITE3_ASSOC)) {
            $msgs[] = ['role' => $row['role'], 'content' => $row['content']];
        }
        $ai_db->close();
        $msgs = array_reverse($msgs);
        echo json_encode(['messages' => $msgs], JSON_UNESCAPED_UNICODE);
    } catch (Exception $e) {
        echo json_encode(['messages' => []]);
    }
    exit;
}

$raw_input = file_get_contents('php://input');
error_log('chat.php: input_len=' . strlen($raw_input) . ' has_image=' . (strpos($raw_input, '"image"') !== false ? 'YES' : 'NO'));
$body = json_decode($raw_input, true);

if (!$body) {
    http_response_code(400);
    echo json_encode(['error' => 'Invalid JSON']);
    exit;
}

$start_ms   = (int)(microtime(true) * 1000);
$user_name  = trim($body['user']['name']  ?? '');
$user_phone = normalize_phone(trim($body['user']['phone'] ?? ''));
$source     = $body['source'] ?? 'app';
$messages   = $body['messages'] ?? [];
$image_b64  = $body['image'] ?? null;  // base64 encoded image
$image_type = $body['image_type'] ?? 'image/jpeg';  // media type

// Validate image if provided
if ($image_b64) {
    // Size check: ~5MB file = ~6.7MB base64
    if (strlen($image_b64) > 7 * 1024 * 1024) {
        http_response_code(413);
        echo json_encode(['error' => 'Image too large (max 5MB)']);
        exit;
    }
    // Type whitelist
    $allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
    if (!in_array($image_type, $allowed_types, true)) {
        $image_type = 'image/jpeg';
    }
    // Strip whitespace from base64 and basic sanity check
    $image_b64 = preg_replace('/\s/', '', $image_b64);
}
$client_ip  = $_SERVER['HTTP_X_REAL_IP'] ?? $_SERVER['REMOTE_ADDR'] ?? 'unknown';

// Очищаємо і валідуємо messages
$clean_messages = [];
foreach ($messages as $msg) {
    $role    = $msg['role']    ?? '';
    $content = trim($msg['content'] ?? '');
    if (in_array($role, ['user', 'assistant'], true) && $content !== '') {
        $clean_messages[] = ['role' => $role, 'content' => $content];
    }
}

// Cap message history to last 20 messages
$clean_messages = array_slice($clean_messages, -20);

// If image present but no text — add default question
if (empty($clean_messages) && $image_b64) {
    $clean_messages[] = ['role' => 'user', 'content' => 'Що ви бачите на цьому фото?'];
} elseif (empty($clean_messages)) {
    http_response_code(400);
    echo json_encode(['error' => 'No valid messages']);
    exit;
}

// ═══════════════════════════════════════════════════════════════
//  SERVER-SIDE RATE LIMIT
//  authed (phone known): 20 req/day  |  guest: 10 req/day
//  key = last-9-digits-of-phone OR ip (whichever is more specific)
// ═══════════════════════════════════════════════════════════════

$rl_db_path = '/home/gomoncli/zadarma/chat_rl.db';
$today      = date('Y-m-d');
$phone_norm = preg_replace('/[^\d]/', '', $user_phone);
$rl_key     = $phone_norm ? substr($phone_norm, -9) : 'ip:' . $client_ip;
$rl_limit   = $phone_norm ? 10 : 5;

try {
    $rl_db = new SQLite3($rl_db_path);
    $rl_db->exec('PRAGMA journal_mode=WAL');
    $rl_db->exec(
        'CREATE TABLE IF NOT EXISTS rl ('
        . 'key TEXT NOT NULL, date TEXT NOT NULL, count INTEGER DEFAULT 0,'
        . ' PRIMARY KEY(key, date))'
    );
    $rl_db->exec(
        'CREATE TABLE IF NOT EXISTS chat_log ('
        . 'id INTEGER PRIMARY KEY AUTOINCREMENT,'
        . 'ts TEXT NOT NULL, ip TEXT, phone TEXT, source TEXT,'
        . 'duration_ms INTEGER, model TEXT, status TEXT, req_len INTEGER)'
    );

    $stmt = $rl_db->prepare('SELECT count FROM rl WHERE key=:k AND date=:d');
    $stmt->bindValue(':k', $rl_key);
    $stmt->bindValue(':d', $today);
    $row   = $stmt->execute()->fetchArray(SQLITE3_ASSOC);
    $count = $row ? (int)$row['count'] : 0;

    if ($count >= $rl_limit) {
        // Deposit rate limit bypass
        if ($phone_norm) {
            try {
                $dep_db = new SQLite3('/home/gomoncli/zadarma/users.db');
                $dep_st = $dep_db->prepare("SELECT 1 FROM deposits WHERE phone=:p AND status='Approved' AND date(created_at)=date('now') LIMIT 1");
                $dep_st->bindValue(':p', $phone_norm);
                $has_deposit = $dep_st->execute()->fetchArray();
                $dep_db->close();
                if ($has_deposit) {
                    $count = 0;  // Reset limit for depositors
                }
            } catch (Exception $e) {}
        }

        if ($count >= $rl_limit) {
            $rl_db->close();
            // Try to create deposit payment URL for authed users
            $deposit_url = null;
            if ($phone_norm) {
                try {
                    $ch_dep = curl_init('http://127.0.0.1:5001/api/deposit/create-internal');
                    curl_setopt_array($ch_dep, [
                        CURLOPT_RETURNTRANSFER => true,
                        CURLOPT_POST => true,
                        CURLOPT_TIMEOUT => 10,
                        CURLOPT_HTTPHEADER => [
                            'Content-Type: application/json',
                            'X-Internal-Phone: ' . $phone_norm,
                        ],
                        CURLOPT_POSTFIELDS => json_encode(['phone' => $phone_norm]),
                    ]);
                    $dep_resp = curl_exec($ch_dep);
                    curl_close($ch_dep);
                    $dep_data = json_decode($dep_resp, true);
                    if (!empty($dep_data['pay_url'])) {
                        $deposit_url = $dep_data['pay_url'];
                    }
                } catch (Exception $e) {}
            }
            http_response_code(429);
            echo json_encode(['error' => 'rate_limit', 'deposit_url' => $deposit_url]);
            exit;
        }
    }
    // Rate limit increment deferred — will be applied AFTER successful API call
} catch (Exception $e) {
    error_log('chat.php RL error: ' . $e->getMessage());
    $rl_db = null;
}

// ═══════════════════════════════════════════════════════════════
//  СИСТЕМНИЙ ПРОМПТ
// ═══════════════════════════════════════════════════════════════

if (!file_exists(SYSTEM_PROMPT_FILE)) {
    http_response_code(500);
    echo json_encode(['error' => 'System prompt not found']);
    exit;
}

$system_prompt = file_get_contents(SYSTEM_PROMPT_FILE);

// ── 1. Дані клієнта ─────────────────────────────────────────
$client_info_parts = [];
if ($user_name)  $client_info_parts[] = "Ім'я: {$user_name}";
if ($user_phone) $client_info_parts[] = "Телефон: {$user_phone}";

if (!empty($client_info_parts)) {
    $system_prompt .= "\n\n---\nДані поточного клієнта:\n" . implode("\n", $client_info_parts);
}

// ── 2. Записи клієнта з БД ───────────────────────────────────
if ($user_phone) {
    try {
        $db = new SQLite3('/home/gomoncli/zadarma/users.db', SQLITE3_OPEN_READONLY);
        $tail = substr(preg_replace('/\D/', '', $user_phone), -9);
        $stmt = $db->prepare(
            "SELECT services_json, visits_count FROM clients " .
            "WHERE REPLACE(REPLACE(REPLACE(phone,'+',''),'-',''),' ','') LIKE ? LIMIT 1"
        );
        $stmt->bindValue(1, '%' . $tail, SQLITE3_TEXT);
        $row = $stmt->execute()->fetchArray(SQLITE3_ASSOC);
        if ($row) {
            $services = json_decode($row['services_json'] ?? '[]', true) ?: [];
            $visits_count = (int)($row['visits_count'] ?? 0);
            if (!empty($services)) {
                $today = date('Y-m-d');
                $upcoming_active = array_filter($services, fn($s) =>
                    ($s['date'] ?? '') >= $today && strtoupper($s['status'] ?? '') !== 'CANCELLED');
                $upcoming_cancelled = array_filter($services, fn($s) =>
                    ($s['date'] ?? '') >= $today && strtoupper($s['status'] ?? '') === 'CANCELLED');
                $upcoming = array_merge(array_values($upcoming_active), array_values($upcoming_cancelled));
                $past = array_filter($services, fn($s) =>
                    ($s['date'] ?? '') < $today || strtoupper($s['status'] ?? '') === 'CANCELLED');
                usort($upcoming, fn($a, $b) => strcmp($a['date'] ?? '', $b['date'] ?? ''));
                usort($past, fn($a, $b) => strcmp($b['date'] ?? '', $a['date'] ?? ''));
                if (!empty($upcoming)) {
                    $ulines = [];
                    foreach ($upcoming as $s) {
                        $line = "- {$s['date']} о " . ($s['hour'] ?? '?') . ":00: {$s['service']} (спеціаліст: " . ($s['specialist'] ?? '?') . ")";
                        if (strtoupper($s['status'] ?? '') === 'CANCELLED') $line .= ' [СКАСОВАНО]';
                        $ulines[] = $line;
                    }
                    $system_prompt .= "\n\n---\n## Майбутні записи клієнта\n" . implode("\n", $ulines);
                } else {
                    $system_prompt .= "\n\n---\n## Майбутні записи клієнта\nНемає майбутніх записів.";
                }
                if (!empty($past)) {
                    $plines = [];
                    foreach (array_slice(array_values($past), 0, 5) as $s) {
                        $plines[] = "- {$s['date']}: {$s['service']} ({$s['status']})";
                    }
                    $system_prompt .= "\n\n## Історія візитів (всього: {$visits_count})\n" . implode("\n", $plines);
                }
            } else {
                $system_prompt .= "\n\n---\n## Записи клієнта\nКлієнт ще не має записаних візитів.";
            }
        }
        $db->close();
    } catch (Exception $e) { /* ігноруємо помилки БД */ }
}

// ── 3. Поточні акції ─────────────────────────────────────────
$promos_file = '/home/gomoncli/private_data/promos.json';
if (file_exists($promos_file)) {
    $promos = json_decode(file_get_contents($promos_file), true) ?: [];
    if (!empty($promos)) {
        $promo_lines = [];
        foreach ($promos as $p) {
            $tag   = $p['tag']   ?? '';
            $title = $p['title'] ?? '';
            $desc  = $p['desc']  ?? '';
            $promo_lines[] = "- [{$tag}] {$title} — {$desc}";
        }
        $system_prompt .= "\n\n---\n## Поточні актуальні акції\n" . implode("\n", $promo_lines);
    }
}


// ── 4. Актуальний прайс ───────────────────────────────────────
$prices_file = '/home/gomoncli/private_data/prices.json';
if (file_exists($prices_file)) {
    $prices_data = json_decode(file_get_contents($prices_file), true) ?: [];
    if (!empty($prices_data)) {

        // Знижки з промо (price_categories → percent) — тільки для джерела 'app'
        $cat_discounts = [];
        if ($source === 'app') {
            $promos_raw = json_decode(file_get_contents('/home/gomoncli/private_data/promos.json'), true) ?: [];
            foreach ($promos_raw as $pr) {
                if (!empty($pr['discount']['price_categories'])) {
                    foreach ($pr['discount']['price_categories'] as $cat_id) {
                        $cat_discounts[$cat_id] = [
                            'percent' => $pr['discount']['percent'],
                            'promo'   => $pr['title'],
                        ];
                    }
                }
            }
        }

        $price_lines = [];
        foreach ($prices_data as $cat_entry) {
            $cat_name = $cat_entry['cat'] ?? '';
            $items    = $cat_entry['items'] ?? [];
            if (!$cat_name || empty($items)) continue;

            // Знижка: шукаємо у cat_discounts по індексу, якщо є
            $discount = null;
            foreach ($cat_discounts as $disc_cat_id => $disc) {
                // cat_id у promos відповідає порядковому номеру категорії прайсу (1-based)
                // Порівнюємо ключове слово категорії
                if (stripos($cat_name, 'ін\'єкц') !== false || stripos($cat_name, 'філер') !== false
                    || stripos($cat_name, 'ботул') !== false || stripos($cat_name, 'контурна') !== false) {
                    $discount = $disc;
                    break;
                }
            }

            // Шукаємо про що питає клієнт (останнє повідомлення)
            static $__last_msg = null;
            if ($__last_msg === null) {
                $__last_msg = '';
                for ($mi = count($clean_messages) - 1; $mi >= 0; $mi--) {
                    if ($clean_messages[$mi]['role'] === 'user') {
                        $__last_msg = mb_strtolower($clean_messages[$mi]['content']);
                        break;
                    }
                }
            }

            $price_lines[] = "\n**" . $cat_name . "**";
            foreach ($items as $item) {
                $name  = $item['name']  ?? '';
                $price = $item['price'] ?? '';
                if (!$name) continue;
                if ($price && $discount && $source === 'app') {
                    $orig = (int) preg_replace('/[^\d]/', '', $price);
                    $sale = (int) round($orig * (1 - $discount['percent'] / 100));
                    $line = "- {$name}: повна ₴ {$orig}, зі знижкою ₴ {$sale}";
                } elseif ($price) {
                    $line = "- {$name}: {$price}";
                } else {
                    $line = "- {$name} — ціна індивідуально";
                }

                // Короткий опис — завжди (щоб AI міг підібрати процедуру за описом проблеми)
                $desc = $item['desc'] ?? '';
                if ($desc) {
                    // Перше речення — суть процедури
                    $first_sentence = preg_split('/(?<=[.!?])\s+/u', $desc, 2)[0] ?? $desc;
                    $line .= " — {$first_sentence}";
                }

                // Повні деталі — тільки якщо клієнт згадує процедуру або категорію
                $name_lower = mb_strtolower($name);
                $cat_lower  = mb_strtolower($cat_name);
                $mentioned  = ($__last_msg !== '' && (
                    mb_strpos($__last_msg, $name_lower) !== false ||
                    mb_strpos($__last_msg, $cat_lower) !== false ||
                    (mb_strlen($name_lower) >= 5 && mb_strpos($__last_msg, mb_substr($name_lower, 0, 5)) !== false)
                ));
                if ($mentioned) {
                    $duration  = $item['duration']   ?? '';
                    $prep      = $item['prep']       ?? '';
                    $aftercare = $item['aftercare']  ?? '';
                    if ($duration)  $line .= " | Тривалість: {$duration}";
                    // Повний опис (всі речення) якщо клієнт питав
                    if (mb_strlen($desc) > mb_strlen($first_sentence ?? ''))
                        $line .= "\n  Повний опис: {$desc}";
                    if ($prep)      $line .= "\n  Підготовка: {$prep}";
                    if ($aftercare) $line .= "\n  Після процедури: {$aftercare}";
                }
                $price_lines[] = $line;
            }
        }
        $system_prompt .= "\n\n---\n## Актуальний прайс\n" . implode("\n", $price_lines);
        $system_prompt .= "\n\nПримітка: кожна процедура має короткий опис (перше речення). Використовуй його щоб підібрати процедуру під проблему клієнта (наприклад, 'тьмяна шкіра' → кисневий догляд). Для процедур, які клієнт згадує напряму, тобі доступні повні деталі (тривалість, підготовка, після процедури).";

        if ($source === 'app') {
            $system_prompt .= "\n\nВАЖЛИВО: Клієнт спілкується через додаток. Якщо процедура має знижку через застосунок — ЗАВЖДИ називай обидві ціни: повну і зі знижкою через застосунок.";
        } else {
            $system_prompt .= "\n\nПідказка для відповідей про ін'єкційні процедури: нагадай клієнту що при записі через додаток діє -10% знижка на всі ін'єкційні процедури.";
        }
    }
}

// ── 5. Контекст канала (сайт / додаток) ──────────────────────
if ($source === 'site') {
    $system_prompt .= "\n\n---\n## Контекст: сайт drgomon.beauty\nТи спілкуєшся з відвідувачем сайту drgomon.beauty. Людина ще не є зареєстрованим клієнтом. Після відповіді на питання природно запропонуй записатись через [Instagram](https://ig.me/m/dr.gomon) або [Telegram](https://t.me/DrGomonCosmetology), або зателефонувати [073-310-31-10](tel:+380733103110). Також можна порадити завантажити додаток https://drgomon.beauty/app — там діє -10% на ін'єкційні процедури.\nЗавжди використовуй клікабельні markdown-лінки для контактів.";
} else {
    // source === 'app' (включно з незареєстрованими, що використовують inline chat)
    $system_prompt .= "\n\n---\n## Контекст: додаток Dr. Gómon\nТи вбудований асистент у мобільному додатку Dr. Gomon. Для запису пропонуй написати в чаті додатку, зателефонувати [073-310-31-10](tel:+380733103110), або написати лікарю в [Instagram](https://ig.me/m/dr.gomon) чи [Telegram](https://t.me/DrGomonCosmetology).\nЗавжди використовуй клікабельні markdown-лінки для контактів.";
}

// ═══════════════════════════════════════════════════════════════
//  ЗАПИТ ДО CLAUDE (Anthropic API) + автофолбек моделей
// ═══════════════════════════════════════════════════════════════

// Порядок пріоритету: найновіші спочатку
$model_chain = [
    'claude-sonnet-4-6',
    'claude-sonnet-4-5',
    'claude-3-5-sonnet-20241022',
    'claude-haiku-4-5-20251001',
];

// Кеш активної моделі — не тестуємо щоразу
$model_cache_file = '/home/gomoncli/private_data/active_model.txt';
$active_model = file_exists($model_cache_file)
    ? trim(file_get_contents($model_cache_file))
    : $model_chain[0];

// Якщо кешована модель не в списку — беремо першу
if (!in_array($active_model, $model_chain)) {
    $active_model = $model_chain[0];
}

// Спробуємо кешовану, потім fallback по ланцюжку
$models_to_try = array_unique(array_merge(
    [$active_model],
    $model_chain
));

$raw = false; $code = 0; $used_model = null;

foreach ($models_to_try as $idx => $model) {
    // Inject image into last user message if provided
    $api_messages = $clean_messages;
    if ($image_b64 && count($api_messages) > 0) {
        // Find last user message (may not be the very last if assistant replied)
        $user_idx = null;
        for ($i = count($api_messages) - 1; $i >= 0; $i--) {
            if ($api_messages[$i]['role'] === 'user') { $user_idx = $i; break; }
        }
        if ($user_idx !== null) {
            $text = $api_messages[$user_idx]['content'] ?: 'Що ви бачите на цьому фото?';
            $api_messages[$user_idx]['content'] = [
                ['type' => 'image', 'source' => ['type' => 'base64', 'media_type' => $image_type, 'data' => $image_b64]],
                ['type' => 'text', 'text' => $text],
            ];
        } else {
            // No user message — append one with the image
            $api_messages[] = ['role' => 'user', 'content' => [
                ['type' => 'image', 'source' => ['type' => 'base64', 'media_type' => $image_type, 'data' => $image_b64]],
                ['type' => 'text', 'text' => 'Що ви бачите на цьому фото?'],
            ]];
        }
    }

    $payload = json_encode([
        'model'      => $model,
        'max_tokens' => 1024,
        'system'     => $system_prompt,
        'messages'   => $api_messages,
    ], JSON_UNESCAPED_UNICODE);

    $ch = curl_init('https://api.anthropic.com/v1/messages');
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => $payload,
        CURLOPT_HTTPHEADER     => [
            'Content-Type: application/json',
            'x-api-key: ' . ANTHROPIC_API_KEY,
            'anthropic-version: 2023-06-01',
        ],
        // Primary model: 20s full timeout. Fallbacks: 12s (швидші моделі).
        // CONNECTTIMEOUT: fail-fast при недоступності endpoint (5s).
        CURLOPT_CONNECTTIMEOUT => 5,
        CURLOPT_TIMEOUT        => ($idx === 0 ? 20 : 12),
    ]);
    $raw      = curl_exec($ch);
    $curl_err = curl_error($ch);
    $code     = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    // Помилка з'єднання (HTTP 000) — endpoint недоступний,
    // немає сенсу пробувати інші моделі на тому самому хості
    if ($raw === false || $code === 0) {
        break;
    }

    if ($code === 200) {
        if ($model !== $active_model) {
            file_put_contents($model_cache_file, $model);
        }
        $used_model = $model;
        break;
    }
    // 429 rate limit = key-level, не модель-специфічна — не пробуємо наступну
    if ($code === 429) {
        break;
    }
    // 529 overloaded або 4xx (модель не знайдена) → пробуємо наступну
}

if (!$used_model) {
    http_response_code(502);
    echo json_encode(['error' => 'Claude API unavailable', 'code' => $code]);
    exit;
}

$claude_data = json_decode($raw, true);
$reply       = $claude_data['content'][0]['text'] ?? '';

if (!$reply) {
    http_response_code(502);
    echo json_encode(['error' => 'Empty Claude response']);
    exit;
}

// Increment rate limit AFTER successful API call (not before)
if (isset($rl_db) && $rl_db) {
    try {
        $ins = $rl_db->prepare('INSERT INTO rl(key,date,count) VALUES(:k,:d,1) ON CONFLICT(key,date) DO UPDATE SET count=count+1');
        $ins->bindValue(':k', $rl_key);
        $ins->bindValue(':d', $today);
        $ins->execute();
    } catch (Exception $e) {
        error_log('chat.php RL increment error: ' . $e->getMessage());
    }
}

// ═══════════════════════════════════════════════════════════════
//  ДЕТЕКЦІЯ СКАСУВАННЯ ЗАПИСУ
// ═══════════════════════════════════════════════════════════════

$cancelled = false;
if (preg_match('/<CANCEL(?:\s+date="(\d{4}-\d{2}-\d{2})")?\s*>/', $reply, $cm) && $phone_norm) {
    $cancel_date = $cm[1] ?? null;
    $reply = trim(preg_replace('/<CANCEL[^>]*>/', '', $reply));
    $cancel_payload = ['phone' => $phone_norm];
    if ($cancel_date) $cancel_payload['date'] = $cancel_date;
    $cancel_ch = curl_init('http://127.0.0.1:5001/api/chat/cancel-appointment');
    curl_setopt_array($cancel_ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_POST => true,
        CURLOPT_TIMEOUT => 15,
        CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
        CURLOPT_POSTFIELDS => json_encode($cancel_payload),
    ]);
    $cancel_raw = curl_exec($cancel_ch);
    $cancel_code = curl_getinfo($cancel_ch, CURLINFO_HTTP_CODE);
    curl_close($cancel_ch);
    $cancel_data = json_decode($cancel_raw, true) ?: [];
    if ($cancel_code === 200 && !empty($cancel_data['ok'])) {
        $reply .= "\n\n\u{2705} " . ($cancel_data['message'] ?? 'Запис скасовано.');
        $cancelled = true;
    } else {
        $reply .= "\n\n\u{26a0}\u{fe0f} " . ($cancel_data['error'] ?? 'Не вдалося скасувати запис.');
    }
} elseif (preg_match('/<CANCEL[^>]*>/', $reply) && !$phone_norm) {
    $reply = trim(preg_replace('/<CANCEL[^>]*>/', '', $reply));
    $reply .= "\n\n\u{26a0}\u{fe0f} Для скасування потрібно авторизуватись у додатку.";
}

//  ДЕТЕКЦІЯ ПІДІБРАНОЇ ПРОЦЕДУРИ
// ═══════════════════════════════════════════════════════════════

$procedure = null;

if (preg_match('/<PROCEDURE>(.*?)<\/PROCEDURE>/si', $reply, $matches)) {
    $procedure = trim($matches[1]);
    // Видаляємо тег з відповіді — клієнт його не бачить
    $reply = trim(preg_replace('/<PROCEDURE>.*?<\/PROCEDURE>/si', '', $reply));
}

// ═══════════════════════════════════════════════════════════════
//  ВІДПОВІДЬ ФРОНТУ
// (Telegram надсилає фронт через notify_procedure.php при закритті)

// ═══════════════════════════════════════════════════════════════

echo json_encode([
    'reply'     => $reply,
    'procedure' => $procedure,
], JSON_UNESCAPED_UNICODE);

// ── SAVE TO AI CHAT LOG DB ──────────────────────────────────────
try {
    $ai_db = new SQLite3('/home/gomoncli/zadarma/ai_chat.db');
    $ai_db->exec('PRAGMA journal_mode=WAL');
    $ai_db->exec(
        'CREATE TABLE IF NOT EXISTS ai_messages ('
        . 'id INTEGER PRIMARY KEY AUTOINCREMENT,'
        . 'session_key TEXT NOT NULL,'
        . 'source TEXT NOT NULL,'
        . 'user_phone TEXT,'
        . 'user_name TEXT,'
        . 'role TEXT NOT NULL,'
        . 'content TEXT NOT NULL,'
        . 'created_at TEXT DEFAULT CURRENT_TIMESTAMP)'
    );
    $ai_db->exec('CREATE INDEX IF NOT EXISTS idx_ai_session ON ai_messages(session_key)');
    $ai_db->exec('CREATE INDEX IF NOT EXISTS idx_ai_created ON ai_messages(created_at)');

    // Session key: phone for authed users, IP+date for guests
    $sess_key = $user_phone ? 'phone_' . substr($user_phone, -9) : 'ip_' . $client_ip . '_' . $today;

    // Save last user message
    $last_user_msg = '';
    for ($i = count($clean_messages) - 1; $i >= 0; $i--) {
        if ($clean_messages[$i]['role'] === 'user') {
            $last_user_msg = $clean_messages[$i]['content'];
            break;
        }
    }
    if ($last_user_msg) {
        $st = $ai_db->prepare('INSERT INTO ai_messages (session_key, source, user_phone, user_name, role, content) VALUES (:sk, :src, :ph, :nm, :r, :c)');
        $st->bindValue(':sk', $sess_key);
        $st->bindValue(':src', $source);
        $st->bindValue(':ph', $user_phone ?: null, SQLITE3_TEXT);
        $st->bindValue(':nm', $user_name ?: null, SQLITE3_TEXT);
        $st->bindValue(':r', 'user');
        $st->bindValue(':c', $last_user_msg);
        $st->execute();
    }
    // Save AI reply
    $st2 = $ai_db->prepare('INSERT INTO ai_messages (session_key, source, user_phone, user_name, role, content) VALUES (:sk, :src, :ph, :nm, :r, :c)');
    $st2->bindValue(':sk', $sess_key);
    $st2->bindValue(':src', $source);
    $st2->bindValue(':ph', $user_phone ?: null, SQLITE3_TEXT);
    $st2->bindValue(':nm', $user_name ?: null, SQLITE3_TEXT);
    $st2->bindValue(':r', 'assistant');
    $st2->bindValue(':c', $reply);
    $st2->execute();

    // Cleanup >90 days (1 in 50 requests)
    if (rand(1, 50) === 1) {
        $ai_db->exec("DELETE FROM ai_messages WHERE created_at < datetime('now', '-90 days')");
    }
    $ai_db->close();
} catch (Exception $e) {
    error_log('ai_chat log error: ' . $e->getMessage());
}

// ── LOG ──────────────────────────────────────────────────────────
$duration_ms = (int)(microtime(true) * 1000) - $start_ms;
if (!empty($rl_db)) {
    try {
        $log_stmt = $rl_db->prepare(
            'INSERT INTO chat_log(ts,ip,phone,source,duration_ms,model,status,req_len)'
            . ' VALUES(:ts,:ip,:ph,:src,:dur,:mdl,:st,:rlen)'
        );
        $log_stmt->bindValue(':ts',   date('Y-m-d H:i:s'));
        $log_stmt->bindValue(':ip',   $client_ip);
        $log_stmt->bindValue(':ph',   $phone_norm ?: null);
        $log_stmt->bindValue(':src',  $source);
        $log_stmt->bindValue(':dur',  $duration_ms, SQLITE3_INTEGER);
        $log_stmt->bindValue(':mdl',  $used_model ?: 'unknown');
        $log_stmt->bindValue(':st',   'ok');
        $log_stmt->bindValue(':rlen', strlen($clean_messages[count($clean_messages)-1]['content'] ?? ''), SQLITE3_INTEGER);
        $log_stmt->execute();
    } catch (Exception $e) {
        error_log('chat.php log error: ' . $e->getMessage());
    } finally {
        $rl_db->close();
    }
}

// ═══════════════════════════════════════════════════════════════
//  ХЕЛПЕРИ
// ═══════════════════════════════════════════════════════════════

