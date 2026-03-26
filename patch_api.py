with open("/home/gomoncli/pwa_api.py", "r") as f:
    content = f.read()

# Add redirect to flask imports
content = content.replace(
    "from flask import Flask, request, jsonify, send_from_directory",
    "from flask import Flask, request, jsonify, send_from_directory, redirect"
)

# Add feed constants after existing DB_PATH
old_const = "DB_PATH      = '/home/gomoncli/zadarma/users.db'"
new_const = (
    "DB_PATH      = '/home/gomoncli/zadarma/users.db'\n"
    "FEED_DB      = '/home/gomoncli/zadarma/feed.db'\n"
    "TG_TOKEN     = '6372404755:AAHsWIfh54R70qrnCfBf3Ml4GSljEOKCn5A'\n"
    "\n"
    "def init_feed_db():\n"
    "    conn = sqlite3.connect(FEED_DB)\n"
    "    conn.execute(\n"
    "        'CREATE TABLE IF NOT EXISTS posts ('\n"
    "        'id INTEGER PRIMARY KEY AUTOINCREMENT,'\n"
    "        'tg_msg_id INTEGER UNIQUE,'\n"
    "        'text TEXT,'\n"
    "        'date INTEGER,'\n"
    "        'media_type TEXT,'\n"
    "        'file_id TEXT,'\n"
    "        \"created_at TEXT DEFAULT (datetime('now'))\"\n"
    "        ')'\n"
    "    )\n"
    "    conn.commit()\n"
    "    conn.close()\n"
    "\n"
    "init_feed_db()\n"
)
content = content.replace(old_const, new_const, 1)

feed_routes = (
    "\n# -- NEWS FEED --\n"
    "\n"
    "@app.route('/api/feed', methods=['GET'])\n"
    "def get_feed():\n"
    "    try:\n"
    "        conn = sqlite3.connect(FEED_DB)\n"
    "        conn.row_factory = sqlite3.Row\n"
    "        rows = conn.execute(\n"
    "            'SELECT id, tg_msg_id, text, date, media_type, file_id FROM posts ORDER BY date DESC LIMIT 30'\n"
    "        ).fetchall()\n"
    "        conn.close()\n"
    "        return jsonify([dict(r) for r in rows])\n"
    "    except Exception:\n"
    "        return jsonify([])\n"
    "\n"
    "@app.route('/api/feed/media/<fid>')\n"
    "def feed_media(fid):\n"
    "    import urllib.request\n"
    "    try:\n"
    "        url = 'https://api.telegram.org/bot' + TG_TOKEN + '/getFile?file_id=' + fid\n"
    "        with urllib.request.urlopen(url, timeout=5) as r:\n"
    "            data = json.loads(r.read())\n"
    "        if not data.get('ok'):\n"
    "            return jsonify({'error': 'not found'}), 404\n"
    "        fp = data['result']['file_path']\n"
    "        return redirect('https://api.telegram.org/file/bot' + TG_TOKEN + '/' + fp)\n"
    "    except Exception as e:\n"
    "        return jsonify({'error': str(e)}), 500\n"
    "\n"
)
content = content.replace("# ── PWA STATIC FILES ──", feed_routes + "# ── PWA STATIC FILES ──")

with open("/home/gomoncli/pwa_api.py", "w") as f:
    f.write(content)
print("ok")
