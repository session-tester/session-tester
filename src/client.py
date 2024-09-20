import queue
import threading
import time
from typing import Optional, Callable

import requests

from .session import Session, HttpTransaction


# Client 用于收发HTTP请求的
class Client(object):
    http_session_lock = threading.Lock()
    http_session_queue = queue.Queue()

    def __init__(self, session, url):
        self.session = session
        self.url = url
        self.http_session = self.get_http_session()

    # 这三个函数从session中拿信息做处理
    def run(self, wrap_data_func: Callable[[Session], None],
            session_update_func: Optional[Callable[[Session], None]] = None,
            stop_func: Optional[Callable[[Session], None]] = None):

        http_trans = HttpTransaction(url=self.url, method="POST", request=None, response=None, status_code=None,
                                     request_time=None)
        while True:

            try:
                http_trans.request = wrap_data_func(self.session)
                r = self.http_session.post(self.url, json=http_trans.request)
            except:
                time.sleep(1)
                # 重试一次
                r = self.http_session.post(self.url, json=http_trans.request)

            http_trans.status_code = r.status_code
            http_trans.response = r.text
            self.session.append_transaction(http_trans)

            if r.status_code != 200:
                raise RuntimeError(f"url: {self.url}, code: {r.status_code}), rsp: {r.text}")

            if session_update_func is not None:
                session_update_func(self.session)

            if stop_func is None or stop_func(self.session):
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
