from dataclasses import dataclass
from datetime import date, datetime
import os
from typing import Optional

import streamlit as st

from garbanzo.ledger import FilterOptions, Ledger, TimeGrain


def date_to_datetime(date: Optional[date]) -> Optional[datetime]:
    if date is None:
        return None
    return datetime(date.year, date.month, date.day)

@st.cache_data
def load_ledger(path: str) -> Ledger:
    return Ledger.load(path)

def get_ledger() -> Ledger:
    if 'ledger' not in st.session_state:
        ledger_path = os.getenv('LEDGER_PATH')
        if ledger_path is None:
            raise ValueError('environment variable LEDGER_PATH must be set')
        with st.spinner(f'Loading beancount ledger: {ledger_path}'):
            ledger = load_ledger(ledger_path)
        st.session_state['ledger'] = ledger
    return st.session_state['ledger']


@dataclass
class SidebarOptions:
    filter_options: FilterOptions = FilterOptions()
    time_grain: TimeGrain = TimeGrain.MONTHLY


def setup_sidebar() -> SidebarOptions:
    with st.sidebar:
        if 'ledger' in st.session_state:
            default_start_date = st.session_state['ledger'].config.default_start_date
        else:
            default_start_date = None
        min_date = st.date_input('Start date', value = default_start_date, format = 'YYYY-MM-DD')
        max_date = st.date_input('End date', value = None, format = 'YYYY-MM-DD')
        assert (min_date is None) or isinstance(min_date, date)
        assert (max_date is None) or isinstance(max_date, date)
        filter_options = FilterOptions(date_to_datetime(min_date), date_to_datetime(max_date))
        time_grain_dict = TimeGrain.value_dict()
        time_grains = list(time_grain_dict)
        selected = st.selectbox('Time grain', time_grains, index = time_grains.index('monthly'))
        assert isinstance(selected, str)
        time_grain = time_grain_dict[selected]
    sidebar_options = SidebarOptions(filter_options, time_grain)
    st.session_state['sidebar_options'] = sidebar_options
    return sidebar_options

# def get_sidebar_options() -> SidebarOptions:
#     if 'sidebar_options' not in st.session_state:
#         setup_sidebar()
#     return st.session_state['sidebar_options']
