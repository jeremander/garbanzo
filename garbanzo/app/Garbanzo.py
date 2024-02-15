import streamlit as st

from garbanzo.app.utils import get_ledger, setup_sidebar


st.set_page_config(page_title = 'Garbanzo', layout = 'wide')


def run() -> None:
    ledger = get_ledger()
    sidebar_options = setup_sidebar()
    st.write(sidebar_options)
    st.dataframe(ledger.prices)


if __name__ == "__main__":
    run()