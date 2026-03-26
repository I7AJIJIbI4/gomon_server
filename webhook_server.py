#!/usr/bin/env python3
import http.server
import socketserver
import urllib.parse
import json
from datetime import datetime

class WebhookHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # Парсинг URL та параметрів
        parsed_url = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        # Zadarma echo test
        if 'zd_echo' in query_params:
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(query_params['zd_echo'][0].encode())
            return
        
        # Звичайна відповідь
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        response = {
            "status": "working",
            "message": "Python webhook працює!",
            "time": datetime.now().isoformat()
        }
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))
    
    def do_POST(self):
        # Отримання POST даних
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        # Логування
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] POST webhook: {post_data.decode('utf-8', errors='ignore')}\n"
        
        with open('/home/gomoncli/zadarma/python_webhook.log', 'a') as f:
            f.write(log_entry)
        
        # Відповідь
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status": "ok"}')

PORT = 8080
with socketserver.TCPServer(("", PORT), WebhookHandler) as httpd:
    print(f"Python webhook сервер запущено на порту {PORT}")
    httpd.serve_forever()
