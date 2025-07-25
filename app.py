import streamlit as st
from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.pubkey import Pubkey as PublicKey  # Alias to match old usage
from solders.message import Message
from solders.transaction import Transaction
from solders.system_program import TransferParams, transfer
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import get_associated_token_address, create_associated_token_account, TransferCheckedParams, transfer_checked
import json
import qrcode
import io
import time
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import altair as alt
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.ensemble import IsolationForest
import numpy as np
import asyncio
import websockets
import base64  # For decoding account data
import stripe  # For Stripe integration
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import bcrypt

# Initialize database connection at the top
conn = sqlite3.connect('stunr_db.sqlite', check_same_thread=False)
c = conn.cursor()

st.set_page_config(layout="wide", page_title="STUNR.ai", page_icon="💳")

# Initialize session state keys if not present
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
if 'org_id' not in st.session_state:
    st.session_state['org_id'] = None
if 'role' not in st.session_state:
    st.session_state['role'] = None
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = None
if 'username' not in st.session_state:
    st.session_state['username'] = None
if 'name' not in st.session_state:
    st.session_state['name'] = None
if 'authentication_status' not in st.session_state:
    st.session_state['authentication_status'] = None
if 'new_customer_created' not in st.session_state:
    st.session_state['new_customer_created'] = False
if 'current_customer_id' not in st.session_state:
    st.session_state['current_customer_id'] = None

# Load config.yaml for authentication
with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

# Initialize authenticator
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# Render login widget and update session state
authenticator.login(location='main', key='login_form')

# Control app flow based on authentication status from session state
if not st.session_state['authenticated']:
    if st.session_state.get('authentication_status'):
        st.session_state['authenticated'] = True
        st.session_state['username'] = st.session_state.get('username')
        st.session_state['name'] = st.session_state.get('name')
        st.session_state['role'] = 'admin' if st.session_state['username'] == 'admin' else 'user'
        st.session_state['org_id'] = 1
        st.session_state['user_id'] = 1
        st.write(f'Welcome, {st.session_state["name"]}!')
        authenticator.logout(location='sidebar')
    elif st.session_state.get('authentication_status') == False:
        st.error('Username/password is incorrect')
        st.stop()
    elif st.session_state.get('authentication_status') is None:
        st.warning('Please enter your username and password')
        st.stop()
else:
    authenticator.logout(location='sidebar')

# Custom CSS for enhanced modern look
st.markdown("""
    <style>
    /* General styling - Inspired by Waveapps and Freshbooks */
    body {
        font-family: 'Inter', sans-serif;
        background-color: #f9fafc;
    }
    .stApp {
        background-color: #f9fafc;
    }
    /* Header and titles - Consistent green accents from Freshbooks */
    h1, h2, h3 {
        color: #04837b;
        font-weight: 600;
    }
    /* Modern header styling - Minimalist like Waveapps */
    .modern-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #04837b;
        text-align: center;
        margin-bottom: 1.5rem;
        letter-spacing: -0.5px;
    }
    /* Buttons - Green accents, rounded, with hover from Shopify/Freshbooks */
    .stButton > button {
        background-color: #04837b;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.6rem 1.2rem;
        font-weight: 500;
        transition: background-color 0.3s;
    }
    .stButton > button:hover {
        background-color: #036b65;
    }
    /* Metrics cards - Card style with shadows, inspired by Chargebee */
    .stMetric {
        background-color: white;
        border-radius: 8px;
        padding: 1.2rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    /* Inputs - Clean borders, inspired by Waveapps */
    .stTextInput > div > div > input {
        border-radius: 6px;
        border: 1px solid #d1d5db;
    }
    .stTextArea > div > div > textarea {
        border-radius: 6px;
        border: 1px solid #d1d5db;
    }
    /* Success/warning messages - Rounded like Freshbooks */
    .stAlert {
        border-radius: 6px;
    }
    /* Sidebar - Clean, with icons and hover effects */
    .css-1lcbmhc {
        background-color: white;
        padding: 1rem;
        border-right: 1px solid #d1d5db;
    }
    .stRadio > div {
        display: flex;
        flex-direction: column;
    }
    .stRadio > div > label {
        padding: 0.8rem 1.2rem;
        border-bottom: 1px solid #f0f2f6;
        cursor: pointer;
        transition: background-color 0.2s;
    }
    .stRadio > div > label:hover {
        background-color: #f0f2f6;
    }
    .stRadio > div > label[data-checked="true"] {
        background-color: #e6e9ef;
        font-weight: 500;
        border-left: 4px solid #04837b;
    }
    /* Tables - Responsive and modern with hover, like Chargebee */
    .stDataFrame table {
        border-collapse: collapse;
        width: 100%;
    }
    .stDataFrame th {
        background-color: #f0f2f6;
        padding: 0.8rem;
        text-align: left;
        font-weight: 600;
    }
    .stDataFrame td {
        padding: 0.8rem;
        border-bottom: 1px solid #d1d5db;
    }
    .stDataFrame tr:hover {
        background-color: #f0f2f6;
    }
    /* Cards for quick actions - Rounded with icons */
    .quick-action-card {
        background-color: white;
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
        cursor: pointer;
        transition: box-shadow 0.3s;
    }
    .quick-action-card:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    /* Tooltips - For help icons */
    .tooltip {
        position: relative;
        display: inline-block;
        cursor: pointer;
    }
    .tooltip .tooltiptext {
        visibility: hidden;
        width: 200px;
        background-color: #555;
        color: #fff;
        text-align: center;
        border-radius: 6px;
        padding: 5px;
        position: absolute;
        z-index: 1;
        bottom: 125%;
        left: 50%;
        margin-left: -100px;
        opacity: 0;
        transition: opacity 0.3s;
    }
    .tooltip:hover .tooltiptext {
        visibility: visible;
        opacity: 1;
    }
    /* Increased spacing */
    [data-testid="stMarkdownContainer"] {
        margin-bottom: 1rem;
    }
    [data-testid="stExpander"] {
        margin-bottom: 1rem;
    }
    /* Mobile responsiveness - Adjust columns on small screens */
    @media (max-width: 768px) {
        .stColumns > div {
            flex-direction: column;
        }
    }
    </style>
""", unsafe_allow_html=True)

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

# Create tables
c.execute('''CREATE TABLE IF NOT EXISTS audit_logs
             (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT, details TEXT, timestamp TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS users
             (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, email TEXT, password TEXT, name TEXT, role TEXT DEFAULT 'user', created_at TEXT, org_id INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS subscriptions
             (id INTEGER PRIMARY KEY, customer_id INTEGER, plan TEXT, amount FLOAT, start_date TEXT, last_bill_date TEXT, status TEXT, trial_days INTEGER, coupon_pct FLOAT, tax_rate FLOAT, entitlement TEXT, auto_dunning INTEGER DEFAULT 1)''')
