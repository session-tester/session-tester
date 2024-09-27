from .session import Session


class SessionMaintainerBase(object):
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
