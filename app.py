import streamlit as st
from utils.auth import check_auth
from utils.db import supabase
# No need to import get_branches – we fetch branches directly

# Import page render functions
from pages.page_dashboard import render as render_dashboard
from pages.page_branches import render as render_branches
from pages.page_products import render as render_products
from pages.page_inventory import render as render_inventory
from pages.page_csv_upload import render as render_csv_upload
from pages.page_alerts import render as render_alerts
from pages.page_ai_limits import render as render_ai_limits
from pages.page_risk_fefo import render as render_risk
from pages.page_transfers import render as render_transfers

# ---- AUTHENTICATION ----
check_auth()

# ---- EMAIL LINK AUTO-MARK ----
params = st.query_params
if "alert_id" in params and "action" in params:
    alert_id = params["alert_id"][0] if isinstance(params["alert_id"], list) else params["alert_id"]
    supabase.table("alert_log").update({
        "action_taken": "Marked done via email link",
        "action_date": "now()"
    }).eq("id", alert_id).execute()
    st.success(f"✅ Alert #{alert_id} marked as done!")
    st.query_params.clear()
    st.rerun()

# ---- GLOBAL BRANCH SELECTOR (direct Supabase call) ----
branches_data = supabase.table("branches").select("*").execute().data
branch_names = [b['name'] for b in branches_data]

selected_branch_name = st.sidebar.selectbox("Select Branch", ["All Branches"] + branch_names)
if selected_branch_name == "All Branches":
    branch_id = None
else:
    branch_id = next(b['id'] for b in branches_data if b['name'] == selected_branch_name)

# ---- PAGE ROUTING ----
PAGES = {
    "Dashboard": render_dashboard,
    "Branches": render_branches,
    "Products": render_products,
    "Inventory": render_inventory,
    "CSV Upload": render_csv_upload,
    "Alerts & Advisories": render_alerts,
    "AI Limits": render_ai_limits,
    "Risk & FEFO": render_risk,
    "Transfer Suggestions": render_transfers,
}

page = st.sidebar.radio("Go to", list(PAGES.keys()))
render_func = PAGES[page]
render_func(branch_id, selected_branch_name)
