from typing import List

from .session import Session
from .session_maintainer import SessionMaintainerBase
from .testcase import CheckResult
from .utils import stat_http_transaction_cost


# 为测试套件添加请求耗时统计
def ts_with_http_cost_stat(cls):
    @staticmethod
    def chk_http_cost_dist(ssl: List[Session]):
        """检查请求耗时分布:
        None
        """
        time_stat, report = stat_http_transaction_cost(ssl)
        return CheckResult(True, None, report)

    cls.chk_http_cost_dist = chk_http_cost_dist
    return cls


# 以下是SessionMaintainer的装饰器

def sm_n_rounds(n: int):
    """
    N 轮后停止
    :param n:
    :return:
    """

    def decorator(cls):
        class NewClass(cls):
            @staticmethod
            def should_stop_session(s: Session) -> bool:
                return len(s.transactions) >= n

        return NewClass

    return decorator


def sm_no_update(cls):
    """
    不更新会话状态
    :param cls:
    :return:
    """

    class NewClass(cls):
        @staticmethod
        def update_session(_: Session):
            pass

    return NewClass


def sm_no_init(cls):
    """
    默认初始化状态
    :param cls:
    :return:
    """

    class NewClass(cls):
        @staticmethod
        def init_session(_: Session):
            pass

    return NewClass


def sm_simple_n(n: int):
    """
    简单N轮停止
    :param n:
    :return:
    """

    def decorator(cls):
        @sm_no_init
        @sm_no_update
        @sm_n_rounds(n)
        class NewClass(cls):
            @staticmethod
            def should_stop_session(s: Session) -> bool:
                return len(s.transactions) >= n

        return NewClass

    return decorator


@sm_simple_n(1)
class SessionMaintainerSimple(SessionMaintainerBase):
    """
    单轮会话维持
    """
    pass