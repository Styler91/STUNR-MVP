import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import sqlite3
import numpy as np

# Initialize database connection
conn = sqlite3.connect('stunr_db.sqlite', check_same_thread=False)
c = conn.cursor()

# Audit logging function
def log_audit(user_id, action, details):
    timestamp = datetime.now().isoformat()
    c.execute("INSERT INTO audit_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
              (user_id, action, details, timestamp))
    conn.commit()
    st.write(f"Audit Log: {action} - {details} at {timestamp}")  # Optional feedback

st.markdown('<div class="modern-header">STUNR.ai Billing Dashboard</div>', unsafe_allow_html=True)

# Fetch historical data for analytics
subs_df = pd.read_sql_query("SELECT id, customer_id, plan, amount, start_date, status FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?)", conn, params=(st.session_state['org_id'],))
invoices_df = pd.read_sql_query("SELECT sub_id, date, amount, status FROM invoices WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?))", conn, params=(st.session_state['org_id'],))
usage_df = pd.read_sql_query("SELECT sub_id, timestamp, quantity FROM usage_logs WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?))", conn, params=(st.session_state['org_id'],))
customers_df = pd.read_sql_query("SELECT id FROM customers WHERE org_id = ?", conn, params=(st.session_state['org_id'],))

# Convert dates
subs_df['start_date'] = pd.to_datetime(subs_df['start_date'])
invoices_df['date'] = pd.to_datetime(invoices_df['date'])
usage_df['timestamp'] = pd.to_datetime(usage_df['timestamp'])

# Aggregate monthly revenue
invoices_df['month'] = invoices_df['date'].dt.to_period('M')
monthly_rev = invoices_df[invoices_df['status'] == 'paid'].groupby('month')['amount'].sum().reset_index()
monthly_rev['month'] = monthly_rev['month'].dt.to_timestamp()

# Add cohort column to subs
subs_df['cohort_month'] = subs_df['start_date'].dt.to_period('M')

# Calculate metrics
active_subs = len(subs_df[subs_df['status'] == 'active']) if not subs_df.empty else 0
mrr = subs_df[subs_df['status'] == 'active']['amount'].sum() if not subs_df.empty else 0.0
total_canceled = len(subs_df[subs_df['status'] == 'canceled']) if not subs_df.empty else 0
total_subs = len(subs_df) if not subs_df.empty else 0
churn_rate = (total_canceled / total_subs * 100) if total_subs > 0 else 0.0
total_revenue = invoices_df[invoices_df['status'] == 'paid']['amount'].sum() if not invoices_df.empty else 0.0
deferred_total = pd.read_sql_query("SELECT SUM(amount) as total FROM deferred_revenue WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?))", conn, params=(st.session_state['org_id'],))['total'].iloc[0] if not pd.read_sql_query("SELECT SUM(amount) as total FROM deferred_revenue WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?))", conn, params=(st.session_state['org_id'],)).empty else 0.0
total_customers = len(customers_df) if not customers_df.empty else 0
recent_payments = invoices_df[invoices_df['status'] == 'paid'].sort_values('date', ascending=False).head(5)['amount'].sum() if not invoices_df.empty else 0.0

# Metrics in cards
st.subheader("Key Metrics")
col1, col2, col3, col4, col5, col6 = st.columns(6)
with col1:
    st.metric("Active Subs", active_subs, delta_color="normal")
with col2:
    st.metric("MRR (USDC)", f"{mrr:.2f}", delta_color="normal")
with col3:
    st.metric("Churn Rate", f"{churn_rate:.1f}%", delta_color="inverse")
with col4:
    st.metric("Total Revenue (USDC)", f"{total_revenue:.2f}", delta_color="normal")
with col5:
    value = deferred_total if deferred_total is not None else 0.0
    st.metric("Deferred Revenue (USDC)", f"{value:.2f}", delta_color="normal")
with col6:
    st.metric("Total Customers", total_customers, delta_color="normal")

