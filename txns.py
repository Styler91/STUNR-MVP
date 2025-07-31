import streamlit as st
import pandas as pd
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

st.header("Transactions")
txn_tab1, txn_tab2 = st.tabs(["Transaction Log", "Revenue Recognition"])

with txn_tab1:
    st.subheader("Transaction Log")
    # Modified query to avoid merchant_keypair dependency, focusing on customer transactions
    txns_df = pd.read_sql_query("SELECT id AS ID, tx_sig AS 'Transaction Signature', amount AS 'Amount (USDC)', from_addr AS 'From Address', timestamp AS 'Timestamp', status AS Status FROM transactions WHERE from_addr IN (SELECT address FROM customers WHERE org_id = ?)", conn, params=(st.session_state['org_id'],))
    if not txns_df.empty:
        search_query = st.text_input("Search Transactions (ID, Signature, Status)", placeholder="Search by ID or status...")
        if search_query:
            txns_df = txns_df[
                txns_df['ID'].astype(str).str.contains(search_query, case=False) |
                txns_df['Transaction Signature'].str.contains(search_query, case=False) |
                txns_df['Status'].str.contains(search_query, case=False)
            ]
        st.dataframe(txns_df, use_container_width=True, hide_index=True)
        csv = txns_df.to_csv(index=False)
        st.download_button("Export Transactions to CSV", csv, "transactions.csv", "text/csv")
    else:
        st.write("No transactions logged yet.")

with txn_tab2:
    st.subheader("Revenue Recognition")
    recognized_df = pd.read_sql_query("SELECT id AS ID, sub_id AS 'Subscription ID', month AS Month, amount AS 'Total Amount (USDC)', recognized_amount AS 'Recognized Amount (USDC)', prorated AS Prorated FROM recognized_revenue WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?))", conn, params=(st.session_state['org_id'],))
    deferred_df = pd.read_sql_query("SELECT id AS ID, sub_id AS 'Subscription ID', amount AS 'Deferred Amount (USDC)', start_date AS 'Start Date', end_date AS 'End Date', status AS Status FROM deferred_revenue WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?))", conn, params=(st.session_state['org_id'],))
    if not recognized_df.empty or not deferred_df.empty:
        st.subheader("Recognized Revenue")
        st.dataframe(recognized_df, use_container_width=True, hide_index=True)
        st.subheader("Deferred Revenue")
        st.dataframe(deferred_df, use_container_width=True, hide_index=True)
    else:
        st.write("No revenue recognition data yet.")