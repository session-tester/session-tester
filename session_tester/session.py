import glob
import json
import math
import os
import threading
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from .logger import logger
from .user_info import UserInfo

test_session_dir = os.getenv("TEST_SESSION_DIR", "./test_sessions")
if not os.path.exists(test_session_dir):
    os.makedirs(test_session_dir)
sub_session_dir_exists = False


def update_test_session_dir(name: str):
    global test_session_dir, sub_session_dir_exists
    test_session_dir = os.path.join(test_session_dir, name)
    if not os.path.exists(test_session_dir):
        os.makedirs(test_session_dir)

    sub_session_dir_exists = True


@dataclass
class HttpTransaction:
    url: str  # 存储请求的URL
    method: str  # 存储请求的方法
    status_code: Optional[int]  # 存储HTTP状态码
    request: Optional[str]  # 存储请求数据（序列化后的字符串）
    response: Optional[str]  # 存储响应数据（序列化后的字符串）
    request_time: Optional[datetime] = datetime.now()  # 存储请求时间
    cost_time: Optional[float] = 0.0
    retry_cnt: Optional[int] = 0

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def to_dict(self) -> dict:
        # 将 datetime 对象转换为字符串
        data = asdict(self)
        data['request_time'] = self.request_time.isoformat()
        return data

    def req_json(self):
        return json.loads(self.request)

    def rsp_json(self):
        return json.loads(self.response)

    def rsp_json_data(self):
        return self.rsp_json()["data"]

    def finished_without_error(self):
        return self.status_code == 200

    @staticmethod
    def from_json(json_str: str) -> 'HttpTransaction':
        data = json.loads(json_str)
        # 将字符串转换回 datetime 对象
        data['request_time'] = datetime.fromisoformat(data['request_time'])
        return HttpTransaction(**data)


class IDGenerator:
    _id = None
    _lock = threading.Lock()  # 使用线程锁来保护类变量
    id_dict = {}

    @classmethod
    def _read_initial_id(cls, file_path):
        k = file_path
        file_path = os.path.join(test_session_dir, file_path)
        try:
            with open(file_path, 'r') as file:
                cls.id_dict[k] = int(file.read().strip())
        except:
            cls.id_dict[k] = 0

    @classmethod
    def _write_id_to_file(cls, file_path: str):
        k = file_path
        file_path = os.path.join(test_session_dir, file_path)
        with open(file_path, 'w') as file:
            file.write(str(cls.id_dict[k]))

    @classmethod
    def get_next_id(cls, file_path: str) -> int:
        with cls._lock:  # 使用线程锁来保护临界区
            if cls.id_dict.get(file_path, None) is None:
                cls._read_initial_id(file_path)
            cls.id_dict[file_path] += 1
            cls._write_id_to_file(file_path)
            return cls.id_dict[file_path]

    @classmethod
    def get_curr_id(cls, file_path: str) -> int:
        with cls._lock:  # 使用线程锁来保护临界区
            cls._read_initial_id(file_path)
            return cls.id_dict[file_path]


class Session(IDGenerator):

    def __init__(self, label: str, create_flag=True):
        self.label = label
        self.user_info: UserInfo = None
        self.transactions: List[HttpTransaction] = []
        self.start_time = None
        self.session_filename = None
        self.no_dump = False
        self.ext_state = {}
        if create_flag:
            self.session_id = Session.get_next_id(label)

    def finished_without_error(self):
        return all([x.finished_without_error() for x in self.transactions])

    @staticmethod
    def load_session(session_filename: str) -> 'Session':
        with open(session_filename, 'r') as file:
            return Session.from_json(file.read())

    @staticmethod
    def clear_sessions(label: str):
        if sub_session_dir_exists:
            # remote all files in test_session_dir but not remove the dir
            for root, _, files in os.walk(test_session_dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
            return
        id_file = os.path.join(test_session_dir, f"{label}")
        session_filename_list = glob.glob(id_file + "-*.json")
        files = session_filename_list + [id_file]
        for filename in files:
            try:
                os.remove(filename)
            except Exception as e:
                logger.error("Failed to remove session {%s}: {%s}", filename, e)

    @staticmethod
    def load_sessions(label: str, n: int = math.inf) -> List['Session']:
        sessions = []
        id_ = Session.get_curr_id(label)
        while id_ > 0 and len(sessions) < n:
            session_filename = f"{label}-{id_:08d}.json"
            # TODO 数据量过大时，可以考虑分批加载和校验
            try:
                s = Session.load_session(os.path.join(test_session_dir, session_filename))
                sessions.append(s)
            except Exception as e:
                logger.error("Failed to load session {%s}: {%s}", session_filename, e)
            id_ -= 1
        return sessions

    def create(self, user_info: UserInfo, transactions: List[HttpTransaction],
               start_time: Optional[float] = None,
               no_dump: bool = False) -> 'Session':
        self.user_info = user_info
        self.transactions = transactions
        self.start_time = start_time
        # 创建一个session文件
        self.session_filename = f"{self.label}-{self.session_id:08d}.json"
        self.ext_state = {}
        self.no_dump = no_dump
        if not no_dump:
            self.dump()
        return self

    def append_transaction(self, transaction: HttpTransaction):
        self.transactions.append(transaction)

    def to_json(self) -> str:
        return json.dumps({
            'label': self.label,
            'session_id': self.session_id,
            'user_info': self.user_info.to_dict() if self.user_info else None,
            'transactions': [x.to_dict() for x in self.transactions],
            'ext_state': self.ext_state,
            'start_time': self.start_time
        }, indent=2)

    def dump(self):
        if self.session_filename:
            if self.no_dump:
                return
            full_session_filename = os.path.join(test_session_dir, self.session_filename)
            with open(full_session_filename, 'w') as file:
                file.write(self.to_json())
        else:
            raise ValueError("Session filename is not set")

    @staticmethod
    def from_json(json_str: str) -> 'Session':
        data = json.loads(json_str)
        user_info = UserInfo(**data['user_info'])  # 假设 UserInfo 类可以通过 **kwargs 初始化
        if not data['transactions']:
            raise ValueError("No transactions found")

        transactions = [HttpTransaction(**tx) for tx in data['transactions']]
        s = Session(label=data['label'], create_flag=False)
        s.user_info = user_info
        s.transactions = transactions
        s.start_time = data.get('start_time')
        s.session_id = data['session_id']
        s.ext_state = data['ext_state']
        s.session_filename = f"{s.label}-{s.session_id:08d}.json"
        return s
