import uuid
from typing import List

from demo.demo_svr import calc_sig
from session_tester import Session, UserInfo, Tester, TestSuite, CheckResult, HttpTransaction, SessionMaintainerBase, \
    ts_with_http_cost_stat


class SessionMaintainer(SessionMaintainerBase):
    def __init__(self):
        super().__init__("http://localhost:8000", http_method="POST")

    def load_user_info(self):
        for i in range(10):
            self.user_info_queue.put(UserInfo(userid=uuid.uuid4().hex, extra={"index": i}))

    @staticmethod
    def init_session(s: Session):
        s.ext_state.update({"items": [], "round": 0})

    @staticmethod
    def wrap_req(s: Session):
        ui = s.user_info
        items_owned = s.ext_state.get("items", [])
        round_ = s.ext_state.get("round", 0)
        return {"user_id": ui.userid, "round": round_, "items_owned": items_owned}

    @staticmethod
    def should_stop_session(s: Session) -> bool:
        return len(s.transactions) >= 20

    @staticmethod
    def update_session(s: Session):
        o = s.transactions[-1].rsp_json()
        s.ext_state["items"] += o["items"]
        s.ext_state["round"] = o["next_round"]


@ts_with_http_cost_stat
class T(TestSuite):
    """测试模块"""

    @staticmethod
    def chk_rsp_sig(s: HttpTransaction) -> CheckResult:
        """单请求-签名校验:
        1. 接口返回sig字段
        2. sig字段与user_id, round, items计算结果一致
        """
        req = s.req_json()
        rsp = s.rsp_json()
        sig = calc_sig(rsp.get("user_id", ""), req.get("round", 0), rsp.get("items", []))
        if sig == rsp.get("signature"):
            return CheckResult(True, "sig check pass")
        return CheckResult(False, f"sig check failed, {s.response}")

    @staticmethod
    def chk_no_repeat_item(s: HttpTransaction) -> CheckResult:
        """单请求-返回道具重复性校验:
        1. 返回结果中items字段不重复
        """
        items = s.rsp_json().get("items", [])
        if len(set(items)) == len(items):
            return CheckResult(True)
        return CheckResult(False, f"items repeat, {s.response}")

    @staticmethod
    def chk_no_repeat_item_in_all_sessions(s: Session) -> CheckResult:
        """
        单用户-返回道具重复性校验:
        1. 所有请求返回结果中items字段不重复
        """
        item_set = set()
        for t in s.transactions:
            items = t.rsp_json().get("items", [])
            for item in items:
                if item in item_set:
                    return CheckResult(False, f"item[{item}] repeat, {t}")
                item_set.add(item)
        return CheckResult(True)

    @staticmethod
    def chk_items_dist_in_all_sessions(ss: List[Session]) -> CheckResult:
        """
        返回道具分布校验:
        1. 所有请求返回结果中items字段分布均匀
        """
        item_dist = {}
        for s in ss:
            for t in s.transactions:
                items = t.rsp_json().get("items", [])
                for item in items:
                    item_dist[item] = item_dist.get(item, 0) + 1

        dist_detail = [{"item": k, "count": v} for k, v in sorted(item_dist.items())]

        return CheckResult(True, "", dist_detail)


def main():
    # 1. 创建测试对象
    t = Tester(
        name=f"release_12345",
        test_suites=[T(session_maintainer=SessionMaintainer()),
                     T(session_maintainer=SessionMaintainer(), name="test2")],
    )

    # 2. 运行测试用例产生报告
    t.run(
        mode=Tester.RUN_MODE_NEW,
    )


if __name__ == "__main__":
    main()
