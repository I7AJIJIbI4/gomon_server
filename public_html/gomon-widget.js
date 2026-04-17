/**
 * GomonAI Chat Widget v2 — inline input + blur modal
 * v20260326k — textarea placeholder nowrap + overflow fix on mobile
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'gw_messages';
  var API_URL = '/app/chat.php';
  var NOTIFY_URL = '/app/notify_procedure.php';

  var GREETING = 'Привіт! Я GomonAI — асистент Dr.\u00a0G\u00f3mon Cosmetology.\nЧим можу допомогти? Запитайте про процедури, ціни або підготовку — відповім одразу.';
  var TYPING_MSGS = [
    'Аналізую ваш запит…',
    'Підбираю процедуру…',
    'Консультуюсь з базою знань…',
    'Готую рекомендацію…',
    'Вивчаю ваш запит…',
    'Думаю про найкраще для вас…',
    'Гортаю картки процедур…',
    'Раджусь з лікарем…',
    'Заглядаю в протоколи…',
  ];

  // ── Styles ────────────────────────────────────────────────────
  var css = `
    /* Floating btn — hidden, kept for API compat */
    #gw-btn { display: none !important; }

    /* ── Full-screen blur overlay ── */
    #gw-overlay {
      position: fixed;
      inset: 0;
      z-index: 99999;
      background: rgba(11,10,8,0.85);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 12px;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.28s ease;
    }
    #gw-overlay.gw-open {
      opacity: 1;
      pointer-events: all;
    }

    /* ── Modal panel ── */
    #gw-panel {
      background: #161310;
      border: 1px solid rgba(184,149,90,0.22);
      border-radius: 18px;
      width: 100%;
      max-width: 1000px;
      height: 96vh;
      max-height: 96vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      box-shadow: 0 24px 80px rgba(0,0,0,0.7);
      transform: translateY(18px) scale(0.985);
      transition: transform 0.28s cubic-bezier(.22,.68,0,1.2);
      font-family: 'Jost', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    #gw-overlay.gw-open #gw-panel {
      transform: translateY(0) scale(1);
    }
    @media (max-width: 600px) {
      #gw-overlay { padding: 0; align-items: stretch; }
      #gw-panel {
        max-width: 100%;
        height: 100vh;
        height: 100dvh;
        max-height: 100vh;
        max-height: 100dvh;
        border-radius: 0;
        border: none;
        transform: translateY(30px);
      }
      #gw-input-area {
        padding-bottom: max(12px, env(safe-area-inset-bottom));
      }
    }

    /* ── Header ── */
    #gw-header {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 14px 20px;
      border-bottom: 1px solid rgba(184,149,90,0.15);
      flex-shrink: 0;
    }
    #gw-header-dot {
      width: 9px; height: 9px; border-radius: 50%;
      background: #b8955a;
      box-shadow: 0 0 8px rgba(184,149,90,0.6);
      flex-shrink: 0;
    }
    #gw-header-title {
      color: #b8955a;
      font-size: 14px;
      font-weight: 500;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      flex: 1;
    }
    #gw-close {
      background: none;
      border: none;
      cursor: pointer;
      width: 32px; height: 32px;
      border-radius: 8px;
      display: flex; align-items: center; justify-content: center;
      color: rgba(247,243,238,0.45);
      font-size: 20px;
      line-height: 1;
      transition: background 0.15s, color 0.15s;
      flex-shrink: 0;
    }
    #gw-close:hover {
      background: rgba(255,255,255,0.06);
      color: #f7f3ee;
    }

    /* ── Messages ── */
    #gw-messages {
      flex: 1;
      overflow-y: auto;
      padding: 18px 20px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      scroll-behavior: smooth;
    }
    #gw-messages::-webkit-scrollbar { width: 4px; }
    #gw-messages::-webkit-scrollbar-track { background: transparent; }
    #gw-messages::-webkit-scrollbar-thumb { background: rgba(184,149,90,0.2); border-radius: 4px; }
    .gw-bubble {
      max-width: 76%;
      padding: 10px 15px;
      border-radius: 14px;
      font-size: 15px;
      line-height: 1.6;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .gw-bubble-ai {
      align-self: flex-start;
      background: rgba(255,255,255,0.055);
      color: #f7f3ee;
      border-bottom-left-radius: 4px;
    }
    .gw-bubble-ai a {
      color: #d4b07a;
      text-decoration: underline;
      text-underline-offset: 2px;
      display: inline-block;
      padding: 2px 0;
      min-height: 44px;
      line-height: 1.8;
      touch-action: manipulation;
      -webkit-tap-highlight-color: rgba(212, 176, 122, 0.2);
    }
    .gw-bubble-ai a:hover { color: #e8d5b0; }
    .gw-bubble-ai a:active { color: #c9a76a; }

    /* ── Procedure card ── */
    .gw-procedure-card {
      background: rgba(184,149,90,0.08);
      border: 1px solid rgba(184,149,90,0.35);
      border-radius: 14px;
      padding: 14px 16px 12px;
      margin: 4px 0 8px;
      align-self: flex-start;
      max-width: 100%;
    }
    .gw-proc-label {
      font-size: 11px; font-weight: 500; letter-spacing: .6px;
      text-transform: uppercase; color: #d4b07a; margin: 0 0 10px;
    }
    .gw-proc-row {
      display: flex; align-items: center; gap: 10px; margin-bottom: 12px;
    }
    .gw-proc-name {
      flex: 1; font-size: 15px; font-weight: 400; color: #f7f3ee; line-height: 1.4;
    }
    .gw-proc-copy {
      flex-shrink: 0; background: rgba(255,255,255,0.07); border: 1px solid rgba(184,149,90,0.3);
      border-radius: 8px; width: 34px; height: 34px; cursor: pointer;
      display: flex; align-items: center; justify-content: center; transition: background .15s;
      color: #d4b07a;
    }
    .gw-proc-copy:hover { background: rgba(184,149,90,0.15); }
    .gw-proc-copy svg { width: 16px; height: 16px; }
    .gw-proc-ig {
      display: flex; align-items: center; gap: 8px; width: 100%;
      padding: 10px 14px; border-radius: 10px; text-decoration: none;
      background: #b8955a; color: #1a1612;
      font-size: 13px; font-weight: 500; letter-spacing: .3px;
      transition: background .15s; margin-bottom: 10px;
    }
    .gw-proc-ig:hover { background: #c9a76a; }
    .gw-proc-ig svg { width: 18px; height: 18px; flex-shrink: 0; }
    .gw-proc-hint {
      font-size: 11px; color: rgba(247,243,238,0.4); margin: 0; line-height: 1.5;
    }
    /* ── Reminder banner ── */
    .gw-reminder-banner {
      display: flex; align-items: flex-start; gap: 10px;
      background: rgba(184,149,90,0.12); border: 1px solid rgba(184,149,90,0.4);
      border-radius: 12px; padding: 12px 14px; margin: 4px 0;
      animation: gw-fade-in .4s ease;
    }
    @keyframes gw-fade-in { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:none; } }
    .gw-reminder-icon { font-size: 18px; flex-shrink: 0; margin-top: 1px; }
    .gw-reminder-text { font-size: 13px; color: #e8d5b0; line-height: 1.5; }
    .gw-bubble-user {
      align-self: flex-end;
      background: #b8955a;
      color: #1a1612;
      border-bottom-right-radius: 4px;
      font-weight: 500;
    }
    .gw-typing {
      align-self: flex-start;
      display: flex;
      align-items: center;
      gap: 5px;
      padding: 12px 16px;
      background: rgba(255,255,255,0.055);
      border-radius: 14px;
      border-bottom-left-radius: 4px;
    }
    .gw-typing-text {
      font-size: 12px;
      color: var(--gw-text2, #888);
      margin-left: 8px;
      opacity: 1;
      transition: opacity 0.3s;
    }
    .gw-typing-dots span {
      width: 7px; height: 7px;
      border-radius: 50%;
      background: #b8955a;
      display: inline-block;
      animation: gw-bounce 1.2s infinite;
    }
    .gw-typing span:nth-child(2) { animation-delay: 0.2s; }
    .gw-typing span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes gw-bounce {
      0%,60%,100% { transform: translateY(0); opacity: 0.6; }
      30% { transform: translateY(-5px); opacity: 1; }
    }

    /* ── Input area (modal) ── */
    #gw-input-area {
      display: flex;
      align-items: flex-end;
      gap: 10px;
      padding: 12px 16px;
      border-top: 1px solid rgba(184,149,90,0.15);
      flex-shrink: 0;
      background: rgba(255,255,255,0.02);
    }
    #gw-textarea {
      flex: 1;
      min-width: 0;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(184,149,90,0.22);
      border-radius: 11px;
      color: #f7f3ee;
      font-size: 15px;
      padding: 10px 13px;
      resize: none;
      outline: none;
      font-family: inherit;
      line-height: 1.5;
      max-height: 110px;
      overflow-y: hidden;
      transition: border-color 0.15s;
    }
    #gw-textarea::placeholder {
      color: rgba(247,243,238,0.3);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    #gw-textarea:focus { border-color: rgba(184,149,90,0.5); }
    #gw-send {
      width: 42px; height: 42px;
      border-radius: 11px;
      background: #b8955a;
      border: none;
      cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0;
      transition: background 0.15s, transform 0.1s;
    }
    #gw-send:hover { background: #c9a76a; }
    #gw-send:active { transform: scale(0.92); }
    #gw-send svg { width: 18px; height: 18px; fill: #1a1612; }
    #gw-send:disabled { opacity: 0.4; cursor: not-allowed; }

    #gw-mic, #gw-inline-mic {
      width: 42px; height: 42px;
      border-radius: 11px;
      border: 1px solid rgba(184,149,90,0.3);
      background: transparent;
      cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0;
      color: #8a7a5a;
      transition: color 0.15s, border-color 0.15s, background 0.15s;
    }
    #gw-mic.listening, #gw-inline-mic.listening {
      border-color: #b8955a;
      color: #b8955a;
      background: rgba(184,149,90,0.08);
      animation: gwMicPulse 1.2s ease-in-out infinite;
    }
    @keyframes gwMicPulse {
      0%,100% { box-shadow: 0 0 0 0 rgba(184,149,90,0.4); }
      50%      { box-shadow: 0 0 0 5px rgba(184,149,90,0); }
    }

    /* ── Inline input block on page ── */
    #gw-inline {
      display: flex;
      align-items: flex-end;
      gap: 10px;
      background: rgba(184,149,90,0.06);
      border: 1px solid rgba(184,149,90,0.28);
      color: var(--cream, #f7f3ee);
      border-radius: 14px;
      padding: 10px 12px 10px 16px;
      margin-top: 32px;
      max-width: 680px;
      margin-left: auto;
      margin-right: auto;
      transition: border-color 0.2s;
    }
    #gw-inline:focus-within {
      border-color: rgba(184,149,90,0.55);
    }
    #gw-inline-textarea {
      flex: 1;
      background: transparent;
      border: none;
      outline: none;
      color: inherit;
      font-family: 'Jost', sans-serif;
      font-size: 15px;
      line-height: 1.5;
      resize: none;
      max-height: 90px;
      padding: 4px 0;
    }
    #gw-inline-textarea::placeholder { color: #8a7a5a; }
    #gw-inline-send {
      width: 40px; height: 40px;
      border-radius: 10px;
      background: #b8955a;
      border: none;
      cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0;
      transition: background 0.15s, transform 0.1s;
    }
    #gw-inline-send:hover { background: #c9a76a; }
    #gw-inline-send:active { transform: scale(0.92); }
    #gw-inline-send svg { width: 17px; height: 17px; fill: #1a1612; }
    /* Hide the old button in ai-section since we replace with inline input */
    .ai-section-btn { display: none !important; }
  `;

  // ── SVG helpers ───────────────────────────────────────────────
  function sendSVG() {
    return '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>';
  }
  function micSVG() {
    return '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="11" rx="3"/><path d="M5 10a7 7 0 0 0 14 0"/><line x1="12" y1="17" x2="12" y2="22"/><line x1="8" y1="22" x2="16" y2="22"/></svg>';
  }
  function closeSVG() {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" xmlns="http://www.w3.org/2000/svg"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
  }

  // ── Inject styles ─────────────────────────────────────────────
  function injectStyles() {
    var s = document.createElement('style');
    s.textContent = css;
    document.head.appendChild(s);
  }

  // ── Build DOM ─────────────────────────────────────────────────
  function buildWidget() {
    // Floating btn (hidden, kept for GomonWidget.open() compat from nav)
    var btn = document.createElement('button');
    btn.id = 'gw-btn';
    document.body.appendChild(btn);

    // Full-screen overlay
    var overlay = document.createElement('div');
    overlay.id = 'gw-overlay';
    overlay.innerHTML =
      '<div id="gw-panel" role="dialog" aria-label="GomonAI чат">' +
        '<div id="gw-header">' +
          '<div id="gw-header-dot"></div>' +
          '<span id="gw-header-title">GomonAI \u00b7 \u0410\u0441\u0438\u0441\u0442\u0435\u043d\u0442 Dr. Gomon</span>' +
          '<button id="gw-close" aria-label="\u0417\u0430\u043a\u0440\u0438\u0442\u0438">' + closeSVG() + '</button>' +
        '</div>' +
        '<div id="gw-messages"></div>' +
        '<div id="gw-input-area">' +
          '<textarea id="gw-textarea" placeholder="\u0417\u0430\u043f\u0438\u0442\u0430\u0439\u0442\u0435 \u043f\u0440\u043e \u043f\u0440\u043e\u0446\u0435\u0434\u0443\u0440\u0438, \u0446\u0456\u043d\u0438 \u0430\u0431\u043e \u043f\u0456\u0434\u0433\u043e\u0442\u043e\u0432\u043a\u0443\u2026" rows="1"></textarea>' +
          '<button id="gw-mic" aria-label="\u0413\u043e\u043b\u043e\u0441\u043e\u0432\u0438\u0439 \u0432\u0432\u0456\u0434">' + micSVG() + '</button>' +
          '<button id="gw-send" aria-label="\u041d\u0430\u0434\u0456\u0441\u043b\u0430\u0442\u0438">' + sendSVG() + '</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);

    // Inline input — inject into .ai-section-inner
    var aiInner = document.querySelector('.ai-section-inner');
    var inlineBlock = null;
    if (aiInner) {
      inlineBlock = document.createElement('div');
      inlineBlock.id = 'gw-inline';
      inlineBlock.innerHTML =
        '<textarea id="gw-inline-textarea" placeholder="\u0417\u0430\u043f\u0438\u0442\u0430\u0439\u0442\u0435 \u043f\u0440\u043e \u043f\u0440\u043e\u0446\u0435\u0434\u0443\u0440\u0438, \u0446\u0456\u043d\u0438 \u0430\u0431\u043e \u043f\u0456\u0434\u0433\u043e\u0442\u043e\u0432\u043a\u0443\u2026" rows="1"></textarea>' +
        '<button id="gw-inline-mic" aria-label="\u0413\u043e\u043b\u043e\u0441\u043e\u0432\u0438\u0439 \u0432\u0432\u0456\u0434">' + micSVG() + '</button>' +
        '<button id="gw-inline-send" aria-label="\u041d\u0430\u0434\u0456\u0441\u043b\u0430\u0442\u0438">' + sendSVG() + '</button>';
      aiInner.appendChild(inlineBlock);
    }

    return {
      btn: btn,
      overlay: overlay,
      panel: overlay.querySelector('#gw-panel'),
      closeBtn: overlay.querySelector('#gw-close'),
      messagesEl: overlay.querySelector('#gw-messages'),
      textarea: overlay.querySelector('#gw-textarea'),
      sendBtn: overlay.querySelector('#gw-send'),
      micBtn: overlay.querySelector('#gw-mic'),
      inlineBlock: inlineBlock,
      inlineTextarea: inlineBlock ? inlineBlock.querySelector('#gw-inline-textarea') : null,
      inlineSend: inlineBlock ? inlineBlock.querySelector('#gw-inline-send') : null,
      inlineMic: inlineBlock ? inlineBlock.querySelector('#gw-inline-mic') : null,
    };
  }

  // ── Storage ───────────────────────────────────────────────────
  function loadMessages() {
    try { return JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '[]'); }
    catch (e) { return []; }
  }
  function saveMessages(msgs) {
    try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(msgs)); }
    catch (e) {}
  }

  // ── Render ────────────────────────────────────────────────────
  function renderBubble(role, content, messagesEl) {
    var div = document.createElement('div');
    div.className = 'gw-bubble ' + (role === 'user' ? 'gw-bubble-user' : 'gw-bubble-ai');
    if (role === 'assistant') {
      div.innerHTML = content
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/\*\*([\s\S]+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\[([^\]]+)\]\(((?:https?:\/\/|tel:)[^\s\)\"]+)\)/g, function(m, text, url) {
          if (url.startsWith('tel:')) return '<a href="' + url.replace(/"/g, '&quot;') + '">' + text + '</a>';
          try { new URL(url); } catch(e) { return text; }
          return '<a href="' + url.replace(/"/g, '&quot;') + '" target="_blank" rel="noopener noreferrer">' + text + '</a>';
        })
        .replace(/\n/g, '<br>');
    } else {
      div.textContent = content;
    }
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }
  var _typingTimer = null;
  function showTyping(messagesEl) {
    var div = document.createElement('div');
    div.className = 'gw-typing';
    var dotsEl = document.createElement('span');
    dotsEl.className = 'gw-typing-dots';
    dotsEl.innerHTML = '<span></span><span></span><span></span>';
    var textEl = document.createElement('span');
    textEl.className = 'gw-typing-text';
    var idx = 0;
    textEl.textContent = TYPING_MSGS[idx];
    div.appendChild(dotsEl);
    div.appendChild(textEl);
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    _typingTimer = setInterval(function() {
      textEl.style.opacity = '0';
      setTimeout(function() {
        idx = (idx + 1) % TYPING_MSGS.length;
        textEl.textContent = TYPING_MSGS[idx];
        textEl.style.opacity = '1';
      }, 300);
    }, 2800);
    return div;
  }
  function renderAllMessages(messages, messagesEl) {
    messagesEl.innerHTML = '';
    messages.forEach(function (m) { renderBubble(m.role, m.content, messagesEl); });
  }

  // ── RATE LIMIT (5 запитів/день для гостей, localStorage) ────────────────
  function _gwRlData() {
    var today = new Date().toISOString().slice(0, 10);
    try {
      var d = JSON.parse(localStorage.getItem('gw_rl') || 'null');
      if (!d || d.date !== today) return { date: today, count: 0 };
      return d;
    } catch (e) { return { date: new Date().toISOString().slice(0, 10), count: 0 }; }
  }
  function gwIsRateLimited() { return _gwRlData().count >= 5; }
  function gwRateLimitBump() {
    var d = _gwRlData(); d.count++;
    try { localStorage.setItem('gw_rl', JSON.stringify(d)); } catch (e) {}
  }

  // ── API ───────────────────────────────────────────────────────
  function sendToAPI(messages, callback) {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', API_URL);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.timeout = 30000;
    xhr.onload = function () {
      if (xhr.status === 200) {
        try { callback(null, JSON.parse(xhr.responseText)); }
        catch (e) { callback(new Error('parse')); }
      } else { callback(new Error('http ' + xhr.status)); }
    };
    xhr.onerror = function () { callback(new Error('network')); };
    xhr.ontimeout = function () { callback(new Error('timeout')); };
    xhr.send(JSON.stringify({ messages: messages, user: {}, source: 'site' }));
  }

  function notifyProcedure(procedure, action) {
    var payload = JSON.stringify({ procedure: procedure, action: action, user_name: 'Відвідувач сайту', user_phone: '', source: 'site' });
    if (navigator.sendBeacon) {
      navigator.sendBeacon(NOTIFY_URL, new Blob([payload], { type: 'application/json' }));
    } else {
      var xhr = new XMLHttpRequest();
      xhr.open('POST', NOTIFY_URL, true);
      xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.send(payload);
    }
  }

  function renderConsultCard(messagesEl) {
    var card = document.createElement('div');
    card.className = 'gw-procedure-card';
    card.innerHTML =
      '<p class="gw-proc-label">&#x1F469;&#x200D;&#x2695;&#xFE0F; \u0420\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0430\u0446\u0456\u044f</p>' +
      '<p style="font-size:13px;color:var(--text3,#8a8278);line-height:1.5;margin:4px 0 12px">' +
        '\u0417\u0432\u0430\u0436\u0430\u044e\u0447\u0438 \u043d\u0430 \u0441\u043a\u043b\u0430\u0434\u043d\u0456\u0441\u0442\u044c \u0432\u0430\u0448\u043e\u0433\u043e \u0437\u0430\u043f\u0438\u0442\u0443, \u0440\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0443\u044e \u0437\u0432\u0435\u0440\u043d\u0443\u0442\u0438\u0441\u044c \u0434\u043e \u043b\u0456\u043a\u0430\u0440\u044f \u043d\u0430 \u043e\u0441\u043e\u0431\u0438\u0441\u0442\u0443 \u043a\u043e\u043d\u0441\u0443\u043b\u044c\u0442\u0430\u0446\u0456\u044e.' +
      '</p>' +
      '<div class="gw-proc-row"><span class="gw-proc-name">\u041a\u043e\u043d\u0441\u0443\u043b\u044c\u0442\u0430\u0446\u0456\u044f \u043b\u0456\u043a\u0430\u0440\u044f</span></div>' +
      '<a class="gw-proc-ig" href="https://ig.me/m/dr.gomon" target="_blank" rel="noopener noreferrer">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="0.8" fill="currentColor" stroke="none"/></svg>' +
        '\u0417\u0430\u043f\u0438\u0441\u0430\u0442\u0438\u0441\u044c \u043d\u0430 \u043a\u043e\u043d\u0441\u0443\u043b\u044c\u0442\u0430\u0446\u0456\u044e' +
      '</a>' +
      '<p class="gw-proc-hint">\u041d\u0430\u043f\u0438\u0448\u0456\u0442\u044c \u043b\u0456\u043a\u0430\u0440\u044e \u0432 Direct \u2014 \u0432\u0430\u043c \u043f\u0456\u0434\u0431\u0435\u0440\u0443\u0442\u044c \u0437\u0440\u0443\u0447\u043d\u0438\u0439 \u0447\u0430\u0441</p>';
    var igBtn = card.querySelector('.gw-proc-ig');
    if (igBtn) igBtn.addEventListener('click', function () {
      notifyProcedure('Консультація лікаря', 'instagram');
    }, { once: true });
    messagesEl.appendChild(card);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function renderProcedureCard(procedure, messagesEl) {
    _siteStartReminder(procedure); // 10 хв → нагадування якщо не записався
    var card = document.createElement('div');
    card.className = 'gw-procedure-card';
    card.innerHTML =
      '<p class="gw-proc-label">\u2728 \u041f\u0456\u0434\u0456\u0431\u0440\u0430\u043d\u0430 \u043f\u0440\u043e\u0446\u0435\u0434\u0443\u0440\u0430</p>' +
      '<div class="gw-proc-row">' +
        '<span class="gw-proc-name"></span>' +
        '<button class="gw-proc-copy" title="\u0421\u043a\u043e\u043f\u0456\u044e\u0432\u0430\u0442\u0438 \u043d\u0430\u0437\u0432\u0443">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>' +
        '</button>' +
      '</div>' +
      '<a class="gw-proc-ig" href="https://ig.me/m/dr.gomon" target="_blank" rel="noopener noreferrer">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="0.8" fill="currentColor" stroke="none"/></svg>' +
        '\u041d\u0430\u043f\u0438\u0441\u0430\u0442\u0438 \u043b\u0456\u043a\u0430\u0440\u044e \u0432 Instagram' +
      '</a>' +
      '<p class="gw-proc-hint">\u0421\u043a\u043e\u043f\u0456\u0439\u0442\u0435 \u043d\u0430\u0437\u0432\u0443 \u0442\u0430 \u043d\u0430\u0434\u0456\u0448\u043b\u0456\u0442\u044c \u043b\u0456\u043a\u0430\u0440\u044e \u0432 Direct \u0434\u043b\u044f \u0437\u0430\u043f\u0438\u0441\u0443</p>';

    // Назва процедури через textContent — повністю безпечно від XSS
    var procNameEl = card.querySelector('.gw-proc-name');
    if (procNameEl) procNameEl.textContent = procedure;

    var igBtn = card.querySelector('.gw-proc-ig');
    if (igBtn) igBtn.addEventListener('click', function () {
      _siteCancelReminder();
      notifyProcedure(procedure, 'instagram');
    }, { once: true });

    var copyBtn = card.querySelector('.gw-proc-copy');
    if (copyBtn) {
      copyBtn.addEventListener('click', function () {
        var name = card.querySelector('.gw-proc-name').textContent;
        if (navigator.clipboard) {
          navigator.clipboard.writeText(name).catch(function(){});
        } else {
          var ta = document.createElement('textarea');
          ta.value = name; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta);
        }
        copyBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="#6fcf97" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
        setTimeout(function () {
          copyBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>';
        }, 2000);
        _siteCancelReminder();
        notifyProcedure(name, 'copy');
      });
    }

    messagesEl.appendChild(card);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  // ── Reminder state ────────────────────────────────────────────
  var _sitePendingProc   = null;
  var _siteReminderTimer = null;

  function _siteStartReminder(procedure) {
    _sitePendingProc = procedure;
    if (_siteReminderTimer) clearTimeout(_siteReminderTimer);
    _siteReminderTimer = setTimeout(function () { _siteFireReminder(procedure); }, 10 * 60 * 1000);
  }

  function _siteCancelReminder() {
    _sitePendingProc = null;
    if (_siteReminderTimer) { clearTimeout(_siteReminderTimer); _siteReminderTimer = null; }
  }

  function _siteFireReminder(procedure) {
    _sitePendingProc = null;
    _siteReminderTimer = null;
    // Показуємо in-widget reminder якщо модалка відкрита
    var messagesEl = document.getElementById('gw-messages');
    if (messagesEl) {
      var banner = document.createElement('div');
      banner.className = 'gw-reminder-banner';
      banner.innerHTML =
        '<span class="gw-reminder-icon">🌸</span>' +
        '<span class="gw-reminder-text">Ваша процедура ще чекає! Залишилось лише написати лікарю — це займе хвилину.</span>';
      messagesEl.appendChild(banner);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }
  }

  document.addEventListener('visibilitychange', function () {
    if (document.hidden && _sitePendingProc) {
      _siteCancelReminder();
      // на сайті — анонімний відвідувач, телеграм не надсилаємо
    }
  });

  // ── Main ──────────────────────────────────────────────────────
  function init() {
    injectStyles();
    var els = buildWidget();
    var messages = loadMessages();
    var isOpen = false;
    var isBusy = false;

    if (messages.length === 0) {
      messages.push({ role: 'assistant', content: GREETING });
      saveMessages(messages);
    }

    function _applyViewportHeight() {
      if (window.innerWidth > 600) return;
      var vv = window.visualViewport;
      if (!vv) return;
      // Reposition overlay to match visual viewport (iOS keyboard shifts visual viewport offset)
      els.overlay.style.top    = vv.offsetTop + 'px';
      els.overlay.style.left   = vv.offsetLeft + 'px';
      els.overlay.style.right  = 'auto';
      els.overlay.style.bottom = 'auto';
      els.overlay.style.width  = vv.width + 'px';
      els.overlay.style.height = vv.height + 'px';
      els.panel.style.height    = vv.height + 'px';
      els.panel.style.maxHeight = vv.height + 'px';
      setTimeout(function () { els.messagesEl.scrollTop = els.messagesEl.scrollHeight; }, 30);
    }

    function _resetOverlayPosition() {
      ['top','left','right','bottom','width','height'].forEach(function(p) {
        els.overlay.style[p] = '';
      });
      els.panel.style.height = '';
      els.panel.style.maxHeight = '';
    }

    var _chatOpenConvSent = false;
    function openModal() {
      if (isOpen) return;
      isOpen = true;
      if (!_chatOpenConvSent && typeof gtag === 'function') {
        gtag('event', 'conversion', {'send_to': 'AW-719653819/WaavCKa45JAcELuXlNcC'});
        _chatOpenConvSent = true;
      }
      document.body.style.overflow = 'hidden';
      renderAllMessages(messages, els.messagesEl);
      els.overlay.classList.add('gw-open');
      setTimeout(function () { els.textarea.focus(); }, 50);
      if (window.visualViewport) {
        window.visualViewport.addEventListener('resize', _applyViewportHeight);
        window.visualViewport.addEventListener('scroll', _applyViewportHeight);
        _applyViewportHeight();
      }
    }

    function closeModal() {
      isOpen = false;
      document.body.style.overflow = '';
      els.overlay.classList.remove('gw-open');
      if (window.visualViewport) {
        window.visualViewport.removeEventListener('resize', _applyViewportHeight);
        window.visualViewport.removeEventListener('scroll', _applyViewportHeight);
      }
      _resetOverlayPosition();
    }

    function setDisabled(val) {
      isBusy = val;
      els.sendBtn.disabled = val;
      els.textarea.disabled = val;
      if (els.inlineSend) els.inlineSend.disabled = val;
      if (els.inlineTextarea) els.inlineTextarea.disabled = val;
    }

    function processReply(typingEl) {
      sendToAPI(messages, function (err, data) {
        if (_typingTimer) { clearInterval(_typingTimer); _typingTimer = null; }
        if (typingEl.parentNode) typingEl.parentNode.removeChild(typingEl);
        setDisabled(false);
        var reply = (!err && data && data.reply)
          ? data.reply
          : 'Вибачте, сталась помилка. Спробуйте ще раз.';
        messages.push({ role: 'assistant', content: reply });
        saveMessages(messages);
        renderBubble('assistant', reply, els.messagesEl);
        if (!err && data && data.procedure) renderProcedureCard(data.procedure, els.messagesEl);
        els.textarea.focus();
      });
    }

    // Send from modal input
    function doSendModal() {
      var text = (els.textarea.value || '').trim();
      if (!text || isBusy) return;
      els.textarea.value = '';
      els.textarea.style.height = 'auto';
      messages.push({ role: 'user', content: text });
      saveMessages(messages);
      // Google Ads conversion — перше повідомлення
      if (messages.filter(function(m){return m.role==='user'}).length === 1 && typeof gtag === 'function') {
        gtag('event', 'conversion', {'send_to': 'AW-719653819/WaavCKa45JAcELuXlNcC'});
      }
      renderBubble('user', text, els.messagesEl);
      if (gwIsRateLimited()) {
        renderConsultCard(els.messagesEl);
        return;
      }
      gwRateLimitBump();
      setDisabled(true);
      processReply(showTyping(els.messagesEl));
    }

    // Send from inline block — open modal and process
    function doSendInline() {
      if (!els.inlineTextarea) return;
      var text = (els.inlineTextarea.value || '').trim();
      if (!text || isBusy) return;
      els.inlineTextarea.value = '';
      els.inlineTextarea.style.height = 'auto';
      messages.push({ role: 'user', content: text });
      saveMessages(messages);
      openModal(); // renders all messages including the just-added user msg
      if (gwIsRateLimited()) {
        renderConsultCard(els.messagesEl);
        return;
      }
      gwRateLimitBump();
      setDisabled(true);
      processReply(showTyping(els.messagesEl));
    }

    // Public API
    window.GomonWidget = { open: openModal };

    // Modal close
    els.closeBtn.addEventListener('click', closeModal);
    els.overlay.addEventListener('click', function (e) {
      if (e.target === els.overlay) closeModal();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && isOpen) closeModal();
    });

    // Modal send
    els.sendBtn.addEventListener('click', doSendModal);
    els.textarea.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); doSendModal(); }
    });
    els.textarea.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 110) + 'px';
      this.style.overflowY = this.scrollHeight > 110 ? 'auto' : 'hidden';
    });

    // ── Голосовий ввід (modal + inline) ──────────────────────────────────────
    function _gwVoice(textarea, micBtn, onFinal) {
      if (!window.SpeechRecognition && !window.webkitSpeechRecognition) return;
      if (micBtn._recog) { micBtn._recog.stop(); return; }
      var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      var r = new SR();
      r.lang = 'uk-UA'; r.continuous = false; r.interimResults = true;
      micBtn._recog = r;
      micBtn.classList.add('listening');
      var ph = textarea.placeholder;
      textarea.placeholder = 'Слухаю\u2026';
      var fin = '';
      r.onresult = function(e) {
        var interim = ''; fin = '';
        for (var i = 0; i < e.results.length; i++) {
          if (e.results[i].isFinal) fin += e.results[i][0].transcript;
          else interim += e.results[i][0].transcript;
        }
        textarea.value = interim ? fin + ' ' + interim : fin;
        textarea.dispatchEvent(new Event('input'));
      };
      var done = function() {
        micBtn.classList.remove('listening');
        micBtn._recog = null;
        textarea.placeholder = ph;
        if (fin) onFinal();
      };
      r.onend = done; r.onerror = done;
      r.start();
    }
    if (els.micBtn) {
      els.micBtn.addEventListener('click', function() {
        _gwVoice(els.textarea, els.micBtn, doSendModal);
      });
    }

    // Inline send
    if (els.inlineSend) {
      els.inlineSend.addEventListener('click', doSendInline);
    }
    if (els.inlineMic && els.inlineTextarea) {
      els.inlineMic.addEventListener('click', function() {
        _gwVoice(els.inlineTextarea, els.inlineMic, doSendInline);
      });
    }
    if (els.inlineTextarea) {
      els.inlineTextarea.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); doSendInline(); }
      });
      els.inlineTextarea.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 90) + 'px';
      });

      // Підбір placeholder під ширину поля
      var FULL_PLACEHOLDER = 'Запитайте про процедури, ціни або підготовку\u2026';
      var _phCanvas = document.createElement('canvas');
      function fitPlaceholder() {
        var el = els.inlineTextarea;
        var w = el.clientWidth;
        if (!w) return;
        var ctx = _phCanvas.getContext('2d');
        var cs = window.getComputedStyle(el);
        ctx.font = (cs.fontWeight || '300') + ' ' + (cs.fontSize || '15px') + ' ' + (cs.fontFamily || 'Jost,sans-serif');
        if (ctx.measureText(FULL_PLACEHOLDER).width <= w) {
          el.placeholder = FULL_PLACEHOLDER;
          return;
        }
        // Запас ~4 символи ('абвг')
        var spare = ctx.measureText('\u0430\u0431\u0432\u0433').width;
        var text = FULL_PLACEHOLDER.replace(/\u2026$/, '');
        while (text.length > 4 && ctx.measureText(text + '\u2026').width > w - spare) {
          text = text.slice(0, -1);
        }
        el.placeholder = text.replace(/[\s,]+$/, '') + '\u2026';
      }
      // Запуск після layout
      requestAnimationFrame(function () { setTimeout(fitPlaceholder, 50); });
      var _phResizeTimer;
      window.addEventListener('resize', function () {
        clearTimeout(_phResizeTimer);
        _phResizeTimer = setTimeout(fitPlaceholder, 120);
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
