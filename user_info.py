from dataclasses import dataclass, asdict, field
from typing import List


@dataclass
class UserInfo:
    userid: str = None
    area: str = None
    plat: str = None
    partition: str = None
    role_id: str = None
    extra: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)

    def parse(self, info_dict):
        for key, value in info_dict.items():
            setattr(self, key, value)


class UserInfoGenerator:
    def __init__(self, field_list: list[str]):
        self.field_list = field_list

    def generate(self) -> List[UserInfo]:
        raise NotImplementedError


# Load from offline files

# 固定产生用户信息


def demo_userinfo_generator(n):
    for i in range(n):
        user_info = UserInfo()
        user_info.userid = f"lottery-test-{i:05}"
        user_info.area = "1"
        user_info.plat = "2"
        user_info.partition = "100"
        user_info.role_id = None
        yield user_info
