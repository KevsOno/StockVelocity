import streamlit as st
import pandas as pd
from utils.db import supabase

def render(branch_id, selected_branch_name):
    st.header("🚨 Alerts & Advisories")

    query = supabase.table("alert_log").select("*, products(name), branches(name)")
    if branch_id:
        query = query.eq("branch_id", branch_id)
    alerts = query.order("created_at", desc=True).execute().data

    if alerts:
        df_al = pd.DataFrame(alerts)
        df_al['product'] = df_al['products'].apply(lambda x: x['name'] if x else '')
        df_al['branch'] = df_al['branches'].apply(lambda x: x['name'] if x else '')
        st.dataframe(df_al[['branch','product','batch','alert_type','details','action_taken','created_at']])

        st.subheader("Manual Action Update")
        unactioned = [a for a in alerts if not a.get('action_taken')]
        if unactioned:
            alert_id = st.selectbox("Select Alert ID", [a['id'] for a in unactioned])
            action_text = st.text_input("Action Description")
            if st.button("Mark Done"):
                supabase.table("alert_log").update({
                    "action_taken": action_text,
                    "action_date": "now()"
                }).eq("id", alert_id).execute()
                st.success("Marked as done.")
                st.rerun()
        else:
            st.info("All alerts have been actioned.")
    else:
        st.info("No alerts available. Good job!")
