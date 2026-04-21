<?php
/**
 * Instagram Messaging Webhook — receives incoming DMs from Meta.
 *
 * Meta sends:
 * - GET with hub.verify_token for verification
 * - POST with messaging events (text, media, reactions)
 *
 * Forwards messages to Flask API for storage in messages DB
 * (same as TG Business messages — unified messenger inbox).
 */

date_default_timezone_set('Europe/Kyiv');
header('Content-Type: application/json; charset=utf-8');

require_once dirname(__DIR__) . '/app/config.php';

define('VERIFY_TOKEN', 'gomon_ig_webhook_2026');
define('FLASK_API', 'http://127.0.0.1:5001');

// ── Webhook Verification (GET) ──
if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    $mode      = $_GET['hub_mode'] ?? $_GET['hub.mode'] ?? '';
    $token     = $_GET['hub_verify_token'] ?? $_GET['hub.verify_token'] ?? '';
    $challenge = $_GET['hub_challenge'] ?? $_GET['hub.challenge'] ?? '';

    if ($mode === 'subscribe' && $token === VERIFY_TOKEN) {
        http_response_code(200);
        echo $challenge;
    } else {
        http_response_code(403);
        echo json_encode(['error' => 'Verification failed']);
    }
    exit;
}

// ── Incoming Messages (POST) ──
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    exit;
}

$raw = file_get_contents('php://input');
$data = json_decode($raw, true);

// Log for debugging
$log_file = '/var/log/gomon/ig_webhook.log';
$ts = date('Y-m-d H:i:s');
file_put_contents($log_file, "[$ts] " . substr($raw, 0, 500) . "\n", FILE_APPEND);

if (!$data || !isset($data['entry'])) {
    http_response_code(200);
    echo 'ok';
    exit;
}

// Process each entry
foreach ($data['entry'] as $entry) {
    // entry.id = our IG page ID that received the webhook
    $page_id = $entry['id'] ?? '';
    $messaging = $entry['messaging'] ?? [];
    foreach ($messaging as $event) {
        // Skip non-message events (read receipts, message_edit, reactions, delivery)
        if (isset($event['read']) || isset($event['message_edit']) || isset($event['delivery'])) continue;

        $sender_id    = $event['sender']['id'] ?? '';
        $recipient_id = $event['recipient']['id'] ?? '';
        $timestamp    = $event['timestamp'] ?? time();
        $message      = $event['message'] ?? null;

        if (!$message || !$sender_id) continue;

        // Echo = message sent BY our page (sender = our page or entry page)
        $is_echo = !empty($message['is_echo']) || ($sender_id === $page_id);

        $text      = $message['text'] ?? '';
        $mid       = $message['mid'] ?? '';
        $media_url = '';
        $media_type = 'text';

        // Check for attachments (images, video, etc.)
        if (isset($message['attachments'])) {
            foreach ($message['attachments'] as $att) {
                $att_type = $att['type'] ?? '';
                $att_url  = $att['payload']['url'] ?? '';
                if ($att_type === 'image') {
                    $media_type = 'photo';
                    $media_url = $att_url;
                } elseif ($att_type === 'video') {
                    $media_type = 'video';
                    $media_url = $att_url;
                } elseif ($att_type === 'audio') {
                    $media_type = 'voice';
                    $media_url = $att_url;
                }
            }
        }

        // Forward to Flask API for unified messenger storage
        $payload = json_encode([
            'platform'     => 'ig',
            'sender_id'    => $sender_id,
            'recipient_id' => $recipient_id,
            'text'         => $text,
            'media_type'   => $media_type,
            'media_url'    => $media_url,
            'is_echo'      => $is_echo,
            'timestamp'    => $timestamp,
        ]);

        $ch = curl_init(FLASK_API . '/api/webhook/ig-message');
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => $payload,
            CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 10,
        ]);
        $resp = curl_exec($ch);
        curl_close($ch);

        file_put_contents($log_file, "[$ts] Forwarded: sender=$sender_id text=" . substr($text, 0, 50) . " resp=$resp\n", FILE_APPEND);

        // AI auto-reply — only for incoming client messages (not echoes, not our page)
        if ($text && $media_type === 'text' && !$is_echo) {
            // Call Flask AI endpoint for IG
            $ai_payload = json_encode([
                'sender_id'    => $sender_id,
                'text'         => $text,
                'platform'     => 'ig',
            ]);
            $ch2 = curl_init(FLASK_API . '/api/webhook/ig-ai-reply');
            curl_setopt_array($ch2, [
                CURLOPT_POST           => true,
                CURLOPT_POSTFIELDS     => $ai_payload,
                CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
                CURLOPT_RETURNTRANSFER => true,
                CURLOPT_TIMEOUT        => 25,
            ]);
            $ai_resp = curl_exec($ch2);
            curl_close($ch2);
            file_put_contents($log_file, "[$ts] AI reply: $ai_resp\n", FILE_APPEND);
        }
    }
}

// Meta expects 200 OK quickly
http_response_code(200);
echo 'ok';
