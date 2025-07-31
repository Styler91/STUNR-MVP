import streamlit as st
from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.pubkey import Pubkey as PublicKey
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
from datetime import datetime
import pandas as pd
import altair as alt
import numpy as np
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

# Connect to Solana devnet
client = Client("https://api.devnet.solana.com")

# Load your merchant wallet (adjusted path)
try:
    with open('C:/Users/Tyler/Desktop/stunr-mvp/wallet.json') as f:  # Absolute path to your project folder
        wallet_data = json.load(f)
    merchant_keypair = Keypair.from_bytes(bytes(wallet_data))
except FileNotFoundError:
    st.error("wallet.json not found. Please place it in C:/Users/Tyler/Desktop/stunr-mvp/ and restart the app.")
    st.stop()

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

# Fetch or initialize payment settings
payment_settings = c.execute("SELECT * FROM payment_settings").fetchone()
if not payment_settings:
    c.execute("INSERT INTO payment_settings (stripe_publishable_key, stripe_secret_key) VALUES (?, ?)",
              ("pk_test_...", "sk_test_..."))  # Replace with real test keys
    conn.commit()
    payment_settings = c.execute("SELECT * FROM payment_settings").fetchone()
stripe.api_key = payment_settings[2]  # Secret key

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
                                        except Exception as e:
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