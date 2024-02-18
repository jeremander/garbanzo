from dataclasses import field
from datetime import datetime
from typing import Annotated, Optional

import dateparser
from pydantic import BeforeValidator, ConfigDict, Field
from pydantic.dataclasses import dataclass


NonnegativeInt = Annotated[int, Field(ge = 0)]
Datetime = Annotated[datetime, BeforeValidator(lambda s: dateparser.parse(s))]


@dataclass(config = ConfigDict(extra = 'forbid'))
class GarbanzoConfig:
    default_start_date: Optional[Datetime] = None
    default_account_depth: Optional[NonnegativeInt] = 3
    income_deduction_accounts: list[str] = field(default_factory = list)
