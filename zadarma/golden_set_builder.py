"""
golden_set_builder.py — будує golden set з реальних розмов для LLM-as-Judge тестування.

Джерела:
  - Відповіді лікаря (is_from_admin=1, sender_id != 'ai_bot')
  - AI-відповіді без корекції лікарем (sender_id='ai_bot' і лікар не відповів протягом 30хв)

Запуск: python3 golden_set_builder.py [--limit N] [--output PATH]
"""
import sqlite3
import json
import re
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from user_db import DB_PATH

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'private_data', 'golden_set.json')
CONTEXT_WINDOW = 6   # messages before the response to include as context
MIN_CONTENT_LEN = 15  # ignore very short/empty responses
CORRECTION_WINDOW_MINUTES = 30

ADMIN_SENDER_IDS = {'ai_bot', 'admin_ig', 'admin_380733103110'}


def _is_admin_sender(sender_id):
    if sender_id == 'ai_bot':
        return False
    return (
        sender_id in ADMIN_SENDER_IDS
        or str(sender_id).startswith('admin_')
    )


def _anonymize(text, phone_map):
    """Замінює номери телефонів на [PHONE_N]."""
    if not text:
        return text
    def replace_phone(m):
        raw = m.group(0)
        if raw not in phone_map:
            phone_map[raw] = '[PHONE_{}]'.format(len(phone_map) + 1)
        return phone_map[raw]
    text = re.sub(r'\+?380\d{9}', replace_phone, text)
    text = re.sub(r'\b0\d{9}\b', replace_phone, text)
    return text


def _load_conversation(conn, conv_id, before_id):
    """Повертає до CONTEXT_WINDOW повідомлень до вказаного id."""
    rows = conn.execute(
        'SELECT id, sender_id, is_from_admin, content FROM messages '
        'WHERE conversation_id=? AND id < ? AND content IS NOT NULL '
        'ORDER BY id DESC LIMIT ?',
        (conv_id, before_id, CONTEXT_WINDOW)
    ).fetchall()
    return list(reversed(rows))


def build(limit_doctor=300, limit_ai=150, output=OUTPUT_PATH):
    conn = sqlite3.connect(DB_PATH, timeout=30)

    # --- Відповіді лікаря ---
    doctor_rows = conn.execute(
        "SELECT m.id, m.conversation_id, m.platform, m.sender_id, m.content, m.created_at "
        "FROM messages m "
        "WHERE m.is_from_admin=1 AND m.sender_id != 'ai_bot' "
        "  AND length(m.content) >= ? "
        "  AND m.media_type IS NULL "
        "ORDER BY m.id DESC LIMIT ?",
        (MIN_CONTENT_LEN, limit_doctor)
    ).fetchall()

    # --- AI-відповіді без корекції ---
    ai_rows = conn.execute(
        "SELECT m.id, m.conversation_id, m.platform, m.sender_id, m.content, m.created_at, "
        "  (SELECT COUNT(*) FROM messages d "
        "   WHERE d.conversation_id = m.conversation_id "
        "     AND d.is_from_admin = 1 AND d.sender_id != 'ai_bot' "
        "     AND d.created_at > m.created_at "
        "     AND datetime(d.created_at) <= datetime(m.created_at, '+{} minutes') "
        "  ) as corrected "
        "FROM messages m "
        "WHERE m.sender_id='ai_bot' AND length(m.content) >= ? AND m.media_type IS NULL "
        "ORDER BY m.id DESC LIMIT ?".format(CORRECTION_WINDOW_MINUTES),
        (MIN_CONTENT_LEN, limit_ai * 2)  # over-fetch then filter
    ).fetchall()

    entries = []
    conv_id_map = {}   # real conv_id → anon_id
    phone_map = {}     # real phone → [PHONE_N]

    def anon_conv(conv_id):
        if conv_id not in conv_id_map:
            conv_id_map[conv_id] = 'conv_{}'.format(len(conv_id_map) + 1)
        return conv_id_map[conv_id]

    def make_entry(row_id, conv_id, platform, content, created_at, source):
        ctx_rows = _load_conversation(conn, conv_id, row_id)
        context = []
        preceding_client_msg = None

        for ctx_id, ctx_sender, ctx_is_admin, ctx_content in ctx_rows:
            if not ctx_content:
                continue
            role = 'assistant' if ctx_is_admin else 'user'
            context.append({'role': role, 'content': _anonymize(ctx_content, phone_map)})
            if role == 'user':
                preceding_client_msg = _anonymize(ctx_content, phone_map)

        if not preceding_client_msg:
            return None  # відповідь без запитання — пропускаємо

        return {
            'id': 'golden_{}'.format(row_id),
            'source': source,
            'platform': platform,
            'conversation_id': anon_conv(conv_id),
            'context': context,
            'client_message': preceding_client_msg,
            'golden_response': _anonymize(content, phone_map),
            'created_at': created_at,
        }

    # Обробка відповідей лікаря
    for row_id, conv_id, platform, sender_id, content, created_at in doctor_rows:
        entry = make_entry(row_id, conv_id, platform, content, created_at, 'doctor')
        if entry:
            entries.append(entry)

    # Обробка прийнятих AI-відповідей
    ai_accepted_count = 0
    for row in ai_rows:
        if ai_accepted_count >= limit_ai:
            break
        row_id, conv_id, platform, sender_id, content, created_at, corrected = row
        if corrected > 0:
            continue  # лікар виправив — пропускаємо
        entry = make_entry(row_id, conv_id, platform, content, created_at, 'ai_accepted')
        if entry:
            entries.append(entry)
            ai_accepted_count += 1

    conn.close()

    # Сортуємо: спочатку відповіді лікаря
    entries.sort(key=lambda e: (0 if e['source'] == 'doctor' else 1, e['created_at']))

    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print('Golden set: {} entries ({} doctor, {} ai_accepted) → {}'.format(
        len(entries),
        sum(1 for e in entries if e['source'] == 'doctor'),
        sum(1 for e in entries if e['source'] == 'ai_accepted'),
        output
    ))
    return entries


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--limit-doctor', type=int, default=300)
    p.add_argument('--limit-ai', type=int, default=150)
    p.add_argument('--output', default=OUTPUT_PATH)
    args = p.parse_args()
    build(args.limit_doctor, args.limit_ai, args.output)
