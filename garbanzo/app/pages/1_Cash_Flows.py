import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit_antd_components as sac

from garbanzo.app.utils import get_ledger, setup_sidebar


# TODO: configure this
MAX_STACK_SEGMENTS = 6
ACCOUNT_DEPTH = 3


def simplify_group(group: pd.DataFrame) -> pd.DataFrame:
    group_sorted = group.sort_values(by = 'amount', key = abs, ascending = False)
    head = group_sorted.head(MAX_STACK_SEGMENTS)
    tail = group_sorted.tail(-MAX_STACK_SEGMENTS)
    if len(tail) == 0:
        return head
    s = pd.Series({'date': tail.iloc[0].date, 'account': 'Other', 'amount': tail.amount.sum()})
    return pd.concat([head, s.to_frame().T])


def run() -> None:
    st.markdown('<h3 style="text-align: center">Cash flows over time</h3>', unsafe_allow_html=True)
    opts = setup_sidebar()
    ledger = get_ledger().filter(opts.filter_options)
    currency = ledger.main_currency
    account_type = st.session_state.get('account_type', ledger.account_types['income'])
    account_types = [ledger.account_types[key] for key in ['income', 'expenses']]
    stacked = st.radio('plot mode', ['basic', 'stacked'], index = 0, horizontal = True, label_visibility = 'hidden') == 'stacked'
    chart = st.empty()
    i = account_types.index(account_type)
    account_type = sac.buttons(items = account_types, index = i, align = 'center', radius = 'md')
    with chart.container():
        account_depth = ACCOUNT_DEPTH if stacked else None
        flows = ledger.account_flows(account_type, currency, opts.time_grain, account_depth = account_depth)
        if account_type == ledger.account_types['income']:
            flows = -flows
        flows = flows.reset_index()
        if stacked:
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
        else:
            flows = flows.rename(columns = {'amount': currency})
            fig = px.bar(flows, x = 'date', y = currency, hover_data = {currency: ':,d'})
            color = ledger.account_type_colors[account_type]
            fig.update_traces(marker_color = color)
        fig.update_layout(showlegend = False)
        st.plotly_chart(fig, use_container_width = True)


run()
