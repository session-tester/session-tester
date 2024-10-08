import ast
import inspect
import sys
from typing import List

from .session import Session, HttpTransaction
from .testcase import SingleSessionCase, SingleRequestCase, AllSessionCase, TestCase

_session_checker_prefix = "chk"


def default_session_checker_prefix():
    return _session_checker_prefix


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
