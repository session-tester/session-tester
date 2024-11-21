import datetime
import json
import queue
import threading
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .logger import logger
from .request import StReq
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

            req = self.session_maintainer.wrap_req(self.session)
            if not isinstance(req, StReq):
                req = StReq(req)
            if req.url is None:
                req.url = self.session_maintainer.url
            if req.http_method is None:
                req.http_method = self.session_maintainer.http_method
            if req.headers is None:
                req.headers = {}
            if isinstance(req.req_data, (dict, list)):
                req.req_data = json.JSONEncoder().encode(req.req_data)
                req.headers["Content-Type"] = "application/json"

            def send_request():
                http_trans.request = req.req_data
                http_trans.request_time = datetime.datetime.now()
                if req.http_method == "GET":
                    r_ = self.http_session.get(req.url, params=req.req_data, headers=req.headers, timeout=req.timeout)
                elif req.http_method == "POST":
                    r_ = self.http_session.post(req.url, data=req.req_data, headers=req.headers, timeout=req.timeout)
                else:
                    raise RuntimeError(f"unsupported http method: {req.http_method}")
                end_time = datetime.datetime.now()  # 记录结束时间
                elapsed_time = (end_time - http_trans.request_time).total_seconds()  # 计算请求时间
                return r_, elapsed_time

            r = None
            cost = 0
            for _ in range(req.retry + 1):
                try:
                    r, cost = send_request()
                    if r.status_code == 200:
                        break
                except:
                    time.sleep(0.5)
                http_trans.retry_cnt += 1

            if r is None:
                self.session.append_transaction(http_trans)
                logger.error(f"break session, failed to send request: {req}")
                break
            http_trans.status_code = r.status_code
            http_trans.response = r.text
            http_trans.cost_time = cost
            self.session.append_transaction(http_trans)
            if r.status_code != 200:
                logger.error("break session, "
                             f"failed to send request: {req}, status_cod: {r.status_code}, rsp: {r.text}")
                break

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
                s = requests.Session()

                # 定义重试策略
                retry_strategy = Retry(
                    total=3,  # 总共重试次数
                    backoff_factor=1,  # 重试间隔时间的倍数
                    status_forcelist=[429, 500, 502, 503, 504],  # 需要重试的HTTP状态码
                    allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]  # 需要重试的方法
                )

                # 创建一个适配器并将其安装到会话中
                adapter = HTTPAdapter(max_retries=retry_strategy)
                s.mount("http://", adapter)
                s.mount("https://", adapter)
                return s

    @classmethod
    def release_session(cls, http_session):
        with cls.http_session_lock:
            cls.http_session_queue.put(http_session)
