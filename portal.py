import streamlit as st
import sqlite3
from datetime import datetime

# Initialize database connection
conn = sqlite3.connect('stunr_db.sqlite', check_same_thread=False)
c = conn.cursor()

# Mock email sender
def mock_email(to_email, subject, body, attachment=None):
    st.info(f"Email sent to {to_email}: Subject - {subject}\nBody - {body}\nAttachment - {attachment if attachment else 'None'}")

# Audit logging function
def log_audit(user_id, action, details):
    timestamp = datetime.now().isoformat()
    c.execute("INSERT INTO audit_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
              (user_id, action, details, timestamp))
    conn.commit()
    st.write(f"Audit Log: {action} - {details} at {timestamp}")  # Optional feedback

st.header("Customer Portal")
portal_addr = st.text_input("Your Address")
if portal_addr:
    customer_id = c.execute("SELECT id FROM customers WHERE address = ? AND org_id = ?", (portal_addr, st.session_state['org_id'])).fetchone()
    if customer_id:
        customer_id = customer_id[0]
        segment = c.execute("SELECT segment FROM customer_segments WHERE customer_id = ?", (customer_id,)).fetchone()
        segment = segment[0] if segment else 'low'
        customer_subs = c.execute("SELECT * FROM subscriptions WHERE customer_id = ?", (customer_id,)).fetchall()
        if customer_subs:
            sub = customer_subs[0]
            if segment == 'high':
                st.warning("Your usage is high! Upgrade for more features and get 1 USDC reward.")
                if st.button("Upgrade to Premium"):
                    reward_amount = 1.0
                    reward_tx = "mock_reward_tx"
                    c.execute("UPDATE subscriptions SET plan = 'Premium ($10/month USDC)', amount = 10.0 WHERE customer_id = ?", (customer_id,))
                    c.execute("INSERT INTO upsell_logs (sub_id, customer_id, upsell_type, status, reward_tx, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                              (sub[0], customer_id, 'premium', 'success', reward_tx, datetime.now().isoformat()))
                    conn.commit()
                    mock_email("customer@email.com", "Upgrade Offer", "Upgrade and claim your reward!")
                    log_audit(st.session_state['user_id'], "upsell", f"Sub ID: {sub[0]}")
                    st.success(f"Upgraded! Reward sent (Tx: {reward_tx})")
            for sub in customer_subs:
                st.write(f"Plan: {sub[2]}, Status: {sub[5]}")
                if st.button(f"Cancel {sub[0]}", key=f"portal_cancel_{sub[0]}"):
                    c.execute("UPDATE subscriptions SET status = 'canceled' WHERE id = ?", (sub[0],))
                    conn.commit()
                    webhooks = c.execute("SELECT url FROM webhooks WHERE event = 'sub_cancel'").fetchall()
                    for hook in webhooks:
                        url = hook[0]
                        payload = json.dumps({"event": "sub_cancel", "sub_id": sub[0]})
                        st.info(f"Mock POST to {url}: {payload}")
                    log_audit(st.session_state['user_id'], "canceled_subscription", f"Sub ID: {sub[0]}")
                    st.success("Canceled.")
    else:
        st.warning("No customer found for this address.")