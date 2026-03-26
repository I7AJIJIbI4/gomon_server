#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
receipt.py — генерує PDF квитанцію і надсилає на email клієнта
Запускається з PHP: python receipt.py <order_id>
Python 3.6 compatible
Потребує: pip install reportlab
"""
from __future__ import print_function
import sys
import os
import sqlite3
import smtplib
import tempfile
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DB_PATH, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SITE_URL

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False
    print('reportlab not installed, PDF generation skipped', file=sys.stderr)


# ── Кольори клініки ───────────────────────────────────────────
GOLD  = colors.HexColor('#c9a96e')
DARK  = colors.HexColor('#1a1410')
MUTED = colors.HexColor('#9a8f87')
CREAM = colors.HexColor('#faf8f5')
WARM  = colors.HexColor('#f3ede4')


def get_order_data(order_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,))
    order = c.fetchone()
    c.execute('SELECT * FROM clients WHERE order_id = ?', (order_id,))
    client = c.fetchone()
    c.execute('''SELECT * FROM transactions WHERE order_id = ?
                 ORDER BY created_at DESC LIMIT 1''', (order_id,))
    tx = c.fetchone()
    conn.close()
    return order, client, tx


def mark_receipt_sent(order_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''UPDATE transactions SET receipt_sent = 1
                        WHERE order_id = ? AND receipt_sent = 0''', (order_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print('mark_receipt_sent: {}'.format(e), file=sys.stderr)


def generate_pdf(order, client, tx, filepath):
    """Генерує PDF квитанцію у стилі клініки."""
    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()

    s_clinic = ParagraphStyle('clinic', fontSize=22, textColor=DARK,
                               fontName='Helvetica', alignment=TA_CENTER, spaceAfter=4)
    s_sub    = ParagraphStyle('sub', fontSize=9, textColor=MUTED,
                               fontName='Helvetica', alignment=TA_CENTER, spaceAfter=2, leading=14)
    s_title  = ParagraphStyle('title', fontSize=14, textColor=DARK,
                               fontName='Helvetica-Bold', alignment=TA_CENTER, spaceBefore=16, spaceAfter=4)
    s_label  = ParagraphStyle('label', fontSize=8, textColor=MUTED,
                               fontName='Helvetica', alignment=TA_LEFT, leading=14)
    s_value  = ParagraphStyle('value', fontSize=11, textColor=DARK,
                               fontName='Helvetica', alignment=TA_LEFT, leading=16)
    s_amount = ParagraphStyle('amount', fontSize=28, textColor=GOLD,
                               fontName='Helvetica-Bold', alignment=TA_CENTER, spaceBefore=8, spaceAfter=8)
    s_footer = ParagraphStyle('footer', fontSize=8, textColor=MUTED,
                               fontName='Helvetica', alignment=TA_CENTER, leading=13)

    paid_at = tx['paid_at'] if tx else datetime.now().strftime('%Y-%m-%d %H:%M')
    try:
        dt = datetime.strptime(paid_at, '%Y-%m-%d %H:%M:%S')
        paid_str = dt.strftime('%d.%m.%Y о %H:%M')
    except Exception:
        paid_str = paid_at

    story = []

    # ── Шапка ─────────────────────────────────────────────────
    story.append(Paragraph('Dr. Gómon Cosmetology', s_clinic))
    story.append(Paragraph('вул. Смілянська, 23, БЦ Галерея · Черкаси · gomonclinic.com', s_sub))
    story.append(HRFlowable(width='100%', thickness=0.5, color=GOLD, spaceAfter=12, spaceBefore=8))

    story.append(Paragraph('КВИТАНЦІЯ ПРО ОПЛАТУ', s_title))
    story.append(Spacer(1, 0.3*cm))

    # ── Сума ──────────────────────────────────────────────────
    amount_str = '{} грн'.format(int(order['amount']))
    story.append(Paragraph(amount_str, s_amount))
    story.append(HRFlowable(width='60%', thickness=0.3, color=GOLD,
                             hAlign='CENTER', spaceAfter=16, spaceBefore=4))

    # ── Таблиця деталей ───────────────────────────────────────
    def row(label, value):
        return [
            Paragraph(label, s_label),
            Paragraph(str(value) if value else '—', s_value),
        ]

    data = [
        row('ПОСЛУГА', order['description']),
        row('ДАТА ОПЛАТИ', paid_str),
        row('НОМЕР ЗАМОВЛЕННЯ', order['order_id']),
        row('СТАТУС', '✓ Оплачено'),
    ]

    if client:
        if client['name']:
            data.append(row('ІМ\'Я', client['name']))
        data.append(row('ТЕЛЕФОН', client['phone']))
        if client['email']:
            data.append(row('EMAIL', client['email']))

    table = Table(data, colWidths=[4.5*cm, 12*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0), (-1, -1), CREAM),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [CREAM, WARM]),
        ('TOPPADDING',  (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('LINEBELOW',   (0, 0), (-1, -2), 0.3, colors.HexColor('#e8d5b0')),
        ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(table)

    story.append(Spacer(1, 0.8*cm))
    story.append(HRFlowable(width='100%', thickness=0.5, color=GOLD, spaceAfter=10))
    story.append(Paragraph(
        'Дякуємо за довіру · Dr. Gómon Cosmetology · 073-310-31-10',
        s_footer
    ))

    doc.build(story)


def send_email(to_email, order, client, pdf_path):
    """Надсилає email з PDF квитанцією."""
    client_name = client['name'] if client and client['name'] else 'Клієнте'

    msg = MIMEMultipart()
    msg['From']    = SMTP_FROM
    msg['To']      = to_email
    msg['Subject'] = 'Квитанція про оплату — Dr. Gomon Cosmetology'

    body = '''\
<!DOCTYPE html>
<html lang="uk">
<head><meta charset="UTF-8"/></head>
<body style="font-family:'Georgia',serif;background:#faf8f5;margin:0;padding:0">
<div style="max-width:520px;margin:40px auto;background:#fff;border:1px solid rgba(201,169,110,.25)">
  <div style="height:3px;background:linear-gradient(90deg,#e8d5b0,#c9a96e,#e8d5b0)"></div>
  <div style="padding:36px 40px">
    <p style="font-size:10px;letter-spacing:.15em;text-transform:uppercase;color:#c9a96e;margin:0 0 16px">
      Dr. Gomon Cosmetology
    </p>
    <h1 style="font-size:28px;font-weight:300;color:#1a1410;margin:0 0 8px;line-height:1.2">
      {name}, дякуємо<br/><em style="color:#c9a96e">за довіру</em>
    </h1>
    <p style="font-size:14px;color:#9a8f87;font-weight:300;margin:16px 0 24px;line-height:1.7">
      Ваш платіж успішно зараховано.<br/>
      Квитанцію прикріплено до цього листа.
    </p>
    <div style="background:#f3ede4;padding:20px 24px;margin-bottom:24px">
      <table style="width:100%;border-collapse:collapse;font-size:13px">
        <tr>
          <td style="color:#9a8f87;padding:6px 0;border-bottom:1px solid rgba(201,169,110,.2)">Послуга</td>
          <td style="color:#1a1410;text-align:right;padding:6px 0;border-bottom:1px solid rgba(201,169,110,.2)">{desc}</td>
        </tr>
        <tr>
          <td style="color:#9a8f87;padding:6px 0">Сума</td>
          <td style="color:#c9a96e;font-size:18px;text-align:right;padding:6px 0">{amount} грн</td>
        </tr>
      </table>
    </div>
    <a href="https://gomonclinic.com" style="display:inline-block;padding:13px 28px;background:#1a1410;color:#faf8f5;text-decoration:none;font-size:11px;letter-spacing:.12em;text-transform:uppercase">
      Повернутись на сайт
    </a>
  </div>
  <div style="padding:16px 40px;border-top:1px solid rgba(201,169,110,.2)">
    <p style="font-size:11px;color:#9a8f87;margin:0">
      © 2026 Dr. Gómon Cosmetology · Черкаси · 073-310-31-10
    </p>
  </div>
</div>
</body>
</html>
'''.format(
        name=client_name,
        desc=order['description'],
        amount=int(order['amount']),
    )

    msg.attach(MIMEText(body, 'html', 'utf-8'))

    # Прикріплюємо PDF
    with open(pdf_path, 'rb') as f:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(f.read())
    encoders.encode_base64(part)
    filename = 'kvitanciya_{}.pdf'.format(order['order_id'][-8:])
    part.add_header('Content-Disposition', 'attachment', filename=filename)
    msg.attach(part)

    # Відправляємо
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print('Email error: {}'.format(e), file=sys.stderr)
        return False


def main():
    if len(sys.argv) < 2:
        print('Usage: receipt.py <order_id>', file=sys.stderr)
        sys.exit(1)

    order_id = sys.argv[1]
    order, client, tx = get_order_data(order_id)

    if not order:
        print('Order not found: {}'.format(order_id), file=sys.stderr)
        sys.exit(1)

    # Перевіряємо наявність email
    if not client or not client['email']:
        print('No email for {}'.format(order_id))
        sys.exit(0)

    # Перевіряємо чи вже надсилали
    if tx and tx['receipt_sent']:
        print('Receipt already sent for {}'.format(order_id))
        sys.exit(0)

    if not HAS_REPORTLAB:
        print('reportlab missing, cannot generate PDF', file=sys.stderr)
        sys.exit(1)

    # Генеруємо PDF у тимчасовий файл
    tmp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    tmp.close()

    try:
        generate_pdf(order, client, tx, tmp.name)
        ok = send_email(client['email'], order, client, tmp.name)
        if ok:
            mark_receipt_sent(order_id)
            print('Receipt sent to {} for {}'.format(client['email'], order_id))
        else:
            sys.exit(1)
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


if __name__ == '__main__':
    main()
