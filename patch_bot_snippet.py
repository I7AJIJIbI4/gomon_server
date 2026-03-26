FEED_DB = "/home/gomoncli/zadarma/feed.db"

def _init_feed_db():
    import sqlite3
    conn = sqlite3.connect(FEED_DB)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS posts ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "tg_msg_id INTEGER UNIQUE,"
        "text TEXT,"
        "date INTEGER,"
        "media_type TEXT,"
        "file_id TEXT,"
        "created_at TEXT DEFAULT (datetime('now'))"
        ")"
    )
    conn.commit()
    conn.close()

_init_feed_db()

def save_channel_post(update, context):
    import sqlite3
    msg = update.channel_post
    if not msg:
        return
    text = msg.text or msg.caption or ""
    media_type = None
    file_id = None
    if msg.photo:
        media_type = "photo"
        file_id = msg.photo[-1].file_id
    elif msg.video:
        media_type = "video"
        file_id = msg.video.file_id
    try:
        conn = sqlite3.connect(FEED_DB)
        conn.execute(
            "INSERT OR IGNORE INTO posts (tg_msg_id, text, date, media_type, file_id) VALUES (?,?,?,?,?)",
            (msg.message_id, text, int(msg.date.timestamp()), media_type, file_id)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"feed save error: {e}")
