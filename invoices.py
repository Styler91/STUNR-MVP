import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
import stripe

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

# Fetch or initialize invoice settings
settings = c.execute("SELECT * FROM invoice_settings").fetchone()
if not settings:
    c.execute("INSERT INTO invoice_settings (company_name, company_address, logo_url, footer_text, primary_color, font) VALUES (?, ?, ?, ?, ?, ?)",
              ("STUNR.ai", "Mock Merchant Address", "", "Thank you for your business! Contact: support@stunr.ai", '#6772e5', 'Helvetica'))
    conn.commit()
    settings = c.execute("SELECT * FROM invoice_settings").fetchone()

st.header("Invoices")
invoice_tab1, invoice_tab2, invoice_tab3, invoice_tab4 = st.tabs(["Invoice List", "Generate PDF", "Dunning", "Credit Notes"])

with invoice_tab1:
    st.subheader("Invoice List")
    invoices_df = pd.read_sql_query("SELECT id AS ID, sub_id AS 'Subscription ID', date AS 'Issue Date', amount AS 'Amount (USDC)', status AS Status, due_date AS 'Due Date' FROM invoices WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?))", conn, params=(st.session_state['org_id'],))
    if not invoices_df.empty:
        search_query = st.text_input("Search Invoices (ID, Subscription ID, Status)", placeholder="Search by ID or status...")
        if search_query:
            invoices_df = invoices_df[
                invoices_df['ID'].astype(str).str.contains(search_query, case=False) |
                invoices_df['Subscription ID'].astype(str).str.contains(search_query, case=False) |
                invoices_df['Status'].str.contains(search_query, case=False)
            ]
        st.dataframe(invoices_df, use_container_width=True, hide_index=True)
        csv = invoices_df.to_csv(index=False)
        st.download_button("Export Invoices to CSV", csv, "invoices.csv", "text/csv")
    else:
        st.write("No invoices yet.")

with invoice_tab2:
    st.subheader("Generate Invoice PDF")
    invoices = c.execute("SELECT id, sub_id, date, amount, due_date FROM invoices WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?))", (st.session_state['org_id'],)).fetchall()
    if invoices:
        selected_invoice = st.selectbox("Select Invoice", [f"ID: {inv[0]} - {inv[2]} - ${inv[3]} USDC" for inv in invoices])
        invoice_id = int(selected_invoice.split("ID: ")[1].split(" - ")[0])
        invoice_data = c.execute("SELECT i.id, i.sub_id, i.date, i.amount, i.due_date, s.customer_id, c.name, c.email, c.address FROM invoices i JOIN subscriptions s ON i.sub_id = s.id JOIN customers c ON s.customer_id = c.id WHERE i.id = ?", (invoice_id,)).fetchone()
        if invoice_data:
            invoice_id, sub_id, issue_date, amount, due_date, customer_id, customer_name, customer_email, customer_address = invoice_data
            buffer = io.BytesIO()
            can = canvas.Canvas(buffer, pagesize=letter)
            can.setFont(settings[6], 16)
            can.drawString(inch, 10 * inch, settings[1])  # Company Name
            can.drawString(inch, 9.5 * inch, settings[2])  # Company Address
            can.line(inch, 9 * inch, 6 * inch, 9 * inch)
            can.drawString(inch, 8.5 * inch, f"Invoice #: {invoice_id}")
            can.drawString(inch, 8 * inch, f"Date: {issue_date}")
            can.drawString(inch, 7.5 * inch, f"Due Date: {due_date}")
            can.drawString(4 * inch, 8.5 * inch, f"Bill To:")
            can.drawString(4 * inch, 8 * inch, customer_name)
            can.drawString(4 * inch, 7.5 * inch, customer_email)
            can.drawString(4 * inch, 7 * inch, customer_address)
            can.line(inch, 6.5 * inch, 6 * inch, 6.5 * inch)
            can.drawString(inch, 6 * inch, "Description")
            can.drawString(4 * inch, 6 * inch, "Amount")
            can.line(inch, 5.5 * inch, 6 * inch, 5.5 * inch)
            can.drawString(inch, 5 * inch, "Subscription Fee")
            can.drawString(4 * inch, 5 * inch, f"${amount} USDC")
            can.line(inch, 4.5 * inch, 6 * inch, 4.5 * inch)
            can.drawString(4 * inch, 4 * inch, f"Total: ${amount} USDC")
            can.setFont(settings[6], 10)
            can.drawString(inch, 3 * inch, settings[4])  # Footer Text
            can.showPage()
            can.save()
            buffer.seek(0)
            st.download_button("Download PDF", buffer, f"invoice_{invoice_id}.pdf", "application/pdf")
        else:
            st.error("Invoice data not found.")
    else:
        st.write("No invoices to generate PDF for.")

