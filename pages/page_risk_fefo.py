import streamlit as st
import pandas as pd
from datetime import date, datetime
from utils.db import supabase
from utils.helpers import get_sales_velocity

def render(branch_id, selected_branch_name):
    st.header("⚠️ Risk Scoring & FEFO Recommendations")
    st.markdown("""
    **FEFO** = *First Expired, First Out* – we recommend consuming batches with the earliest expiry date first.  
    **Risk Score** combines expiry proximity, financial exposure, and sales velocity.  
    **Risk Levels:** LOW 🟢 → MODERATE 🟡 → HIGH 🟠 → CRITICAL 🔴
    """)

    inv_query = supabase.table("inventory").select("""
        id, batch, quantity, expiry_date, storage_location,
        product_id, branch_id,
        products(name, sku, cost)
    """)
    if branch_id:
        inv_query = inv_query.eq("branch_id", branch_id)
    inventory = inv_query.execute().data

    if not inventory:
        st.info("No inventory records found. Please upload inventory data first.")
        return

    today = date.today()
    risk_data = []
    velocity_cache = {}
    unique_keys = {(item['branch_id'], item['product_id']) for item in inventory}
    for (b_id, p_id) in unique_keys:
        velocity_cache[(b_id, p_id)] = get_sales_velocity(b_id, p_id)

    for item in inventory:
        product = item.get('products') or {}
        product_name = product.get('name', 'Unknown')
        sku = product.get('sku', '')
        cost = float(product.get('cost', 0))
        quantity = item.get('quantity', 0)
        expiry_date_str = item.get('expiry_date')
        if not expiry_date_str:
            continue
        expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
        days_to_expiry = (expiry_date - today).days

        if days_to_expiry <= 0:
            expiry_score = 100.0
        elif days_to_expiry <= 7:
            expiry_score = 95.0
        elif days_to_expiry <= 30:
            expiry_score = 80.0
        elif days_to_expiry <= 90:
            expiry_score = 50.0
        else:
            expiry_score = 20.0

        financial_value = quantity * cost
        risk_data.append({
            'product_name': product_name,
            'sku': sku,
            'batch': item['batch'],
            'quantity': quantity,
            'cost': cost,
            'financial_value': financial_value,
            'expiry_date': expiry_date,
            'days_to_expiry': days_to_expiry,
            'expiry_score': expiry_score,
            'branch_id': item['branch_id'],
            'product_id': item['product_id']
        })

    if not risk_data:
        st.warning("No valid inventory items with expiry dates found.")
        return

    financial_vals = [d['financial_value'] for d in risk_data]
    max_financial = max(financial_vals) if financial_vals else 1
    for d in risk_data:
        financial_score = (d['financial_value'] / max_financial) * 100 if max_financial > 0 else 0
        velocity = velocity_cache.get((d['branch_id'], d['product_id']), 0.0)
        if velocity <= 0.1:
            velocity_score = 90.0
        elif velocity <= 0.5:
            velocity_score = 70.0
        elif velocity <= 2:
            velocity_score = 40.0
        else:
            velocity_score = 10.0
        risk_score = (d['expiry_score'] * 0.5) + (financial_score * 0.3) + (velocity_score * 0.2)
        if risk_score >= 80:
            risk_level = "CRITICAL"
            risk_emoji = "🔴"
        elif risk_score >= 60:
            risk_level = "HIGH"
            risk_emoji = "🟠"
        elif risk_score >= 35:
            risk_level = "MODERATE"
            risk_emoji = "🟡"
        else:
            risk_level = "LOW"
            risk_emoji = "🟢"
        d['risk_level'] = f"{risk_emoji} {risk_level}"
        d['risk_score'] = risk_score
        d['sales_velocity'] = velocity

    df_risk = pd.DataFrame(risk_data)
    df_risk['expiry_date'] = pd.to_datetime(df_risk['expiry_date']).dt.date

    sort_by = st.selectbox("Sort by", ["Risk Score (highest first)", "Expiry Date (earliest first)", "Financial Value (highest first)"])
    if sort_by == "Risk Score (highest first)":
        df_display = df_risk.sort_values('risk_score', ascending=False)
    elif sort_by == "Expiry Date (earliest first)":
        df_display = df_risk.sort_values('expiry_date')
    else:
        df_display = df_risk.sort_values('financial_value', ascending=False)

    st.subheader("📋 Batch Risk Assessment")
    display_cols = ['product_name', 'sku', 'batch', 'quantity', 'cost', 'financial_value', 
                    'expiry_date', 'days_to_expiry', 'sales_velocity', 'risk_level']
    st.dataframe(df_display[display_cols].rename(columns={
        'product_name': 'Product', 'sku': 'SKU', 'financial_value': 'Financial Exposure (₦)',
        'days_to_expiry': 'Days Left', 'sales_velocity': 'Daily Demand (units)'
    }))

    st.subheader("📌 FEFO Recommendation (Consumption Order)")
    fefo_df = df_risk.sort_values(['expiry_date', 'risk_score'], ascending=[True, False])
    st.markdown("**Recommended order** – consume batches with earliest expiry date first, and within same expiry date prioritise higher risk:")
    for _, row in fefo_df.iterrows():
        st.write(f"- **{row['product_name']}** (Batch `{row['batch']}`) – Expires **{row['expiry_date']}** – {row['risk_level']}")

    st.subheader("📊 Risk Distribution")
    risk_counts = df_risk['risk_level'].value_counts()
    st.bar_chart(risk_counts)

    with st.expander("ℹ️ How risk score is calculated"):
        st.markdown("""
        **Risk Score = (Expiry Score × 0.5) + (Financial Score × 0.3) + (Low Velocity Score × 0.2)**  
        - **Expiry Score** (0–100): ≤0d→100, 1-7d→95, 8-30d→80, 31-90d→50, >90d→20  
        - **Financial Score** (0–100): normalised quantity×cost  
        - **Low Velocity Score** (0–100): ≤0.1 units/day→90, 0.11-0.5→70, 0.51-2→40, >2→10  
        **Risk levels:** CRITICAL (≥80) → HIGH (60–79) → MODERATE (35–59) → LOW (<35)
        """)
