import traceback
from typing import Tuple, Callable, List

from .session import HttpTransaction, Session


class TestCase(object):
    def __init__(self, name: str, expectation: str):
        self.name = name
        self.expectation = expectation


def overwrite_name_and_expectation(name, expectation, doc):
    if doc is None:
        name_, expectation_ = None, None
    else:
        if doc.find(":") == -1:
            # 避免用户使用中文冒号
            doc = doc.replace("：", ":")
        fields = doc.split(":", 1)
        name_ = fields[0].strip()
        if len(fields) > 1:
            expectation_ = '\n'.join([x.lstrip(" ") for x in fields[1].strip().split("\n")])
        else:
            expectation_ = None
    if name is None:
        name = name_
    if expectation is None:
        expectation = expectation_
    if not name:
        raise RuntimeError("name is required")

    return name, expectation


# 单个请求检查
class SingleRequestCase(TestCase):
    def __init__(self, name: str = None, expectation: str = None,
                 rsp_checker: Callable[[HttpTransaction], Tuple[bool, str]] = None):
        if rsp_checker is None:
            raise RuntimeError("rsp_checker is required")
        name, expectation = overwrite_name_and_expectation(name, expectation, rsp_checker.__doc__)
        super().__init__(name, expectation)
        self.rsp_checker = rsp_checker


# 单个会话检查
class SingleSessionCase(TestCase):
    def __init__(self, name: str = None, expectation: str = None,
                 session_checker: Callable[[Session], Tuple[bool, str]] = None):
        if session_checker is None:
            raise RuntimeError("session_checker is required")
        name, expectation = overwrite_name_and_expectation(name, expectation, session_checker.__doc__)
        super().__init__(name, expectation)
        self.session_checker = session_checker


# 全体会话检查
class AllSessionCase(TestCase):
    def __init__(self, name: str = None, expectation: str = None,
                 session_list_checker: Callable[[List[Session]], Tuple[bool, str]] = None):
        if session_list_checker is None:
            raise RuntimeError("session_list_checker is required")
        name, expectation = overwrite_name_and_expectation(name, expectation, session_list_checker.__doc__)
        super().__init__(name, expectation)
        self.session_list_checker = session_list_checker


class Report(TestCase):
    def __init__(self, name: str, expectation: str, case_type: str):
        super().__init__(name, expectation)
        self.case_type = case_type
        self.result = None
        self.bad_case = None
        self.report_content = []
        self.case_results = []

    def summary(self):
        if not self.case_results:
            self.result = "未覆盖"
            return
        self.result = "通过"
        for result, report_content in self.case_results:
            if not result:
                self.result = "未通过"
                self.bad_case = report_content
                return

    def summary_dict(self):
        self.summary()
        return {
            "name": self.name,
            "expectation": self.expectation,
            "result": self.result,
            "bad_case": self.bad_case,
            "report_content": self.report_content
        }

    def __str__(self):
        self.summary()
        return f"{self.name} {self.expectation} {self.case_type} {self.result} {self.report_content}"


class BatchTester(object):
    def __init__(self, title, session_list: List[Session] = None):
        self.title = title
        self.session_list = session_list
        self.test_cases = []
        self.report_list = []

    def append_case(self, case: TestCase):
        self.test_cases.append(case)

    def check(self, extra_cases=[]):
        self.report_list = []

        def run_and_append(report_, f, target):
            try:
                result, report_content = f(target)
            except Exception as e:
                # 获取异常堆栈信息
                stack_trace = traceback.format_exc()
                result, report_content = False, f"checking exception: {e}\nStack trace:\n{stack_trace}"
            if result is not None:
                report_.case_results.append((result, report_content))

        for case in self.test_cases + extra_cases:
            if isinstance(case, SingleRequestCase):
                report = Report(case.name, case.expectation, "SingleRequestCase")
                for session in self.session_list:
                    for transaction in session.transactions:
                        run_and_append(report, case.rsp_checker, transaction)
            elif isinstance(case, SingleSessionCase):
                report = Report(case.name, case.expectation, "SingleSessionCase")
                for session in self.session_list:
                    run_and_append(report, case.session_checker, session)
            elif isinstance(case, AllSessionCase):
                report = Report(case.name, case.expectation, "AllSessionCase")
                run_and_append(report, case.session_list_checker, self.session_list)
            else:
                raise RuntimeError("unknown case type")

            self.report_list.append(report)

    def report(self):
        # TODO
        return self.report_list