with invoice_tab3:
    st.subheader("Dunning Management")
    invoices = c.execute("SELECT id, sub_id, date, amount, status, due_date FROM invoices WHERE status = 'open' AND sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?))", (st.session_state['org_id'],)).fetchall()
    if invoices:
        selected_invoice = st.selectbox("Select Overdue Invoice", [f"ID: {inv[0]} - {inv[2]} - ${inv[3]} USDC" for inv in invoices])
        invoice_id = int(selected_invoice.split("ID: ")[1].split(" - ")[0])
        invoice_data = c.execute("SELECT id, sub_id, date, amount, due_date, status FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if invoice_data:
            invoice_id, sub_id, issue_date, amount, due_date, status = invoice_data
            if datetime.now() > datetime.fromisoformat(due_date):
                attempt = st.number_input("Dunning Attempt #", min_value=1, value=1)
                if st.button("Initiate Dunning"):
                    c.execute("INSERT INTO dunning_logs (invoice_id, attempt, date, status) VALUES (?, ?, ?, ?)",
                              (invoice_id, attempt, datetime.now().isoformat(), "pending"))
                    conn.commit()
                    sub = c.execute("SELECT customer_id FROM subscriptions WHERE id = ?", (sub_id,)).fetchone()
                    customer = c.execute("SELECT email FROM customers WHERE id = ?", (sub[0],)).fetchone()
                    mock_email(customer[0], "Payment Reminder", f"Invoice {invoice_id} is overdue. Amount: ${amount} USDC, Due: {due_date}")
                    log_audit(st.session_state['user_id'], "initiated_dunning", f"Invoice ID: {invoice_id}, Attempt: {attempt}")
                    st.success(f"Dunning attempt {attempt} initiated for invoice {invoice_id}!")
            else:
                st.warning("Invoice is not yet overdue.")
        else:
            st.error("Invoice data not found.")
    else:
        st.write("No overdue invoices for dunning.")

with invoice_tab4:
    st.subheader("Credit Notes")
    sub_id = st.selectbox("Select Subscription", [f"ID: {sub[0]} - {sub[2]}" for sub in c.execute("SELECT id, customer_id, plan FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?)", (st.session_state['org_id'],)).fetchall()])
    sub_id = int(sub_id.split("ID: ")[1].split(" - ")[0])
    amount = st.number_input("Credit Amount (USDC)", min_value=0.01, value=1.0)
    reason = st.text_input("Reason for Credit")
    if st.button("Issue Credit Note"):
        c.execute("INSERT INTO credit_notes (sub_id, amount, reason) VALUES (?, ?, ?)", (sub_id, amount, reason))
        conn.commit()
        log_audit(st.session_state['user_id'], "issued_credit_note", f"Sub ID: {sub_id}, Amount: {amount}")
        st.success(f"Credit note of ${amount} USDC issued for Subscription ID {sub_id}!")
    credit_notes_df = pd.read_sql_query("SELECT id AS ID, sub_id AS 'Subscription ID', amount AS 'Amount (USDC)', reason AS Reason FROM credit_notes WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?))", conn, params=(st.session_state['org_id'],))
    if not credit_notes_df.empty:
        st.dataframe(credit_notes_df, use_container_width=True, hide_index=True)
    else:
        st.write("No credit notes issued yet.")