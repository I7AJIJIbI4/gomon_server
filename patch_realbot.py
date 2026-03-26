with open("/home/gomoncli/zadarma/bot.py", "r") as f:
    content = f.read()

# The bot already imports MessageHandler, Filters - just add the function and handler
snippet = (
    "\n\n# -- Channel post handler for news feed --\n"
    "def save_channel_post(update, context):\n"
    "    import sqlite3 as _sq\n"
    "    FEED_DB = '/home/gomoncli/zadarma/feed.db'\n"
    "    msg = update.channel_post\n"
    "    if not msg:\n"
    "        return\n"
    "    text = msg.text or msg.caption or ''\n"
    "    media_type = None\n"
    "    file_id = None\n"
    "    if msg.photo:\n"
    "        media_type = 'photo'\n"
    "        file_id = msg.photo[-1].file_id\n"
    "    elif msg.video:\n"
    "        media_type = 'video'\n"
    "        file_id = msg.video.file_id\n"
    "    try:\n"
    "        conn = _sq.connect(FEED_DB)\n"
    "        conn.execute(\n"
    "            'INSERT OR IGNORE INTO posts (tg_msg_id, text, date, media_type, file_id) VALUES (?,?,?,?,?)',\n"
    "            (msg.message_id, text, int(msg.date.timestamp()), media_type, file_id)\n"
    "        )\n"
    "        conn.commit()\n"
    "        conn.close()\n"
    "        logger.info(f'Channel post saved: {msg.message_id}')\n"
    "    except Exception as e:\n"
    "        logger.error(f'Feed save error: {e}')\n"
)

# Insert before the main() function
content = content.replace("\ndef main():", snippet + "\ndef main():", 1)

# Add handler inside main() before start_polling
content = content.replace(
    "    dp.add_error_handler(error_handler)",
    "    dp.add_handler(MessageHandler(Filters.update.channel_posts, save_channel_post))\n    dp.add_error_handler(error_handler)",
    1
)

with open("/home/gomoncli/zadarma/bot.py", "w") as f:
    f.write(content)
print("ok")
