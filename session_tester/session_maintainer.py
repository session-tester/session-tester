import queue

from .request import StReq
from .session import Session


class SessionMaintainerBase:
    url: str = None
    http_method: str = "POST"

    def __init__(self, url: str, http_method: str = "POST"):
        self.url = url
        self.http_method = http_method
        self.user_info_queue = queue.Queue()

    def load_user_info(self):
        if self.user_info_queue.empty():
            raise RuntimeError("user_info_queue is empty")

    @staticmethod
    def init_session(_: Session):
        raise NotImplementedError

    @staticmethod
    def wrap_req(_: Session) -> StReq:
        raise NotImplementedError

    @staticmethod
    def update_session(_: Session):
        raise NotImplementedError

    @staticmethod
    def should_stop_session(_: Session) -> bool:
        raise NotImplementedError
