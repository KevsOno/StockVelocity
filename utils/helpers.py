import streamlit as st
import pandas as pd
from datetime import date, timedelta
from utils.db import supabase

def validate_csv_columns(df, required_cols, label="CSV"):
    missing = required_cols - set(df.columns)
    if missing:
        return False, f"❌ Missing columns in {label}: {', '.join(missing)}\n\n📋 Required: {', '.join(required_cols)}"
    return True, ""

def upload_csv_to_table(table_name, df, extra_columns={}):
    for col, val in extra_columns.items():
        df[col] = val
    records = df.to_dict(orient="records")
    try:
        res = supabase.table(table_name).insert(records).execute()
        return res
    except Exception as e:
        st.error(f"Error inserting into {table_name}: {e}")
        return None

def get_sales_velocity(branch_id, product_id, days_back=30):
    """Returns avg daily demand (units/day) for product+branch."""
    limit_res = supabase.table("stock_limits").select("avg_daily_demand") \
        .eq("branch_id", branch_id).eq("product_id", product_id).execute()
    if limit_res.data and limit_res.data[0].get("avg_daily_demand") is not None:
        return float(limit_res.data[0]["avg_daily_demand"])
    
    start_date = (date.today() - timedelta(days=days_back)).isoformat()
    mov_res = supabase.table("stock_movements").select("quantity_change") \
        .eq("branch_id", branch_id).eq("product_id", product_id) \
        .gte("movement_date", start_date).execute()
    if mov_res.data:
        total_sold = abs(sum(m["quantity_change"] for m in mov_res.data if m["quantity_change"] < 0))
        return total_sold / days_back
    return 0.0

def get_reorder_point(branch_id, product_id):
    """Fetch reorder point from stock_limits if exists, else compute from demand (lead time 7 days)."""
    lim = supabase.table("stock_limits").select("reorder_point, safety_stock") \
        .eq("branch_id", branch_id).eq("product_id", product_id).execute()
    if lim.data:
        return lim.data[0].get("reorder_point", 0), lim.data[0].get("safety_stock", 0)
    demand = get_sales_velocity(branch_id, product_id)
    reorder = max(5, int(demand * 7))
    safety = max(3, int(demand * 3))
    return reorder, safety

# NEW FUNCTION – fetches all branches and returns (branches_list, branch_names, branch_map)
def get_branches():
    """Returns (branches_data, branch_names, branch_options) where:
       - branches_data: list of all branch dicts
       - branch_names: list of branch names
       - branch_options: dict {branch_name: branch_id}
    """
    branches_data = supabase.table("branches").select("*").execute().data
    branch_names = [b['name'] for b in branches_data]
    branch_options = {b['name']: b['id'] for b in branches_data}
    return branches_data, branch_names, branch_options
