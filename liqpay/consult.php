<?php
/**
 * consult.php — постійна сторінка "Онлайн консультація" (500 грн)
 * gomonclinic.com/consult.php
 *
 * Кожне відкриття генерує новий order_id і зберігає в БД
 * POST: зберігає дані клієнта → редирект на LiqPay
 */

define('BASE_DIR', __DIR__);
define('DB_PATH',  BASE_DIR . '/payments.db');

require_once BASE_DIR . '/gomon_payments/liqpay_php.php';

$AMOUNT      = 500.0;
$DESCRIPTION = 'Онлайн консультація';
$error       = '';

// ── Генеруємо або беремо order_id з сесії ────────────────────
session_start();

// Якщо сесійний order_id вже існує і ще pending — використовуємо його
// Інакше генеруємо новий (щоб не плодити тисячі рядків при F5)
try {
    $db = new PDO('sqlite:' . DB_PATH);
    $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

    $reuse = false;
    if (!empty($_SESSION['consult_order_id'])) {
        $stmt = $db->prepare('SELECT status FROM orders WHERE order_id = ?');
        $stmt->execute([$_SESSION['consult_order_id']]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);
        if ($row && $row['status'] === 'pending') {
            $order_id = $_SESSION['consult_order_id'];
            $reuse = true;
        }
    }

    if (!$reuse) {
        $order_id = 'consult_' . substr(uniqid('', true), -8);
        $db->prepare('
            INSERT INTO orders (order_id, amount, description, status, is_permanent)
            VALUES (?, ?, ?, \'pending\', 1)
        ')->execute([$order_id, $AMOUNT, $DESCRIPTION]);
        $_SESSION['consult_order_id'] = $order_id;
    }

} catch (Exception $e) {
    error_log('consult.php DB: ' . $e->getMessage());
    http_response_code(500);
    exit('Server error');
}

// ── POST: зберегти дані → редирект на LiqPay ─────────────────
if ($_SERVER['REQUEST_METHOD'] === 'POST') {

    $phone = preg_replace('/[^\d+]/', '', trim($_POST['phone'] ?? ''));
    $name  = htmlspecialchars(trim($_POST['name']  ?? ''), ENT_QUOTES, 'UTF-8');
    $email = filter_var(trim($_POST['email'] ?? ''), FILTER_SANITIZE_EMAIL);
    $insta = trim($_POST['instagram'] ?? '');

    if (strlen($phone) < 10) {
        $error = 'Введіть коректний номер телефону';
    }

    if (empty($error)) {
        if (!empty($insta)) {
            $insta = preg_replace('/^@/', '', $insta);
            $insta = preg_replace('#^https?://(www\.)?instagram\.com/#', '', $insta);
            $insta = 'https://instagram.com/' . rtrim($insta, '/');
        }

        try {
            $db->prepare('
                INSERT OR REPLACE INTO clients (order_id, phone, name, email, instagram)
                VALUES (?, ?, ?, ?, ?)
            ')->execute([$order_id, $phone, $name ?: null, $email ?: null, $insta ?: null]);
        } catch (Exception $e) {
            error_log('consult.php client: ' . $e->getMessage());
        }

        // Новий order_id після відправки (щоб наступне відкриття було чисте)
        unset($_SESSION['consult_order_id']);

        $result_params = http_build_query([
            'desc'   => $DESCRIPTION,
            'order'  => $order_id,
            'amount' => $AMOUNT,
            'name'   => $name,
        ]);
        $result_url = 'https://gomonclinic.com/payment-success.php?' . $result_params;

        $lp  = new LiqPayPHP(
            trim(file_get_contents(BASE_DIR . '/gomon_payments/.public_key')),
            trim(file_get_contents(BASE_DIR . '/gomon_payments/.private_key'))
        );
        $url = $lp->createPaymentUrl(
            $order_id, $AMOUNT,
            'Клініка Гомон — ' . $DESCRIPTION,
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
  <title>Онлайн консультація — Dr. Gomon Cosmetology</title>
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
    body{font-family:'Jost',sans-serif;background:var(--cream);color:var(--text);min-height:100vh;display:flex;flex-direction:column}
    header{padding:20px 40px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border)}
    .logo img{height:38px}
    main{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:0;max-width:960px;margin:0 auto;width:100%;padding:60px 24px;align-items:start}

    /* Left: hero */
    .hero{padding-right:60px}
    .hero-tag{font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--gold);margin-bottom:20px}
    .hero h1{font-family:'Cormorant Garamond',serif;font-weight:300;font-size:clamp(32px,4vw,48px);line-height:1.15;color:var(--dark);margin-bottom:20px}
    .hero h1 em{font-style:italic;color:var(--gold)}
    .hero p{font-size:14px;font-weight:300;color:var(--muted);line-height:1.8;margin-bottom:12px}
    .hero-price{margin-top:32px;padding:20px 0;border-top:1px solid var(--border);border-bottom:1px solid var(--border)}
    .hero-price .label{font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin-bottom:6px}
    .hero-price .amount{font-family:'Cormorant Garamond',serif;font-size:48px;font-weight:300;color:var(--dark)}
    .hero-price .amount span{font-size:20px;color:var(--muted);margin-left:4px}
    .includes{margin-top:28px;list-style:none}
    .includes li{font-size:13px;font-weight:300;color:var(--text);padding:6px 0;border-bottom:1px solid var(--border);display:flex;gap:10px;align-items:baseline}
    .includes li::before{content:'◈';color:var(--gold);font-size:9px;flex-shrink:0}

    /* Right: form */
    .form-wrap{background:#fff;border:1px solid var(--border);border-radius:2px;padding:36px 32px;position:relative;overflow:hidden}
    .form-wrap::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--gold-lt),var(--gold),var(--gold-lt))}
    .form-title{font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin-bottom:24px}
    .field{margin-bottom:18px}
    .field label{display:block;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:7px}
    .field label .opt{font-size:10px;font-weight:300;letter-spacing:.03em;text-transform:none;font-style:italic;margin-left:4px}
    .field input{width:100%;padding:11px 14px;border:1px solid var(--border);border-radius:1px;background:var(--cream);color:var(--dark);font-family:'Jost',sans-serif;font-size:14px;font-weight:300;outline:none;transition:border-color .2s,background .2s}
    .field input:focus{border-color:var(--gold);background:#fff}
    .field input::placeholder{color:var(--muted);opacity:.6}
    .hint{font-size:11px;color:var(--muted);margin-top:5px;font-weight:300}
    .error-msg{background:#fdf2f2;border:1px solid rgba(192,57,43,.2);border-radius:1px;padding:11px 14px;font-size:13px;color:var(--red);margin-bottom:18px}
    .btn-pay{width:100%;padding:15px;background:var(--dark);color:var(--cream);border:none;border-radius:1px;cursor:pointer;font-family:'Jost',sans-serif;font-size:11px;font-weight:500;letter-spacing:.15em;text-transform:uppercase;transition:background .22s;display:flex;align-items:center;justify-content:center;gap:8px;margin-top:6px}
    .btn-pay:hover{background:var(--gold);color:var(--dark)}
    .btn-pay svg{width:15px;height:15px;stroke:currentColor;fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
    .secure{display:flex;align-items:center;justify-content:center;gap:6px;margin-top:14px;font-size:10px;color:var(--muted);font-weight:300}
    .secure svg{width:12px;height:12px;stroke:var(--muted);fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}

    footer{padding:18px 40px;border-top:1px solid var(--border);display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}
    footer p{font-size:11px;color:var(--muted);font-weight:300}
    footer a{color:var(--muted);text-decoration:none}
    footer a:hover{color:var(--gold)}

    @media(max-width:720px){
      main{grid-template-columns:1fr;padding:32px 16px}
      .hero{padding-right:0;margin-bottom:32px}
      header,footer{padding:14px 16px}
    }
  </style>
</head>
<body>
<header>
  <a href="https://gomonclinic.com"><img src="https://www.gomonclinic.com/logo.png" alt="Dr. Gomon Cosmetology"/></a>
  <span style="font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:300">Черкаси</span>
</header>

<main>
  <!-- Hero -->
  <div class="hero">
    <p class="hero-tag">Dr. Gomon Cosmetology</p>
    <h1>Онлайн<br/><em>консультація</em></h1>
    <p>Індивідуальна консультація з косметологом. Аналіз стану шкіри, підбір процедур та домашнього догляду.</p>
    <div class="hero-price">
      <p class="label">Вартість</p>
      <p class="amount">500 <span>грн</span></p>
    </div>
    <ul class="includes">
      <li>Аналіз стану шкіри за фото</li>
      <li>Підбір процедур під ваш запит</li>
      <li>Рекомендації з домашнього догляду</li>
      <li>Відповідь протягом 24 годин</li>
    </ul>
  </div>

  <!-- Form -->
  <div class="form-wrap">
    <p class="form-title">Контактні дані</p>

    <?php if ($error): ?>
      <div class="error-msg"><?= htmlspecialchars($error) ?></div>
    <?php endif ?>

    <form method="POST" novalidate>
      <div class="field">
        <label>Телефон <span style="color:var(--gold)">*</span></label>
        <input type="tel" name="phone" placeholder="+380 XX XXX XX XX"
               value="<?= htmlspecialchars($_POST['phone'] ?? '') ?>"
               inputmode="tel" autocomplete="tel" required/>
      </div>
      <div class="field">
        <label>Ім'я <span class="opt">необов'язково</span></label>
        <input type="text" name="name" placeholder="Ваше ім'я"
               value="<?= htmlspecialchars($_POST['name'] ?? '') ?>"/>
      </div>
      <div class="field">
        <label>Email <span class="opt">отримаєте квитанцію</span></label>
        <input type="email" name="email" placeholder="your@email.com"
               value="<?= htmlspecialchars($_POST['email'] ?? '') ?>"/>
      </div>
      <div class="field">
        <label>Instagram <span class="opt">необов'язково</span></label>
        <input type="text" name="instagram" placeholder="@ваш_акаунт"
               value="<?= htmlspecialchars($_POST['instagram'] ?? '') ?>"/>
        <p class="hint">@нікнейм або посилання</p>
      </div>
      <button type="submit" class="btn-pay">
        <svg viewBox="0 0 24 24"><rect x="1" y="4" width="22" height="16" rx="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>
        Оплатити · 500 грн
      </button>
    </form>
    <p class="secure">
      <svg viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
      Захищено LiqPay · SSL
    </p>
  </div>
</main>

<footer>
  <p>© 2026 Dr. Gómon Cosmetology · Черкаси</p>
  <p><a href="tel:+380733103110">073-310-31-10</a></p>
</footer>
<script>
document.querySelector('input[name=phone]').addEventListener('input',function(){
  var v=this.value.replace(/[^\d+]/g,'');
  if(v&&v[0]!=='+')v='+'+v;
  this.value=v;
});
</script>
</body>
</html>
