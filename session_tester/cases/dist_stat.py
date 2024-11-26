from typing import List, Dict

from session_tester import AllSessionCase, Session, CheckResult, utils


class HttpTransactionDistStatAllSessionCase(AllSessionCase):
    def __init__(self, name: str = None, expectation: str = None, tag_get_func=None):
        super().__init__(name, expectation)
        self.tag_get_func = tag_get_func

    def check(self, ssl: List[Session]) -> CheckResult:
        output = utils.transaction_elem_dist_stat(ssl, self.tag_get_func)
        return CheckResult(True, "", output)


class HttpTransactionDistStatCheckAllSessionCase(AllSessionCase):
    def __init__(self, name: str = None, expectation: str = None, tag_get_func=None,
                 dist_expectation: Dict = None):
        super().__init__(name, expectation)
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
