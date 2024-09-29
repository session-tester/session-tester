import queue

from .session import Session


class SessionMaintainerBase(object):
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
    def wrap_data_func(s: Session):
        raise NotImplementedError

    @staticmethod
    def start_func(_: Session):
        raise NotImplementedError

    @staticmethod
    def session_update_func(_: Session):
        raise NotImplementedError

    @staticmethod
    def stop_func(_: Session) -> bool:
        raise NotImplementedError
