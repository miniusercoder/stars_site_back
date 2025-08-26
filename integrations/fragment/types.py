from dataclasses import dataclass
from enum import Enum, IntEnum
from gettext import gettext

from pydantic import BaseModel, ConfigDict

from integrations.wallet.types import TonTransaction


@dataclass()
class PremiumSubscription:
    msgid: str
    id: int
    fragment_price: float = 1.5
    months: int = 3


class FragmentPremiumPrices(IntEnum):
    THREE_MONTHS = 12
    SIX_MONTHS = 16
    YEAR = 29


_ = gettext  # just to add it to locales


class PremiumSubscriptions(PremiumSubscription, Enum):
    THREE_MONTHS = (_("3 Months"), 0, FragmentPremiumPrices.THREE_MONTHS, 3)
    SIX_MONTHS = (_("6 Months"), 1, FragmentPremiumPrices.SIX_MONTHS, 6)
    ONE_YEAR = (_("1 Year"), 2, FragmentPremiumPrices.YEAR, 12)

    @classmethod
    def get_by_id(cls, id: int) -> PremiumSubscription:
        return next(sub for sub in PremiumSubscriptions if sub.id == id)


class StarsRecipient(BaseModel):
    model_config = ConfigDict(extra="ignore")

    recipient: str
    photo: str  # can be a link
    name: str


class StarsPrice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ton: float
    usd: float


class StarsBuy(BaseModel):
    model_config = ConfigDict(extra="ignore")

    transaction: TonTransaction


class PremiumRecipient(BaseModel):
    model_config = ConfigDict(extra="ignore")

    recipient: str
    photo: str  # can be a link
    name: str


class PremiumBuy(BaseModel):
    model_config = ConfigDict(extra="ignore")

    transaction: TonTransaction
