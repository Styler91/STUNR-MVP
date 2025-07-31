import streamlit as st
import pandas as pd
import sqlite3
import base64
from datetime import datetime  # Added for log_audit

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

st.header("Products")
product_tab1, product_tab2 = st.tabs(["Product List", "Add/Edit Product"])

with product_tab1:
    st.subheader("Product List")
    products_df = pd.read_sql_query("SELECT id AS ID, name AS Name, description AS Description, price AS 'Price (USDC)', billing_frequency AS 'Billing Frequency', active AS Active FROM products WHERE active = 1", conn)
    if not products_df.empty:
        search_query = st.text_input("Search Products (Name, Description)", placeholder="Search by name or description...")
        min_price = st.number_input("Min Price", value=0.0)
        max_price = st.number_input("Max Price", value=1000.0)
        billing_filter = st.selectbox("Filter Billing Frequency", ["All", "Daily", "Weekly", "Monthly", "Yearly", "One-Time"])

        if search_query:
            products_df = products_df[
                products_df['Name'].str.contains(search_query, case=False) |
                products_df['Description'].str.contains(search_query, case=False)
            ]
        products_df = products_df[(products_df['Price (USDC)'] >= min_price) & (products_df['Price (USDC)'] <= max_price)]
        if billing_filter != "All":
            products_df = products_df[products_df['Billing Frequency'] == billing_filter]

        st.dataframe(products_df, use_container_width=True, hide_index=True)
        csv = products_df.to_csv(index=False)
        st.download_button("Export Products to CSV", csv, "products.csv", "text/csv")
    else:
        st.write("No active products yet.")

with product_tab2:
    st.subheader("Add/Edit Product")
    name = st.text_input("Product Name")
    description = st.text_area("Description")
    price = st.number_input("Price (USDC)", min_value=0.01, value=1.0)
    billing_frequency = st.selectbox("Billing Frequency", ["Daily", "Weekly", "Monthly", "Yearly", "One-Time"])
    image = st.file_uploader("Product Image", type=["png", "jpg", "jpeg"])
    image_url = None
    if image:
        image_url = base64.b64encode(image.read()).decode('utf-8')  # Save as base64
    active = st.checkbox("Active", value=True, key="new_product_active")

    tiers = st.text_area("Pricing Tiers (e.g., Basic:5, Premium:10)", value="")

    if st.button("Save Product"):
        if name and description and price:
            c.execute("INSERT INTO products (name, description, price, image_url, billing_frequency, active) VALUES (?, ?, ?, ?, ?, ?)",
                      (name, description, price, image_url, billing_frequency, 1 if active else 0))
            conn.commit()
            log_audit(st.session_state['user_id'], "added_product", f"Name: {name}, Price: {price}")
            st.success("Product saved successfully!")
        else:
            st.error("Please fill all required fields.")

    products = c.execute("SELECT id, name, description, price, image_url, billing_frequency, active FROM products").fetchall()
    if products:
        selected_product = st.selectbox("Edit Product", [f"ID: {prod[0]} - {prod[1]}" for prod in products])
        prod_id = int(selected_product.split("ID: ")[1].split(" - ")[0])
        prod_data = c.execute("SELECT id, name, description, price, image_url, billing_frequency, active FROM products WHERE id = ?", (prod_id,)).fetchone()
        if prod_data:
            edit_name = st.text_input("Edit Product Name", value=prod_data[1])
            edit_description = st.text_area("Edit Description", value=prod_data[2])
            edit_price = st.number_input("Edit Price (USDC)", min_value=0.01, value=float(prod_data[3]))
            edit_billing_frequency = st.selectbox("Edit Billing Frequency", ["Daily", "Weekly", "Monthly", "Yearly", "One-Time"], index=["Daily", "Weekly", "Monthly", "Yearly", "One-Time"].index(prod_data[5]))
            edit_image = st.file_uploader("Edit Product Image", type=["png", "jpg", "jpeg"])
            edit_image_url = prod_data[4]
            if edit_image:
                edit_image_url = base64.b64encode(edit_image.read()).decode('utf-8')
            edit_active = st.checkbox("Active", value=bool(prod_data[6]), key=f"edit_product_active_{prod_id}")

            edit_tiers = st.text_area("Edit Pricing Tiers (e.g., Basic:5, Premium:10)", value="")

            if st.button("Update Product"):
                c.execute("UPDATE products SET name = ?, description = ?, price = ?, image_url = ?, billing_frequency = ?, active = ? WHERE id = ?",
                          (edit_name, edit_description, edit_price, edit_image_url, edit_billing_frequency, 1 if edit_active else 0, prod_id))
                conn.commit()
                log_audit(st.session_state['user_id'], "updated_product", f"ID: {prod_id}, Name: {edit_name}")
                st.success("Product updated successfully!")

            # Deactivate/Activate button
            if st.button("Toggle Active Status", key=f"toggle_active_{prod_id}"):
                new_active = 0 if prod_data[6] else 1
                c.execute("UPDATE products SET active = ? WHERE id = ?", (new_active, prod_id))
                conn.commit()
                log_audit(st.session_state['user_id'], "toggled_product_active", f"ID: {prod_id}, New Active: {new_active}")
                st.success(f"Product {prod_data[1]} active status toggled!")
                st.experimental_rerun()