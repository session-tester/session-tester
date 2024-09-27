import hashlib
import json
import random
from http.server import BaseHTTPRequestHandler, HTTPServer


def calc_sig(user_id, round_num, items):
    return hashlib.md5((user_id + str(round_num) + ",".join([str(x) for x in items])).encode('utf-8')).hexdigest()


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
        items_owned = data.get('items_owned', [])
        candidate_items = set(list(range(100))) - set(items_owned)
        # items = random.choices(list(candidate_items), k=5)
        items = random.sample(list(candidate_items), k=5)
        sig = calc_sig(user_id, round_num, items)
        response_data = {
            "user_id": user_id,
            "next_round": round_num + 1,
            "items": list(items),
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
