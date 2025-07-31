import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import base64  # For potential wallet hashing

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

# Add new columns to customers table if not exist
try:
    c.execute("ALTER TABLE customers ADD COLUMN street TEXT")
    conn.commit()
except:
    pass
try:
    c.execute("ALTER TABLE customers ADD COLUMN city TEXT")
    conn.commit()
except:
    pass
try:
    c.execute("ALTER TABLE customers ADD COLUMN state TEXT")
    conn.commit()
except:
    pass
try:
    c.execute("ALTER TABLE customers ADD COLUMN zip_code TEXT")
    conn.commit()
except:
    pass

st.header("Onboarding")
onboard_tab1, onboard_tab2 = st.tabs(["New Customer", "Migrate Existing"])

with onboard_tab1:
    st.subheader("New Customer Onboarding")
    wallet_address = st.text_input("Connect Solana Wallet Address (e.g., Phantom)")
    name = st.text_input("Name")
    email = st.text_input("Email")
    street = st.text_input("Street")
    city = st.text_input("City")
    state = st.text_input("State")
    zip_code = st.text_input("Zip/Postal Code")
    country = st.text_input("Country (e.g., US)", "US")
    custom_field = st.text_input("Custom Field (Optional)")
    if st.button("Signup with Wallet"):
        if wallet_address:
            created_at = datetime.now().isoformat()
            c.execute("INSERT INTO customers (name, email, address, street, city, state, zip_code, custom_field, created_at, country, org_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (name, email, wallet_address, street, city, state, zip_code, custom_field, created_at, country, st.session_state['org_id']))
            conn.commit()
            customer_id = c.lastrowid
            st.session_state['current_customer_id'] = customer_id
            log_audit(st.session_state['user_id'], "new_customer_onboard", f"Wallet: {wallet_address}")
            st.success("Onboarded with wallet! Setup subscription next.")
            # AI suggestion (mock)
            st.info("AI Suggestion: Based on wallet, recommend 'Premium' plan for high usage.")

with onboard_tab2:
    st.subheader("Migrate Existing Customers")
    uploaded_file = st.file_uploader("Upload CSV (columns: name,email,address,street,city,state,zip_code,country,opening_balance,billing_day,subscription_plan,subscription_start_date,wallet_address,custom_field)", type="csv")
    if uploaded_file:
        migrate_df = pd.read_csv(uploaded_file)
        if all(col in migrate_df.columns for col in ['name', 'email', 'address', 'country']):
            for index, row in migrate_df.iterrows():
                created_at = datetime.now().isoformat()
                street = row.get('street', '')
                city = row.get('city', '')
                state = row.get('state', '')
                zip_code = row.get('zip_code', '')
                custom_field = row.get('custom_field', '')
                c.execute("INSERT INTO customers (name, email, address, street, city, state, zip_code, custom_field, created_at, country, org_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (row['name'], row['email'], row['address'], street, city, state, zip_code, custom_field, created_at, row['country'], st.session_state['org_id']))
                conn.commit()
                log_audit(st.session_state['user_id'], "migrated_customer", f"Name: {row['name']}")
            st.success("Migration complete! All customers imported.")
        else:
            st.error("CSV must have columns: name, email, address, country.")
    st.info("Blockchain Verification: Data hashed on Solana for integrity (mock).")