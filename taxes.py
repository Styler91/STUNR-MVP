import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime  # Added missing import
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

# Fetch or initialize payment settings for Stripe
payment_settings = c.execute("SELECT * FROM payment_settings").fetchone()
if not payment_settings:
    c.execute("INSERT INTO payment_settings (stripe_publishable_key, stripe_secret_key) VALUES (?, ?)",
              ("pk_test_...", "sk_test_..."))  # Replace with real test keys
    conn.commit()
    payment_settings = c.execute("SELECT * FROM payment_settings").fetchone()
stripe.api_key = payment_settings[2]  # Secret key

st.header("Taxes")
tax_tab1, tax_tab2 = st.tabs(["Tax Rules", "Apply Tax"])

with tax_tab1:
    st.subheader("Tax Rules")
    tax_rules_df = pd.read_sql_query("SELECT id AS ID, country AS Country, rate AS 'Tax Rate (%)' FROM tax_rules", conn)
    if not tax_rules_df.empty:
        st.dataframe(tax_rules_df, use_container_width=True, hide_index=True)
    else:
        st.write("No tax rules defined yet.")

    country = st.text_input("Country Code (e.g., US)")
    rate = st.number_input("Tax Rate (%)", min_value=0.0, max_value=100.0, value=0.0)
    if st.button("Add Tax Rule"):
        if country:
            c.execute("INSERT INTO tax_rules (country, rate) VALUES (?, ?)", (country.upper(), rate))
            conn.commit()
            log_audit(st.session_state['user_id'], "added_tax_rule", f"Country: {country}, Rate: {rate}%")
            st.success("Tax rule added successfully!")

with tax_tab2:
    st.subheader("Apply Tax")
    invoices = c.execute("SELECT id, sub_id, date, amount, due_date FROM invoices WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?))", (st.session_state['org_id'],)).fetchall()
    if invoices:
        selected_invoice = st.selectbox("Select Invoice", [f"ID: {inv[0]} - {inv[2]} - ${inv[3]} USDC" for inv in invoices])
        invoice_id = int(selected_invoice.split("ID: ")[1].split(" - ")[0])
        invoice_data = c.execute("SELECT i.id, i.amount, s.customer_id, c.country FROM invoices i JOIN subscriptions s ON i.sub_id = s.id JOIN customers c ON s.customer_id = c.id WHERE i.id = ?", (invoice_id,)).fetchone()
        if invoice_data:
            invoice_id, amount, customer_id, country = invoice_data
            tax_rate = c.execute("SELECT rate FROM tax_rules WHERE country = ?", (country,)).fetchone()
            tax_rate = tax_rate[0] if tax_rate else 0.0
            tax_amount = amount * (tax_rate / 100)
            total_amount = amount + tax_amount
            st.write(f"Tax Rate: {tax_rate}%")
            st.write(f"Tax Amount: ${tax_amount:.2f} USDC")
            st.write(f"Total Amount: ${total_amount:.2f} USDC")
            if st.button("Apply Tax"):
                c.execute("UPDATE invoices SET amount = ? WHERE id = ?", (total_amount, invoice_id))
                conn.commit()
                log_audit(st.session_state['user_id'], "applied_tax", f"Invoice ID: {invoice_id}, Tax Rate: {tax_rate}%")
                st.success(f"Tax applied! New total: ${total_amount} USDC")
        else:
            st.error("Invoice data not found.")
    else:
        st.write("No invoices to apply tax to.")