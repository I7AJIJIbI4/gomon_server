<?php
/**
 * already_paid.php — підключається через include коли замовлення вже оплачено
 */
?>
<!DOCTYPE html>
<html lang="uk">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Вже оплачено — Dr. Gomon Cosmetology</title>
  <meta name="robots" content="noindex,nofollow"/>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400&family=Jost:wght@300;400;500&display=swap" rel="stylesheet"/>
  <style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    :root{--cream:#faf8f5;--gold:#c9a96e;--gold-lt:#e8d5b0;--dark:#1a1410;--muted:#9a8f87;--border:rgba(201,169,110,.22)}
    body{font-family:'Jost',sans-serif;background:var(--cream);min-height:100vh;display:flex;flex-direction:column}
    header{padding:20px 40px;border-bottom:1px solid var(--border)}
    header img{height:36px}
    main{flex:1;display:flex;align-items:center;justify-content:center;padding:60px 20px}
    .card{background:#fff;border:1px solid var(--border);border-radius:2px;max-width:440px;width:100%;padding:48px 40px;text-align:center;position:relative;overflow:hidden}
    .card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--gold-lt),var(--gold),var(--gold-lt))}
    .icon{font-size:36px;margin-bottom:20px}
    .label{font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--gold);margin-bottom:12px}
    h1{font-family:'Cormorant Garamond',serif;font-weight:300;font-size:30px;color:var(--dark);margin-bottom:14px}
    p{font-size:14px;font-weight:300;color:var(--muted);line-height:1.7;margin-bottom:28px}
    a.btn{display:inline-flex;align-items:center;gap:8px;padding:13px 28px;background:var(--dark);color:var(--cream);text-decoration:none;font-size:11px;font-weight:500;letter-spacing:.13em;text-transform:uppercase;border-radius:1px;transition:background .2s}
    a.btn:hover{background:var(--gold);color:var(--dark)}
    footer{padding:18px 40px;border-top:1px solid var(--border)}
    footer p{font-size:11px;color:var(--muted)}
  </style>
</head>
<body>
<header>
  <a href="https://gomonclinic.com"><img src="https://www.gomonclinic.com/logo.png" alt="Dr. Gomon"/></a>
</header>
<main>
  <div class="card">
    <div class="icon">✅</div>
    <p class="label">Статус замовлення</p>
    <h1>Вже <em style="font-style:italic;color:var(--gold)">оплачено</em></h1>
    <p>Це замовлення вже було успішно оплачено раніше.<br/>Якщо є питання — зверніться до нас.</p>
    <a href="https://gomonclinic.com" class="btn">Повернутись на сайт</a>
  </div>
</main>
<footer><p>© 2026 Dr. Gómon Cosmetology · Черкаси · <a href="tel:+380733103110" style="color:inherit">073-310-31-10</a></p></footer>
</body>
</html>
