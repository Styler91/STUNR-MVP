import streamlit as st
from streamlit.web.server.websocket_headers import _get_websocket_headers
import pandas as pd
import sqlite3
from datetime import datetime
import bcrypt
import yaml
from yaml.loader import SafeLoader
import stripe
import numpy as np  # For mock data

# Sidebar for navigation
st.sidebar.title("STUNR Navigation")
page = st.sidebar.radio("Go to", ["🏠 Dashboard", "💸 Payment", "📝 Sub Setup", "⚙️ Admin", "👤 Portal", "📤 Payouts", "👥 Customers", "🧾 Invoices", "🔄 Txns", "🛒 Products", "🗳 Taxes", "📊 Reporting"])

# Connect to your database
conn = sqlite3.connect('stunr_db.sqlite')
c = conn.cursor()

# Get the customer data
customers_df = pd.read_sql_query("SELECT id, name, email, address, street, city, state, zip_code, custom_field, country, created_at FROM customers WHERE org_id = ?", conn, params=(1,))
customers_df['sub_status'] = [c.execute("SELECT status FROM subscriptions WHERE customer_id = ? LIMIT 1", (row['id'],)).fetchone()[0] if c.execute("SELECT status FROM subscriptions WHERE customer_id = ? LIMIT 1", (row['id'],)).fetchone() else "None" for index, row in customers_df.iterrows()]

# Audit logging function
def log_audit(user_id, action, details):
    timestamp = datetime.now().isoformat()
    c.execute("INSERT INTO audit_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)", (user_id, action, details, timestamp))
    conn.commit()
    st.write(f"Audit Log: {action} - {details} at {timestamp}")

# Fetch or initialize invoice settings
settings = c.execute("SELECT * FROM invoice_settings").fetchone()
if not settings:
    c.execute("INSERT INTO invoice_settings (company_name, company_address, logo_url, footer_text, primary_color, font) VALUES (?, ?, ?, ?, ?, ?)",
              ("STUNR.ai", "Mock Merchant Address", "", "Thank you for your business! Contact: support@stunr.ai", '#6772e5', 'Helvetica'))
    conn.commit()
    settings = c.execute("SELECT * FROM invoice_settings").fetchone()

# Fetch or initialize payment settings
payment_settings = c.execute("SELECT * FROM payment_settings").fetchone()
if not payment_settings:
    c.execute("INSERT INTO payment_settings (stripe_publishable_key, stripe_secret_key) VALUES (?, ?)",
              ("pk_test_...", "sk_test_..."))  # Replace with real test keys
    conn.commit()
    payment_settings = c.execute("SELECT * FROM payment_settings").fetchone()
stripe.api_key = payment_settings[2]  # Secret key

# Mock Solana/USDC data (replace with real API later)
def mock_solana_balance():
    return round(np.random.uniform(0, 1000), 2)

# Page content
if page == "🏠 Dashboard":
    st.header("Dashboard")
    st.write("Metrics: Active Subs:", len(customers_df[customers_df['sub_status'] == 'active']), "MRR:", round(len(customers_df) * 10, 2), "Churn Rate:", round(np.random.uniform(0, 5), 2), "%")
    st.write("Cohort analysis, churn charts, customer segments, usage trends, subscription growth, quick actions (create sub, initiate payout) to be added!")
elif page == "💸 Payment":
    st.header("Payment")
    st.write("Create one-time payment intents (Solana USDC QR code or Stripe card/bank), wait for confirmation to be added!")
    if st.button("Generate Payment Intent"):
        st.write("Mock Solana QR or Stripe intent here—add real API later!")
elif page == "📝 Sub Setup":
    st.header("Sub Setup")
    st.write("Set up subscriptions (plans, trials, coupons, taxes, entitlements), with prorating and deferred revenue logging to be added!")
    if st.button("Create Subscription"):
        st.write("Mock subscription setup—add plans later!")
