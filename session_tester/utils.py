import ast
import inspect
import sys
from typing import List, Callable

import numpy as np
import pandas as pd

from .session import Session, HttpTransaction
from .testcase import SingleSessionCase, SingleRequestCase, AllSessionCase, TestCase
from .user_info import UserInfo

_session_checker_prefix = "chk"


def default_session_checker_prefix():
    return _session_checker_prefix


def _dist_dict_to_list(dist: dict):
    kv_list = list(dist.items())
    kv_list = sorted(kv_list, key=lambda x: x[1], reverse=True)
    output = []
    total = 0
    for _, v in kv_list:
        total += v

    for k, v in kv_list:
        ratio = v / total
        output.append((k, v, ratio))

    output = sorted(output, key=lambda x: (-x[1], x[2]))
    return output


def _dist_list_to_format_dict(dist_list: List, format_ratio=True):
    ret = []
    for k, v, ratio in dist_list:
        if format_ratio:
            ret.append({"group": k, "count": v, "ratio": f"{ratio * 100:.2f}%"})
        else:
            ret.append({"group": k, "count": v, "ratio": ratio})
    return ret


def transaction_elem_dist_stat_(session_list: List[Session], custom_flag_func: Callable):
    """HTTP transaction级别元素分布统计
    """
    dist = {}
    for ss in session_list:
        for s in ss.transactions:
            rsp = s.rsp_json()
            flag = custom_flag_func(rsp)
            if isinstance(flag, list):
                for f in flag:
                    dist[f] = dist.get(f, 0) + 1
            else:
                dist[flag] = dist.get(flag, 0) + 1
    return _dist_dict_to_list(dist)


def transaction_elem_dist_stat(session_list: List[Session], custom_flag_func: Callable, format_ratio=True):
    """HTTP transaction级别元素分布统计
    """
    dist_list = transaction_elem_dist_stat_(session_list, custom_flag_func)
    return _dist_list_to_format_dict(dist_list, format_ratio)


def session_elem_dist_stat_(session_list: List[Session], custom_flag_func: Callable):
    """session级别元素分布统计
    """
    dist = {}
    for s in session_list:
        flag = custom_flag_func(s)
        if isinstance(flag, list):
            for f in flag:
                dist[f] = dist.get(f, 0) + 1
        else:
            dist[flag] = dist.get(flag, 0) + 1

    return _dist_dict_to_list(dist)


def session_elem_dist_stat(session_list: List[Session], custom_flag_func: Callable, format_ratio=True):
    """session级别元素分布统计
    """
    dist_list = session_elem_dist_stat_(session_list, custom_flag_func)
    return _dist_list_to_format_dict(dist_list, format_ratio)


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
        {"耗时类型": "平均值", "耗时": f"{int(mean_time * 1000)}ms"},
        {"耗时类型": "P50", "耗时": f"{int(mean_time * 1000)}ms"},
        {"耗时类型": "P90", "耗时": f"{int(p90_time * 1000)}ms"},
        {"耗时类型": "P99", "耗时": f"{int(p99_time * 1000)}ms"},
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


def _replace_map_key(o: dict, k1, k2):
    if k1 not in o or k2 in o:
        return
    o[k2] = o[k1]
    del o[k1]


def load_user_info_from_json(content) -> List[UserInfo]:
    user_info_list = []
    for user_info_json in content:
        user_info = UserInfo()
        for k1, k2 in [("platid", "plat"), ("areaid", "area"), ("open_id", "userid"), ("openid", "userid"),
                       ("roleid", "role_id"), ("user_id", "userid"), ("plat_id", "plat")]:
            _replace_map_key(user_info_json, k1, k2)
        user_info.parse(user_info_json)
        user_info_list.append(user_info)
    return user_info_list


def load_user_info_from_csv(file_path, headers=None, skip_header=False, sep=',') -> List[UserInfo]:
    if headers:
        df = pd.read_csv(file_path, sep=sep, names=headers, header=0 if skip_header else None)
    else:
        df = pd.read_csv(file_path, sep=sep)
    k = df.to_dict(orient='records')
    return load_user_info_from_json(k)
