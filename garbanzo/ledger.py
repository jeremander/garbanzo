from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import partial
from pathlib import Path
from typing import NamedTuple, Optional, Set, TypeAlias, cast

from beancount import loader
import beancount.core.data
import pandas as pd
from plotly.colors import qualitative


AnyPath: TypeAlias = str | Path
LedgerOptions: TypeAlias = dict[str, object]
PostingMeta: TypeAlias = dict[str, object]

ACCOUNT_TYPE_NAMES = ['assets', 'liabilities', 'income', 'expenses', 'equity']


def split_account(account: str) -> list[str]:
    return account.split(':')

def account_at_depth(account: str, depth: int) -> str:
    return ':'.join(split_account(account)[:depth])


class Transaction(NamedTuple):
    date: datetime
    payee: Optional[str]
    narration: Optional[str]
    tags: Set[str]
    links: Set[str]
    meta: Optional[PostingMeta] = None

    @classmethod
    def from_beancount(cls, txn: beancount.core.data.Transaction) -> 'Transaction':
        return cls(**{field: getattr(txn, field) for field in cls._fields})


class Posting(NamedTuple):
    # TODO: use date entry in metadata to override transaction date?
    txn_id: int
    date: datetime
    account: str
    amount: float
    currency: str
    cost: Optional[float] = None
    cost_currency: Optional[float] = None
    price: Optional[float] = None
    price_currency: Optional[float] = None
    meta: Optional[PostingMeta] = None

    @classmethod
    def from_beancount(cls, txn_id: int, date: datetime, posting: beancount.core.data.Posting) -> 'Posting':
        if posting.cost is None:
            cost, cost_currency = None, None
        else:
            cost, cost_currency = posting.cost.number, posting.cost.currency
        if posting.price is None:
            price, price_currency = None, None
        else:
            price, price_currency = posting.price.number, posting.price.currency
        return cls(txn_id = txn_id, date = date, account = posting.account, amount = float(posting.units.number), currency = posting.units.currency, cost = cost, cost_currency = cost_currency, price = price, price_currency = price_currency, meta = posting.meta)


class Price(NamedTuple):
    date: datetime
    currency: str
    amount: float
    conv_currency: str

    @classmethod
    def from_beancount(cls, price: beancount.core.data.Price) -> 'Price':
        return cls(date = price.date, currency = price.currency, amount = float(price.amount.number), conv_currency = price.amount.currency)


class TimeGrain(str, Enum):
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    QUARTERLY = 'quarterly'
    YEARLY = 'yearly'

    @classmethod
    def value_dict(cls) -> dict[str, 'TimeGrain']:
        return {val.value: val for val in cls}

    @property
    def frequency(self) -> str:
        match self:
            case TimeGrain.DAILY:
                return 'D'
            case TimeGrain.WEEKLY:
                return 'W'
            case TimeGrain.MONTHLY:
                return 'MS'
            case TimeGrain.QUARTERLY:
                return 'QS'
            case _:
                return 'YS'


@dataclass(frozen = True)
class FilterOptions:
    min_date: Optional[datetime] = None
    max_date: Optional[datetime] = None

    def filter_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filters a dataframe based on the filter options."""
        if (self.min_date is not None):
            df = df[df['date'] >= self.min_date]
        if (self.max_date is not None):
            df = df[df['date'] <= self.max_date]
        return df


@dataclass(frozen = True, repr = False)
class Ledger:
    options: LedgerOptions
    transactions: pd.DataFrame
    postings: pd.DataFrame
    prices: pd.DataFrame

    @classmethod
    def load(cls, path: AnyPath) -> 'Ledger':
        entries, errors, options = loader.load_file(path)
        # TODO: for now, we do not allow errors, but perhaps we should be more permissive
        if errors:
            raise ValueError(f'{len(errors)} error(s) occurred in beancount ledger')
        groups = defaultdict(list)
        for entry in entries:
            groups[type(entry)].append(entry)
        txn_rows = []
        posting_rows = []
        for (txn_id, txn) in enumerate(groups[beancount.core.data.Transaction]):
            txn_rows.append(Transaction.from_beancount(txn))
            for posting in txn.postings:
                posting_rows.append(Posting.from_beancount(txn_id, txn.date, posting))
        transactions = pd.DataFrame(txn_rows)
        postings = pd.DataFrame(posting_rows)
        price_rows = [Price.from_beancount(price) for price in groups[beancount.core.data.Price]]
        prices = pd.DataFrame(price_rows)
        for df in [transactions, postings, prices]:
            df['date'] = pd.to_datetime(df['date'])
        return cls(options, transactions, postings, prices)

    @property
    def main_currency(self) -> str:
        """Gets the main currency configured by the ledger."""
        operating_currencies = cast(list[str], self.options.get('operating_currency', []))
        return operating_currencies[0] if operating_currencies else 'USD'

    @property
    def account_types(self) -> dict[str, str]:
        """Gets a mapping from the canonical category names (lowercase) to their configured names."""
        return {key: cast(str, self.options[f'name_{key}']) for key in ACCOUNT_TYPE_NAMES}

    @property
    def account_type_colors(self) -> dict[str, str]:
        """For plotting purposes, gets a mapping from canonical category names to plot colors."""
        return {cast(str, self.options[f'name_{key}']): color for (key, color) in zip(ACCOUNT_TYPE_NAMES, qualitative.D3)}

    def filter(self, filter_options: FilterOptions) -> 'Ledger':
        return Ledger(self.options, filter_options.filter_dataframe(self.transactions), filter_options.filter_dataframe(self.postings), filter_options.filter_dataframe(self.prices))

    def account_flows(self, account_prefix: str, currency: str, time_grain: TimeGrain, account_depth: Optional[int] = None) -> pd.Series:
        """Calculates the total cash flow for a given account prefix with a given time grain.
        This is the sum total of transaction amounts within each time period.
        If account_depth is a given integer, additionally groups by the account at the given maximum depth.
        (E.g. if level is 2, would include as a group the prefix 'Expenses:Restaurants' and the like.)"""
        grouper = pd.Grouper(key = 'date', freq = time_grain.frequency)
        flags = self.postings.account.str.startswith(account_prefix) & (self.postings.currency == currency)
        df = self.postings[flags]
        if (account_depth is None):
            return df.groupby(grouper)['amount'].sum()
        else:
            df['account'] = df.account.map(partial(account_at_depth, depth = account_depth))
            grouped = df.groupby(grouper)
            return grouped.apply(lambda x: x.groupby('account')['amount'].sum())
