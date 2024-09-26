import json
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer


class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def _set_response(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)
        user_id = data.get('user_id')
        round_num = data.get('round')
        items = list(set([12, 3, 3, 5]))  # Replace with your logic to generate unrepeated int list
        # md5sum of user_id + round_num + items
        sig = hashlib.md5((user_id + str(round_num) + str(items)).encode('utf-8')).hexdigest()
        response_data = {
            "user_id": user_id,
            "next_round": round_num + 1,
            "items": items,
            "signature": sig,
        }
        self._set_response()
        self.wfile.write(json.dumps(response_data).encode('utf-8'))


def run(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting httpd on port {port}')
    httpd.serve_forever()


if __name__ == '__main__':
    run()
