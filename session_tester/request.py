from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class StReq:
    req_data: Any
    url: Optional[str] = None
    http_method: Optional[str] = None
    timeout: Optional[tuple] = (1, 5)
    headers: Optional[dict] = None
    retry: Optional[int] = 1
