<?php
/**
 * telegram_webhook.php - ВИПРАВЛЕНИЙ webhook для інтеграції з телеграм ботом
 */

header('Content-Type: application/json');

function writeLog($message) {
    $timestamp = date('Y-m-d H:i:s');
    $logMessage = "[$timestamp] $message" . PHP_EOL;
    file_put_contents('/home/gomoncli/zadarma/telegram_webhook.log', $logMessage, FILE_APPEND | LOCK_EX);
}

try {
    writeLog("🔔 Webhook called - FIXED VERSION");
    
    $input = file_get_contents('php://input');
    
    if (empty($input)) {
        if (!empty($_POST)) {
            $input = json_encode($_POST);
            writeLog("📥 Using POST data: " . $input);
        } else {
            echo json_encode(['status' => 'error', 'message' => 'Empty request']);
            exit;
        }
    }
    
    writeLog("📥 Received data: " . $input);
    
    $webhookData = json_decode($input, true);
    if (json_last_error() !== JSON_ERROR_NONE) {
        if (!empty($_POST)) {
            $webhookData = $_POST;
            writeLog("📥 Using POST array instead of JSON");
        } else {
            echo json_encode(['status' => 'error', 'message' => 'Invalid JSON']);
            exit;
        }
    }
    
    $event = $webhookData['event'] ?? '';
    writeLog("📡 Event type: " . $event);
    
    // ГОЛОВНЕ ВИПРАВЛЕННЯ: Обробляємо NOTIFY_END події для телеграм інтеграції
    if (in_array($event, ['NOTIFY_START', 'NOTIFY_END', 'NOTIFY_INTERNAL'])) {
        writeLog("📞 Processing Telegram integration event: $event");
        
        $pythonScript = '/home/gomoncli/zadarma/process_webhook.py';
        $jsonData = escapeshellarg($input);
        
        $command = "cd /home/gomoncli/zadarma && /usr/bin/python3 $pythonScript $jsonData 2>&1";
        
        writeLog("🐍 Executing Python: $command");
        
        $output = shell_exec($command);
        $exitCode = shell_exec("echo $?");
        
        writeLog("📤 Python output: " . ($output ?: 'No output'));
        writeLog("📊 Exit code: " . ($exitCode ?: 'Unknown'));
        
        if (trim($exitCode) == "0") {
            writeLog("✅ Python script executed successfully");
            echo json_encode(['status' => 'success', 'message' => 'Processed by Python']);
        } else {
            writeLog("❌ Python script failed with exit code: " . $exitCode);
            echo json_encode(['status' => 'error', 'message' => 'Python processing failed']);
        }
    } else {
        writeLog("ℹ️ Event $event not processed for Telegram integration");
        echo json_encode(['status' => 'ignored', 'message' => 'Event not relevant']);
    }
    
} catch (Exception $e) {
    writeLog("❌ Exception: " . $e->getMessage());
    echo json_encode(['status' => 'error', 'message' => $e->getMessage()]);
}
?>
