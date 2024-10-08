import ast
import inspect
import queue
import threading
import time
from typing import List

from . import Session, Client
from .session_maintainer import SessionMaintainerBase
from .testcase import TestCase, SingleRequestCase, Report, SingleSessionCase, AllSessionCase
from .utils import func_to_case

_session_checker_prefix = "chk"


class TestSuite:
    def __init__(self, name=None, session_maintainer: SessionMaintainerBase = None, session_cnt_to_check=0):
        self.name = name
        if name is None:
            self.name = self.__doc__

        if not self.name:
            raise RuntimeError("test suite name is required")
        self.name = self.name.strip()

        self.session_maintainer: SessionMaintainerBase = session_maintainer
        self.session_cnt_to_check = session_cnt_to_check
        self.report_list: List[Report] = []

    @classmethod
    def auto_gen_test_cases(cls) -> List[TestCase]:
        source = inspect.getsource(cls)
        tree = ast.parse(source)
        if len(tree.body) != 1 or not isinstance(tree.body[0], ast.ClassDef):
            raise ValueError("Only one class is allowed in the suite")
        tree = tree.body[0]

        check_cases = []

        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith(_session_checker_prefix):
                func = getattr(cls, node.name)
                if isinstance(func, ast.FunctionDef) and func.name.startswith(_session_checker_prefix):
                    func = getattr(cls, func.name)
                if isinstance(cls.__dict__.get(func.__name__), staticmethod):
                    case = func_to_case(node.name, func)
                    check_cases.append(case)

        return check_cases

    def do_send(self, thread_cnt=50):
        stopped = threading.Event()
        stopped.clear()
        user_cnt = 0
        lock = threading.Lock()

        class SendWorker(threading.Thread):
            def __init__(self, label, session_maintainer_cls: SessionMaintainerBase):
                threading.Thread.__init__(self)
                self.label = label
                self.user_info_queue = session_maintainer_cls.user_info_queue
                self.session_maintainer_cls = session_maintainer_cls

            def run(self):
                nonlocal user_cnt
                while True:
                    try:
                        user_info = self.user_info_queue.get_nowait()
                        session = Session(label=self.label)
                        session.create(user_info=user_info, transactions=[])
                        client = Client(session=session, session_maintainer=self.session_maintainer_cls)
                        client.run()
                        session.dump()
                        with lock:
                            user_cnt += 1
                    except queue.Empty:
                        if stopped.is_set():
                            return
                        time.sleep(0.1)

        class QueueLoader(threading.Thread):
            def __init__(self, session_maintainer_cls: SessionMaintainerBase):
                threading.Thread.__init__(self)
                self.user_info_queue = session_maintainer_cls.user_info_queue
                self.session_maintainer_cls = session_maintainer_cls

            def run(self):
                if not self.session_maintainer_cls.user_info_queue.empty():
                    stopped.set()
                    return

                self.session_maintainer_cls.load_user_info()
                stopped.set()

        t_list = [QueueLoader(self.session_maintainer)]

        q = self.session_maintainer.user_info_queue
        if not q.empty() and q.qsize() > 0:
            thread_cnt = min(thread_cnt, q.qsize())

        for _ in range(thread_cnt):
            t = SendWorker(self.name, self.session_maintainer)
            t_list.append(t)

        for t in t_list:
            t.start()

        for t in t_list:
            t.join()

        if self.session_cnt_to_check == 0:
            self.session_cnt_to_check = user_cnt

    def clear_sessions(self):
        Session.clear_sessions(self.name)

    def check(self):
        # 加载会话结果
        session_list = Session.load_sessions(self.name, n=self.session_cnt_to_check)
        if len(session_list) < self.session_cnt_to_check:
            raise ValueError(
                f"No enough sessions data found. expect[{self.session_cnt_to_check}], got[{len(session_list)}]")

        self.report_list = []
        for case in self.auto_gen_test_cases():
            if isinstance(case, SingleRequestCase):
                report = Report(case.name, case.expectation, "SingleRequestCase")
                report.case_results = case.batch_check(
                    [transaction for session in session_list for transaction in session.transactions])
            elif isinstance(case, SingleSessionCase):
                report = Report(case.name, case.expectation, "SingleSessionCase")
                report.case_results = case.batch_check(session_list)
            elif isinstance(case, AllSessionCase):
                report = Report(case.name, case.expectation, "AllSessionCase")
                report.case_results = case.batch_check([session_list])
            else:
                raise RuntimeError("unknown case type")

            self.report_list.append(report)

        return self.report_list
