import json
import queue
import threading
import time

import requests

from .session import HttpTransaction
from .session_maintainer import SessionMaintainerBase


# Client 用于收发HTTP请求的
class Client:
    http_session_lock = threading.Lock()
    http_session_queue = queue.Queue()

    def __init__(self, session, session_maintainer: SessionMaintainerBase):
        self.session = session
        self.session_maintainer = session_maintainer
        self.http_session = self.get_http_session()

    # 这四个函数从session中拿信息做处理
    def run(self):
        if self.session_maintainer.init_session is not None:
            self.session_maintainer.init_session(self.session)

        while True:
            http_trans = HttpTransaction(
                url=self.session_maintainer.url,
                method=self.session_maintainer.http_method,
                request=None, response=None, status_code=None,
                request_time=None)

            def send_request():
                req = self.session_maintainer.wrap_req(self.session)
                if isinstance(req, dict) or isinstance(http_trans.request, list):
                    r = self.http_session.post(self.session_maintainer.url, json=req)
                    http_trans.request = json.JSONEncoder().encode(req)
                else:
                    r = self.http_session.post(self.session_maintainer.url, req)
                    http_trans.request = req

                return r

            try:
                r = send_request()
            except:
                time.sleep(1)
                # 重试一次
                r = send_request()

            http_trans.status_code = r.status_code
            http_trans.response = r.text
            self.session.append_transaction(http_trans)

            if r.status_code != 200:
                raise RuntimeError(f"url: {self.session_maintainer.url}, code: {r.status_code}), rsp: {r.text}")

            if self.session_maintainer.update_session is not None:
                self.session_maintainer.update_session(self.session)

            if self.session_maintainer.should_stop_session is None or \
                    self.session_maintainer.should_stop_session(self.session):
                break

    def __del__(self):
        self.release_session(self.http_session)

    @classmethod
    def get_http_session(cls):
        with cls.http_session_lock:
            try:
                return cls.http_session_queue.get_nowait()
            except:
                return requests.Session()

    @classmethod
    def release_session(cls, http_session):
        with cls.http_session_lock:
            cls.http_session_queue.put(http_session)
