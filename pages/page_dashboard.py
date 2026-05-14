import streamlit as st
import pandas as pd
from utils.db import supabase

def render(branch_id, selected_branch_name):
    st.header("📊 Executive Summary")

    inv_query = supabase.table("inventory").select("product_id, quantity, products(cost)")
    alert_query = supabase.table("alert_log").select("*, products(cost)")

    if branch_id:
        inv_query = inv_query.eq("branch_id", branch_id)
        alert_query = alert_query.eq("branch_id", branch_id)

    inv = inv_query.execute().data
    alerts = alert_query.execute().data

    if alerts:
        df_a = pd.DataFrame(alerts)
        total_alerts = len(df_a)

        expiring = df_a[df_a['alert_type'] == 'EXPIRY']
        inv_df = pd.DataFrame(inv) if inv else pd.DataFrame()
        wastage_val = 0
        if not inv_df.empty:
            for _, row in expiring.iterrows():
                qty = inv_df[inv_df['product_id'] == row['product_id']]['quantity'].sum()
                cost = row['products']['cost'] if row['products'] else 0
                wastage_val += qty * cost

        stockout = len(df_a[df_a['alert_type'] == 'RESTOCK'])
        dead_stock = len(df_a[df_a['alert_type'] == 'DEAD_STOCK'])
        actioned = len(df_a[df_a['action_taken'].notna()])
        compliance = round((actioned / total_alerts * 100), 1) if total_alerts else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Waste Risk", f"₦{wastage_val:,.0f}")
        c2.metric("Stock‑out Risks", stockout)
        c3.metric("Dead Stock", dead_stock)
        c4.metric("Actions Done", f"{compliance}%")

        st.subheader("Alert Type Breakdown")
        st.bar_chart(df_a['alert_type'].value_counts())
    else:
        st.info("No alert data available yet. Run the daily Edge Function to generate alerts.")
