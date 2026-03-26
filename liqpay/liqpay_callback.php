<?php
/**
 * liqpay_callback.php
 * Розмістити у корені сайту: gomonclinic.com/liqpay_callback.php
 * LiqPay надсилає POST сюди після кожної транзакції
 */

define('BASE_DIR', __DIR__);
define('DB_PATH',  BASE_DIR . '/payments.db');
define('PYTHON',   '/usr/bin/python3.6');
define('SCRIPTS',  BASE_DIR . '/gomon_payments');

// ── Читаємо POST ──────────────────────────────────────────────
$data      = $_POST['data']      ?? '';
$signature = $_POST['signature'] ?? '';

if (empty($data) || empty($signature)) {
    http_response_code(400);
    exit('Bad Request');
}

// ── Верифікація підпису ───────────────────────────────────────
require_once BASE_DIR . '/gomon_payments/liqpay_verify.php';

$private_key = file_get_contents(BASE_DIR . '/gomon_payments/.private_key');
$private_key = trim($private_key);

$expected = base64_encode(sha1($private_key . $data . $private_key, true));

if (!hash_equals($expected, $signature)) {
    http_response_code(403);
    error_log('LiqPay callback: invalid signature');
    exit('Forbidden');
}

// ── Декодуємо payload ─────────────────────────────────────────
$payload  = json_decode(base64_decode($data), true);
$order_id = $payload['order_id']      ?? '';
$status   = $payload['status']        ?? '';
$amount   = $payload['amount']        ?? 0;
$currency = $payload['currency']      ?? 'UAH';
$method   = $payload['payment_method'] ?? '';
$lp_id    = $payload['payment_id']    ?? '';
$paid_at  = date('Y-m-d H:i:s');

if (empty($order_id)) {
    http_response_code(200);
    exit('OK');
}

// ── Пишемо в SQLite ───────────────────────────────────────────
try {
    $db = new PDO('sqlite:' . DB_PATH);
    $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    // Вставляємо або оновлюємо транзакцію
    $stmt = $db->prepare('
        INSERT INTO transactions
            (order_id, liqpay_id, status, amount, currency, payment_method, paid_at, liqpay_raw)
        VALUES
            (:order_id, :liqpay_id, :status, :amount, :currency, :method, :paid_at, :raw)
        ON CONFLICT(rowid) DO NOTHING
    ');
    $stmt->execute([
        ':order_id'  => $order_id,
        ':liqpay_id' => $lp_id,
        ':status'    => $status,
        ':amount'    => $amount,
        ':currency'  => $currency,
        ':method'    => $method,
        ':paid_at'   => $paid_at,
        ':raw'       => json_encode($payload),
    ]);

    // Оновлюємо статус замовлення
    if ($status === 'success' || $status === 'sandbox') {
        $db->prepare('UPDATE orders SET status = ? WHERE order_id = ?')
           ->execute(['paid', $order_id]);
    } elseif (in_array($status, ['failure', 'error'])) {
        $db->prepare('UPDATE orders SET status = ? WHERE order_id = ?')
           ->execute(['failed', $order_id]);
    } elseif ($status === 'reversed') {
        $db->prepare('UPDATE orders SET status = ? WHERE order_id = ?')
           ->execute(['refunded', $order_id]);
    }

} catch (Exception $e) {
    error_log('LiqPay DB error: ' . $e->getMessage());
    http_response_code(500);
    exit('DB Error');
}

// ── Запускаємо Python notify (async, не чекаємо) ──────────────
if (in_array($status, ['success', 'sandbox', 'reversed', 'failure'])) {
    $cmd = escapeshellcmd(PYTHON . ' ' . SCRIPTS . '/notify.py ' . escapeshellarg($order_id));
    exec($cmd . ' > /dev/null 2>&1 &');
}

// ── Запускаємо Python receipt (якщо є email) ──────────────────
if (in_array($status, ['success', 'sandbox'])) {
    $cmd = escapeshellcmd(PYTHON . ' ' . SCRIPTS . '/receipt.py ' . escapeshellarg($order_id));
    exec($cmd . ' > /dev/null 2>&1 &');
}

http_response_code(200);
echo 'OK';
