from session_tester import SingleSessionCase, Session, CheckResult


class SameRspSessionCase(SingleSessionCase):
    def __init__(self, name: str = None, expectation: str = None, compare_func=None, parse_json=False):
        super().__init__(name, expectation)
        self.compare_func = compare_func
        self.parse_json = parse_json

    def check(self, s: Session) -> CheckResult:
        if len(s.transactions) == 0:
            return CheckResult(False, "No transactions in session")
        if len(s.transactions) == 1:
            return CheckResult(True, "Only one transaction in session")

        if self.parse_json:
            rsp_base = s.transactions[0].rsp_json()
        else:
            rsp_base = s.transactions[0].response

        for t in s.transactions[1:]:
            to_check = t.rsp_json() if self.parse_json else t.response
            if self.compare_func is not None:
                if not self.compare_func(rsp_base, to_check):
                    return CheckResult(False, "Different responses in session")
            elif to_check != rsp_base:
                return CheckResult(False, "Different responses in session")

        return CheckResult(True)


class SameRspJsonSessionCase(SameRspSessionCase):
    def __init__(self, name: str = None, expectation: str = None, compare_func=None):
        super().__init__(name, expectation, compare_func, True)
