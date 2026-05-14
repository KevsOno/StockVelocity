import streamlit as st
import pandas as pd
from utils.db import supabase
from utils.helpers import validate_csv_columns, upload_csv_to_table

def render(branch_id, selected_branch_name):
    st.header("📁 Upload Inventory or Movement Data")
    upload_type = st.selectbox("Data Type", ["Inventory (current stock)", "Stock Movements (sales/restock)"])

    # Determine branch for upload
    if branch_id:
        selected_branch_id = branch_id
        selected_branch_label = selected_branch_name
    else:
        branch_list = supabase.table("branches").select("id,name").execute().data
        branch_map = {b['name']: b['id'] for b in branch_list}
        selected_branch_label = st.selectbox("Select branch for data", list(branch_map.keys()))
        selected_branch_id = branch_map[selected_branch_label]

    uploaded_file = st.file_uploader("Choose CSV", type="csv", key="data_csv")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.dataframe(df.head())

        if upload_type == "Inventory (current stock)":
            required_cols = {'product_sku','batch','quantity','expiry_date','storage_location'}
            is_valid, msg = validate_csv_columns(df, required_cols, "inventory CSV")
            if not is_valid:
                st.error(msg)
                st.stop()
            skus = df['product_sku'].unique().tolist()
            products_data = supabase.table("products").select("id, sku").in_("sku", skus).execute().data
            sku_to_id = {p['sku']: p['id'] for p in products_data}
            df['product_id'] = df['product_sku'].map(sku_to_id)
            missing = df[df['product_id'].isna()]['product_sku'].unique()
            if len(missing) > 0:
                st.error(f"❌ These SKUs not found in products: {missing}. Add them first.")
                st.stop()
            df['branch_id'] = selected_branch_id
            df['expiry_date'] = pd.to_datetime(df['expiry_date']).dt.date
            df = df[['branch_id','product_id','batch','quantity','expiry_date','storage_location']]
            if st.button("Upload Inventory"):
                res = upload_csv_to_table("inventory", df)
                if res:
                    st.success(f"Inventory uploaded for {selected_branch_label}!")

        else:  # Stock Movements
            required_cols = {'product_sku','quantity_change','movement_date'}
            is_valid, msg = validate_csv_columns(df, required_cols, "movements CSV")
            if not is_valid:
                st.error(msg)
                st.stop()
            skus = df['product_sku'].unique().tolist()
            products_data = supabase.table("products").select("id, sku").in_("sku", skus).execute().data
            sku_to_id = {p['sku']: p['id'] for p in products_data}
            df['product_id'] = df['product_sku'].map(sku_to_id)
            missing = df[df['product_id'].isna()]['product_sku'].unique()
            if len(missing) > 0:
                st.error(f"❌ These SKUs not found: {missing}")
                st.stop()
            df['branch_id'] = selected_branch_id
            df['movement_date'] = pd.to_datetime(df['movement_date']).dt.date
            if 'notes' not in df.columns:
                df['notes'] = ""
            df = df[['branch_id','product_id','quantity_change','movement_date','notes']]
            if st.button("Upload Movements"):
                res = upload_csv_to_table("stock_movements", df)
                if res:
                    st.success(f"Movements uploaded for {selected_branch_label}!")
