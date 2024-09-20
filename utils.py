import ast
import inspect
import sys
from typing import List

from client import Session, SingleSessionCase, SingleRequestCase, AllSessionCase
from client.session import HttpTransaction


def stop_till_n_repeat(n):
    def session_stop_func(s: Session):
        return len(s.transactions) >= n

    return session_stop_func


def auto_gen_cases_from_ck_func():
    module = sys.modules["__main__"]
    source = inspect.getsource(module)
    tree = ast.parse(source)

    check_cases = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith('ck'):
            func = getattr(module, node.name)
            signature = inspect.signature(func)
            params = list(signature.parameters.values())
            if params:
                if params[0].annotation == HttpTransaction:
                    # 单请求
                    check_cases.append(SingleRequestCase(rsp_checker=func))
                elif params[0].annotation == Session:
                    # 单会话
                    check_cases.append(SingleSessionCase(session_checker=func))
                elif params[0].annotation == List[Session]:
                    # 所有会话
                    check_cases.append(AllSessionCase(session_list_checker=func))
                else:
                    raise ValueError(
                        f"First parameter of function {node.name} should be of type HttpTransaction or Session")
            else:
                raise ValueError(f"Function {node.name} should have at least one parameter")

    return check_cases
