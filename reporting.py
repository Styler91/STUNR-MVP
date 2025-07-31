import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import sqlite3

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

st.header("Reporting")
report_tab1, report_tab2 = st.tabs(["Revenue Report", "Custom Report"])

with report_tab1:
    st.subheader("Revenue Report")
    start_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=30))
    end_date = st.date_input("End Date", value=datetime.now())
    if start_date and end_date and start_date <= end_date:
        recognized_df = pd.read_sql_query("SELECT month AS Month, SUM(recognized_amount) AS 'Recognized Revenue (USDC)' FROM recognized_revenue WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?)) AND month BETWEEN ? AND ? GROUP BY month", conn, params=(st.session_state['org_id'], start_date.strftime('%Y-%m'), end_date.strftime('%Y-%m')))
        deferred_df = pd.read_sql_query("SELECT start_date AS 'Start Date', end_date AS 'End Date', SUM(amount) AS 'Deferred Revenue (USDC)' FROM deferred_revenue WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?)) AND start_date BETWEEN ? AND ? GROUP BY start_date, end_date", conn, params=(st.session_state['org_id'], start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        if not recognized_df.empty:
            st.subheader("Recognized Revenue")
            st.dataframe(recognized_df, use_container_width=True, hide_index=True)
            chart = alt.Chart(recognized_df).mark_bar().encode(x='Month:T', y='Recognized Revenue (USDC):Q', color=alt.value('#04837b')).properties(title="Recognized Revenue Over Time").interactive()
            st.altair_chart(chart, use_container_width=True)
        if not deferred_df.empty:
            st.subheader("Deferred Revenue")
            st.dataframe(deferred_df, use_container_width=True, hide_index=True)
        if recognized_df.empty and deferred_df.empty:
            st.write("No revenue data for the selected period.")
    else:
        st.error("Please ensure Start Date is not after End Date.")

with report_tab2:
    st.subheader("Custom Report")
    metric = st.selectbox("Select Metric", ["Active Subscriptions", "MRR", "Churn Rate", "Total Revenue", "Deferred Revenue"])
    time_period = st.selectbox("Time Period", ["Last 7 Days", "Last 30 Days", "Last 90 Days", "All Time"])
    if st.button("Generate Report"):
        end_date = datetime.now()
        if time_period == "Last 7 Days":
            start_date = end_date - timedelta(days=7)
        elif time_period == "Last 30 Days":
            start_date = end_date - timedelta(days=30)
        elif time_period == "Last 90 Days":
            start_date = end_date - timedelta(days=90)
        else:
            start_date = datetime(1970, 1, 1)  # All time
        subs_df = pd.read_sql_query("SELECT id, customer_id, plan, amount, start_date, status FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?) AND start_date BETWEEN ? AND ?", conn, params=(st.session_state['org_id'], start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        invoices_df = pd.read_sql_query("SELECT sub_id, date, amount, status FROM invoices WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?)) AND date BETWEEN ? AND ?", conn, params=(st.session_state['org_id'], start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        if not subs_df.empty and not invoices_df.empty:
            subs_df['start_date'] = pd.to_datetime(subs_df['start_date'])
            invoices_df['date'] = pd.to_datetime(invoices_df['date'])
            if metric == "Active Subscriptions":
                active_subs = len(subs_df[subs_df['status'] == 'active'])
                st.write(f"Active Subscriptions: {active_subs}")
            elif metric == "MRR":
                mrr = subs_df[subs_df['status'] == 'active']['amount'].sum()
                st.write(f"MRR: ${mrr:.2f} USDC")
            elif metric == "Churn Rate":
                total_canceled = len(subs_df[subs_df['status'] == 'canceled'])
                total_subs = len(subs_df)
                churn_rate = (total_canceled / total_subs * 100) if total_subs > 0 else 0.0
                st.write(f"Churn Rate: {churn_rate:.1f}%")
            elif metric == "Total Revenue":
                total_revenue = invoices_df[invoices_df['status'] == 'paid']['amount'].sum()
                st.write(f"Total Revenue: ${total_revenue:.2f} USDC")
            elif metric == "Deferred Revenue":
                deferred_total = pd.read_sql_query("SELECT SUM(amount) as total FROM deferred_revenue WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?)) AND start_date BETWEEN ? AND ?", conn, params=(st.session_state['org_id'], start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))['total'].iloc[0] if not pd.read_sql_query("SELECT SUM(amount) as total FROM deferred_revenue WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?)) AND start_date BETWEEN ? AND ?", conn, params=(st.session_state['org_id'], start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))).empty else 0.0
                st.write(f"Deferred Revenue: ${deferred_total:.2f} USDC")
        else:
            st.write("No data available for the selected period.")