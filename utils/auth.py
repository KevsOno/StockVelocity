import streamlit as st

def check_auth():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        pwd = st.text_input("Enter access password", type="password")
        if pwd == st.secrets.get("APP_PASSWORD", "changeme"):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.stop()
