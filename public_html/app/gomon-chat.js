/**
 * Dr. Gomon AI Chat Widget — v20260326j
 * guest mode: banner + SMS reminder; openAsGuest()
 * ─────────────────────────────────────────────────────────────
 * Підключення (перед </body>):
 *
 *   <script>
 *     window.GomonChatConfig = {
 *       apiUrl:     '/api/chat.php',
 *       userName:   currentUser.name,   // з вашого PWA
 *       userPhone:  currentUser.phone,  // з вашого PWA
 *     };
 *   </script>
 *   <script src="/js/gomon-chat.js"></script>
 *
 * Віджет сам додає кнопку і вікно чату на сторінку.
 * Підтримує вбудований режим (куточок) і повноекранний.
 */

(function () {
  'use strict';

  // ── КОНФІГ ────────────────────────────────────────────────────────────────

  const CONFIG = Object.assign({
    apiUrl:    '/api/chat.php',
    userName:  '',
    userPhone: '',
  }, window.GomonChatConfig || {});

  const TYPING_MESSAGES = [
    'Аналізую ваш запит\u2026',
    'Підбираю процедуру\u2026',
    'Консультуюсь з базою знань\u2026',
    'Готую рекомендацію\u2026',
    'Вивчаю ваш запит\u2026',
    'Піклуюсь про вашу відповідь\u2026',
    'Думаю про найкраще для вас\u2026',
    'Гортаю картки процедур\u2026',
    'Раджусь з лікарем\u2026',
    'Заглядаю в протоколи\u2026',
    'Читаю медичну карту\u2026',
  ];

  const WELCOME_MESSAGE =
    'Вітаю! 🌸 Я AI-асистент клініки Dr. Gomon.\n' +
    'Розкажіть, що вас турбує або яка процедура вас цікавить — ' +
    'і я підберу найкращий варіант догляду.';

  // ── СТАН ──────────────────────────────────────────────────────────────────

  let isOpen       = false;
  let isLoading    = false;
  let unreadCount  = 0;
  let typingTimer  = null;

  // ── ДЕБАУНС СПОВІЩЕНЬ ─────────────────────────────────────────────────────
  let stopTypingFn = null;
  let _pendingProc    = null;  // процедура, по якій ще не зроблено дію
  let _reminderTimer  = null;  // 10-хв таймер нагадування

  // Зберігаємо історію для контексту Claude
  const history = []; // { role, content }

  // ── RATE LIMIT ────────────────────────────────────────────────────────────
  // Гість: 10 запитів/день; авторизований: 20 запитів/день
  function _gcRlKey() {
    return CONFIG.userPhone ? ('gc_rl_' + CONFIG.userPhone) : 'gc_rl_guest';
  }
  function _gcRlData() {
    const today = new Date().toISOString().slice(0, 10);
    try {
      const d = JSON.parse(localStorage.getItem(_gcRlKey()) || 'null');
      if (!d || d.date !== today) return { date: today, count: 0 };
      return d;
    } catch (e) { return { date: new Date().toISOString().slice(0, 10), count: 0 }; }
  }
  function gcIsRateLimited() {
    const limit = CONFIG.userPhone ? 20 : 10;
    return _gcRlData().count >= limit;
  }
  function gcRateLimitBump() {
    const d = _gcRlData(); d.count++;
    try { localStorage.setItem(_gcRlKey(), JSON.stringify(d)); } catch (e) {}
  }

  // ── ШРИФТ ─────────────────────────────────────────────────────────────────

  const fontLink = document.createElement('link');
  fontLink.rel  = 'stylesheet';
  fontLink.href = 'https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600&family=Jost:wght@300;400;500&display=swap';
  document.head.appendChild(fontLink);

  // ── CSS ───────────────────────────────────────────────────────────────────

  const style = document.createElement('style');
  style.textContent = `
    /* ── ЗМІННІ ── */
    #gc-window, #gc-toggle {
      --gc-gold:    #c9a96e;
      --gc-gold-dim:#a07d48;
      --gc-gold-pale:#e8d5b0;
      --gc-bg:      #111010;
      --gc-bg2:     #1a1918;
      --gc-surface: #252422;
      --gc-surface2:#2e2c2a;
      --gc-border:  #333130;
      --gc-border-g:rgba(201,169,110,0.25);
      --gc-text:    #f0ece4;
      --gc-text2:   #a09890;
      --gc-text3:   #6a6460;
      --gc-serif:   'Cormorant Garamond',Georgia,serif;
      --gc-sans:    'Jost',sans-serif;
      --gc-r:       16px;
    }

    /* ── КНОПКА ВІДКРИТТЯ ── */
    #gc-toggle {
      display: none !important;
      position: fixed;
      bottom: 28px;
      right: 28px;
      z-index: 9998;
    }

    /* ── ВІКНО ── */
    #gc-window {
      position: fixed;
      z-index: 9999;
      background: var(--gc-bg);
      border: 1px solid var(--gc-border-g);
      box-shadow: 0 -4px 40px rgba(0,0,0,0.6);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      overflow-x: hidden;
      max-width: 100vw;
      transition: opacity 0.35s cubic-bezier(0.34, 1.2, 0.64, 1), transform 0.35s cubic-bezier(0.34, 1.2, 0.64, 1);
      transform-origin: bottom right;
      font-family: var(--gc-sans);
      color: var(--gc-text);
      font-weight: 300;

      bottom: 90px;
      right: 20px;
      width: 370px;
      height: 560px;
      border-radius: var(--gc-r);

      opacity: 0;
      transform: scale(0.9) translateY(16px);
      pointer-events: none;
    }
    #gc-window.open {
      opacity: 1;
      transform: scale(1) translateY(0);
      pointer-events: all;
    }
    #gc-window.fullscreen {
      inset: 0;
      width: 100%;
      height: 100dvh;
      border-radius: 0;
      border: none;
    }
    @media (max-width: 480px) {
      #gc-window {
        position: fixed !important;
        inset: 0 !important;
        width: 100% !important;
        height: 100dvh !important;
        max-width: 100vw !important;
        border-radius: 0 !important;
        border: none !important;
        bottom: 0 !important; right: 0 !important;
      }
    }

    /* ── HEADER ── */
    #gc-header {
      background: linear-gradient(180deg, var(--gc-bg2) 0%, var(--gc-bg) 100%);
      border-bottom: 1px solid var(--gc-border-g);
      padding: 14px 16px;
      display: flex;
      align-items: center;
      gap: 10px;
      flex-shrink: 0;
    }
    #gc-avatar {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      border: 1px solid var(--gc-border-g);
      background: var(--gc-surface);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    #gc-avatar svg { width: 18px; height: 18px; }
    #gc-header-text { flex: 1; }
    #gc-header-title {
      font-family: var(--gc-serif);
      font-size: 16px;
      font-weight: 400;
      color: var(--gc-gold-pale);
      letter-spacing: 0.3px;
      line-height: 1.2;
    }
    #gc-header-subtitle {
      font-size: 11px;
      font-weight: 300;
      color: var(--gc-text3);
      letter-spacing: 0.8px;
      text-transform: uppercase;
    }
    #gc-header-actions { display: flex; gap: 4px; align-items: center; }
    .gc-icon-btn {
      width: 30px; height: 30px;
      border: none;
      background: transparent;
      border-radius: 8px;
      cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      color: var(--gc-text3);
      font-size: 14px;
      transition: color 0.15s, background 0.15s;
      line-height: 1;
    }
    .gc-icon-btn:hover { color: var(--gc-text2); background: var(--gc-surface); }

    /* ── MESSAGES ── */
    #gc-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px 14px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      scroll-behavior: smooth;
      background: var(--gc-bg);
    }
    #gc-messages::-webkit-scrollbar { width: 3px; }
    #gc-messages::-webkit-scrollbar-track { background: transparent; }
    #gc-messages::-webkit-scrollbar-thumb { background: var(--gc-border); border-radius: 2px; }

    .gc-bubble-wrap { display: flex; animation: gcFadeUp 0.22s ease; }
    .gc-bubble-wrap.user      { justify-content: flex-end; }
    .gc-bubble-wrap.assistant { justify-content: flex-start; }

    .gc-bubble {
      max-width: 78%;
      padding: 10px 14px;
      font-size: 14px;
      line-height: 1.6;
      word-break: break-word;
      white-space: pre-wrap;
      font-weight: 300;
    }
    .gc-bubble-wrap.user .gc-bubble {
      background: linear-gradient(135deg, var(--gc-gold), var(--gc-gold-dim));
      color: #111;
      border-radius: 14px 4px 14px 14px;
      font-weight: 400;
    }
    .gc-bubble-wrap.assistant .gc-bubble {
      background: var(--gc-surface);
      color: var(--gc-text);
      border-radius: 4px 14px 14px 14px;
      border: 1px solid var(--gc-border);
    }
    .gc-bubble a {
      color: var(--gc-gold);
      text-decoration: underline;
      text-underline-offset: 2px;
      word-break: break-all;
    }
    .gc-bubble a:active { opacity: 0.7; }

    /* ── PROCEDURE CARD ── */
    .gc-procedure-card {
      background: var(--gc-surface);
      border: 1px solid var(--gc-border-g);
      border-radius: 12px;
      padding: 14px;
      font-size: 13px;
      color: var(--gc-text);
      animation: gcFadeUp 0.3s ease;
      margin-top: 4px;
    }
    .gc-procedure-card strong {
      font-family: var(--gc-serif);
      font-size: 15px;
      font-weight: 400;
      display: block;
      margin-bottom: 4px;
      color: var(--gc-gold-pale);
    }
    .gc-procedure-card .gc-card-hint {
      font-size: 12px;
      color: var(--gc-text3);
      display: block;
      margin-bottom: 12px;
      line-height: 1.5;
    }
    .gc-ig-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 7px;
      width: 100%;
      padding: 10px 14px;
      border-radius: 9px;
      background: linear-gradient(135deg, var(--gc-gold), var(--gc-gold-dim));
      color: #111;
      font-family: var(--gc-sans);
      font-size: 13px;
      font-weight: 500;
      text-decoration: none;
      border: none;
      cursor: pointer;
      transition: opacity 0.2s;
      letter-spacing: 0.3px;
    }
    .gc-ig-btn:hover  { opacity: 0.85; }
    .gc-ig-btn:active { opacity: 0.7; }
    .gc-ig-btn svg { width: 15px; height: 15px; flex-shrink: 0; }

    /* ── PROCEDURE NAME ROW ── */
    .gc-procedure-name-row {
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 10px;
    }
    .gc-procedure-name {
      font-family: var(--gc-serif);
      font-size: 15px;
      font-weight: 400;
      color: var(--gc-gold-pale);
      flex: 1;
      user-select: text;
      -webkit-user-select: text;
      cursor: text;
    }
    .gc-copy-btn {
      background: transparent;
      border: 1px solid var(--gc-border);
      border-radius: 6px;
      width: 28px;
      height: 28px;
      cursor: pointer;
      font-size: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      transition: background 0.15s;
      color: var(--gc-text3);
      padding: 0;
    }
    .gc-copy-btn:hover { background: var(--gc-surface2); }
    .gc-procedure-hint {
      font-size: 11px;
      color: var(--gc-text3);
      text-align: center;
      margin: 8px 0 0;
      line-height: 1.5;
    }

    /* ── TYPING ── */
    #gc-typing { display: none; align-items: center; padding: 2px 4px; }
    #gc-typing.visible { display: flex; }
    #gc-typing-dots {
      display: flex; gap: 4px;
      background: var(--gc-surface);
      border: 1px solid var(--gc-border);
      border-radius: 4px 14px 14px 14px;
      padding: 10px 14px;
      align-items: center;
      min-width: 190px;
    }
    .gc-dot {
      width: 5px; height: 5px;
      border-radius: 50%;
      background: var(--gc-gold-dim);
      animation: gcBounce 1.2s infinite;
    }
    .gc-dot:nth-child(2) { animation-delay: 0.2s; }
    .gc-dot:nth-child(3) { animation-delay: 0.4s; }
    #gc-typing-text {
      font-size: 12px;
      color: var(--gc-text3);
      font-style: italic;
      transition: opacity 0.3s;
      white-space: nowrap;
      margin-left: 6px;
    }

    /* ── INPUT ── */
    #gc-footer {
      padding: 12px 14px 14px;
      background: var(--gc-bg2);
      border-top: 1px solid var(--gc-border);
      flex-shrink: 0;
    }
    #gc-input-row { display: flex; gap: 8px; align-items: flex-end; }
    #gc-input {
      flex: 1;
      border: 1px solid var(--gc-border);
      border-radius: 10px;
      padding: 10px 14px;
      font-family: var(--gc-sans);
      font-size: 16px;
      font-weight: 300;
      color: var(--gc-text);
      background: var(--gc-surface);
      resize: none;
      min-height: 42px;
      max-height: 120px;
      overflow-y: auto;
      line-height: 1.5;
      transition: border-color 0.2s;
      outline: none;
    }
    #gc-input:focus { border-color: var(--gc-border-g); }
    #gc-input::placeholder { color: var(--gc-text3); }

    #gc-send {
      width: 42px; height: 42px;
      border-radius: 10px;
      background: linear-gradient(135deg, var(--gc-gold), var(--gc-gold-dim));
      border: none;
      cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0;
      transition: opacity 0.2s, transform 0.15s;
      color: #111;
      font-size: 16px;
    }
    #gc-send:hover  { opacity: 0.85; }
    #gc-send:active { transform: scale(0.93); }
    #gc-send:disabled { opacity: 0.3; cursor: default; }

    #gc-mic {
      width: 42px; height: 42px;
      border-radius: 10px;
      border: 1px solid var(--gc-border);
      background: transparent;
      cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0;
      color: var(--gc-text3);
      transition: color 0.2s, border-color 0.2s, background 0.2s;
    }
    #gc-mic.listening {
      border-color: var(--gc-gold);
      color: var(--gc-gold);
      background: rgba(193,156,82,.08);
      animation: gcMicPulse 1.2s ease-in-out infinite;
    }
    @keyframes gcMicPulse {
      0%,100% { box-shadow: 0 0 0 0 rgba(193,156,82,.4); }
      50%      { box-shadow: 0 0 0 5px rgba(193,156,82,0); }
    }

    /* ── KEYFRAMES ── */
    @keyframes gcFadeUp {
      from { opacity: 0; transform: translateY(8px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes gcBounce {
      0%, 80%, 100% { transform: translateY(0); }
      40%           { transform: translateY(-5px); }
    }

    /* ── GUEST BANNER ── */
    #gc-guest-banner {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin: 12px 12px 4px;
      padding: 12px 14px;
      background: rgba(201,169,110,0.08);
      border: 1px solid rgba(201,169,110,0.25);
      border-radius: 12px;
      animation: gcFadeUp 0.4s ease;
    }
    #gc-guest-banner p {
      margin: 0;
      font-size: 12px;
      color: var(--gc-text2);
      line-height: 1.5;
    }
    #gc-guest-banner strong { color: var(--gc-gold-pale); font-weight: 500; }
    .gc-guest-links { display: flex; gap: 8px; flex-wrap: wrap; }
    .gc-guest-link {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 5px 12px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 400;
      text-decoration: none;
      color: var(--gc-gold);
      border: 1px solid rgba(201,169,110,0.35);
      transition: background 0.2s;
    }
    .gc-guest-link:hover { background: rgba(201,169,110,0.12); }

  `;
  document.head.appendChild(style);

  // ── HTML СТРУКТУРА ────────────────────────────────────────────────────────

  document.body.insertAdjacentHTML('beforeend', `
    <!-- Кнопка відкриття -->
    <button id="gc-toggle" aria-label="Відкрити AI-консультант">
      🌸
      <span id="gc-badge"></span>
    </button>

    <!-- Вікно чату -->
    <div id="gc-window" role="dialog" aria-label="AI-консультант Dr. Gomon">

      <!-- Header -->
      <div id="gc-header">
        <div id="gc-avatar"><svg viewBox="0 0 24 24" fill="none" stroke="#c9a96e" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l1.4 4.2L18 8l-4.6 1.8L12 14l-1.4-4.2L6 8l4.6-1.8L12 2z"/><path d="M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15z"/></svg></div>
        <div id="gc-header-text">
          <div id="gc-header-title">AI-консультант</div>
          <div id="gc-header-subtitle">клініка Dr. Gomon</div>
        </div>
        <div id="gc-header-actions">
          <button class="gc-icon-btn" id="gc-close-btn" title="Закрити">✕</button>
        </div>
      </div>

      <!-- Messages -->
      <div id="gc-messages">
        <!-- Typing indicator -->
        <div id="gc-typing">
          <div id="gc-typing-dots">
            <div class="gc-dot"></div>
            <div class="gc-dot"></div>
            <div class="gc-dot"></div>
            <span id="gc-typing-text"></span>
          </div>
        </div>
      </div>

      <!-- Footer / Input -->
      <div id="gc-footer">
        <div id="gc-input-row">
          <textarea id="gc-input" placeholder="Напишіть ваш запит…" rows="1"></textarea>
          <button id="gc-mic" aria-label="Голосовий ввід" title="Голосовий ввід"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="11" rx="3"/><path d="M5 10a7 7 0 0 0 14 0"/><line x1="12" y1="17" x2="12" y2="22"/><line x1="8" y1="22" x2="16" y2="22"/></svg></button>
          <button id="gc-send" aria-label="Надіслати">➤</button>
        </div>
      </div>
    </div>
  `);

  // ── ЕЛЕМЕНТИ ──────────────────────────────────────────────────────────────

  const elWindow      = document.getElementById('gc-window');
  const elToggle      = document.getElementById('gc-toggle');
  const elBadge       = document.getElementById('gc-badge');
  const elMessages    = document.getElementById('gc-messages');
  const elTyping      = document.getElementById('gc-typing');
  const elTypingText  = document.getElementById('gc-typing-text');
  const elInput       = document.getElementById('gc-input');
  const elSend        = document.getElementById('gc-send');
  const elMic         = document.getElementById('gc-mic');
  const elClose       = document.getElementById('gc-close-btn');

  // Переміщуємо typing indicator в кінець messages (щоб скрол пра цювало)
  elMessages.appendChild(elTyping);

  // ── УТИЛІТИ ───────────────────────────────────────────────────────────────

  function scrollBottom() {
    elMessages.scrollTop = elMessages.scrollHeight;
  }

  function setBadge(n) {
    elBadge.textContent = n > 9 ? '9+' : n;
    elBadge.classList.toggle('visible', n > 0);
  }

  function addMessage(role, content) {
    const wrap = document.createElement('div');
    wrap.className = `gc-bubble-wrap ${role}`;
    const bubble = document.createElement('div');
    bubble.className = 'gc-bubble';
    bubble.innerHTML = linkify(content);
    wrap.appendChild(bubble);
    elMessages.insertBefore(wrap, elTyping);
    scrollBottom();
    return wrap;
  }

  function addProcedureCard(procedure) {
    _startReminderTimer(procedure); // 10 хв → push якщо не записався
    const card = document.createElement('div');
    card.className = 'gc-procedure-card';
    card.innerHTML = `
      <strong>✨ Підібрана процедура</strong>
      <div class="gc-procedure-name-row">
        <span class="gc-procedure-name">${escapeHtml(procedure)}</span>
        <button class="gc-copy-btn" title="Скопіювати назву">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <rect x="9" y="9" width="13" height="13" rx="2"/>
            <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
          </svg>
        </button>
      </div>
      <a
        class="gc-ig-btn"
        href="https://ig.me/m/dr.gomon"
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Написати лікарю в Instagram Direct"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <rect x="2" y="2" width="20" height="20" rx="5" ry="5"/>
          <circle cx="12" cy="12" r="4"/>
          <circle cx="17.5" cy="6.5" r="0.8" fill="currentColor" stroke="none"/>
        </svg>
        Написати лікарю в Instagram
      </a>
      <p class="gc-procedure-hint">Скопіюйте назву процедури та надішліть самостійно лікарю в Direct</p>
    `;
    const igBtn = card.querySelector('.gc-ig-btn');
    if (igBtn) igBtn.addEventListener('click', () => {
      _cancelReminder();
      _sendProcedureNotify(procedure, 'instagram');
    }, { once: true });
    const copyBtn = card.querySelector('.gc-copy-btn');
    if (copyBtn) {
      const copySvg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>';
      const checkSvg = '<svg viewBox="0 0 24 24" fill="none" stroke="#6fcf97" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
      copyBtn.addEventListener('click', () => {
        const nameEl = card.querySelector('.gc-procedure-name');
        const name = nameEl ? nameEl.textContent : procedure;
        navigator.clipboard.writeText(name).then(() => {
          copyBtn.innerHTML = checkSvg;
          setTimeout(() => { copyBtn.innerHTML = copySvg; }, 2000);
        }).catch(() => {
          copyBtn.innerHTML = checkSvg;
          setTimeout(() => { copyBtn.innerHTML = copySvg; }, 2000);
        });
        _cancelReminder();
        _sendProcedureNotify(name, 'copy');
      });
    }
    elMessages.insertBefore(card, elTyping);
    scrollBottom();
  }

  function addConsultCard() {
    const card = document.createElement('div');
    card.className = 'gc-procedure-card';
    card.innerHTML = `
      <strong>&#x1F469;&#x200D;&#x2695;&#xFE0F; \u0420\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0430\u0446\u0456\u044f</strong>
      <p style="font-size:13px;color:var(--gc-text2,#a09890);line-height:1.5;margin:6px 0 12px">\u0417\u0432\u0430\u0436\u0430\u044e\u0447\u0438 \u043d\u0430 \u0441\u043a\u043b\u0430\u0434\u043d\u0456\u0441\u0442\u044c \u0432\u0430\u0448\u043e\u0433\u043e \u0437\u0430\u043f\u0438\u0442\u0443, \u0440\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0443\u044e \u0437\u0432\u0435\u0440\u043d\u0443\u0442\u0438\u0441\u044c \u0434\u043e \u043b\u0456\u043a\u0430\u0440\u044f \u043d\u0430 \u043e\u0441\u043e\u0431\u0438\u0441\u0442\u0443 \u043a\u043e\u043d\u0441\u0443\u043b\u044c\u0442\u0430\u0446\u0456\u044e.</p>
      <div class="gc-procedure-name-row">
        <span class="gc-procedure-name">\u041a\u043e\u043d\u0441\u0443\u043b\u044c\u0442\u0430\u0446\u0456\u044f \u043b\u0456\u043a\u0430\u0440\u044f</span>
      </div>
      <a class="gc-ig-btn" href="https://ig.me/m/dr.gomon" target="_blank" rel="noopener noreferrer" aria-label="\u0417\u0430\u043f\u0438\u0441\u0430\u0442\u0438\u0441\u044c \u0432 Instagram Direct">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <rect x="2" y="2" width="20" height="20" rx="5" ry="5"/>
          <circle cx="12" cy="12" r="4"/>
          <circle cx="17.5" cy="6.5" r="0.8" fill="currentColor" stroke="none"/>
        </svg>
        \u0417\u0430\u043f\u0438\u0441\u0430\u0442\u0438\u0441\u044c \u043d\u0430 \u043a\u043e\u043d\u0441\u0443\u043b\u044c\u0442\u0430\u0446\u0456\u044e
      </a>
      <p class="gc-procedure-hint">\u041d\u0430\u043f\u0438\u0448\u0456\u0442\u044c \u043b\u0456\u043a\u0430\u0440\u044e \u0432 Direct \u2014 \u0432\u0430\u043c \u043f\u0456\u0434\u0431\u0435\u0440\u0443\u0442\u044c \u0437\u0440\u0443\u0447\u043d\u0438\u0439 \u0447\u0430\u0441 \u0434\u043b\u044f \u0437\u0443\u0441\u0442\u0440\u0456\u0447\u0456</p>
    `;
    const igBtn = card.querySelector('.gc-ig-btn');
    if (igBtn) igBtn.addEventListener('click', function () {
      const payload = JSON.stringify({
        procedure: 'Консультація лікаря',
        action: 'instagram',
        source: 'app',
        user_name: CONFIG.userName || (CONFIG.userPhone ? CONFIG.userPhone : 'Гість додатку'),
        user_phone: CONFIG.userPhone || '',
      });
      if (navigator.sendBeacon) {
        navigator.sendBeacon('/app/notify_procedure.php', new Blob([payload], { type: 'application/json' }));
      } else {
        fetch('/app/notify_procedure.php', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: payload }).catch(() => {});
      }
    }, { once: true });
    elMessages.insertBefore(card, elTyping);
    scrollBottom();
  }

  function parseMarkdown(text) {
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>');
  }

  function linkify(text) {
    text = escapeHtml(text);
    text = parseMarkdown(text);
    // markdown [text](url) -> clickable with original text
    text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s\)\"]+)\)/g, function(m, text, url) {
      try { new URL(url); } catch(e) { return text; }
      return '<a href="' + url.replace(/"/g, '&quot;') + '" target="_blank" rel="noopener">' + text + '</a>';
    });
    // plain https://...
    text = text.replace(/(^|[\s,>])(https?:\/\/[^\s<,]+)/g,
      '$1<a href="$2" target="_blank" rel="noopener">$2</a>');
    return text;
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  // ── TYPING ROTATION ───────────────────────────────────────────────────────

  function startTyping() {
    const msgs = [...TYPING_MESSAGES].sort(() => Math.random() - 0.5);
    let idx = 0;

    elTypingText.textContent = msgs[idx];
    elTypingText.style.opacity = '1';
    elTyping.classList.add('visible');
    scrollBottom();

    typingTimer = setInterval(() => {
      elTypingText.style.opacity = '0';
      setTimeout(() => {
        idx = (idx + 1) % msgs.length;
        elTypingText.textContent = msgs[idx];
        elTypingText.style.opacity = '1';
      }, 300);
    }, 2800);
  }

  function stopTyping() {
    clearInterval(typingTimer);
    typingTimer = null;
    elTyping.classList.remove('visible');
  }

  // ── OPEN / CLOSE ──────────────────────────────────────────────────────────

  function _showGuestBanner() {
    if (document.getElementById('gc-guest-banner')) return;
    const elMessages = document.getElementById('gc-messages');
    if (!elMessages) return;
    const banner = document.createElement('div');
    banner.id = 'gc-guest-banner';
    banner.innerHTML =
      '<p>👋 Ви ще не клієнт клініки. <strong>AI підбере процедуру</strong> — а записатися можна одним повідомленням лікарю:</p>' +
      '<div class="gc-guest-links">' +
        '<a class="gc-guest-link" href="https://t.me/DrGomonCosmetology" target="_blank" rel="noopener">✈ Telegram</a>' +
        '<a class="gc-guest-link" href="https://ig.me/m/dr.gomon" target="_blank" rel="noopener">◎ Instagram Direct</a>' +
      '</div>';
    elMessages.insertBefore(banner, elMessages.firstChild);
  }

  function openChat() {
    isOpen = true;
    elWindow.classList.add('open');
    unreadCount = 0;
    setBadge(0);
    elToggle.innerHTML = '✕ <span id="gc-badge"></span>';
    document.body.style.overflow = 'hidden';
    setTimeout(() => elInput.focus(), 350);
    scrollBottom();
  }

  function openAsGuest() {
    if (!localStorage.getItem('guest_phone')) return;
    openChat();
    _showGuestBanner();
  }

  function closeChat() {
    isOpen = false;
    elWindow.classList.remove('open');
    document.body.style.overflow = '';
    elToggle.innerHTML = '🌸 <span id="gc-badge"></span>';
    // Оновлюємо ref на badge
    setBadge(unreadCount);
  }

  // ── PROCEDURE NOTIFY ──────────────────────────────────────────────────────

  function _sendProcedureNotify(procedure, action) {
    const payload = JSON.stringify({
      procedure:  procedure,
      action:     action,
      user_name:  CONFIG.userName  || '',
      user_phone: CONFIG.userPhone || '',
    });
    try {
      if (navigator.sendBeacon) {
        navigator.sendBeacon('/app/notify_procedure.php', new Blob([payload], { type: 'application/json' }));
      } else {
        fetch('/app/notify_procedure.php', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: payload,
          keepalive: true,
        }).catch(() => {});
      }
    } catch(e) {}
  }

  function _startReminderTimer(procedure) {
    _pendingProc = procedure;
    if (_reminderTimer) clearTimeout(_reminderTimer);
    // 10 хвилин — якщо юзер не записався, відправляємо push
    _reminderTimer = setTimeout(() => _fireReminder(procedure), 10 * 60 * 1000);
  }

  function _cancelReminder() {
    _pendingProc = null;
    if (_reminderTimer) { clearTimeout(_reminderTimer); _reminderTimer = null; }
  }

  function _fireReminder(procedure) {
    _pendingProc = null;
    _reminderTimer = null;
    // Push + SMS для авторизованого юзера
    if (CONFIG.token) {
      fetch('/api/push/procedure-reminder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + CONFIG.token },
        body: JSON.stringify({ procedure }),
        keepalive: true,
      }).catch(() => {});
      return;
    }
    // SMS для гостя (ввів телефон, але не авторизований клієнт)
    const guestPhone = localStorage.getItem('guest_phone');
    if (guestPhone) {
      fetch('/api/sms/procedure-reminder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: guestPhone, procedure }),
        keepalive: true,
      }).catch(() => {});
    }
  }

  // ── SEND MESSAGE ──────────────────────────────────────────────────────────

  async function sendMessage() {
    const text = elInput.value.trim();
    if (!text || isLoading) return;

    // Команда виходу з акаунту
    if (/^\/(logout|вийти|exit)$/i.test(text) || text.toLowerCase() === 'вийти з акаунту') {
      elInput.value = '';
      closeChat();
      if (typeof logout === 'function') logout();
      return;
    }

    elInput.value = '';
    elInput.style.height = 'auto';
    isLoading = true;
    elSend.disabled = true;

    addMessage('user', text);
    history.push({ role: 'user', content: text });

    // Google Ads conversion — перше повідомлення в чаті
    if (history.length === 1 && typeof gtag === 'function') {
      gtag('event', 'conversion', {'send_to': 'AW-719653819/WaavCKa45JAcELuXlNcC'});
    }

    // Rate limit check
    if (gcIsRateLimited()) {
      isLoading = false;
      elSend.disabled = false;
      addConsultCard();
      elInput.focus();
      return;
    }
    gcRateLimitBump();

    startTyping();

    try {
      const res = await fetch(CONFIG.apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user: {
            name:  CONFIG.userName,
            phone: CONFIG.userPhone,
          },
          messages: history,
        }),
      });

      const data = await res.json();

      stopTyping();

      if (data.error) {
        addMessage('assistant', 'Вибачте, сталася помилка. Спробуйте ще раз або зателефонуйте нам.');
        return;
      }

      addMessage('assistant', data.reply);
      history.push({ role: 'assistant', content: data.reply });

      // Якщо агент підібрав процедуру — показуємо картку
      if (data.procedure) {
        addProcedureCard(data.procedure);
      }

      // Якщо чат закритий — збільшуємо лічильник
      if (!isOpen) {
        unreadCount++;
        setBadge(unreadCount);
      }

    } catch (err) {
      stopTyping();
      addMessage('assistant', 'Немає зв\'язку із сервером. Перевірте інтернет і спробуйте ще раз.');
    } finally {
      isLoading = false;
      elSend.disabled = false;
      elInput.focus();
    }
  }

  // ── ПОДІЇ ─────────────────────────────────────────────────────────────────

  elToggle.addEventListener('click', () => isOpen ? closeChat() : openChat());
  elClose.addEventListener('click', closeChat);

  elSend.addEventListener('click', sendMessage);

  // ── ГОЛОСОВИЙ ВВІД ────────────────────────────────────────────────────────
  let _gcMicRecog = null;
  elMic.addEventListener('click', () => {
    if (!window.SpeechRecognition && !window.webkitSpeechRecognition) return;
    if (_gcMicRecog) { _gcMicRecog.stop(); return; }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const r  = new SR();
    r.lang = 'uk-UA'; r.continuous = false; r.interimResults = true;
    _gcMicRecog = r;
    elMic.classList.add('listening');
    const ph = elInput.placeholder;
    elInput.placeholder = 'Слухаю…';
    let fin = '';
    r.onresult = e => {
      let interim = ''; fin = '';
      for (let i = 0; i < e.results.length; i++) {
        if (e.results[i].isFinal) fin += e.results[i][0].transcript;
        else interim += e.results[i][0].transcript;
      }
      elInput.value = interim ? fin + ' ' + interim : fin;
      elInput.dispatchEvent(new Event('input'));
    };
    const done = () => {
      elMic.classList.remove('listening');
      _gcMicRecog = null;
      elInput.placeholder = ph;
      if (fin) sendMessage();
    };
    r.onend = done; r.onerror = done;
    r.start();
  });

  elInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // Автовисота textarea
  elInput.addEventListener('input', () => {
    elInput.style.height = 'auto';
    elInput.style.height = Math.min(elInput.scrollHeight, 120) + 'px';
  });
  elInput.addEventListener('focus', () => {
    const m = document.querySelector('meta[name=viewport]');
    if (m) m.content = 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover';
  });
  elInput.addEventListener('blur', () => {
    setTimeout(() => {
      const m = document.querySelector('meta[name=viewport]');
      if (m) m.content = 'width=device-width, initial-scale=1.0, viewport-fit=cover';
    }, 300);
  });


  // ESC — закриття чату
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && isOpen) closeChat();
  });




  // ── KEYBOARD / VIEWPORT FIX (Android) ────────────────────────────────────

  function applyViewport() {
    if (!window.visualViewport) return;
    const vh     = window.visualViewport.height;
    const offTop = window.visualViewport.offsetTop || 0;
    elWindow.style.maxHeight = (vh - 8) + 'px';
    elWindow.style.bottom    = offTop > 0 ? offTop + 'px' : '';
  }

  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', applyViewport);
    window.visualViewport.addEventListener('scroll', applyViewport);
  }

  // При згортанні/закритті — одразу надсилаємо push якщо є pending процедура
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && _pendingProc) {
      const proc = _pendingProc;
      _cancelReminder();
      _fireReminder(proc);
    }
  });

  // ── ПУБЛІЧНИЙ API ─────────────────────────────────────────────────────────

  window.GomonChat = {
    open:  openChat,
    close: closeChat,
    openAsGuest: openAsGuest,
    openWithMessage: function(text) {
      openChat();
      if (text && text.trim()) {
        elInput.value = text.trim();
        setTimeout(sendMessage, 350);
      }
    },
  };

  // ── ПОЧАТКОВЕ ПОВІДОМЛЕННЯ ────────────────────────────────────────────────

  addMessage('assistant', WELCOME_MESSAGE);

})();
