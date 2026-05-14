import streamlit as st
import pandas as pd
from utils.db import supabase
from utils.helpers import validate_csv_columns

def render(branch_id, selected_branch_name):
    st.header("🏢 Branch Management")

    st.subheader("Current Branches")
    all_branches = supabase.table("branches").select("*").execute().data
    if all_branches:
        df_b = pd.DataFrame(all_branches)
        display_cols = ['name','code','storekeeper_email','procurement_email','inventory_email','auditor_email','manager_email']
        st.dataframe(df_b[display_cols].rename(columns={
            'name':'Name', 'code':'Code', 'storekeeper_email':'Storekeeper', 'procurement_email':'Procurement',
            'inventory_email':'Inventory', 'auditor_email':'Auditor', 'manager_email':'Manager'
        }))
    else:
        st.info("No branches yet.")

    st.markdown("---")
    st.subheader("➕ Add Single Branch")
    with st.form("add_branch_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Branch Name*")
            code = st.text_input("Branch Code* (e.g., LG01)")
        with col2:
            storekeeper_email = st.text_input("Storekeeper Email")
            procurement_email = st.text_input("Procurement Email")
            inventory_email = st.text_input("Inventory Email")
            auditor_email = st.text_input("Auditor Email")
        submitted = st.form_submit_button("Add Branch")
        if submitted:
            if not name or not code:
                st.error("Name and code are required.")
            else:
                try:
                    supabase.table("branches").insert({
                        "name": name,
                        "code": code,
                        "storekeeper_email": storekeeper_email or None,
                        "procurement_email": procurement_email or None,
                        "inventory_email": inventory_email or None,
                        "auditor_email": auditor_email or None
                    }).execute()
                    st.success(f"Branch '{name}' added.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

    st.markdown("---")
    st.subheader("📁 Upload Branches CSV")
    st.markdown("**CSV columns:** `name`, `code`, `storekeeper_email`, `procurement_email`, `inventory_email`, `auditor_email`")
    template_df = pd.DataFrame(columns=['name','code','storekeeper_email','procurement_email','inventory_email','auditor_email'])
    csv = template_df.to_csv(index=False)
    st.download_button("📥 Download Branch Template", csv, "branches_template.csv", "text/csv")

    uploaded_file = st.file_uploader("Choose branches CSV", type="csv", key="branches_csv")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.dataframe(df.head())
        required = {'name','code'}
        is_valid, msg = validate_csv_columns(df, required, "branches CSV")
        if not is_valid:
            st.error(msg)
            st.stop()
        for col in ['storekeeper_email','procurement_email','inventory_email','auditor_email']:
            if col not in df.columns:
                df[col] = None
        if st.button("Upload Branches"):
            records = df[['name','code','storekeeper_email','procurement_email','inventory_email','auditor_email']].to_dict(orient="records")
            try:
                supabase.table("branches").insert(records).execute()
                st.success("Branches uploaded!")
                st.rerun()
            except Exception as e:
                st.error(f"Upload failed: {e}")
