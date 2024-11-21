import ast
import inspect
import sys
from typing import List, Callable

import numpy as np

from .session import Session, HttpTransaction
from .testcase import SingleSessionCase, SingleRequestCase, AllSessionCase, TestCase

_session_checker_prefix = "chk"


def default_session_checker_prefix():
    return _session_checker_prefix


def _dist_dict_to_list(dist: dict, format_ratio=True):
    kv_list = list(dist.items())
    kv_list = sorted(kv_list, key=lambda x: x[1], reverse=True)
    output = []
    total = 0
    for _, v in kv_list:
        total += v

    for k, v in kv_list:
        ratio = v / total
        if format_ratio:
            output.append({"group": k, "count": v, "ratio": f"{ratio * 100:.2f}%"})
        else:
            output.append({"group": k, "count": v, "ratio": ratio})
    return output


def transaction_elem_dist_stat(session_list: List[Session], custom_flag_func: Callable, format_ratio=True):
    """HTTP transaction级别元素分布统计
    """
    dist = {}
    for ss in session_list:
        for s in ss.transactions:
            rsp = s.rsp_json()
            flag = custom_flag_func(rsp)
            dist[flag] = dist.get(flag, 0) + 1
    return _dist_dict_to_list(dist, format_ratio)


def session_elem_dist_stat(session_list: List[Session], custom_flag_func: Callable, format_ratio=True):
    """session级别元素分布统计
    """
    dist = {}
    for s in session_list:
        flag = custom_flag_func(s)
        dist[flag] = dist.get(flag, 0) + 1
    return _dist_dict_to_list(dist, format_ratio)


def stat_http_transaction_cost(session_list: List[Session]):
    """统计请求耗时，按照平均值，中位值，P90，P99进行统计"""
    request_times = []
    for s in session_list:
        for t in s.transactions:
            if t.cost_time is not None:
                request_times.append(t.cost_time)

    # 计算平均值
    mean_time = np.mean(request_times)

    # 计算中位值
    median_time = np.median(request_times)

    # 计算 P90
    p90_time = np.percentile(request_times, 90)

    # 计算 P99
    p99_time = np.percentile(request_times, 99)

    report = [
        {"耗时类型": "平均值", "耗时": f"{int(mean_time * 100)}ms"},
        {"耗时类型": "P50", "耗时": f"{int(mean_time * 100)}ms"},
        {"耗时类型": "P90", "耗时": f"{int(p90_time * 100)}ms"},
        {"耗时类型": "P99", "耗时": f"{int(p99_time * 100)}ms"},
    ]

    return (mean_time, median_time, p90_time, p99_time), report


def func_to_case(name: str, func) -> TestCase:
    signature = inspect.signature(func)
    params = list(signature.parameters.values())
    if params:
        if params[0].annotation == HttpTransaction:
            # 单请求
            case = SingleRequestCase(rsp_checker=func)
        elif params[0].annotation == Session:
            # 单会话
            case = SingleSessionCase(session_checker=func)
        elif params[0].annotation == List[Session]:
            # 所有会话
            case = AllSessionCase(session_list_checker=func)
        else:
            raise ValueError(
                f"First parameter of function {name} should be of type HttpTransaction or Session")

        if not case.name:
            raise ValueError(f"Function {name} should have a name")
        if not case.expectation:
            raise ValueError(f"Function {name} should have an expectation")
        return case

    raise ValueError(f"Function {name} should have at least one parameter")


def auto_gen_cases_from_chk_func(checker_prefix=_session_checker_prefix, module_name="__main__"):
    module = sys.modules[module_name]
    source = inspect.getsource(module)
    tree = ast.parse(source)

    check_cases = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith(checker_prefix):
            func = getattr(module, node.name)
            case = func_to_case(node.name, func)
            check_cases.append(case)

    return check_cases
