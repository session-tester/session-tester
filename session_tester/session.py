import glob
import json
import os
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from filelock import FileLock

from .logger import logger
from .user_info import UserInfo

test_session_dir = os.getenv("TEST_SESSION_DIR", "./test_sessions")
if not os.path.exists(test_session_dir):
    os.makedirs(test_session_dir)


@dataclass
class HttpTransaction:
    url: str  # 存储请求的URL
    method: str  # 存储请求的方法
    status_code: int  # 存储HTTP状态码
    request: str  # 存储请求数据（序列化后的字符串）
    response: str  # 存储响应数据（序列化后的字符串）
    request_time: datetime  # 存储请求时间

    def __post_init__(self):
        # 如果 request_time 未传递，则使用当前时间
        if not isinstance(self.request_time, datetime):
            self.request_time = datetime.now()

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

    @staticmethod
    def from_json(json_str: str) -> 'HttpTransaction':
        data = json.loads(json_str)
        # 将字符串转换回 datetime 对象
        data['request_time'] = datetime.fromisoformat(data['request_time'])
        return HttpTransaction(**data)


class IDGenerator:
    _id = None

    @classmethod
    def _read_initial_id(cls, file_path):
        file_path = os.path.join(test_session_dir, file_path)
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                try:
                    cls._id = int(file.read().strip())
                except ValueError:
                    cls._id = 0
        else:
            cls._id = 0

    @classmethod
    def _write_id_to_file(cls, file_path: str):
        file_path = os.path.join(test_session_dir, file_path)
        with open(file_path, 'w') as file:
            file.write(str(cls._id))

    @classmethod
    def get_next_id(cls, file_path: str) -> int:
        lock_path = file_path + ".lock"
        with FileLock(os.path.join(test_session_dir, lock_path)):
            if cls._id is None:
                cls._read_initial_id(file_path)
            cls._id += 1
            cls._write_id_to_file(file_path)
            return cls._id

    @classmethod
    def get_curr_id(cls, file_path: str) -> int:
        lock_path = file_path + ".lock"
        with FileLock(os.path.join(test_session_dir, lock_path)):
            cls._read_initial_id(file_path)
            return cls._id


class Session(IDGenerator):

    def __init__(self, label: str, create_flag=True):
        self.label = label
        self.user_info: UserInfo = None
        self.transactions = []
        self.start_time = None
        self.session_filename = None
        self.ext_state = {}
        if create_flag:
            self.session_id = Session.get_next_id(label)

    @staticmethod
    def load_session(session_filename: str) -> 'Session':
        with open(session_filename, 'r') as file:
            return Session.from_json(file.read())

    @staticmethod
    def clear_sessions(label: str):
        id_file = os.path.join(test_session_dir, f"{label}")
        session_filename_list = glob.glob(id_file + "-*.json")
        files = session_filename_list + [id_file]
        for filename in files:
            try:
                os.remove(filename)
            except Exception as e:
                logger.error("Failed to remove session {%s}: {%s}", filename, e)

    @staticmethod
    def load_sessions(label: str, n: int = 100) -> List['Session']:
        sessions = []
        id_ = Session.get_curr_id(label)
        while id_ > 0 and len(sessions) < n:
            session_filename = f"{label}-{id_:08d}.json"
            try:
                s = Session.load_session(os.path.join(test_session_dir, session_filename))
                sessions.append(s)
            except Exception as e:
                logger.error("Failed to load session {%s}: {%s}", session_filename, e)
            id_ -= 1
        return sessions

    def create(self, user_info: UserInfo, transactions: List[HttpTransaction],
               start_time: Optional[float] = None) -> 'Session':
        self.user_info = user_info
        self.transactions = transactions
        self.start_time = start_time
        # 创建一个session文件
        self.session_filename = f"{self.label}-{self.session_id:08d}.json"
        self.ext_state = {}
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
