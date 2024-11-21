import ast
import datetime
import inspect
import queue
import threading
import time
from dataclasses import dataclass
from typing import List

from .client import Client
from .logger import logger
from .session import Session
from .session_maintainer import SessionMaintainerBase
from .testcase import TestCase, SingleRequestCase, Report, SingleSessionCase, AllSessionCase
from .utils import func_to_case, default_session_checker_prefix


class TestSuite:
    def __init__(self, name=None, session_maintainer: SessionMaintainerBase = None, spec_cases=None):
        self.name = name
        if name is None:
            self.name = self.__doc__

        if not self.name:
            raise RuntimeError("test suite name is required")
        self.name = self.name.strip()

        self.session_maintainer: SessionMaintainerBase = session_maintainer
        self.report_list: List[Report] = []
        self.parent_name = None
        self._check_cases = self.merge_cases(spec_cases)

    def merge_cases(self, spec_cases):
        if spec_cases is None:
            spec_cases = []

        ret = []
        inserted_cases = set()
        for case in spec_cases:
            if case.name in inserted_cases:
                raise ValueError(f"Duplicate case name: {case.name}")
            inserted_cases.add(case.name)
            ret.append(case)

        for case in self.auto_gen_test_cases():
            if case.name in inserted_cases:
                raise ValueError(f"Duplicate case name: {case.name}, please change the name in chk func")
            inserted_cases.add(case.name)
            ret.append(case)
        return ret

    def check_cases(self):
        return self._check_cases

    @classmethod
    def auto_gen_test_cases(cls, inserted_check_func=None) -> List[TestCase]:
        if inserted_check_func is None:
            inserted_check_func = set()
        methods = [func for func in dir(cls) if callable(getattr(cls, func))]
        check_cases = []

        source = inspect.getsource(cls)
        tree = ast.parse(source)
        if len(tree.body) != 1 or not isinstance(tree.body[0], ast.ClassDef):
            raise ValueError("Only one class is allowed in the suite")
        tree = tree.body[0]

        # 有序的检查
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith(default_session_checker_prefix()):
                func = getattr(cls, node.name)
                if isinstance(func, ast.FunctionDef):
                    func = getattr(cls, func.name)
                func_name = node.name
                if isinstance(cls.__dict__.get(func.__name__), staticmethod) and func_name not in inserted_check_func:
                    inserted_check_func.add(func_name)
                    case = func_to_case(func_name, func)
                    check_cases.append(case)

        # 处理修饰器的检查
        for method_name in methods:
            method = getattr(cls, method_name)
            # print(f"Method: {method}")
            if inspect.isfunction(method) or inspect.ismethod(method):
                if isinstance(cls.__dict__.get(method_name), staticmethod) and method_name.startswith(
                        default_session_checker_prefix()):
                    if method_name in inserted_check_func:
                        continue

                    inserted_check_func.add(method_name)
                    func = cls.__dict__.get(method_name)
                    case = func_to_case(method_name, func)
                    check_cases.append(case)
                    # sig = inspect.signature(method)
        # 处理父类中的函数
        for base in inspect.getmro(cls):
            if base == cls or not isinstance(base, TestSuite):
                continue
            try:
                check_cases += base.auto_gen_test_cases(inserted_check_func)
            except AttributeError:
                pass

        return check_cases

    def do_send(self, thread_cnt=50, no_dump=False):
        stopped = threading.Event()
        stopped.clear()
        lock = threading.Lock()

        logger.info(f"{self.name} 开始发送")

        @dataclass
        class SendStat:
            total_session_cnt: int = 0
            total_session_cost: int = 0
            total_send_cnt: int = 0
            total_send_err_cnt: int = 0
            total_retry_cnt: int = 0
            total_send_cost: int = 0
            start_time: datetime.datetime = 0
            end_time: datetime.datetime = 0

            def report(self):
                logger.info("发送请求统计：")
                logger.info(f"    {self.total_session_cnt} 个会话")
                logger.info(
                    f"    {self.total_send_cnt} 个请求(失败重试 {self.total_retry_cnt}, 最终失败 {self.total_send_err_cnt})")
                logger.info(f"    总耗时: {(self.end_time - self.start_time).total_seconds()} 秒")
                logger.info(f"    请求平均耗时: {self.total_send_cost * 1000 / self.total_send_cnt} 毫秒")
                logger.info(f"    会话平均耗时: {self.total_session_cost * 1000 / self.total_session_cnt} 毫秒")
                logger.info(f"    QPS: {self.total_send_cnt / (self.end_time - self.start_time).total_seconds()}")

        send_stat = SendStat()

        class SendWorker(threading.Thread):
            def __init__(self, label, session_maintainer_cls: SessionMaintainerBase):
                threading.Thread.__init__(self)
                self.label = label
                self.user_info_queue = session_maintainer_cls.user_info_queue
                self.session_maintainer_cls = session_maintainer_cls

            def run(self):
                while True:
                    try:
                        user_info = self.user_info_queue.get_nowait()
                        session = Session(label=self.label)
                        session.create(user_info=user_info, transactions=[], no_dump=no_dump)
                        client = Client(session=session, session_maintainer=self.session_maintainer_cls)

                        start_time = datetime.datetime.now()
                        client.run()
                        elapsed_time = (datetime.datetime.now() - start_time).total_seconds()  # 计算请求时间
                        session.dump()
                        with lock:
                            nonlocal send_stat
                            send_stat.total_session_cnt += 1
                            send_stat.total_send_cnt += len(session.transactions)
                            send_stat.total_send_err_cnt += len(
                                [x for x in session.transactions if not x.finished_without_error()])
                            send_stat.total_retry_cnt += sum([x.retry_cnt for x in session.transactions])
                            send_stat.total_send_cost += sum([x.cost_time for x in session.transactions])
                            send_stat.total_session_cost += elapsed_time
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

        send_stat.start_time = datetime.datetime.now()
        for t in t_list:
            t.start()

        for t in t_list:
            t.join()
        send_stat.end_time = datetime.datetime.now()
        return send_stat

    def clear_sessions(self):
        Session.clear_sessions(self.name)

    def check(self):
        # 加载会话结果
        session_list = Session.load_sessions(self.name)
        self.report_list = []
        for case in self.check_cases():
            if isinstance(case, SingleRequestCase):
                report = Report(case.name, case.expectation, "SingleRequestCase")
                transactions = [transaction for session in session_list for transaction in session.transactions]
                report.total_case_count = len(transactions)
                report.finished_with_err_count = len([x for x in transactions if not x.finished_without_error()])
                report.case_results = case.batch_check([x for x in transactions if x.finished_without_error()])

            elif isinstance(case, SingleSessionCase):
                report = Report(case.name, case.expectation, "SingleSessionCase")
                report.finished_with_err_count = len([x for x in session_list if not x.finished_without_error()])
                report.total_case_count = len(session_list)
                report.case_results = case.batch_check([x for x in session_list if x.finished_without_error()])
            elif isinstance(case, AllSessionCase):
                report = Report(case.name, case.expectation, "AllSessionCase")
                session_list = [x for x in session_list if x.finished_without_error()]
                if not session_list:
                    report.uncover_case_count = 1
                else:
                    report.case_results = case.batch_check([session_list])
            else:
                raise RuntimeError("unknown case type")

            for result in report.case_results:
                if result is None:
                    report.uncover_case_count += 1
                elif result.result:
                    report.passed_case_count += 1
                else:
                    report.not_passed_case_count += 1

            self.report_list.append(report)
            logger.info(f"{self.name}-{case.name} 检查完成")

        return self.report_list
