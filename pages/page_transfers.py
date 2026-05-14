import streamlit as st
import pandas as pd
from datetime import date, datetime
from collections import defaultdict
from utils.db import supabase
from utils.helpers import get_sales_velocity, get_reorder_point

def render(branch_id, selected_branch_name):
    st.header("🔄 Inter‑Branch Transfer Suggestions")
    st.markdown("""
    **Enterprise logic:** Automatically identifies surplus stock that can be moved to branches with deficit or high demand.
    - **Surplus** = days of inventory > 45 days **OR** quantity > (reorder_point + safety_stock)
    - **Deficit** = days of inventory < 7 days **OR** quantity < reorder_point
    - **Expiry risk** = batches expiring within 30 days with low local demand → transfer to high‑demand branch
    - **High‑value slow movers** = financial exposure > ₦100k and sales velocity < 0.5 units/day → consolidate
    """)

    all_branches = supabase.table("branches").select("id, name").execute().data
    if len(all_branches) < 2:
        st.info("Need at least two branches to suggest transfers. Please add more branches.")
        return
    branch_map = {b['id']: b['name'] for b in all_branches}

    inv_all = supabase.table("inventory").select("""
        id, batch, quantity, expiry_date, branch_id, product_id,
        products(name, sku, cost)
    """).execute().data

    if not inv_all:
        st.info("No inventory data found. Please upload inventory first.")
        return

    # Group data
    branch_product_data = defaultdict(lambda: {
        'total_qty': 0,
        'batches': [],
        'cost': 0,
        'sales_velocity': 0,
        'reorder_point': 0,
        'safety_stock': 0,
        'days_inventory': float('inf')
    })
    velocity_cache = {}
    reorder_cache = {}

    for inv_item in inv_all:
        b_id = inv_item['branch_id']
        p_id = inv_item['product_id']
        key = (b_id, p_id)
        if key not in velocity_cache:
            velocity_cache[key] = get_sales_velocity(b_id, p_id)
        if key not in reorder_cache:
            rp, ss = get_reorder_point(b_id, p_id)
            reorder_cache[key] = (rp, ss)

    for inv_item in inv_all:
        b_id = inv_item['branch_id']
        p_id = inv_item['product_id']
        product = inv_item.get('products') or {}
        cost = float(product.get('cost', 0))
        qty = inv_item.get('quantity', 0)
        expiry = inv_item.get('expiry_date')
        key = (b_id, p_id)

        data = branch_product_data[key]
        data['total_qty'] += qty
        data['cost'] = cost
        data['sales_velocity'] = velocity_cache.get(key, 0.0)
        rp, ss = reorder_cache.get(key, (0,0))
        data['reorder_point'] = rp
        data['safety_stock'] = ss

        if expiry:
            days_left = (datetime.strptime(expiry, '%Y-%m-%d').date() - date.today()).days
            data['batches'].append({
                'batch': inv_item['batch'],
                'qty': qty,
                'expiry_date': expiry,
                'days_left': days_left
            })

    for key, data in branch_product_data.items():
        vel = data['sales_velocity']
        if vel > 0:
            data['days_inventory'] = data['total_qty'] / vel
        else:
            data['days_inventory'] = 999

    # Identify surplus and deficit
    surplus_items = []
    deficit_items = []
    for key, data in branch_product_data.items():
        b_id, p_id = key
        qty = data['total_qty']
        days = data['days_inventory']
        rp = data['reorder_point']
        ss = data['safety_stock']
        is_surplus = (days > 45) or (qty > (rp + ss + 10))
        is_deficit = (days < 7) or (qty < rp)
        if is_surplus:
            surplus_items.append({
                'branch_id': b_id,
                'product_id': p_id,
                'quantity': qty,
                'days_inventory': days,
                'reorder_point': rp,
                'safety_stock': ss,
                'batches': data['batches'],
                'cost': data['cost'],
                'sales_velocity': data['sales_velocity']
            })
        if is_deficit:
            deficit_items.append({
                'branch_id': b_id,
                'product_id': p_id,
                'quantity': qty,
                'days_inventory': days,
                'reorder_point': rp,
                'safety_stock': ss,
                'batches': data['batches'],
                'cost': data['cost'],
                'sales_velocity': data['sales_velocity']
            })

    suggestions = []

    # 1. Surplus -> Deficit
    for surp in surplus_items:
        for defi in deficit_items:
            if surp['product_id'] == defi['product_id'] and surp['branch_id'] != defi['branch_id']:
                transfer_qty = min(surp['quantity'] - (surp['reorder_point'] + surp['safety_stock']),
                                   (defi['reorder_point'] + defi['safety_stock']) - defi['quantity'])
                if transfer_qty > 0:
                    product_name = next((p['products']['name'] for p in inv_all if p['product_id'] == surp['product_id']), 'Unknown')
                    sku = next((p['products']['sku'] for p in inv_all if p['product_id'] == surp['product_id']), '')
                    suggestions.append({
                        'from_branch': branch_map[surp['branch_id']],
                        'to_branch': branch_map[defi['branch_id']],
                        'product_name': product_name,
                        'sku': sku,
                        'quantity': transfer_qty,
                        'reason': f"Surplus in {branch_map[surp['branch_id']]} ({surp['days_inventory']:.0f} days of stock) → deficit in {branch_map[defi['branch_id']]} (only {defi['days_inventory']:.0f} days left).",
                        'urgency': 'HIGH' if defi['days_inventory'] < 3 else 'MEDIUM'
                    })

    # 2. Expiry risk transfer
    for inv_item in inv_all:
        expiry = inv_item.get('expiry_date')
        if not expiry:
            continue
        days_left = (datetime.strptime(expiry, '%Y-%m-%d').date() - date.today()).days
        if days_left <= 30:
            b_id_from = inv_item['branch_id']
            p_id = inv_item['product_id']
            vel_from = velocity_cache.get((b_id_from, p_id), 0.0)
            if vel_from <= 0.5:
                best_target = None
                best_vel = vel_from
                for target_branch in all_branches:
                    t_id = target_branch['id']
                    if t_id == b_id_from:
                        continue
                    vel_to = velocity_cache.get((t_id, p_id), 0.0)
                    if vel_to > best_vel:
                        best_vel = vel_to
                        best_target = t_id
                if best_target and best_vel > vel_from + 0.2:
                    suggestions.append({
                        'from_branch': branch_map[b_id_from],
                        'to_branch': branch_map[best_target],
                        'product_name': inv_item['products']['name'],
                        'sku': inv_item['products']['sku'],
                        'quantity': inv_item['quantity'],
                        'reason': f"Batch expires in {days_left} days, but current branch has very low demand ({vel_from:.1f} units/day). Transfer to {branch_map[best_target]} where demand is {best_vel:.1f} units/day to avoid waste.",
                        'urgency': 'CRITICAL' if days_left <= 7 else 'HIGH'
                    })

    # 3. High-value slow movers
    for key, data in branch_product_data.items():
        b_id, p_id = key
        if data['total_qty'] * data['cost'] > 100000 and data['sales_velocity'] < 0.5:
            if len(all_branches) > 1:
                target_branch = all_branches[0]['id']
                if target_branch == b_id:
                    target_branch = all_branches[1]['id']
                product_name = next((p['products']['name'] for p in inv_all if p['product_id'] == p_id), 'Unknown')
                sku = next((p['products']['sku'] for p in inv_all if p['product_id'] == p_id), '')
                suggestions.append({
                    'from_branch': branch_map[b_id],
                    'to_branch': branch_map[target_branch],
                    'product_name': product_name,
                    'sku': sku,
                    'quantity': data['total_qty'],
                    'reason': f"High‑value slow mover (₦{data['total_qty']*data['cost']:,.0f} value, {data['sales_velocity']:.1f} units/day). Consolidate to reduce holding cost.",
                    'urgency': 'MEDIUM'
                })

    # Deduplicate
    unique_suggestions = []
    seen = set()
    for s in suggestions:
        key = (s['from_branch'], s['to_branch'], s['product_name'])
        if key not in seen:
            seen.add(key)
            unique_suggestions.append(s)

    if unique_suggestions:
        df_sugg = pd.DataFrame(unique_suggestions)
        urgency_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2}
        df_sugg['urgency_num'] = df_sugg['urgency'].map(urgency_order)
        df_sugg = df_sugg.sort_values('urgency_num')
        st.subheader("📋 Suggested Transfers")
        st.dataframe(df_sugg[['from_branch', 'to_branch', 'product_name', 'sku', 'quantity', 'urgency', 'reason']])
        st.subheader("📊 Summary by Urgency")
        st.bar_chart(df_sugg['urgency'].value_counts())
    else:
        st.success("✅ No transfer suggestions at this time. Inventory appears well balanced.")

    with st.expander("ℹ️ How suggestions are generated"):
        st.markdown("""
        - **Surplus → Deficit:** A branch has >45 days of stock or exceeds reorder point + safety stock; another branch is below reorder point.
        - **Expiry risk transfer:** Batch expiring in ≤30 days located in a slow‑selling branch is suggested to move to a branch with higher demand for that product.
        - **High‑value slow movers:** Products with total value >₦100,000 and sales velocity <0.5 units/day are recommended for consolidation.
        """)
