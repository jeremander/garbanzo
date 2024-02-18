
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit_antd_components as sac

from garbanzo.app.utils import get_ledger, setup_sidebar
from garbanzo.ledger import Ledger


# TODO: configure this
MAX_STACK_SEGMENTS = 6
ACCOUNT_DEPTH = 3

st.set_page_config(layout = 'wide')


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
    colors = px.colors.qualitative.D3
    assert len(colors) >= MAX_STACK_SEGMENTS + 1
    flows['index'] = flows.groupby('date').cumcount()
    flows['pct'] = flows.groupby('date', group_keys = False)['amount'].apply(lambda x: 100 * x / x.sum())
    fig = go.Figure()
    for tup in flows.itertuples():
        customdata = [tup.pct]
        hovertemplate = '%{y:,d} ' + currency + ' (%{customdata:.2g}%)'
        marker = {'color': colors[tup.index]}
        fig.add_trace(go.Bar(x = [tup.date], y = [tup.amount], customdata = customdata, hovertemplate = hovertemplate, marker = marker, name = tup.account, showlegend = False))
    fig.update_layout(barmode = 'stack')
    return fig

def make_profit_bars(ledger: Ledger, flows: pd.DataFrame, currency: str) -> go.Figure:
    fig = go.Figure()
    for col in flows.columns:
        marker_color = ledger.account_type_colors.get(col, 'purple')
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
    account_depth = ACCOUNT_DEPTH if stacked else None
    flow_kwargs = {'currency': currency, 'time_grain': opts.time_grain, 'account_depth': account_depth, 'adjust_sign': True}
    with chart.container():
        if (account_option == 'Savings'):
            if stacked:
                # TODO: implement
                fig = go.Figure()
            else:
                flows = ledger.income_expense_data(**flow_kwargs).rename(columns = {'amount': currency})  # type: ignore
                fig = make_profit_bars(ledger, flows, currency)
        else:
            flows = ledger.account_flows(account_option, **flow_kwargs).reset_index()  # type: ignore
            if stacked:
                fig = make_stacked_bars(flows, currency)
            else:
                flows = flows.rename(columns = {'amount': currency})
                fig = px.bar(flows, x = 'date', y = currency, hover_data = {currency: ':,d'})
                color = ledger.account_type_colors[account_option]
                fig.update_traces(marker_color = color)
        showlegend = account_option == 'P&L'
        fig.update_layout(showlegend = showlegend)
        st.plotly_chart(fig, use_container_width = True)


run()
