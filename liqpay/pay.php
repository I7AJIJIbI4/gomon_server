<?php
/**
 * pay.php — сторінка форми клієнта
 * Розмістити як: gomonclinic.com/pay.php
 * Використання: gomonclinic.com/pay.php?oid=clinic_123_abc12345
 *
 * Також обробляє POST: зберігає дані клієнта → редирект на LiqPay
 */

define('BASE_DIR', __DIR__);
define('DB_PATH',  BASE_DIR . '/payments.db');

$error    = '';
$order    = null;
$client   = null;

// ── Отримуємо order_id ────────────────────────────────────────
$order_id = trim($_GET['oid'] ?? $_POST['order_id'] ?? '');

if (empty($order_id)) {
    http_response_code(404);
    include 'error_page.php';
    exit;
}

// ── Завантажуємо замовлення з БД ─────────────────────────────
try {
    $db = new PDO('sqlite:' . DB_PATH);
    $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    $stmt = $db->prepare('SELECT * FROM orders WHERE order_id = ?');
    $stmt->execute([$order_id]);
    $order = $stmt->fetch(PDO::FETCH_ASSOC);

    if (!$order) {
        http_response_code(404);
        include 'error_page.php';
        exit;
    }

    // Вже оплачено?
    if ($order['status'] === 'paid') {
        include 'already_paid.php';
        exit;
    }

    // Перевіряємо чи вже є дані клієнта
    $stmt2 = $db->prepare('SELECT * FROM clients WHERE order_id = ?');
    $stmt2->execute([$order_id]);
    $client = $stmt2->fetch(PDO::FETCH_ASSOC);

} catch (Exception $e) {
    error_log('pay.php DB: ' . $e->getMessage());
    http_response_code(500);
    exit('Server error');
}