try:
    c.execute("ALTER TABLE subscriptions ADD COLUMN customer_id INTEGER")
    conn.commit()
except:
    pass
try:
    c.execute("ALTER TABLE subscriptions ADD COLUMN last_bill_date TEXT")
    conn.commit()
except:
    pass
try:
    c.execute("ALTER TABLE subscriptions ADD COLUMN trial_days INTEGER")
    conn.commit()
except:
    pass
try:
    c.execute("ALTER TABLE subscriptions ADD COLUMN coupon_pct FLOAT")
    conn.commit()
except:
    pass
try:
    c.execute("ALTER TABLE subscriptions ADD COLUMN tax_rate FLOAT")
    conn.commit()
except:
    pass
try:
    c.execute("ALTER TABLE subscriptions ADD COLUMN entitlement TEXT")
    conn.commit()
except:
    pass
try:
    c.execute("ALTER TABLE subscriptions ADD COLUMN auto_dunning INTEGER DEFAULT 1")
    conn.commit()
except:
    pass
c.execute('''CREATE TABLE IF NOT EXISTS usage_logs
             (id INTEGER PRIMARY KEY, sub_id INTEGER, timestamp TEXT, quantity INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS invoices
             (id INTEGER PRIMARY KEY, sub_id INTEGER, date TEXT, amount FLOAT, status TEXT, due_date TEXT)''')
try:
    c.execute("ALTER TABLE invoices ADD COLUMN due_date TEXT")
    conn.commit()
except:
    pass
c.execute('''CREATE TABLE IF NOT EXISTS credit_notes
             (id INTEGER PRIMARY KEY, sub_id INTEGER, amount FLOAT, reason TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS payouts
             (id INTEGER PRIMARY KEY, date TEXT, amount FLOAT, destination TEXT, tx_sig TEXT, status TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS dunning_logs
             (id INTEGER PRIMARY KEY, invoice_id INTEGER, attempt INTEGER, date TEXT, status TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS customers
             (id INTEGER PRIMARY KEY, name TEXT, email TEXT, address TEXT, created_at TEXT, country TEXT DEFAULT 'US', org_id INTEGER)''')
try:
    c.execute("ALTER TABLE customers ADD COLUMN country TEXT DEFAULT 'US'")
    conn.commit()
except:
    pass
try:
    c.execute("ALTER TABLE customers ADD COLUMN org_id INTEGER")
    conn.commit()
except:
    pass
c.execute('''CREATE TABLE IF NOT EXISTS transactions
             (id INTEGER PRIMARY KEY, tx_sig TEXT, amount FLOAT, from_addr TEXT, timestamp TEXT, status TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS recognized_revenue
             (id INTEGER PRIMARY KEY, sub_id INTEGER, month TEXT, amount FLOAT, recognized_amount FLOAT, prorated BOOL DEFAULT 0)''')
c.execute('''CREATE TABLE IF NOT EXISTS deferred_revenue
             (id INTEGER PRIMARY KEY, sub_id INTEGER, amount FLOAT, start_date TEXT, end_date TEXT, status TEXT DEFAULT 'deferred')''')
c.execute('''CREATE TABLE IF NOT EXISTS customer_segments
             (id INTEGER PRIMARY KEY, customer_id INTEGER, segment TEXT, usage_level FLOAT, last_updated TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS upsell_logs
             (id INTEGER PRIMARY KEY, sub_id INTEGER, customer_id INTEGER, upsell_type TEXT, status TEXT, reward_tx TEXT, timestamp TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS webhooks
             (id INTEGER PRIMARY KEY, event TEXT, url TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS invoice_settings
             (id INTEGER PRIMARY KEY, company_name TEXT, company_address TEXT, logo_url TEXT, footer_text TEXT, primary_color TEXT DEFAULT '#6772e5', font TEXT DEFAULT 'Helvetica')''')
try:
    c.execute("ALTER TABLE invoice_settings ADD COLUMN primary_color TEXT DEFAULT '#6772e5'")
    conn.commit()
except:
    pass
try:
    c.execute("ALTER TABLE invoice_settings ADD COLUMN font TEXT DEFAULT 'Helvetica'")
    conn.commit()
except:
    pass
c.execute('''CREATE TABLE IF NOT EXISTS payment_settings
             (id INTEGER PRIMARY KEY, stripe_publishable_key TEXT, stripe_secret_key TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS products
             (id INTEGER PRIMARY KEY, name TEXT, description TEXT, price FLOAT, image_url TEXT, billing_frequency TEXT, active INTEGER DEFAULT 1)''')
c.execute('''CREATE TABLE IF NOT EXISTS tax_rules
             (id INTEGER PRIMARY KEY, country TEXT, rate FLOAT)''')
c.execute('''CREATE TABLE IF NOT EXISTS recipients
             (id INTEGER PRIMARY KEY, name TEXT, email TEXT, wallet_address TEXT, bank_details TEXT, verified BOOL DEFAULT 0)''')
c.execute('''CREATE TABLE IF NOT EXISTS payout_batches
             (id INTEGER PRIMARY KEY, date TEXT, status TEXT, total_amount FLOAT, csv_file BLOB, tx_sig TEXT)''')
conn.commit()

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

# Connect to Solana devnet
client = Client("https://api.devnet.solana.com")

# Load your merchant wallet
with open('wallet.json') as f:
    wallet_data = json.load(f)
merchant_keypair = Keypair.from_bytes(bytes(wallet_data))

# Correct USDC mint on Solana devnet
USDC_MINT = PublicKey.from_string("4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU")
USDC_DECIMALS = 6

# Get or create USDC token account
def get_or_create_token_account(owner):
    token_account = get_associated_token_address(owner.pubkey(), USDC_MINT)
    account_info = client.get_account_info(token_account)
    if account_info.value is None:
        recent_blockhash = client.get_latest_blockhash().value.blockhash
        instructions = [create_associated_token_account(owner.pubkey(), owner.pubkey(), USDC_MINT)]
        message = Message.new_with_blockhash(instructions, owner.pubkey(), recent_blockhash)
        txn = Transaction([owner], message, recent_blockhash)
        client.send_transaction(txn)
    return token_account

merchant_usdc_account = get_or_create_token_account(merchant_keypair)

st.markdown('<div class="modern-header">STUNR - Billing, Payments & Accounting on The Blockchain</div>', unsafe_allow_html=True)

# Vertical tabs in sidebar with icons
page = st.sidebar.radio("Navigation", [
    "📊 Dashboard",
    "💳 Payments",
    "👥 Customers",  # Merged tab
    "🔒 Admin",
    "🚪 Portal",
    "📄 Invoices",
    "📜 Txns",
    "🛒 Products",
    "🧾 Taxes",
    "📈 Reporting"
])

