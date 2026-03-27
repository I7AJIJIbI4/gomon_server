<?php
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
    // 'http://localhost:3000', // для локальної розробки
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

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed']);
    exit;
}


// ═══════════════════════════════════════════════════════════════
//  ХЕЛПЕРИ ДЛЯ TELEGRAM
// ═══════════════════════════════════════════════════════════════

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

$body = json_decode(file_get_contents('php://input'), true);

if (!$body) {
    http_response_code(400);
    echo json_encode(['error' => 'Invalid JSON']);
    exit;
}

$user_name  = trim($body['user']['name']  ?? '');
$user_phone = trim($body['user']['phone'] ?? '');
$source     = $body['source'] ?? 'app';
$messages   = $body['messages'] ?? [];

// Очищаємо і валідуємо messages
$clean_messages = [];
foreach ($messages as $msg) {
    $role    = $msg['role']    ?? '';
    $content = trim($msg['content'] ?? '');
    if (in_array($role, ['user', 'assistant'], true) && $content !== '') {
        $clean_messages[] = ['role' => $role, 'content' => $content];
    }
}

if (empty($clean_messages)) {
    http_response_code(400);
    echo json_encode(['error' => 'No valid messages']);
    exit;
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
                usort($services, fn($a, $b) => strcmp($b['date'] ?? '', $a['date'] ?? ''));
                $appt_lines = [];
                foreach (array_slice($services, 0, 15) as $s) {
                    $appt_lines[] = "- {$s['date']}: {$s['service']}";
                }
                $system_prompt .= "\n\n---\n## Попередні візити клієнта (всього: {$visits_count})\n"
                    . implode("\n", $appt_lines);
            } else {
                $system_prompt .= "\n\n---\n## Попередні візити клієнта\nКлієнт ще не має записаних візитів.";
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
        $system_prompt .= "\n\n---\n## Поточні акції клініки\n" . implode("\n", $promo_lines);
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
        foreach ($prices_data as $cat_id => $groups) {
            $discount = $cat_discounts[$cat_id] ?? null;
            if ($discount && $source === 'app') {
                $price_lines[] = "\n> Акція для користувачів додатку: {$discount['promo']} (-{$discount['percent']}% від прайсу)";
            }
            foreach ($groups as $group) {
                $price_lines[] = "\n**" . $group['title'] . "**";
                foreach ($group['rows'] as $row) {
                    $name     = $row[0] ?? '';
                    $desc     = !empty($row[1]) ? " ({$row[1]})" : '';
                    $price    = $row[2] ?? '';
                    $duration = !empty($row[3]) ? ", {$row[3]}" : '';
                    if ($price && $discount && $source === 'app') {
                        $orig = (int) preg_replace('/[^\d]/', '', $price);
                        $sale = (int) round($orig * (1 - $discount['percent'] / 100));
                        $price_lines[] = "- {$name}{$desc}: повна ₴ {$orig}, зі знижкою ₴ {$sale}{$duration}";
                    } elseif ($price) {
                        $price_lines[] = "- {$name}{$desc}: {$price}{$duration}";
                    } else {
                        $price_lines[] = "- {$name}{$desc} — ціна індивідуально";
                    }
                }
            }
        }
        $system_prompt .= "\n\n---\n## Актуальний прайс\n" . implode("\n", $price_lines);

        if ($source === 'app') {
            $system_prompt .= "\n\nВАЖЛИВО: Клієнт спілкується через додаток. Якщо процедура має знижку через застосунок — ЗАВЖДИ називай обидві ціни: повну і зі знижкою через застосунок.";
        } else {
            $system_prompt .= "\n\nПідказка для відповідей про ін'єкційні процедури: нагадай клієнту що при записі через додаток діє -10% знижка на всі ін'єкційні процедури.";
        }
    }
}

// ── 5. Контекст канала (сайт / додаток) ──────────────────────
if ($source === 'site') {
    $system_prompt .= "\n\n---\n## Контекст: сайт gomonclinic.com\nТи спілкуєшся з відвідувачем сайту gomonclinic.com. Людина ще не є зареєстрованим клієнтом. Після відповіді на питання природно запропонуй записатись: Instagram @dr.gomon (ig.me/m/dr.gomon) або Telegram @DrGomonCosmetology. Також можна порадити завантажити додаток gomonclinic.com/app — там діє -10% на ін'єкційні процедури.";
} else {
    // source === 'app' (включно з незареєстрованими, що використовують inline chat)
    $system_prompt .= "\n\n---\n## Контекст: додаток Dr. Gómon\nТи вбудований асистент у мобільному додатку клініки. Для запису пропонуй написати в чаті додатку або зателефонувати 073-310-31-10.";
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

foreach ($models_to_try as $model) {
    $payload = json_encode([
        'model'      => $model,
        'max_tokens' => 1024,
        'system'     => $system_prompt,
        'messages'   => $clean_messages,
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
        CURLOPT_TIMEOUT => 30,
    ]);
    $raw  = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    if ($raw !== false && $code === 200) {
        // Якщо модель змінилась — оновлюємо кеш
        if ($model !== $active_model) {
            file_put_contents($model_cache_file, $model);
        }
        $used_model = $model;
        break;
    }
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

// ═══════════════════════════════════════════════════════════════
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
    'procedure' => $procedure, // null або назва — фронт може показати спецповідомлення
], JSON_UNESCAPED_UNICODE);

// ═══════════════════════════════════════════════════════════════
//  ХЕЛПЕРИ
// ═══════════════════════════════════════════════════════════════

function escape_md(string $text): string {
    // Екранування спецсимволів для Telegram Markdown v1
    return str_replace(['_', '*', '[', '`'], ['\_', '\*', '\[', '\`'], $text);
}
