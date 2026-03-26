with open("/home/gomoncli/public_html/app/index.html", "r") as f:
    content = f.read()

# 1. Add CSS for news feed (after promo CSS)
news_css = (
    "\n/* -- NEWS FEED -- */\n"
    ".news-scroll{display:flex;gap:12px;padding:0 20px 4px;overflow-x:auto;scrollbar-width:none}\n"
    ".news-scroll::-webkit-scrollbar{display:none}\n"
    ".news-tile{\n"
    "  flex-shrink:0;width:240px;\n"
    "  background:var(--surface);border:1px solid var(--border);border-radius:12px;\n"
    "  padding:14px;cursor:pointer;position:relative;overflow:hidden;\n"
    "  transition:border-color .2s;\n"
    "}\n"
    ".news-tile:active{opacity:.8}\n"
    ".news-date{font-size:10px;color:var(--text3);letter-spacing:.6px;margin-bottom:8px;text-transform:uppercase}\n"
    ".news-text{font-size:13px;color:var(--text2);line-height:1.5;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}\n"
    ".news-more{font-size:11px;color:var(--gold);margin-top:8px;letter-spacing:.3px}\n"
    ".news-empty{padding:14px 20px;font-size:13px;color:var(--text3)}\n"
    "\n"
    "/* -- NEWS POPUP -- */\n"
    "#news-modal{position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.8);display:none;align-items:flex-end;justify-content:center;padding:0 0 var(--safe-bottom)}\n"
    "#news-modal.show{display:flex}\n"
    ".news-sheet{background:var(--bg2);border-radius:20px 20px 0 0;border-top:1px solid var(--border-gold);padding:20px 20px 32px;width:100%;max-width:480px;max-height:85vh;overflow-y:auto;animation:sheetUp .3s ease}\n"
    ".news-sheet-handle{width:36px;height:3px;background:var(--border);border-radius:2px;margin:0 auto 16px}\n"
    ".news-sheet-date{font-size:11px;color:var(--text3);letter-spacing:.6px;text-transform:uppercase;margin-bottom:14px}\n"
    ".news-sheet-text{font-size:15px;color:var(--text2);line-height:1.7;white-space:pre-wrap}\n"
    ".news-sheet-media{margin-top:18px;border-radius:12px;overflow:hidden;background:var(--surface)}\n"
    ".news-sheet-media img,.news-sheet-media video{width:100%;display:block;border-radius:12px}\n"
    ".news-sheet-close{display:block;margin:20px auto 0;background:none;border:1px solid var(--border);border-radius:8px;padding:10px 28px;color:var(--text2);font-size:13px;font-family:var(--sans);cursor:pointer}\n"
)
content = content.replace(
    ".section-label{font-size:11px",
    news_css + ".section-label{font-size:11px"
)

# 2. Add HTML: news section after promos + news modal
old_html = '      <p class="section-label">Швидкий доступ</p>'
new_html = (
    '      <p class="section-label">Новини</p>\n'
    '      <div class="news-scroll" id="home-news"><p class="news-empty">Завантаження...</p></div>\n'
    '      <p class="section-label">Швидкий доступ</p>'
)
content = content.replace(old_html, new_html, 1)

# Add news modal before </body>
old_body = '</body>'
news_modal = (
    '<div id="news-modal" onclick="if(event.target===this)closeNewsModal()">\n'
    '  <div class="news-sheet">\n'
    '    <div class="news-sheet-handle"></div>\n'
    '    <p class="news-sheet-date" id="news-modal-date"></p>\n'
    '    <div class="news-sheet-text" id="news-modal-text"></div>\n'
    '    <div class="news-sheet-media" id="news-modal-media" style="display:none"></div>\n'
    '    <button class="news-sheet-close" onclick="closeNewsModal()">Закрити</button>\n'
    '  </div>\n'
    '</div>\n'
    '</body>'
)
content = content.replace(old_body, news_modal, 1)

# 3. Add JS: renderNews + openNews + closeNewsModal
# Find a good spot to insert JS — after renderPromos function
old_js = "function renderAppointments() {"
new_js = (
    "let _newsData = [];\n"
    "\n"
    "async function loadNews() {\n"
    "  try {\n"
    "    const r = await fetch('/api/feed');\n"
    "    _newsData = await r.json();\n"
    "  } catch(e) { _newsData = []; }\n"
    "  renderNews();\n"
    "}\n"
    "\n"
    "function renderNews() {\n"
    "  const el = document.getElementById('home-news');\n"
    "  if (!_newsData.length) {\n"
    "    el.innerHTML = '<p class=\"news-empty\">Новини ще не додано</p>';\n"
    "    return;\n"
    "  }\n"
    "  el.innerHTML = _newsData.map((p, i) => {\n"
    "    const d = new Date(p.date * 1000);\n"
    "    const dateStr = d.toLocaleDateString('uk-UA', {day:'numeric',month:'long'});\n"
    "    const text = (p.text || '').trim();\n"
    "    const long = text.length > 160;\n"
    "    const preview = long ? text.slice(0, 160) + '...' : text;\n"
    "    return `<div class=\"news-tile\" onclick=\"openNews(${i})\">`\n"
    "      + `<p class=\"news-date\">${dateStr}</p>`\n"
    "      + `<p class=\"news-text\">${preview.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\\n/g,'<br>')}</p>`\n"
    "      + (long || p.media_type ? '<p class=\"news-more\">Читати далі &rsaquo;</p>' : '')\n"
    "      + '</div>';\n"
    "  }).join('');\n"
    "}\n"
    "\n"
    "function openNews(i) {\n"
    "  const p = _newsData[i];\n"
    "  if (!p) return;\n"
    "  const d = new Date(p.date * 1000);\n"
    "  document.getElementById('news-modal-date').textContent =\n"
    "    d.toLocaleDateString('uk-UA', {day:'numeric',month:'long',year:'numeric'});\n"
    "  const text = (p.text || '').trim();\n"
    "  document.getElementById('news-modal-text').innerHTML =\n"
    "    text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\\n/g,'<br>');\n"
    "  const mediaEl = document.getElementById('news-modal-media');\n"
    "  if (p.media_type && p.file_id) {\n"
    "    const src = '/api/feed/media/' + p.file_id;\n"
    "    if (p.media_type === 'photo') {\n"
    "      mediaEl.innerHTML = `<img src=\"${src}\" alt=\"\">` ;\n"
    "    } else {\n"
    "      mediaEl.innerHTML = `<video src=\"${src}\" controls playsinline></video>`;\n"
    "    }\n"
    "    mediaEl.style.display = '';\n"
    "  } else {\n"
    "    mediaEl.style.display = 'none';\n"
    "    mediaEl.innerHTML = '';\n"
    "  }\n"
    "  document.getElementById('news-modal').classList.add('show');\n"
    "}\n"
    "\n"
    "function closeNewsModal() {\n"
    "  document.getElementById('news-modal').classList.remove('show');\n"
    "  document.getElementById('news-modal-media').innerHTML = '';\n"
    "  document.getElementById('news-modal-media').style.display = 'none';\n"
    "}\n"
    "\n"
    "function renderAppointments() {"
)
content = content.replace(old_js, new_js, 1)

# 4. Call loadNews() when home screen loads — find where renderPromos is called
content = content.replace(
    "renderPromos();",
    "renderPromos();\n  loadNews();",
    1
)

with open("/home/gomoncli/public_html/app/index.html", "w") as f:
    f.write(content)
print("frontend ok")