# RBAC: Hide Admin for non-admins
if page == "🔒 Admin" and st.session_state['role'] != 'admin':
    st.error("Access denied to Admin tab.")
else:
    if page == "📊 Dashboard":
        st.header("STUNR.ai Billing Dashboard")
        
        # Fetch historical data for analytics
        subs_df = pd.read_sql_query("SELECT id, customer_id, plan, amount, start_date, status FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?)", conn, params=(st.session_state['org_id'],))
        invoices_df = pd.read_sql_query("SELECT sub_id, date, amount, status FROM invoices WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?))", conn, params=(st.session_state['org_id'],))
        usage_df = pd.read_sql_query("SELECT sub_id, timestamp, quantity FROM usage_logs WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?))", conn, params=(st.session_state['org_id'],))
        
        # Convert dates
        subs_df['start_date'] = pd.to_datetime(subs_df['start_date'])
        invoices_df['date'] = pd.to_datetime(invoices_df['date'])
        usage_df['timestamp'] = pd.to_datetime(usage_df['timestamp'])
        
        # Aggregate monthly revenue
        invoices_df['month'] = invoices_df['date'].dt.to_period('M')
        monthly_rev = invoices_df[invoices_df['status'] == 'paid'].groupby('month')['amount'].sum().reset_index()
        monthly_rev['month'] = monthly_rev['month'].dt.to_timestamp()
        
        # Add cohort column to subs
        subs_df['cohort_month'] = subs_df['start_date'].dt.to_period('M')
        
        # Calculate metrics
        active_subs = len(subs_df[subs_df['status'] == 'active']) if not subs_df.empty else 0
        mrr = subs_df[subs_df['status'] == 'active']['amount'].sum() if not subs_df.empty else 0.0
        total_canceled = len(subs_df[subs_df['status'] == 'canceled']) if not subs_df.empty else 0
        total_subs = len(subs_df) if not subs_df.empty else 0
        churn_rate = (total_canceled / total_subs * 100) if total_subs > 0 else 0.0
        total_revenue = invoices_df[invoices_df['status'] == 'paid']['amount'].sum() if not invoices_df.empty else 0.0
        deferred_total = pd.read_sql_query("SELECT SUM(amount) as total FROM deferred_revenue WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?))", conn, params=(st.session_state['org_id'],))['total'].iloc[0] if not pd.read_sql_query("SELECT SUM(amount) as total FROM deferred_revenue WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?))", conn, params=(st.session_state['org_id'],)).empty else 0.0

        # Metrics in cards
        st.subheader("Key Metrics")
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Active Subs", active_subs, delta_color="normal")
        with col2:
            st.metric("MRR (USDC)", f"{mrr:.2f}", delta_color="normal")
        with col3:
            st.metric("Churn Rate", f"{churn_rate:.1f}%", delta_color="inverse")
        with col4:
            st.metric("Total Revenue (USDC)", f"{total_revenue:.2f}", delta_color="normal")
        with col5:
           value = deferred_total if deferred_total is not None else 0.0
        st.metric("Deferred Revenue (USDC)", f"{value:.2f}", delta_color="normal")
        
        # Charts with increased spacing
        st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
        st.subheader("Cohort Analysis (Retention by Acquisition Month)")
        if not subs_df.empty:
            subs_df['month'] = subs_df['start_date'].dt.to_period('M')
            cohort_data = subs_df.groupby(['cohort_month', 'month']).agg(n_customers=('id', 'nunique')).reset_index()
            cohort_data['period'] = (cohort_data['month'] - cohort_data['cohort_month']).apply(lambda x: x.n)
            cohort_pivot = cohort_data.pivot_table(index='cohort_month', columns='period', values='n_customers')
            cohort_pivot = cohort_pivot.divide(cohort_pivot.iloc[:, 0], axis=0) * 100
            st.dataframe(cohort_pivot.style.background_gradient(cmap='viridis'))
            overall_churn = (total_canceled / total_subs * 100) if total_subs > 0 else 0
            st.write(f"Overall Churn Rate: {overall_churn:.1f}% (reduces by 20-30% with optimization)")
        else:
            st.write("No subscription data for cohorts.")
        
        st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
        st.subheader("Churn by Plan")
        if not subs_df.empty:
            churn_by_plan = subs_df.groupby('plan')['status'].apply(lambda x: (x == 'canceled').sum() / len(x) * 100).reset_index(name='churn_rate')
            churn_chart = alt.Chart(churn_by_plan).mark_bar().encode(x='plan', y='churn_rate', color='plan').properties(title="Churn Rate by Plan (%)").interactive()
            st.altair_chart(churn_chart, use_container_width=True)
        else:
            st.write("No data for churn by plan.")
        
        st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
        st.subheader("Customer Segments")
        segments_df = pd.read_sql_query("SELECT segment, COUNT(*) as count FROM customer_segments WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?)", conn, params=(st.session_state['org_id'],))
        if not segments_df.empty:
            seg_chart = alt.Chart(segments_df).mark_bar().encode(x='segment', y='count', color='segment').properties(title="Customer Segments (High/Low Usage)").interactive()
            st.altair_chart(seg_chart, use_container_width=True)
        else:
            st.write("No segment data yet.")
        
        st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
        # Charts with increased spacing
        usage_df = pd.read_sql_query("SELECT timestamp, quantity FROM usage_logs WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?))", conn, params=(st.session_state['org_id'],))
        if not usage_df.empty:
            usage_df['timestamp'] = pd.to_datetime(usage_df['timestamp'])
            chart = alt.Chart(usage_df).mark_line().encode(x='timestamp:T', y='quantity:Q').properties(title="Metered Usage Trends").interactive()
            st.altair_chart(chart, use_container_width=True)
        
        subs_df = pd.read_sql_query("SELECT start_date FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?)", conn, params=(st.session_state['org_id'],))
        if not subs_df.empty:
            subs_df['start_date'] = pd.to_datetime(subs_df['start_date'])
            subs_df['cum_subs'] = range(1, len(subs_df) + 1)
            growth_chart = alt.Chart(subs_df).mark_area().encode(x='start_date:T', y='cum_subs:Q').properties(title="Subscription Growth").interactive()
            st.altair_chart(growth_chart, use_container_width=True)
        
        st.subheader("Quick Actions")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="quick-action-card">Create New Sub</div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="quick-action-card">Initiate Payout</div>', unsafe_allow_html=True)

    elif page == "💳 Payments":
        st.header("Payments")
        payments_tab1, payments_tab2 = st.tabs(["One-Time Payments", "Payouts"])
        
        with payments_tab1:
            st.subheader("Create One-Time Payment Intent")
            payment_method = st.selectbox("Payment Method", ["Solana USDC", "Credit Card (via Stripe)", "Bank Transfer (via Stripe)"])
            amount = st.number_input("Amount in USD", min_value=0.01, value=1.0)
            description = st.text_input("Description", "Test payment")

            if st.button("Generate Payment Intent", key="generate_payment"):
                if payment_method == "Solana USDC":
                    payment_uri = f"solana:{merchant_usdc_account}?amount={amount}&spl-token={USDC_MINT}&label=STUNR.ai&message={description}"
                    qr = qrcode.QRCode(version=1, box_size=10, border=5)
                    qr.add_data(payment_uri)
                    qr.make(fit=True)
                    img = qr.make_image(fill='black', back_color='white')
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    buf.seek(0)
                    st.image(buf, caption="Scan with Solana wallet (e.g., Phantom) to pay")
                    st.write(f"Send {amount} USDC to: {merchant_usdc_account}")
                    with st.spinner("Waiting for payment..."):
                        initial_balance_resp = client.get_token_account_balance(merchant_usdc_account)
                        initial_balance = initial_balance_resp.value.ui_amount or 0.0
                        while True:
                            time.sleep(10)
                            new_balance_resp = client.get_token_account_balance(merchant_usdc_account)
                            new_balance = new_balance_resp.value.ui_amount or 0.0
                            if new_balance > initial_balance:
                                st.success(f"Payment received! New balance: {new_balance} USDC")
                                webhooks = c.execute("SELECT url FROM webhooks WHERE event = 'payment_success'").fetchall()
                                for hook in webhooks:
                                    url = hook[0]
                                    payload = json.dumps({"event": "payment_success", "amount": amount})
                                    st.info(f"Mock POST to {url}: {payload}")
                                break
                else:
                    try:
                        intent = stripe.PaymentIntent.create(
                            amount=int(amount * 100),
                            currency="usd",
                            description=description,
                            payment_method_types=['card'] if payment_method == "Credit Card (via Stripe)" else ['us_bank_account'],
                        )
                        st.write(f"Client Secret: {intent.client_secret}")
                        st.info("Use Stripe Elements or test card (4242 4242 4242 4242) to complete payment.")
                    except Exception as e:
                        st.error(f"Stripe error: {e}")

        with payments_tab2:
            st.subheader("Payouts Management")
            balance_resp = client.get_token_account_balance(merchant_usdc_account)
            current_balance = balance_resp.value.ui_amount or 0.0
            st.write(f"Available USDC Balance: {current_balance}")

            payout_tab1, payout_tab2, payout_tab3 = st.tabs(["Single Payout", "Batch Payouts", "Payout History & Analytics"])

            with payout_tab1:
                st.subheader("Single Payout")
                payout_amount = st.number_input("Payout Amount (USDC)", min_value=0.01, max_value=current_balance, value=1.0)
                destination_addr = st.text_input("Destination Solana Address")
                payout_type = st.selectbox("Payout Type", ["Crypto (USDC)", "Fiat (via Stripe)"])
                verified = st.checkbox("Recipient Verified (Mock KYC/Tax Check)", value=True)
                approve = st.checkbox("Approve Payout", value=True)
                schedule_date = st.date_input("Schedule Payout For (Optional)", value=None)
                mock_mode = st.checkbox("Mock Mode (No Real Transfer)", value=True)

                if st.button("Initiate Payout"):
                    if not verified:
                        st.error("Recipient not verified - cannot proceed.")
                    elif not approve:
                        st.warning("Payout not approved - pending.")
                    else:
                        if destination_addr and payout_amount <= current_balance:
                            payout_data = np.array([payout_amount]).reshape(-1, 1)
                            fraud_model = IsolationForest(contamination=0.1)
                            fraud_model.fit(payout_data)
                            anomaly = fraud_model.predict(payout_data)
                            if anomaly[0] == -1:
                                st.warning("Potential fraud detected! Review payout.")
                            else:
                                destination_pubkey = PublicKey.from_string(destination_addr)
                                destination_usdc_account = get_or_create_token_account(destination_pubkey)
                                fee_estimate = 0.0001
                                net_payout = payout_amount - fee_estimate

                                if payout_type == "Fiat (via Stripe)":
                                    try:
                                        stripe.Transfer.create(
                                            amount=int(payout_amount * 100),
                                            currency="usd",
                                            destination="acct_...",
                                        )
                                        tx_sig = "stripe_mock_tx"
                                        status = "success"
                                        st.success(f"Fiat payout sent via Stripe! Tx ID: {tx_sig}")
                                    except Exception as e:
                                        st.error(f"Stripe payout error: {e}")
                                else:
                                    if not mock_mode:
                                        recent_blockhash = client.get_latest_blockhash().value.blockhash
                                        instructions = [transfer_checked(TransferCheckedParams(
                                            program_id=TOKEN_PROGRAM_ID,
                                            source=merchant_usdc_account,
                                            mint=USDC_MINT,
                                            dest=destination_usdc_account,
                                            owner=merchant_keypair.pubkey(),
                                            amount=int(payout_amount * 10**USDC_DECIMALS),
                                            decimals=USDC_DECIMALS
                                        ))]
                                        message = Message.new_with_blockhash(instructions, merchant_keypair.pubkey(), recent_blockhash)
                                        txn = Transaction([merchant_keypair], message, recent_blockhash)
                                        tx_sig = client.send_transaction(txn).value
                                        status = "success"
                                        st.success(f"Payout sent! Tx Sig: {tx_sig}")
                                    else:
                                        tx_sig = "mock_sig"
                                        status = "mock_success"
                                        st.success(f"Mock payout of {net_payout} USDC to {destination_addr} (fee: {fee_estimate}).")

                                payout_date = schedule_date.isoformat() if schedule_date else datetime.now().isoformat()
                                c.execute("INSERT INTO payouts (date, amount, destination, tx_sig, status) VALUES (?, ?, ?, ?, ?)",
                                          (payout_date, payout_amount, destination_addr, tx_sig, status))
                                conn.commit()
                                log_audit(st.session_state['user_id'], "initiated_payout", f"Amount: {payout_amount}, Dest: {destination_addr}")
                        else:
                            st.error("Invalid address or insufficient balance.")

            with payout_tab2:
                st.subheader("Batch Payouts")
                st.download_button("Download CSV Template", "destination,amount\naddr1,1.0\naddr2,2.0", "payout_template.csv")
                uploaded_file = st.file_uploader("Upload CSV for Batch Payouts", type="csv")
                batch_type = st.selectbox("Batch Type", ["Crypto (USDC)", "Fiat (via Stripe)"])
                verified_batch = st.checkbox("All Recipients Verified (Mock KYC/Tax Check)", value=True)
                approve_batch = st.checkbox("Approve Batch", value=True)
                schedule_batch = st.date_input("Schedule Batch For (Optional)", value=None)
                mock_batch = st.checkbox("Mock Mode", value=True)

                if uploaded_file:
                    batch_df = pd.read_csv(uploaded_file)
                    if 'destination' in batch_df.columns and 'amount' in batch_df.columns:
                        total_batch = batch_df['amount'].sum()
                        if total_batch > current_balance:
                            st.error("Insufficient balance for batch.")
                        else:
                            st.dataframe(batch_df)
                            if st.button("Process Batch"):
                                if not verified_batch:
                                    st.error("Batch not verified - cannot proceed.")
                                elif not approve_batch:
                                    st.warning("Batch not approved - pending.")
                                else:
                                    batch_amounts = batch_df['amount'].values.reshape(-1, 1)
                                    fraud_model = IsolationForest(contamination=0.1)
                                    fraud_model.fit(batch_amounts)
                                    anomalies = fraud_model.predict(batch_amounts)
                                    if -1 in anomalies:
                                        st.warning("Potential fraud in batch! Review amounts.")
                                    else:
                                        batch_id = datetime.now().timestamp()
                                        batch_status = "pending" if schedule_batch else "processing"
                                        batch_date = schedule_batch.isoformat() if schedule_batch else datetime.now().isoformat()
                                        tx_sigs = []
                                        for index, row in batch_df.iterrows():
                                            dest = row['destination']
                                            amt = row['amount']
                                            if batch_type == "Fiat (via Stripe)":
                                                try:
                                                    stripe.Transfer.create(
                                                        amount=int(amt * 100),
                                                        currency="usd",
                                                        destination="acct_...",
                                                    )
                                                    tx_sigs.append("stripe_mock")
                                                except:
                                                    tx_sigs.append("error")
                                            else:
                                                if not mock_batch:
                                                    dest_pubkey = PublicKey.from_string(dest)
                                                    dest_acc = get_or_create_token_account(dest_pubkey)
                                                    recent_blockhash = client.get_latest_blockhash().value.blockhash
                                                    instructions = [transfer_checked(TransferCheckedParams(
                                                        program_id=TOKEN_PROGRAM_ID,
                                                        source=merchant_usdc_account,
                                                        mint=USDC_MINT,
                                                        dest=dest_acc,
                                                        owner=merchant_keypair.pubkey(),
                                                        amount=int(amt * 10**USDC_DECIMALS),
                                                        decimals=USDC_DECIMALS
                                                    ))]
                                                    message = Message.new_with_blockhash(instructions, merchant_keypair.pubkey(), recent_blockhash)
                                                    txn = Transaction([merchant_keypair], message, recent_blockhash)
                                                    tx_sig = client.send_transaction(txn).value
                                                    tx_sigs.append(tx_sig)
                                                else:
                                                    tx_sigs.append("mock_batch_sig")

                                        batch_tx_sig = ",".join(tx_sigs)
                                        c.execute("INSERT INTO payout_batches (date, status, total_amount, tx_sig) VALUES (?, ?, ?, ?)",
                                                  (batch_date, batch_status, total_batch, batch_tx_sig))
                                        conn.commit()
                                        log_audit(st.session_state['user_id'], "processed_batch_payout", f"Total: {total_batch}")
                                        st.success(f"Batch processed! Total: {total_batch} USDC, Status: {batch_status}")
                    else:
                        st.error("CSV must have 'destination' and 'amount' columns.")
                else:
                    st.error("Please upload a CSV file.")

            with payout_tab3:
                st.subheader("Payout History & Analytics")
                payouts_df = pd.read_sql_query("SELECT id, date, amount, destination, status FROM payouts", conn)
                batches_df = pd.read_sql_query("SELECT id, date, status, total_amount AS amount FROM payout_batches", conn)
                combined_df = pd.concat([payouts_df, batches_df], ignore_index=True)
                st.dataframe(combined_df, use_container_width=True)
                if not combined_df.empty:
                    combined_df['date'] = pd.to_datetime(combined_df['date'])
                    payout_chart = alt.Chart(combined_df).mark_line().encode(
                        x='date:T',
                        y='sum(amount):Q',
                        color='status'
                    ).properties(title="Payout Trends").interactive()
                    st.altair_chart(payout_chart, use_container_width=True)
