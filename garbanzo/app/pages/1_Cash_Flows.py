import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit_antd_components as sac

from garbanzo.app.utils import get_ledger, setup_sidebar
from garbanzo.ledger import Ledger


# TODO: configure this
MAX_STACK_SEGMENTS = 6

D3_COLORS = px.colors.qualitative.D3

st.set_page_config(layout = 'wide')


def render_percent(pct: float) -> tuple[str, str]:
    if np.isnan(pct):
        return ('', 'gray')
    pct = round(pct)
    pct_str = f'{pct}%'
    if (pct > 0):
        return (f'▲ {pct_str}', D3_COLORS[2])
    if (pct < 0):
        return (f'▼ {pct_str}', D3_COLORS[3])
    return (pct_str, 'gray')

def make_simple_bars(ledger: Ledger, flows: pd.DataFrame, currency: str, account_option: str) -> go.Figure:
    flows = flows.rename(columns = {'amount': currency})
    pct_change = 100 * flows[currency].pct_change()
    text, text_color = zip(*[render_percent(pct) for pct in pct_change])
    flows['pct'] = text
    fig = px.bar(flows, x = 'date', y = currency, text = 'pct', hover_data = {currency: ':,d', 'pct': False})
    color = ledger.account_type_colors[account_option]
    textfont = {'color': text_color}
    fig.update_traces(marker_color = color, textangle = 0, textposition = 'outside', textfont = textfont)
    return fig

def simplify_group(group: pd.DataFrame) -> pd.DataFrame:
    group_sorted = group.sort_values(by = 'amount', key = abs, ascending = False)
    head = group_sorted.head(MAX_STACK_SEGMENTS)
    tail = group_sorted.tail(-MAX_STACK_SEGMENTS)
    if len(tail) == 0:
        return head
    s = pd.Series({'date': tail.iloc[0].date, 'account': 'Other', 'amount': tail.amount.sum()})
    return pd.concat([head, s.to_frame().T])

def make_stacked_bars(flows: pd.DataFrame, currency: str) -> go.Figure:
    flows = flows.groupby('date').apply(simplify_group).reset_index(drop = True)
    colors = D3_COLORS
    assert len(colors) >= MAX_STACK_SEGMENTS + 1
    flows['index'] = flows.groupby('date').cumcount()
    flows['pct'] = flows.groupby('date', group_keys = False)['amount'].apply(lambda x: 100 * x / x.sum())
    fig = go.Figure()
    for tup in flows.itertuples():
        color = colors[tup.index]
        customdata = [[tup.account, color, tup.pct]]
        hovertemplate = '<span style="color: %{customdata[1]};">%{customdata[0]}</span><br>%{x}<br>%{y:,d} ' + currency + ' (%{customdata[2]:.2g}%)'
        marker = {'color': color}
        fig.add_trace(go.Bar(x = [tup.date], y = [tup.amount], customdata = customdata, hovertemplate = hovertemplate, marker = marker, name = '', showlegend = False))
    fig.update_layout(barmode = 'stack')
    return fig

def make_savings_bars(ledger: Ledger, flows: pd.DataFrame, currency: str) -> go.Figure:
    fig = go.Figure()
    colors = [D3_COLORS[i] for i in [2, 0, 3, 4]]
    for (col, marker_color) in zip(flows.columns, colors):
        hovertemplate = '%{y:,d} ' + currency
        bar = go.Bar(x = flows.index, y = flows[col], name = col, hovertemplate = hovertemplate, marker_color = marker_color)
        fig.add_trace(bar)
    fig.update_layout(barmode = 'group', bargap = 0.15, bargroupgap = 0.1)
    return fig


def run() -> None:
    st.markdown('<h3 style="text-align: center">Cash flows over time</h3>', unsafe_allow_html=True)
    opts = setup_sidebar()
    ledger = get_ledger().filter(opts.filter_options)
    currency = ledger.main_currency
    account_type = st.session_state.get('account_type', ledger.account_types['income'])
    account_options = [ledger.account_types[key] for key in ['income', 'expenses']] + ['Savings']
    stacked = st.radio('plot mode', ['basic', 'stacked'], index = 0, horizontal = True, label_visibility = 'hidden') == 'stacked'
    chart = st.empty()
    i = account_options.index(account_type)
    account_option = sac.buttons(items = account_options, index = i, align = 'center', radius = 'md')
    account_depth = ledger.config.default_account_depth if (stacked and (account_option != 'Savings')) else None
    flow_kwargs = {'currency': currency, 'time_grain': opts.time_grain, 'account_depth': account_depth, 'adjust_sign': True}
    with chart.container():
        if (account_option == 'Savings'):
            # TODO: implement stacked & grouped?
            flows = ledger.income_expense_data(**flow_kwargs).rename(columns = {'amount': currency})  # type: ignore
            fig = make_savings_bars(ledger, flows, currency)
        else:
            flows = ledger.account_flows(account_option, **flow_kwargs).reset_index()  # type: ignore
            if stacked:
                fig = make_stacked_bars(flows, currency)
            else:
                fig = make_simple_bars(ledger, flows, currency, account_option)
        showlegend = account_option == 'Savings'
        fig.update_layout(showlegend = showlegend)
        st.plotly_chart(fig, use_container_width = True)


run()
