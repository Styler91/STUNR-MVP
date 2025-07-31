import streamlit as st
from streamlit.web.server.websocket_headers import _get_websocket_headers
import pandas as pd
import sqlite3
from datetime import datetime

# Sidebar for navigation
st.sidebar.title("STUNR Navigation")
page = st.sidebar.radio("Go to", ["Customer List", "Dashboard", "Invoices"])

# Connect to your database
conn = sqlite3.connect('stunr_db.sqlite')
c = conn.cursor()

# Get the customer data
customers_df = pd.read_sql_query("SELECT id, name, email, address, street, city, state, zip_code, custom_field, country, created_at FROM customers WHERE org_id = ?", conn, params=(1,))
customers_df['sub_status'] = [c.execute("SELECT status FROM subscriptions WHERE customer_id = ? LIMIT 1", (row['id'],)).fetchone()[0] if c.execute("SELECT status FROM subscriptions WHERE customer_id = ? LIMIT 1", (row['id'],)).fetchone() else "None" for index, row in customers_df.iterrows()]

# Page content
if page == "Customer List":
    st.image("stunr_logo.png", width=200)
    st.title("Customer List")
    search = st.text_input("Search by Name, Email, or Address")
    status = st.selectbox("Status", ["All"] + ["active", "trialing", "canceled", "None"], index=0)
    city = st.selectbox("City", ["All"] + sorted(customers_df['city'].dropna().unique().tolist()), index=0)
    state = st.selectbox("State", ["All"] + sorted(customers_df['state'].dropna().unique().tolist()), index=0)
    if st.button("Reset Filters"):
        search = ""
        status = "All"
        city = "All"
        state = "All"
    filtered_df = customers_df.copy()
    if search:
        filtered_df = filtered_df[filtered_df['name'].str.contains(search, case=False) | filtered_df['email'].str.contains(search, case=False) | filtered_df['address'].str.contains(search, case=False)]
    if status != "All":
        filtered_df = filtered_df[filtered_df['sub_status'] == status]
    if city != "All":
        filtered_df = filtered_df[filtered_df['city'] == city]
    if state != "All":
        filtered_df = filtered_df[filtered_df['state'] == state]
    for index, row in filtered_df.iterrows():
        with st.expander(f"{row['name']}"):
            st.write(f"Email: {row['email']}")
            st.write(f"Address: {row['address']}")
            st.write(f"Physical: {row['street']}, {row['city']}, {row['state']} {row['zip_code']}")
            st.write(f"Country: {row['country']}")
            st.write(f"Custom: {row['custom_field']}")
            st.write(f"Status: {row['sub_status']}")
            st.write(f"Created: {row['created_at']}")
            if st.button("Export Invoice", key=f"export_{index}"):
                invoice_df = pd.DataFrame([{'Customer': row['name'], 'Amount': 100, 'Date': datetime.now().isoformat()}])
                invoice_df.to_csv(f"invoice_{row['id']}.csv", index=False)
                st.success("Invoice exported!")
            if st.button("Edit", key=f"edit_{index}"):
                st.write("Edit form here soon!")
elif page == "Dashboard":
    st.header("Dashboard")
    st.write("Dashboard content will go here!")
elif page == "Invoices":
    st.header("Invoices")
    st.write("Invoices content will go here!")

# Note: CSV export might not save locally on Streamlit Cloud; we'll adjust if needed