elif page == "👥 Customers":
    st.header("Customers")
    customer_tab1, customer_tab2 = st.tabs(["Customer List", "Subscription Setup"])

    with customer_tab1:
        st.subheader("Customer List")
        customers_df = pd.read_sql_query("SELECT id, name, email, address, country, created_at FROM customers WHERE org_id = ?", conn, params=(st.session_state['org_id'],))
        if not customers_df.empty:
            search_query = st.text_input("Search Customers (Name, Email, Address)", placeholder="Search by name or email...")
            if search_query:
                customers_df = customers_df[
                    customers_df['name'].str.contains(search_query, case=False) |
                    customers_df['email'].str.contains(search_query, case=False) |
                    customers_df['address'].str.contains(search_query, case=False)
                ]
            for index, row in customers_df.iterrows():
                with st.expander(f"{row['name']} ({row['address']})"):
                    st.write(f"Email: {row['email']}")
                    st.write(f"Country: {row['country']}")
                    st.write(f"Created At: {row['created_at']}")
                    subs = c.execute("SELECT id, plan, status, amount FROM subscriptions WHERE customer_id = ?", (row['id'],)).fetchall()
                    if subs:
                        subs_df = pd.DataFrame(subs, columns=["ID", "Plan", "Status", "Amount"])
                        st.subheader("Associated Subscriptions")
                        st.dataframe(subs_df, use_container_width=True, hide_index=True)
                        for sub in subs:
                            if st.button(f"View Subscription {sub[0]}", key=f"view_sub_{sub[0]}_{row['id']}"):
                                st.write("Subscription Details:")  # Placeholder for full sub view
                    else:
                        st.write("No subscriptions for this customer.")
            csv = customers_df.to_csv(index=False)
            st.download_button("Export Customers to CSV", csv, "customers.csv", "text/csv")
        else:
            st.write("No customers yet.")

    with customer_tab2:
        st.subheader("Subscription Setup")
        customers = c.execute("SELECT id, name, address FROM customers WHERE org_id = ?", (st.session_state['org_id'],)).fetchall()
        customer_options = ["Create New Customer"] + [f"{cust[1]} ({cust[2]})" for cust in customers]
        selected_customer = st.selectbox("Select Customer", customer_options)
        
        if selected_customer == "Create New Customer":
            new_name = st.text_input("New Customer Name")
            new_address = st.text_input("New Customer Solana Address")
            new_email = st.text_input("New Customer Email")
            new_country = st.text_input("Country (e.g., US)", "US", key="new_sub_country")
            if st.button("Create Customer and Proceed"):
                created_at = datetime.now().isoformat()
                c.execute("INSERT INTO customers (name, address, email, created_at, country, org_id) VALUES (?, ?, ?, ?, ?, ?)",
                          (new_name, new_address, new_email, created_at, new_country, st.session_state['org_id']))
                conn.commit()
                c.execute("SELECT last_insert_rowid()")
                customer_id = c.fetchone()[0]
                st.session_state['current_customer_id'] = customer_id
                st.session_state['new_customer_created'] = True
                log_audit(st.session_state['user_id'], "created_customer", f"Name: {new_name}")
                st.success("Customer created! Please set up a subscription below.")
        else:
            st.session_state['current_customer_id'] = next(cust[0] for cust in customers if f"{cust[1]} ({cust[2]})" == selected_customer)
            st.session_state['new_customer_created'] = False

        if st.session_state['current_customer_id']:
            plan = st.selectbox("Plan", ["Basic ($5/month USDC)", "Premium ($10/month USDC)", "Enterprise (Metered Only)"])
            trial_days = st.number_input("Trial Days", min_value=0, value=7, help="Number of free trial days before billing starts")
            coupon_pct = st.number_input("Coupon %", min_value=0.0, max_value=100.0, value=0.0, help="Percentage discount to apply")
            entitlement = st.selectbox("Entitlement (Features)", ["Basic Access", "Full AI + API", "Enterprise Support"])
            auto_dunning = st.checkbox("Enable Auto Dunning for Unpaid Invoices", value=True, help="Automatically retry failed payments")

            if st.button("Setup Subscription"):
                with st.spinner("Processing..."):
                    customer_id = st.session_state['current_customer_id']
                    customer_country = c.execute("SELECT country FROM customers WHERE id = ?", (customer_id,)).fetchone()[0]
                    try:
                        tax_calc = stripe.Tax.Calculation.create(
                            currency="usd",
                            line_items=[{"amount": 1000, "quantity": 1, "reference": plan}],
                            customer_details={"address": {"country": customer_country.upper()}},
                        )
                        tax_rate = tax_calc.tax_amount_exclusive / tax_calc.amount_total * 100 if tax_calc.amount_total > 0 else 0.0
                    except:
                        tax_rate = 10.0
                    amount = 5.0 if plan == "Basic ($5/month USDC)" else 10.0 if plan == "Premium ($10/month USDC)" else 0.0
                    start_date = datetime.now().isoformat()
                    last_bill_date = start_date
                    status = "active" if trial_days == 0 else "trialing"
                    auto_dunning_val = 1 if auto_dunning else 0
                    c.execute("INSERT INTO subscriptions (customer_id, plan, amount, start_date, last_bill_date, status, trial_days, coupon_pct, tax_rate, entitlement, auto_dunning) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                              (customer_id, plan, amount, start_date, last_bill_date, status, trial_days, coupon_pct, tax_rate, entitlement, auto_dunning_val))
                    conn.commit()
                    sub_id = c.lastrowid
                    due_date = (datetime.now() + timedelta(days=30)).isoformat()
                    c.execute("INSERT INTO invoices (sub_id, date, amount, status, due_date) VALUES (?, ?, ?, ?, ?)",
                              (sub_id, start_date, amount, "open", due_date))
                    conn.commit()
                    st.write(f"Debug: Invoice created for Subscription ID {sub_id} with amount {amount} USDC, due on {due_date}")
                    log_audit(st.session_state['user_id'], "created_subscription", f"Customer ID: {customer_id}, Plan: {plan}")
                    today = datetime.now()
                    if today.day > 1:
                        prorate_days = (today + timedelta(days=30 - today.day)).day
                        prorated_amount = amount * (prorate_days / 30)
                        c.execute("INSERT INTO recognized_revenue (sub_id, month, amount, recognized_amount, prorated) VALUES (?, ?, ?, ?, ?)",
                                  (sub_id, today.strftime('%Y-%m'), amount, prorated_amount, 1))
                        c.execute("INSERT INTO deferred_revenue (sub_id, amount, start_date, end_date) VALUES (?, ?, ?, ?)",
                                  (sub_id, amount - prorated_amount, today.isoformat(), (today + timedelta(days=30)).isoformat()))
                        conn.commit()
                        st.info(f"Prorated first month: {prorated_amount} USDC recognized, balance deferred.")
                    st.success("Subscription setup complete! Tax rate applied: {tax_rate}%")
                    st.session_state['new_customer_created'] = False

            if st.button("Generate Missing Invoices for Existing Subscriptions"):
                subs = c.execute("SELECT id, customer_id, amount FROM subscriptions WHERE id NOT IN (SELECT sub_id FROM invoices)").fetchall()
                if subs:
                    for sub in subs:
                        sub_id, customer_id, amount = sub
                        due_date = (datetime.now() + timedelta(days=30)).isoformat()
                        c.execute("INSERT INTO invoices (sub_id, date, amount, status, due_date) VALUES (?, ?, ?, ?, ?)",
                                  (sub_id, datetime.now().isoformat(), amount, "open", due_date))
                        conn.commit()
                        st.write(f"Debug: Generated invoice for Subscription ID {sub_id} with amount {amount} USDC, due on {due_date}")
                    log_audit(st.session_state['user_id'], "generated_missing_invoices", f"Generated {len(subs)} invoices")
                    st.success(f"Generated {len(subs)} missing invoices!")
                else:
                    st.write("No missing invoices to generate.")
    elif page == "📝 Subscriptions":
        st.header("Subscriptions")
        subs_tab1, subs_tab2 = st.tabs(["Manage Customers", "Setup Subscriptions"])
        
        with subs_tab1:
            st.subheader("Customer Management")
            st.subheader("Create New Customer")
            name = st.text_input("Name")
            address = st.text_input("Solana Address")
            email = st.text_input("Email")
            country = st.text_input("Country (e.g., US)", "US", key="new_customer_country")

            if st.button("Create Customer"):
                if name and address and email:
                    created_at = datetime.now().isoformat()
                    c.execute("INSERT INTO customers (name, address, email, created_at, country, org_id) VALUES (?, ?, ?, ?, ?, ?)",
                              (name, address, email, created_at, country, st.session_state['org_id']))
                    conn.commit()
                    log_audit(st.session_state['user_id'], "created_customer", f"Name: {name}")
                    st.success("Customer created!")
                else:
                    st.error("Fill all fields.")

            st.subheader("Customer List")
            customers_df = pd.read_sql_query("SELECT id AS ID, name AS Name, email AS Email, address AS Address, country AS Country, created_at AS 'Created At' FROM customers WHERE org_id = ?", conn, params=(st.session_state['org_id'],))
            if not customers_df.empty:
                search_query = st.text_input("Search Customers (Name, Email, Address)", placeholder="Search by name or email...")
                if search_query:
                    customers_df = customers_df[
                        customers_df['Name'].str.contains(search_query, case=False) |
                        customers_df['Email'].str.contains(search_query, case=False) |
                        customers_df['Address'].str.contains(search_query, case=False)
                    ]
                st.dataframe(customers_df, use_container_width=True, hide_index=True)
                csv = customers_df.to_csv(index=False)
                st.download_button("Export Customers to CSV", csv, "customers.csv", "text/csv")
            else:
                st.write("No customers yet.")

        with subs_tab2:
            st.subheader("Subscription Setup")
            customers = c.execute("SELECT id, name, address FROM customers WHERE org_id = ?", (st.session_state['org_id'],)).fetchall()
            customer_options = ["Create New Customer"] + [f"{cust[1]} ({cust[2]})" for cust in customers]
            selected_customer = st.selectbox("Select Customer", customer_options)
            
            if selected_customer == "Create New Customer":
                new_name = st.text_input("New Customer Name")
                new_address = st.text_input("New Customer Solana Address")
                new_email = st.text_input("New Customer Email")
                new_country = st.text_input("Country (e.g., US)", "US", key="new_sub_country")
                if st.button("Create Customer and Proceed"):
                    created_at = datetime.now().isoformat()
                    c.execute("INSERT INTO customers (name, address, email, created_at, country, org_id) VALUES (?, ?, ?, ?, ?, ?)",
                              (new_name, new_address, new_email, created_at, new_country, st.session_state['org_id']))
                    conn.commit()
                    c.execute("SELECT last_insert_rowid()")
                    customer_id = c.fetchone()[0]
                    st.session_state['current_customer_id'] = customer_id
                    st.session_state['new_customer_created'] = True
                    log_audit(st.session_state['user_id'], "created_customer", f"Name: {new_name}")
                    st.success("Customer created! Please set up a subscription below.")
            else:
                st.session_state['current_customer_id'] = next(cust[0] for cust in customers if f"{cust[1]} ({cust[2]})" == selected_customer)
                st.session_state['new_customer_created'] = False

            if st.session_state['current_customer_id']:
                plan = st.selectbox("Plan", ["Basic ($5/month USDC)", "Premium ($10/month USDC)", "Enterprise (Metered Only)"])
                trial_days = st.number_input("Trial Days", min_value=0, value=7, help="Number of free trial days before billing starts")
                coupon_pct = st.number_input("Coupon %", min_value=0.0, max_value=100.0, value=0.0, help="Percentage discount to apply")
                entitlement = st.selectbox("Entitlement (Features)", ["Basic Access", "Full AI + API", "Enterprise Support"])
                auto_dunning = st.checkbox("Enable Auto Dunning for Unpaid Invoices", value=True, help="Automatically retry failed payments")

                if st.button("Setup Subscription"):
                    with st.spinner("Processing..."):
                        customer_id = st.session_state['current_customer_id']
                        customer_country = c.execute("SELECT country FROM customers WHERE id = ?", (customer_id,)).fetchone()[0]
                        try:
                            tax_calc = stripe.Tax.Calculation.create(
                                currency="usd",
                                line_items=[{"amount": 1000, "quantity": 1, "reference": plan}],
                                customer_details={"address": {"country": customer_country.upper()}},
                            )
                            tax_rate = tax_calc.tax_amount_exclusive / tax_calc.amount_total * 100 if tax_calc.amount_total > 0 else 0.0
                        except:
                            tax_rate = 10.0
                        amount = 5.0 if plan == "Basic ($5/month USDC)" else 10.0 if plan == "Premium ($10/month USDC)" else 0.0
                        start_date = datetime.now().isoformat()
                        last_bill_date = start_date
                        status = "active" if trial_days == 0 else "trialing"
                        auto_dunning_val = 1 if auto_dunning else 0
                        c.execute("INSERT INTO subscriptions (customer_id, plan, amount, start_date, last_bill_date, status, trial_days, coupon_pct, tax_rate, entitlement, auto_dunning) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                  (customer_id, plan, amount, start_date, last_bill_date, status, trial_days, coupon_pct, tax_rate, entitlement, auto_dunning_val))
                        conn.commit()
                        sub_id = c.lastrowid
                        due_date = (datetime.now() + timedelta(days=30)).isoformat()
                        c.execute("INSERT INTO invoices (sub_id, date, amount, status, due_date) VALUES (?, ?, ?, ?, ?)",
                                  (sub_id, start_date, amount, "open", due_date))
                        conn.commit()
                        st.write(f"Debug: Invoice created for Subscription ID {sub_id} with amount {amount} USDC, due on {due_date}")
                        log_audit(st.session_state['user_id'], "created_subscription", f"Customer ID: {customer_id}, Plan: {plan}")
                        today = datetime.now()
                        if today.day > 1:
                            prorate_days = (today + timedelta(days=30 - today.day)).day
                            prorated_amount = amount * (prorate_days / 30)
                            c.execute("INSERT INTO recognized_revenue (sub_id, month, amount, recognized_amount, prorated) VALUES (?, ?, ?, ?, ?)",
                                      (sub_id, today.strftime('%Y-%m'), amount, prorated_amount, 1))
                            c.execute("INSERT INTO deferred_revenue (sub_id, amount, start_date, end_date) VALUES (?, ?, ?, ?)",
                                      (sub_id, amount - prorated_amount, today.isoformat(), (today + timedelta(days=30)).isoformat()))
                            conn.commit()
                            st.info(f"Prorated first month: {prorated_amount} USDC recognized, balance deferred.")
                        st.success("Subscription setup complete! Tax rate applied: {tax_rate}%")
                        st.session_state['new_customer_created'] = False

            if st.button("Generate Missing Invoices for Existing Subscriptions"):
                subs = c.execute("SELECT id, customer_id, amount FROM subscriptions WHERE id NOT IN (SELECT sub_id FROM invoices)").fetchall()
                if subs:
                    for sub in subs:
                        sub_id, customer_id, amount = sub
                        due_date = (datetime.now() + timedelta(days=30)).isoformat()
                        c.execute("INSERT INTO invoices (sub_id, date, amount, status, due_date) VALUES (?, ?, ?, ?, ?)",
                                  (sub_id, datetime.now().isoformat(), amount, "open", due_date))
                        conn.commit()
                        st.write(f"Debug: Generated invoice for Subscription ID {sub_id} with amount {amount} USDC, due on {due_date}")
                    log_audit(st.session_state['user_id'], "generated_missing_invoices", f"Generated {len(subs)} invoices")
                    st.success(f"Generated {len(subs)} missing invoices!")
                else:
                    st.write("No missing invoices to generate.")

    elif page == "🚪 Portal":
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

    elif page == "📄 Invoices":
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
                    c = canvas.Canvas(buffer, pagesize=letter)
                    c.setFont(settings[6], 16)
                    c.drawString(inch, 10 * inch, settings[1])  # Company Name
                    c.drawString(inch, 9.5 * inch, settings[2])  # Company Address
                    c.line(inch, 9 * inch, 6 * inch, 9 * inch)
                    c.drawString(inch, 8.5 * inch, f"Invoice #: {invoice_id}")
                    c.drawString(inch, 8 * inch, f"Date: {issue_date}")
                    c.drawString(inch, 7.5 * inch, f"Due Date: {due_date}")
                    c.drawString(4 * inch, 8.5 * inch, f"Bill To:")
                    c.drawString(4 * inch, 8 * inch, customer_name)
                    c.drawString(4 * inch, 7.5 * inch, customer_email)
                    c.drawString(4 * inch, 7 * inch, customer_address)
                    c.line(inch, 6.5 * inch, 6 * inch, 6.5 * inch)
                    c.drawString(inch, 6 * inch, "Description")
                    c.drawString(4 * inch, 6 * inch, "Amount")
                    c.line(inch, 5.5 * inch, 6 * inch, 5.5 * inch)
                    c.drawString(inch, 5 * inch, "Subscription Fee")
                    c.drawString(4 * inch, 5 * inch, f"${amount} USDC")
                    c.line(inch, 4.5 * inch, 6 * inch, 4.5 * inch)
                    c.drawString(4 * inch, 4 * inch, f"Total: ${amount} USDC")
                    c.setFont(settings[6], 10)
                    c.drawString(inch, 3 * inch, settings[4])  # Footer Text
                    c.showPage()
                    c.save()
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

    elif page == "📜 Txns":
        st.header("Transactions")
        txn_tab1, txn_tab2 = st.tabs(["Transaction Log", "Revenue Recognition"])

        with txn_tab1:
            st.subheader("Transaction Log")
            txns_df = pd.read_sql_query("SELECT id AS ID, tx_sig AS 'Transaction Signature', amount AS 'Amount (USDC)', from_addr AS 'From Address', timestamp AS 'Timestamp', status AS Status FROM transactions WHERE from_addr IN (SELECT address FROM customers WHERE org_id = ?) OR from_addr = ?", (st.session_state['org_id'], str(merchant_keypair.pubkey())), conn)
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

    elif page == "🛒 Products":
        st.header("Products")
        product_tab1, product_tab2 = st.tabs(["Product List", "Add/Edit Product"])

        with product_tab1:
            st.subheader("Product List")
            products_df = pd.read_sql_query("SELECT id AS ID, name AS Name, description AS Description, price AS 'Price (USDC)', billing_frequency AS 'Billing Frequency', active AS Active FROM products WHERE active = 1", conn)
            if not products_df.empty:
                search_query = st.text_input("Search Products (Name, Description)", placeholder="Search by name or description...")
                if search_query:
                    products_df = products_df[
                        products_df['Name'].str.contains(search_query, case=False) |
                        products_df['Description'].str.contains(search_query, case=False)
                    ]
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
            billing_frequency = st.selectbox("Billing Frequency", ["Monthly", "Yearly", "One-Time"])
            image_url = st.text_input("Image URL (Optional)")
            active = st.checkbox("Active", value=True)

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
                    edit_billing_frequency = st.selectbox("Edit Billing Frequency", ["Monthly", "Yearly", "One-Time"], index=["Monthly", "Yearly", "One-Time"].index(prod_data[5]))
                    edit_image_url = st.text_input("Edit Image URL (Optional)", value=prod_data[4] if prod_data[4] else "")
                    edit_active = st.checkbox("Active", value=bool(prod_data[6]))

                    if st.button("Update Product"):
                        c.execute("UPDATE products SET name = ?, description = ?, price = ?, image_url = ?, billing_frequency = ?, active = ? WHERE id = ?",
                                  (edit_name, edit_description, edit_price, edit_image_url, edit_billing_frequency, 1 if edit_active else 0, prod_id))
                        conn.commit()
                        log_audit(st.session_state['user_id'], "updated_product", f"ID: {prod_id}, Name: {edit_name}")
                        st.success("Product updated successfully!")

    elif page == "🧾 Taxes":
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

    elif page == "📈 Reporting":
        st.header("Reporting")
        report_tab1, report_tab2 = st.tabs(["Revenue Report", "Custom Report"])

        with report_tab1:
            st.subheader("Revenue Report")
            start_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=30))
            end_date = st.date_input("End Date", value=datetime.now())
            if start_date and end_date and start_date <= end_date:
                recognized_df = pd.read_sql_query("SELECT month AS Month, SUM(recognized_amount) AS 'Recognized Revenue (USDC)' FROM recognized_revenue WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?)) AND month BETWEEN ? AND ? GROUP BY month", (st.session_state['org_id'], start_date.strftime('%Y-%m'), end_date.strftime('%Y-%m')), conn)
                deferred_df = pd.read_sql_query("SELECT start_date AS 'Start Date', end_date AS 'End Date', SUM(amount) AS 'Deferred Revenue (USDC)' FROM deferred_revenue WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?)) AND start_date BETWEEN ? AND ? GROUP BY start_date, end_date", (st.session_state['org_id'], start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')), conn)
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
                subs_df = pd.read_sql_query("SELECT id, customer_id, plan, amount, start_date, status FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?) AND start_date BETWEEN ? AND ?", (st.session_state['org_id'], start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')), conn)
                invoices_df = pd.read_sql_query("SELECT sub_id, date, amount, status FROM invoices WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?)) AND date BETWEEN ? AND ?", (st.session_state['org_id'], start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')), conn)
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
                        deferred_total = pd.read_sql_query("SELECT SUM(amount) as total FROM deferred_revenue WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?)) AND start_date BETWEEN ? AND ?", (st.session_state['org_id'], start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')), conn)['total'].iloc[0] if not pd.read_sql_query("SELECT SUM(amount) as total FROM deferred_revenue WHERE sub_id IN (SELECT id FROM subscriptions WHERE customer_id IN (SELECT id FROM customers WHERE org_id = ?)) AND start_date BETWEEN ? AND ?", (st.session_state['org_id'], start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')), conn).empty else 0.0
                        st.write(f"Deferred Revenue: ${deferred_total:.2f} USDC")
                else:
                    st.write("No data available for the selected period.")

    elif page == "🔒 Admin":
        st.header("Admin")
        admin_tab1, admin_tab2 = st.tabs(["User Management", "Settings"])

        with admin_tab1:
            st.subheader("User Management")
            users_df = pd.read_sql_query("SELECT id AS ID, username AS Username, email AS Email, name AS Name, role AS Role, created_at AS 'Created At' FROM users WHERE org_id = ?", conn, params=(st.session_state['org_id'],))
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
                selected_user = st.selectbox("Edit User", [f"ID: {user['ID']} - {user['Username']}" for user_index, user in users_df.iterrows()])
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
                selected_webhook = st.selectbox("Edit Webhook", [f"ID: {row['ID']} - {row['Event']}" for index, row in webhooks_df.iterrows()])
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

# Ensure connection is closed when the app stops
conn.close()