elif page == "⚙️ Admin":
    st.header("Admin")
    admin_tab1, admin_tab2 = st.tabs(["User Management", "Settings"])
    with admin_tab1:
        st.subheader("User Management")
        users_df = pd.read_sql_query("SELECT id AS ID, username AS Username, email AS Email, name AS Name, role AS Role, created_at AS 'Created At' FROM users WHERE org_id = ? OR org_id IS NULL", conn, params=(1,))
        if not users_df.empty:
            search_query = st.text_input("Search Users (Username, Email, Name)", placeholder="Search by username or email...")
            if search_query:
                users_df = users_df[
                    users_df['Username'].str.contains(search_query, case=False) |
                    users_df['Email'].str.contains(search_query, case=False) |
                    users_df['Name'].str.contains(search_query, case=False)
                ]
            st.dataframe(users_df, use_container_width=True, hide_index=True)
        else:
            st.write("No users yet.")
        new_username = st.text_input("New Username")
        new_email = st.text_input("New Email")
        new_name = st.text_input("New Name")
        new_password = st.text_input("New Password", type="password")
        new_role = st.selectbox("Role", ["user", "admin"])
        if st.button("Add User"):
            if new_username and new_email and new_name and new_password:
                hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
                created_at = datetime.now().isoformat()
                try:
                    c.execute("INSERT INTO users (username, email, password, name, role, created_at, org_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (new_username, new_email, hashed_password.decode(), new_name, new_role, created_at, 1))
                    conn.commit()
                    log_audit(1, "added_user", f"Username: {new_username}")
                    st.success("User added successfully!")
                except sqlite3.IntegrityError:
                    st.error("Username already exists.")
            else:
                st.error("Fill all fields.")
        if not users_df.empty:
            selected_user = st.selectbox("Edit User", [f"ID: {user['ID']} - {user['Username']}" for _, user in users_df.iterrows()])
            user_id = int(selected_user.split("ID: ")[1].split(" - ")[0])
            user_data = c.execute("SELECT id, username, email, name, role, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
            if user_data:
                edit_username = st.text_input("Edit Username", value=user_data[1])
                edit_email = st.text_input("Edit Email", value=user_data[2])
                edit_name = st.text_input("Edit Name", value=user_data[3])
                edit_role = st.selectbox("Edit Role", ["user", "admin"], index=0 if user_data[4] == "user" else 1)
                edit_password = st.text_input("New Password (leave blank to keep current)", type="password")
                if st.button("Update User"):
                    updates = {"username": edit_username, "email": edit_email, "name": edit_name, "role": edit_role}
                    if edit_password:
                        updates["password"] = bcrypt.hashpw(edit_password.encode(), bcrypt.gensalt()).decode()
                    query_parts = [f"{k} = ?" for k in updates.keys()]
                    query = f"UPDATE users SET {', '.join(query_parts)} WHERE id = ?"
                    values = list(updates.values()) + [user_id]
                    c.execute(query, values)
                    conn.commit()
                    log_audit(1, "updated_user", f"ID: {user_id}, Username: {edit_username}")
                    st.success("User updated successfully!")
                if st.button("Delete User", key=f"delete_user_{user_id}"):
                    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
                    conn.commit()
                    log_audit(1, "deleted_user", f"ID: {user_id}")
                    st.success("User deleted successfully!")
                    st.experimental_rerun()
    with admin_tab2:
        st.subheader("Settings")
        company_name = st.text_input("Company Name", value=settings[1] if settings else "STUNR.ai")
        company_address = st.text_input("Company Address", value=settings[2] if settings else "Mock Merchant Address")
        logo_url = st.text_input("Logo URL", value=settings[3] if settings else "")
        footer_text = st.text_input("Footer Text", value=settings[4] if settings else "Thank you for your business! Contact: support@stunr.ai")
        primary_color = st.color_picker("Primary Color", value=settings[5] if settings else "#6772e5")
        font = st.selectbox("Font", ["Helvetica", "Arial", "Times New Roman"], index=["Helvetica", "Arial", "Times New Roman"].index(settings[6] if settings else "Helvetica"))
        if st.button("Save Settings"):
            if settings:
                c.execute("UPDATE invoice_settings SET company_name = ?, company_address = ?, logo_url = ?, footer_text = ?, primary_color = ?, font = ? WHERE id = ?",
                          (company_name, company_address, logo_url, footer_text, primary_color, font, settings[0]))
            else:
                c.execute("INSERT INTO invoice_settings (company_name, company_address, logo_url, footer_text, primary_color, font) VALUES (?, ?, ?, ?, ?, ?)",
                          (company_name, company_address, logo_url, footer_text, primary_color, font))
            conn.commit()
            log_audit(1, "updated_settings", "Invoice settings updated")
            st.success("Settings saved successfully!")
        stripe_pk = st.text_input("Stripe Publishable Key", value=payment_settings[1] if payment_settings else "pk_test_...")
        stripe_sk = st.text_input("Stripe Secret Key", value=payment_settings[2] if payment_settings else "sk_test_...", type="password")
        if st.button("Update Payment Settings"):
            if payment_settings:
                c.execute("UPDATE payment_settings SET stripe_publishable_key = ?, stripe_secret_key = ? WHERE id = ?",
                          (stripe_pk, stripe_sk, payment_settings[0]))
            else:
                c.execute("INSERT INTO payment_settings (stripe_publishable_key, stripe_secret_key) VALUES (?, ?)",
                          (stripe_pk, stripe_sk))
            conn.commit()
            stripe.api_key = stripe_sk
            log_audit(1, "updated_payment_settings", "Payment settings updated")
            st.success("Payment settings updated successfully!")
        webhook_event = st.selectbox("Webhook Event", ["payment_success", "sub_cancel", "invoice_paid"])
        webhook_url = st.text_input("Webhook URL")
        if st.button("Add Webhook"):
            if webhook_event and webhook_url:
                c.execute("INSERT INTO webhooks (event, url) VALUES (?, ?)", (webhook_event, webhook_url))
                conn.commit()
                log_audit(1, "added_webhook", f"Event: {webhook_event}, URL: {webhook_url}")
                st.success("Webhook added successfully!")
            else:
                st.error("Please fill all fields.")
        webhooks_df = pd.read_sql_query("SELECT id AS ID, event AS Event, url AS URL FROM webhooks", conn)
        if not webhooks_df.empty:
            st.dataframe(webhooks_df, use_container_width=True, hide_index=True)
            selected_webhook = st.selectbox("Edit Webhook", [f"ID: {row['ID']} - {row['Event']}" for _, row in webhooks_df.iterrows()])
            webhook_id = int(selected_webhook.split("ID: ")[1].split(" - ")[0])
            webhook_data = c.execute("SELECT id, event, url FROM webhooks WHERE id = ?", (webhook_id,)).fetchone()
            if webhook_data:
                edit_event = st.selectbox("Edit Event", ["payment_success", "sub_cancel", "invoice_paid"], index=["payment_success", "sub_cancel", "invoice_paid"].index(webhook_data[1]))
                edit_url = st.text_input("Edit URL", value=webhook_data[2])
                if st.button("Update Webhook", key=f"update_webhook_{webhook_id}"):
                    c.execute("UPDATE webhooks SET event = ?, url = ? WHERE id = ?", (edit_event, edit_url, webhook_id))
                    conn.commit()
                    log_audit(1, "updated_webhook", f"ID: {webhook_id}")
                    st.success("Webhook updated successfully!")
                if st.button("Delete Webhook", key=f"delete_webhook_{webhook_id}"):
                    c.execute("DELETE FROM webhooks WHERE id = ?", (webhook_id,))
                    conn.commit()
                    log_audit(1, "deleted_webhook", f"ID: {webhook_id}")
                    st.success("Webhook deleted successfully!")
                    st.experimental_rerun()
elif page == "👤 Portal":
    st.header("Portal")
    st.write("Customer self-service to view/upgrade/cancel subs, with upsell prompts for high-usage users to be added!")
elif page == "📤 Payouts":
    st.header("Payouts")
    st.write(f"Balance: {mock_solana_balance()} USDC")  # Mock balance
    st.write("Initiate USDC payouts to Solana addresses, log history to be added!")
    if st.button("Initiate Payout"):
        st.write("Mock payout initiated—add Solana transfer later!")
elif page == "👥 Customers":
    st.header("Customers")
    st.write("Add new customers, searchable/exportable table already in Customer List—expand if needed!")
elif page == "🧾 Invoices":
    st.header("Invoices")
    st.write("Filter and view invoices, update status, send emails, download CSV/PDF to be added!")
elif page == "🔄 Txns":
    st.header("Transactions")
    st.write("Search and list transaction logs, with webhook endpoint info to be added!")
elif page == "🛒 Products":
    st.header("Products")
    st.write("Add/edit/delete products (name, description, price, image, billing frequency, active status) to be added!")
elif page == "🗳 Taxes":
    st.header("Taxes")
    st.write("Manage tax rules (add country/rate), show total tax collected metric to be added!")
    if st.button("Add Tax Rule"):
        st.write("Mock tax rule added—add country/rate later!")
elif page == "📊 Reporting":
    st.header("Reporting")
    st.write("Advanced reports on revenue, churn (cohorts/plans), CLV, tax, usage; with charts and CSV exports to be added!")

# Mock dunning (auto-run on load)
st.write("Running mock dunning...")
for index, row in customers_df.iterrows():
    if row['sub_status'] == 'unpaid':
        st.write(f"Retrying payment for {row['name']}... Mock success!")
        c.execute("UPDATE subscriptions SET status = 'active' WHERE customer_id = ?", (row['id'],))
        conn.commit()
st.write("Dunning complete.")

# Note: CSV export might not save locally; we'll adjust if needed