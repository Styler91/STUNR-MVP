import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import bcrypt
import yaml
from yaml.loader import SafeLoader
import stripe

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

st.header("Admin")
admin_tab1, admin_tab2 = st.tabs(["User Management", "Settings"])

with admin_tab1:
    st.subheader("User Management")
    # Use a safer query to handle missing org_id
    users_df = pd.read_sql_query("SELECT id AS ID, username AS Username, email AS Email, name AS Name, role AS Role, created_at AS 'Created At' FROM users WHERE org_id = ? OR org_id IS NULL", conn, params=(st.session_state['org_id'],))
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
                          (new_username, new_email, hashed_password.decode(), new_name, new_role, created_at, st.session_state['org_id']))
                conn.commit()
                log_audit(st.session_state['user_id'], "added_user", f"Username: {new_username}")
                st.success("User added successfully!")
                # Update config.yaml dynamically (mock)
                with open('config.yaml', 'r') as file:
                    config_data = yaml.load(file, Loader=SafeLoader)
                config_data['credentials']['usernames'][new_username] = {
                    'email': new_email,
                    'name': new_name,
                    'password': new_password
                }
                with open('config.yaml', 'w') as file:
                    yaml.dump(config_data, file)
                st.info("Config updated (mock) - restart app for changes to take effect.")
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
                log_audit(st.session_state['user_id'], "updated_user", f"ID: {user_id}, Username: {edit_username}")
                st.success("User updated successfully!")
                # Mock config update
                with open('config.yaml', 'r') as file:
                    config_data = yaml.load(file, Loader=SafeLoader)
                config_data['credentials']['usernames'][edit_username] = {
                    'email': edit_email,
                    'name': edit_name,
                    'password': edit_password if edit_password else config_data['credentials']['usernames'][user_data[1]]['password']
                }
                if user_data[1] != edit_username:
                    del config_data['credentials']['usernames'][user_data[1]]
                with open('config.yaml', 'w') as file:
                    yaml.dump(config_data, file)
                st.info("Config updated (mock) - restart app for changes to take effect.")
            if st.button("Delete User", key=f"delete_user_{user_id}"):
                c.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
                log_audit(st.session_state['user_id'], "deleted_user", f"ID: {user_id}")
                st.success("User deleted successfully!")
                # Mock config update
                with open('config.yaml', 'r') as file:
                    config_data = yaml.load(file, Loader=SafeLoader)
                if user_data[1] in config_data['credentials']['usernames']:
                    del config_data['credentials']['usernames'][user_data[1]]
                with open('config.yaml', 'w') as file:
                    yaml.dump(config_data, file)
                st.info("Config updated (mock) - restart app for changes to take effect.")
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
        log_audit(st.session_state['user_id'], "updated_settings", "Invoice settings updated")
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
        log_audit(st.session_state['user_id'], "updated_payment_settings", "Payment settings updated")
        st.success("Payment settings updated successfully!")

    webhook_event = st.selectbox("Webhook Event", ["payment_success", "sub_cancel", "invoice_paid"])
    webhook_url = st.text_input("Webhook URL")
    if st.button("Add Webhook"):
        if webhook_event and webhook_url:
            c.execute("INSERT INTO webhooks (event, url) VALUES (?, ?)", (webhook_event, webhook_url))
            conn.commit()
            log_audit(st.session_state['user_id'], "added_webhook", f"Event: {webhook_event}, URL: {webhook_url}")
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
                log_audit(st.session_state['user_id'], "updated_webhook", f"ID: {webhook_id}")
                st.success("Webhook updated successfully!")
            if st.button("Delete Webhook", key=f"delete_webhook_{webhook_id}"):
                c.execute("DELETE FROM webhooks WHERE id = ?", (webhook_id,))
                conn.commit()
                log_audit(st.session_state['user_id'], "deleted_webhook", f"ID: {webhook_id}")
                st.success("Webhook deleted successfully!")
                st.experimental_rerun()