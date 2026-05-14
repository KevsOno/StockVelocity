import streamlit as st
import pandas as pd
from utils.db import supabase
from utils.helpers import validate_csv_columns

def render(branch_id, selected_branch_name):
    st.header("📦 Products Master")

    st.subheader("Current Products")
    prods = supabase.table("products").select("*").execute().data
    if prods:
        df_p = pd.DataFrame(prods)
        st.dataframe(df_p[['sku','name','category','shelf_life_days','cost']].rename(columns={
            'sku':'SKU','name':'Name','category':'Category','shelf_life_days':'Shelf Life (days)','cost':'Unit Cost (₦)'
        }))
    else:
        st.info("No products yet.")

    st.markdown("---")
    st.subheader("➕ Add Single Product")
    with st.form("add_product_form"):
        col1, col2 = st.columns(2)
        with col1:
            sku = st.text_input("SKU*")
            name = st.text_input("Product Name*")
            category = st.text_input("Category")
        with col2:
            shelf_life = st.number_input("Shelf Life (days)", min_value=1, value=90)
            cost = st.number_input("Unit Cost (₦)", min_value=0.0, value=0.0, format="%.2f")
        submitted = st.form_submit_button("Add Product")
        if submitted:
            if not sku or not name:
                st.error("SKU and name are required.")
            else:
                try:
                    supabase.table("products").insert({
                        "sku": sku,
                        "name": name,
                        "category": category or None,
                        "shelf_life_days": shelf_life,
                        "cost": cost
                    }).execute()
                    st.success(f"Product '{name}' added.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

    st.markdown("---")
    st.subheader("📁 Upload Products CSV")
    st.markdown("**CSV columns:** `sku`, `name`, `category`, `shelf_life_days`, `cost`")
    template_p = pd.DataFrame(columns=['sku','name','category','shelf_life_days','cost'])
    csv_p = template_p.to_csv(index=False)
    st.download_button("📥 Download Product Template", csv_p, "products_template.csv", "text/csv")

    uploaded_file = st.file_uploader("Choose products CSV", type="csv", key="products_csv")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.dataframe(df.head())
        required = {'sku','name'}
        is_valid, msg = validate_csv_columns(df, required, "products CSV")
        if not is_valid:
            st.error(msg)
            st.stop()
        if 'category' not in df.columns:
            df['category'] = None
        if 'shelf_life_days' not in df.columns:
            df['shelf_life_days'] = 90
        if 'cost' not in df.columns:
            df['cost'] = 0.0
        if st.button("Upload Products"):
            records = df[['sku','name','category','shelf_life_days','cost']].to_dict(orient="records")
            try:
                supabase.table("products").insert(records).execute()
                st.success("Products uploaded!")
                st.rerun()
            except Exception as e:
                st.error(f"Upload failed: {e}")
