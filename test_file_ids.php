<?php
// Тестуємо різні формати ID файлів

echo "🎵 Тест різних форматів ID файлів:\n\n";

// Ваші поточні ID
$current_ids = [
    'doors_Laura' => '687a8e13a7987a5ca70a4eb7',
    'gate_Laura' => '687a8e0c3490bc1c2c043ce5', 
    'telegram_Laura' => '687a8e1bf70280c1a109b34c'
];

echo "🔍 Поточні ID (довгі hex):\n";
foreach ($current_ids as $name => $id) {
    echo "$name: $id\n";
}

echo "\n🧪 Можливі альтернативні формати:\n";

// Можливо ID числові
$numeric_ids = [
    'doors_Laura' => '1',
    'gate_Laura' => '2', 
    'telegram_Laura' => '3'
];

foreach ($numeric_ids as $name => $id) {
    echo "$name (числовий): $id\n";
}

echo "\n🔧 Спробуємо скорочені hex:\n";
foreach ($current_ids as $name => $id) {
    $short = substr($id, 0, 8);
    echo "$name (короткий): $short\n";
}

echo "\n📋 JSON відповіді для тестування:\n";

$test_responses = [
    'hex_long' => ['ivr_play' => '687a8e13a7987a5ca70a4eb7'],
    'hex_short' => ['ivr_play' => substr('687a8e13a7987a5ca70a4eb7', 0, 8)],
    'numeric' => ['ivr_play' => '1'],
    'string' => ['ivr_play' => 'doors_Laura'],
    'popular' => ['ivr_saypopular' => 5, 'language' => 'ua']
];

foreach ($test_responses as $type => $response) {
    echo "$type: " . json_encode($response) . "\n";
}
?>
