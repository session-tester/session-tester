import traceback
from dataclasses import dataclass
from typing import Callable, List, Optional, Any

from .session import HttpTransaction, Session


class TestCase:
    def __init__(self, name: str, expectation: str):
        self.name = name
        self.expectation = expectation

    def check(self, _: Any):
        raise NotImplementedError

    def batch_check(self, arg_list: List[Any]):
        ret = []
        for arg in arg_list:
            try:
                check_result = self.check(arg)
            except Exception as e:
                # 获取异常堆栈信息
                stack_trace = traceback.format_exc()
                check_result = CheckResult(False, f"checking exception: {e}\nStack trace:\n{stack_trace}", None)

            ret.append(check_result)
        return ret


@dataclass
class CheckResult:
    result: bool
    exception: Optional[str] = None
    report_lines: Optional[List[Any]] = None


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
                 rsp_checker: Callable[[HttpTransaction], CheckResult] = None):
        if rsp_checker is None:
            raise RuntimeError("rsp_checker is required")
        name, expectation = overwrite_name_and_expectation(name, expectation, rsp_checker.__doc__)
        super().__init__(name, expectation)
        self.rsp_checker = rsp_checker

    def check(self, transaction: HttpTransaction):
        return self.rsp_checker(transaction)


# 单个会话检查
class SingleSessionCase(TestCase):
    def __init__(self, name: str = None, expectation: str = None,
                 session_checker: Callable[[Session], CheckResult] = None):
        if session_checker is None:
            raise RuntimeError("session_checker is required")
        name, expectation = overwrite_name_and_expectation(name, expectation, session_checker.__doc__)
        super().__init__(name, expectation)
        self.session_checker = session_checker

    def check(self, session: Session):
        return self.session_checker(session)


# 全体会话检查
class AllSessionCase(TestCase):
    def __init__(self, name: str = None, expectation: str = None,
                 session_list_checker: Callable[[List[Session]], CheckResult] = None):
        if session_list_checker is None:
            raise RuntimeError("session_list_checker is required")
        name, expectation = overwrite_name_and_expectation(name, expectation, session_list_checker.__doc__)
        super().__init__(name, expectation)
        self.session_list_checker = session_list_checker

    def check(self, session_list: List[Session]):
        return self.session_list_checker(session_list)


class Report:
    def __init__(self, name: str, expectation: str, case_type: str):
        self.name = name
        self.expectation = expectation
        self.case_type = case_type
        self.result = None
        self.bad_case = None
        self.ext_report = []
        self.case_results: List[CheckResult] = []

    def summary(self):
        if not self.case_results:
            self.result = "未覆盖"
            return
        self.result = "通过"

        self.ext_report = []
        for case_result in self.case_results:
            if case_result.report_lines is not None:
                self.ext_report += case_result.report_lines

        for case_result in self.case_results:
            if not case_result.result:
                self.result = "未通过"
                self.bad_case = case_result.exception
                return

    def summary_dict(self):
        self.summary()
        return {
            "name": self.name,
            "expectation": self.expectation,
            "result": self.result,
            "bad_case": self.bad_case,
            "ext_report": self.ext_report
        }

    def __str__(self):
        self.summary()
        return f"{self.name} {self.expectation} {self.case_type} {self.result} {self.ext_report}"