// ── POST: зберегти дані клієнта + редирект на LiqPay ─────────
if ($_SERVER['REQUEST_METHOD'] === 'POST') {

    $phone = preg_replace('/[^\d+]/', '', trim($_POST['phone'] ?? ''));
    $name  = htmlspecialchars(trim($_POST['name']  ?? ''), ENT_QUOTES, 'UTF-8');
    $email = filter_var(trim($_POST['email'] ?? ''), FILTER_SANITIZE_EMAIL);
    $insta = trim($_POST['instagram'] ?? '');

    // Валідація
    if (strlen($phone) < 10) {
        $error = 'Введіть коректний номер телефону';
    }

    if (empty($error)) {
        // Нормалізуємо Instagram
        if (!empty($insta)) {
            $insta = preg_replace('/^@/', '', $insta);
            $insta = preg_replace('#^https?://(www\.)?instagram\.com/#', '', $insta);
            $insta = rtrim($insta, '/');
            $insta = 'https://instagram.com/' . $insta;
        }

        // Зберігаємо або оновлюємо клієнта
        try {
            $db->prepare('
                INSERT OR REPLACE INTO clients (order_id, phone, name, email, instagram)
                VALUES (?, ?, ?, ?, ?)
            ')->execute([$order_id, $phone, $name ?: null, $email ?: null, $insta ?: null]);
        } catch (Exception $e) {
            error_log('pay.php client save: ' . $e->getMessage());
        }

        // Формуємо result_url з параметрами для success сторінки
        $result_params = http_build_query([
            'desc'   => $order['description'],
            'order'  => $order_id,
            'amount' => $order['amount'],
            'name'   => $name,
        ]);
        $result_url = 'https://gomonclinic.com/payment-success.php?' . $result_params;

        // Генеруємо LiqPay URL
        require_once BASE_DIR . '/gomon_payments/liqpay_php.php';
        $lp  = new LiqPayPHP(
            file_get_contents(BASE_DIR . '/gomon_payments/.public_key'),
            file_get_contents(BASE_DIR . '/gomon_payments/.private_key')
        );
        $url = $lp->createPaymentUrl(
            $order_id,
            $order['amount'],
            'Клініка Гомон — ' . $order['description'],
            'https://gomonclinic.com/liqpay_callback.php',
            $result_url
        );

        header('Location: ' . $url);
        exit;
    }
}
?>
<!DOCTYPE html>
<html lang="uk">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Оплата — Dr. Gomon Cosmetology</title>
  <meta name="robots" content="noindex,nofollow"/>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;1,300&family=Jost:wght@300;400;500&display=swap" rel="stylesheet"/>
  <style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    :root{
      --cream:#faf8f5;--warm:#f3ede4;--gold:#c9a96e;--gold-lt:#e8d5b0;
      --dark:#1a1410;--text:#3d3530;--muted:#9a8f87;--border:rgba(201,169,110,.22);
      --red:#c0392b;
    }
    html{scroll-behavior:smooth}
    body{font-family:'Jost',sans-serif;background:var(--cream);color:var(--text);min-height:100vh;display:flex;flex-direction:column}

    header{padding:20px 40px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border)}
    .logo img{height:38px;width:auto}

    main{flex:1;display:flex;align-items:center;justify-content:center;padding:48px 20px}

    .wrap{width:100%;max-width:480px}

    /* Order summary */
    .summary{background:#fff;border:1px solid var(--border);border-radius:2px;padding:28px 32px;margin-bottom:24px;position:relative;overflow:hidden;
      opacity:0;animation:rise .6s cubic-bezier(.22,.68,0,1.2) .1s forwards}
    .summary::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--gold-lt),var(--gold),var(--gold-lt))}
    .summary-label{font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--gold);margin-bottom:12px}
    .summary-desc{font-family:'Cormorant Garamond',serif;font-size:22px;font-weight:300;color:var(--dark);margin-bottom:8px}
    .summary-amount{font-family:'Cormorant Garamond',serif;font-size:36px;font-weight:300;color:var(--dark)}
    .summary-amount span{font-size:18px;color:var(--muted);margin-left:4px}

    /* Form card */
    .card{background:#fff;border:1px solid var(--border);border-radius:2px;padding:36px 32px;
      opacity:0;animation:rise .6s cubic-bezier(.22,.68,0,1.2) .25s forwards}

    .card-title{font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin-bottom:24px}

    .field{margin-bottom:20px}
    .field label{display:block;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:8px}
    .field label .req{color:var(--gold);margin-left:2px}
    .field label .opt{color:var(--muted);font-size:10px;font-weight:300;letter-spacing:.05em;text-transform:none;margin-left:4px;font-style:italic}

    .field input{
      width:100%;padding:12px 16px;
      border:1px solid var(--border);border-radius:1px;
      background:var(--cream);color:var(--dark);
      font-family:'Jost',sans-serif;font-size:14px;font-weight:300;
      transition:border-color .2s,background .2s;
      outline:none;
    }
    .field input:focus{border-color:var(--gold);background:#fff}
    .field input::placeholder{color:var(--muted);opacity:.7}
    .field input.error-field{border-color:var(--red)}

    .field .hint{font-size:11px;color:var(--muted);margin-top:6px;font-weight:300}

    .error-msg{background:#fdf2f2;border:1px solid rgba(192,57,43,.2);border-radius:1px;
      padding:12px 16px;font-size:13px;color:var(--red);margin-bottom:20px}

    .btn-pay{
      width:100%;padding:16px;margin-top:8px;
      background:var(--dark);color:var(--cream);
      border:none;border-radius:1px;cursor:pointer;
      font-family:'Jost',sans-serif;font-size:12px;font-weight:500;
      letter-spacing:.15em;text-transform:uppercase;
      transition:background .22s;
      display:flex;align-items:center;justify-content:center;gap:10px;
    }
    .btn-pay:hover{background:var(--gold);color:var(--dark)}
    .btn-pay svg{width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}

    .secure{display:flex;align-items:center;justify-content:center;gap:8px;margin-top:16px;font-size:11px;color:var(--muted);font-weight:300}
    .secure svg{width:13px;height:13px;stroke:var(--muted);fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}

    footer{padding:18px 40px;border-top:1px solid var(--border);display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}
    footer p{font-size:11px;color:var(--muted);font-weight:300}
    footer a{color:var(--muted);text-decoration:none}
    footer a:hover{color:var(--gold)}

    @keyframes rise{to{opacity:1;transform:translateY(0)}
      from{opacity:0;transform:translateY(20px)}}
    @media(max-width:560px){
      header,footer{padding:14px 16px}
      .card,.summary{padding:28px 20px}
    }
  </style>
</head>
<body>
<header>
  <a href="https://gomonclinic.com">
    <img src="https://www.gomonclinic.com/logo.png" alt="Dr. Gomon Cosmetology"/>
  </a>
  <span style="font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:300">Черкаси</span>
</header>

<main>
  <div class="wrap">

    <!-- Деталі замовлення -->
    <div class="summary">
      <p class="summary-label">Деталі оплати</p>
      <p class="summary-desc"><?= htmlspecialchars($order['description']) ?></p>
      <p class="summary-amount">
        <?= number_format($order['amount'], 0, '.', '\u00a0') ?>
        <span>грн</span>
      </p>
    </div>

    <!-- Форма -->
    <div class="card">
      <p class="card-title">Ваші контактні дані</p>

      <?php if ($error): ?>
        <div class="error-msg"><?= htmlspecialchars($error) ?></div>
      <?php endif ?>

      <form method="POST" action="/pay.php" novalidate>
        <input type="hidden" name="order_id" value="<?= htmlspecialchars($order_id) ?>"/>

        <div class="field">
          <label>Номер телефону <span class="req">*</span></label>
          <input type="tel" name="phone" placeholder="+380 XX XXX XX XX"
                 value="<?= htmlspecialchars($_POST['phone'] ?? '') ?>"
                 inputmode="tel" autocomplete="tel" required/>
        </div>

        <div class="field">
          <label>Ім'я <span class="opt">необов'язково</span></label>
          <input type="text" name="name" placeholder="Ваше ім'я"
                 value="<?= htmlspecialchars($_POST['name'] ?? '') ?>"
                 autocomplete="given-name"/>
        </div>

        <div class="field">
          <label>Email <span class="opt">необов'язково — отримаєте квитанцію</span></label>
          <input type="email" name="email" placeholder="your@email.com"
                 value="<?= htmlspecialchars($_POST['email'] ?? '') ?>"
                 autocomplete="email"/>
        </div>

        <div class="field">
          <label>Instagram <span class="opt">необов'язково</span></label>
          <input type="text" name="instagram" placeholder="@ваш_акаунт"
                 value="<?= htmlspecialchars($_POST['instagram'] ?? '') ?>"/>
          <p class="hint">Введіть @нікнейм або посилання</p>
        </div>

        <button type="submit" class="btn-pay">
          <svg viewBox="0 0 24 24"><rect x="1" y="4" width="22" height="16" rx="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>
          Перейти до оплати · <?= number_format($order['amount'], 0) ?> грн
        </button>
      </form>

      <p class="secure">
        <svg viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
        Захищено LiqPay · SSL шифрування
      </p>
    </div>

  </div>
</main>

<footer>
  <p>© 2026 Dr. Gómon Cosmetology · Черкаси</p>
  <p><a href="tel:+380733103110">073-310-31-10</a></p>
</footer>

<script>
// Форматування телефону
document.querySelector('input[name=phone]').addEventListener('input', function() {
  var v = this.value.replace(/[^\d+]/g, '');
  if (v && v[0] !== '+') v = '+' + v;
  this.value = v;
});
</script>
</body>
</html>
