<?php
/**
 * payment-success.php
 * gomonclinic.com/payment-success.php
 * Параметри: ?desc=...&order=...&amount=...&name=...
 */
$desc   = htmlspecialchars($_GET['desc']   ?? '', ENT_QUOTES, 'UTF-8');
$order  = htmlspecialchars($_GET['order']  ?? '', ENT_QUOTES, 'UTF-8');
$amount = floatval($_GET['amount'] ?? 0);
$name   = htmlspecialchars($_GET['name']   ?? '', ENT_QUOTES, 'UTF-8');

$show_details = !empty($desc) || !empty($order) || $amount > 0;
$greeting     = $name ? ', ' . $name : '';
?>
<!DOCTYPE html>
<html lang="uk">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Оплату підтверджено — Dr. Gomon Cosmetology</title>
  <meta name="robots" content="noindex,nofollow"/>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;1,300&family=Jost:wght@300;400;500&display=swap" rel="stylesheet"/>
  <style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    :root{
      --cream:#faf8f5;--warm:#f3ede4;--gold:#c9a96e;--gold-lt:#e8d5b0;
      --dark:#1a1410;--text:#3d3530;--muted:#9a8f87;--border:rgba(201,169,110,.22);
    }
    body{font-family:'Jost',sans-serif;background:var(--cream);color:var(--text);min-height:100vh;display:flex;flex-direction:column}
    header{padding:20px 40px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border)}
    .logo img{height:38px}
    main{flex:1;display:flex;align-items:center;justify-content:center;padding:60px 20px}
    .card{background:#fff;border:1px solid var(--border);border-radius:2px;max-width:500px;width:100%;padding:52px 44px 44px;text-align:center;position:relative;overflow:hidden;
      opacity:0;transform:translateY(20px);animation:rise .65s cubic-bezier(.22,.68,0,1.2) .1s forwards}
    .card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--gold-lt),var(--gold),var(--gold-lt))}

    .check{width:68px;height:68px;border-radius:50%;border:1.5px solid var(--gold);display:flex;align-items:center;justify-content:center;margin:0 auto 28px;
      opacity:0;animation:pop .5s cubic-bezier(.34,1.56,.64,1) .55s forwards}
    .check svg{width:26px;height:26px;stroke:var(--gold);stroke-width:1.8;fill:none;stroke-linecap:round;stroke-linejoin:round}
    .check svg path{stroke-dasharray:40;stroke-dashoffset:40;animation:draw .4s ease .9s forwards}

    .label{font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--gold);margin-bottom:12px}
    h1{font-family:'Cormorant Garamond',serif;font-weight:300;font-size:clamp(26px,5vw,36px);color:var(--dark);line-height:1.2;margin-bottom:14px}
    h1 em{font-style:italic;color:var(--gold)}
    .desc{font-size:14px;font-weight:300;color:var(--muted);line-height:1.7;margin-bottom:28px}

    .details{background:var(--warm);border-radius:1px;padding:18px 22px;margin-bottom:28px;text-align:left}
    .dr{display:flex;justify-content:space-between;align-items:baseline;padding:6px 0;border-bottom:1px solid var(--border);font-size:13px}
    .dr:last-child{border-bottom:none}
    .dr .k{color:var(--muted);font-weight:300}
    .dr .v{color:var(--dark)}
    .dr .v.amt{font-family:'Cormorant Garamond',serif;font-size:19px;color:var(--gold)}

    .actions{display:flex;flex-direction:column;gap:10px}
    .btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:13px 24px;border-radius:1px;font-family:'Jost',sans-serif;font-size:11px;font-weight:500;letter-spacing:.13em;text-transform:uppercase;text-decoration:none;transition:all .2s;cursor:pointer;border:none}
    .btn-primary{background:var(--dark);color:var(--cream)}
    .btn-primary:hover{background:var(--gold);color:var(--dark)}
    .btn-ghost{background:transparent;color:var(--muted);border:1px solid var(--border)}
    .btn-ghost:hover{border-color:var(--gold);color:var(--gold)}
    .btn svg{width:14px;height:14px;stroke:currentColor;fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}

    footer{padding:18px 40px;border-top:1px solid var(--border);display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}
    footer p{font-size:11px;color:var(--muted);font-weight:300}
    footer a{color:var(--muted);text-decoration:none}
    footer a:hover{color:var(--gold)}

    @keyframes rise{to{opacity:1;transform:translateY(0)}}
    @keyframes pop{to{opacity:1}}
    @keyframes draw{to{stroke-dashoffset:0}}
    @media(max-width:560px){header,footer{padding:14px 16px}.card{padding:36px 20px 28px}}
  </style>
</head>
<body>
<header>
  <a href="https://gomonclinic.com"><img src="https://www.gomonclinic.com/logo.png" alt="Dr. Gomon Cosmetology"/></a>
  <span style="font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:300">Черкаси</span>
</header>

<main>
  <div class="card">
    <div class="check">
      <svg viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg>
    </div>

    <p class="label">Оплату підтверджено</p>
    <h1>Дякуємо<?= $greeting ? '<br/><em>' . $greeting . '</em>' : ' за <em>довіру</em>' ?></h1>
    <p class="desc">Ваш платіж успішно зараховано.<br/>Чекаємо вас у клініці з турботою про результат.</p>

    <?php if ($show_details): ?>
    <div class="details">
      <?php if ($desc): ?>
      <div class="dr"><span class="k">Послуга</span><span class="v"><?= $desc ?></span></div>
      <?php endif ?>
      <?php if ($amount > 0): ?>
      <div class="dr"><span class="k">Сума</span><span class="v amt"><?= number_format($amount, 0) ?> ₴</span></div>
      <?php endif ?>
      <?php if ($order): ?>
      <div class="dr"><span class="k">№ замовлення</span><span class="v" style="font-size:11px;font-family:monospace"><?= $order ?></span></div>
      <?php endif ?>
    </div>
    <?php endif ?>

    <div class="actions">
      <a href="https://gomonclinic.com" class="btn btn-primary">
        <svg viewBox="0 0 24 24"><path d="M3 12l9-9 9 9M5 10v10h5v-6h4v6h5V10"/></svg>
        Повернутись на сайт
      </a>
      <a href="https://t.me/DrGomonCosmetology" class="btn btn-ghost">
        <svg viewBox="0 0 24 24"><path d="M22 2L11 13M22 2L15 22l-4-9-9-4 20-7z"/></svg>
        Написати в Telegram
      </a>
    </div>
  </div>
</main>

<footer>
  <p>© 2026 Dr. Gómon Cosmetology · Черкаси</p>
  <p><a href="tel:+380733103110">073-310-31-10</a></p>
</footer>
</body>
</html>
