from dataclasses import dataclass, asdict, field
from typing import List


@dataclass
class UserInfo:
    userid: str = None
    area: str = None
    plat: str = None
    partition: str = None
    user_type: str = None
    role_id: str = None
    extra: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)

    def parse(self, info_dict):
        for key, value in info_dict.items():
            setattr(self, key, value)


class UserInfoGenerator:
    """ 用户信息生成器 """
    def __init__(self, field_list: list[str]):
        self.field_list = field_list

    def generate(self) -> List[UserInfo]:
        raise NotImplementedError
