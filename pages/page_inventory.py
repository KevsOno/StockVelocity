import streamlit as st
import pandas as pd
from datetime import date
from utils.db import supabase

def render(branch_id, selected_branch_name):
    st.header("📦 Current Inventory")

    query = supabase.table("inventory").select("*, products(name, sku, cost), branches(name)")
    if branch_id:
        query = query.eq("branch_id", branch_id)
    inv_data = query.execute().data

    if inv_data:
        df_i = pd.DataFrame(inv_data)
        df_i['product'] = df_i['products'].apply(lambda x: x['name'] if x else '')
        df_i['branch'] = df_i['branches'].apply(lambda x: x['name'] if x else '')
        st.dataframe(df_i[['branch','product','batch','quantity','expiry_date','storage_location']])
    else:
        st.info("No inventory records found.")

    st.subheader("➕ Quick Manual Entry (one item)")
    with st.form("manual_inv"):
        prod_sku = st.text_input("Product SKU")
        batch = st.text_input("Batch")
        qty = st.number_input("Quantity", min_value=0)
        exp_date = st.date_input("Expiry Date", min_value=date.today())
        location = st.selectbox("Storage Location", ["warehouse", "shelf", "cold_room"])
        if st.form_submit_button("Add Item"):
            if not prod_sku:
                st.error("SKU required.")
            else:
                prod_res = supabase.table("products").select("id").eq("sku", prod_sku).execute()
                if not prod_res.data:
                    st.error("Product not found.")
                else:
                    # If branch_id is None (All Branches), ask user to pick a branch
                    if branch_id is None:
                        branches = supabase.table("branches").select("id, name").execute().data
                        branch_choice = st.selectbox("Select Branch", [b['name'] for b in branches])
                        actual_branch_id = next(b['id'] for b in branches if b['name'] == branch_choice)
                    else:
                        actual_branch_id = branch_id
                    supabase.table("inventory").insert({
                        "branch_id": actual_branch_id,
                        "product_id": prod_res.data[0]['id'],
                        "batch": batch,
                        "quantity": qty,
                        "expiry_date": exp_date.isoformat() if exp_date else None,
                        "storage_location": location
                    }).execute()
                    st.success("Item added!")
                    st.rerun()
