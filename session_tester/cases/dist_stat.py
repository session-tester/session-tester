from typing import List, Dict

from session_tester import AllSessionCase, Session, CheckResult, utils


class HttpTransactionDistStatAllSessionCase(AllSessionCase):
    """ Tag分布，不带校验 """

    def __init__(self, name: str = None, expectation: str = None, tag_get_func=None, filter_func=None):
        """
        :param name: 测试名称
        :param expectation: 预期结果
        :param tag_get_func: 从Session中获取标签的函数
        :param filter_func: 过滤函数，如果filter_func非空，则只有filter_func(s:Session)返回True的元素才会被统计
        """
        super().__init__(name, expectation)
        self.tag_get_func = tag_get_func
        self.filter_func = filter_func

    def check(self, ssl: List[Session]) -> CheckResult:
        if self.filter_func is not None:
            ssl = list(filter(self.filter_func, ssl))
        output = utils.transaction_elem_dist_stat(ssl, self.tag_get_func)
        return CheckResult(True, "", output)


class HttpTransactionDistStatCheckAllSessionCase(AllSessionCase):
    """ Tag分布，带校验 """

    def __init__(self, name: str = None, expectation: str = None, tag_get_func=None, filter_func=None,
                 dist_expectation: Dict = None):
        super().__init__(name, expectation, filter_func)
        self.tag_get_func = tag_get_func
        self.dist_expectation = dist_expectation

    def check(self, ssl: List[Session]) -> CheckResult:
        output = utils.transaction_elem_dist_stat(ssl, self.tag_get_func, format_ratio=False)
        err_result = None
        for i, line in enumerate(output):
            if line["group"] not in self.dist_expectation and err_result is None:
                err_result = CheckResult(False, f"key {line['group']} not in output")

            if abs(line["ratio"] - self.dist_expectation[line["group"]]) > 1e-3 and err_result is None:
                err_result = CheckResult(False,
                                         f"key {line['group']} expect {self.dist_expectation[line['group']]}, got {line['ratio']}")

            output[i]["expectition"] = self.dist_expectation[line["group"]]

        if err_result is None:
            return CheckResult(True, "", output)
        else:
            err_result.report_lines = output
            return err_result
