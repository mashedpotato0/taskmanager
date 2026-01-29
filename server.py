import http.server
import socketserver
import json
import os

PORT = 8000
DATA_DIR = "./data"

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/load':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            data = {}
            config = []
            
            if os.path.exists(f"{DATA_DIR}/fg_data.json"):
                with open(f"{DATA_DIR}/fg_data.json", 'r') as f:
                    data = json.load(f)
            
            if os.path.exists(f"{DATA_DIR}/fg_config.json"):
                with open(f"{DATA_DIR}/fg_config.json", 'r') as f:
                    config = json.load(f)
            
            response = {"data": data, "config": config}
            self.wfile.write(json.dumps(response).encode())
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/api/save':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data)

            with open(f"{DATA_DIR}/fg_data.json", 'w') as f:
                json.dump(payload.get('data', {}), f, indent=4)
            
            with open(f"{DATA_DIR}/fg_config.json", 'w') as f:
                json.dump(payload.get('config', []), f, indent=4)

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status": "success"}')

print(f"Serving at http://localhost:{PORT}")
with socketserver.TCPServer(("", PORT), RequestHandler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
