from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.error

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
API_URL = 'https://api.anthropic.com/v1/messages'

class handler(BaseHTTPRequestHandler):

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        try:
            if not ANTHROPIC_API_KEY:
                self._error(500, 'ANTHROPIC_API_KEY not configured on server')
                return

            length = int(self.headers.get('Content-Length', 0))
            body   = json.loads(self.rfile.read(length))

            prompt = body.get('prompt', '')
            if not prompt:
                self._error(400, 'Missing prompt')
                return

            # Forward to Anthropic
            payload = json.dumps({
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': 8000,
                'messages': [{'role': 'user', 'content': prompt}]
            }).encode('utf-8')

            req = urllib.request.Request(
                API_URL,
                data=payload,
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': ANTHROPIC_API_KEY,
                    'anthropic-version': '2023-06-01',
                },
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                text = result.get('content', [{}])[0].get('text', '')

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._cors()
            self.end_headers()
            self.wfile.write(json.dumps({'text': text}).encode())

        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8')
            try:
                err = json.loads(body)
                msg = err.get('error', {}).get('message', body)
            except Exception:
                msg = body
            self._error(e.code, msg)

        except Exception as e:
            import traceback
            self._error(500, str(e) + '\n' + traceback.format_exc())

    def _error(self, code, msg):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self._cors()
        self.end_headers()
        self.wfile.write(json.dumps({'error': msg}).encode())

    def log_message(self, fmt, *args):
        pass
