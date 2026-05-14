import streamlit as st
import pandas as pd
from utils.db import supabase

def render(branch_id, selected_branch_name):
    st.header("📊 AI-Computed Stock Limits")
    st.caption("These limits are automatically updated daily based on sales velocity.")

    lim_query = supabase.table("stock_limits").select("*, products(name), branches(name)")
    if branch_id:
        lim_query = lim_query.eq("branch_id", branch_id)
    limits = lim_query.execute().data

    if limits:
        df_l = pd.DataFrame(limits)
        df_l['product'] = df_l['products'].apply(lambda x: x['name'] if x else '')
        df_l['branch'] = df_l['branches'].apply(lambda x: x['name'] if x else '')
        st.dataframe(df_l[['branch','product','avg_daily_demand','safety_stock','reorder_point','max_stock','calculated_at']])
    else:
        st.info("No AI limits computed yet. Ensure the Edge Function has run and stock movements exist.")