# Quick Actions with Navigation
st.subheader("Quick Actions")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("Create New Sub", key="quick_create_sub"):
        st.switch_page("pages/customers.py")
with col2:
    if st.button("Initiate Payout", key="quick_initiate_payout"):
        st.switch_page("pages/payments.py")
with col3:
    if st.button("View Reports", key="quick_view_reports"):
        st.switch_page("pages/reporting.py")

# Charts with increased spacing
st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
st.subheader("Cohort Analysis (Retention by Acquisition Month)")
if not subs_df.empty:
    subs_df['month'] = subs_df['start_date'].dt.to_period('M')
    cohort_data = subs_df.groupby(['cohort_month', 'month']).agg(n_customers=('id', 'nunique')).reset_index()
    cohort_data['period'] = (cohort_data['month'] - cohort_data['cohort_month']).apply(lambda x: x.n)
    cohort_pivot = cohort_data.pivot_table(index='cohort_month', columns='period', values='n_customers')
    cohort_pivot = cohort_pivot.divide(cohort_pivot.iloc[:, 0], axis=0) * 100
    st.dataframe(cohort_pivot.style.background_gradient(cmap='viridis'))
    overall_churn = (total_canceled / total_subs * 100) if total_subs > 0 else 0
    st.write(f"Overall Churn Rate: {overall_churn:.1f}% (reduces by 20-30% with optimization)")
else:
    st.write("No subscription data for cohorts.")

st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
st.subheader("Churn by Plan")
if not subs_df.empty:
    churn_by_plan = subs_df.groupby('plan')['status'].apply(lambda x: (x == 'canceled').sum() / len(x) * 100).reset_index(name='churn_rate')
    churn_chart = alt.Chart(churn_by_plan).mark_bar().encode(x='plan', y='churn_rate', color='plan').properties(title="Churn Rate by Plan (%)").interactive()
    st.altair_chart(churn_chart, use_container_width=True)
else:
    st.write("No data for churn by plan.")

st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
st.subheader("Revenue Trends")
if not monthly_rev.empty:
    revenue_chart = alt.Chart(monthly_rev).mark_line().encode(
        x='month:T',
        y='amount:Q',
        color=alt.value('#04837b')
    ).properties(title="Monthly Revenue Trends").interactive()
    st.altair_chart(revenue_chart, use_container_width=True)
else:
    st.write("No revenue data available.")

st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
st.subheader("Customer Segments")
segments_df = pd.read_sql_query("SELECT segment, COUNT(*) as count FROM customer_segments WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?)", conn, params=(st.session_state['org_id'],))
if not segments_df.empty:
    seg_chart = alt.Chart(segments_df).mark_bar().encode(x='segment', y='count', color='segment').properties(title="Customer Segments (High/Low Usage)").interactive()
    st.altair_chart(seg_chart, use_container_width=True)
else:
    st.write("No segment data yet.")

st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
# Charts with increased spacing
usage_df = pd.read_sql_query("SELECT timestamp, quantity FROM usage_logs WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?))", conn, params=(st.session_state['org_id'],))
if not usage_df.empty:
    usage_df['timestamp'] = pd.to_datetime(usage_df['timestamp'])
    chart = alt.Chart(usage_df).mark_line().encode(x='timestamp:T', y='quantity:Q').properties(title="Metered Usage Trends").interactive()
    st.altair_chart(chart, use_container_width=True)

subs_df = pd.read_sql_query("SELECT start_date FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?)", conn, params=(st.session_state['org_id'],))
if not subs_df.empty:
    subs_df['start_date'] = pd.to_datetime(subs_df['start_date'])
    subs_df['cum_subs'] = range(1, len(subs_df) + 1)
    growth_chart = alt.Chart(subs_df).mark_area().encode(x='start_date:T', y='cum_subs:Q').properties(title="Subscription Growth").interactive()
    st.altair_chart(growth_chart, use_container_width=True)