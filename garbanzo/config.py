from datetime import datetime
from typing import Optional

from pydantic.dataclasses import dataclass


@dataclass
class PydanticConfig:
    default_start_date: Optional[datetime] = None
