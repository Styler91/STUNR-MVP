import dash
from dash import Dash
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import stripe
from solana.rpc.api import Client
import numpy as np

# Initialize Dash app
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Initialize database connection
conn = sqlite3.connect('stunr_db.sqlite', check_same_thread=False)
c = conn.cursor()

# Mock email sender
def mock_email(to_email, subject, body, attachment=None):
    print(f"Email sent to {to_email}: Subject - {subject}\nBody - {body}\nAttachment - {attachment if attachment else 'None'}")

# Audit logging function
def log_audit(user_id, action, details):
    timestamp = datetime.now().isoformat()
    c.execute("INSERT INTO audit_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
              (user_id, action, details, timestamp))
    conn.commit()
    print(f"Audit Log: {action} - {details} at {timestamp}")  # Using print for now

# Connect to Solana devnet (for mock balance)
client = Client("https://api.devnet.solana.com")

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
try:
    c.execute("ALTER TABLE customers ADD COLUMN custom_field TEXT")
    conn.commit()
except:
    pass

# Fetch customers
customers_df = pd.read_sql_query("SELECT id, name, email, address, street, city, state, zip_code, custom_field, country, created_at FROM customers WHERE org_id = ?", conn, params=(1,))
if not customers_df.empty:
    customers_df['sub_status'] = [c.execute("SELECT status FROM subscriptions WHERE customer_id = ? LIMIT 1", (row['id'],)).fetchone()[0] if c.execute("SELECT status FROM subscriptions WHERE customer_id = ? LIMIT 1", (row['id'],)).fetchone() else "None" for index, row in customers_df.iterrows()]
    customers_df['solana_balance'] = customers_df['address'].apply(lambda x: round(np.random.uniform(0, 100), 2) if x else 0.0)

# Layout
app.layout = dbc.Container([
    html.H1("Customer List", className="text-center my-4", style={'background': 'linear-gradient(45deg, #04837b, #036b65)', '-webkit-background-clip': 'text', 'color': 'transparent'}),
    dbc.Row([
        dbc.Col([
            dbc.Input(id="search-input", type="text", placeholder="Search by Name, Email, or Address", className="mb-3"),
            dbc.Select(id="status-filter", options=[{"label": s, "value": s} for s in ["All", "active", "trialing", "canceled", "None"]], value="All", className="mb-3"),
            dbc.Select(id="city-filter", options=[{"label": "All", "value": "All"}] + [{"label": c, "value": c} for c in sorted(customers_df['city'].dropna().unique().tolist())], value="All", className="mb-3"),
            dbc.Select(id="state-filter", options=[{"label": "All", "value": "All"}] + [{"label": s, "value": s} for s in sorted(customers_df['state'].dropna().unique().tolist())], value="All", className="mb-3"),
            dbc.Button("Reset Filters", id="reset-filters", color="primary", className="mb-3"),
        ], width=3),
        dbc.Col([
            dbc.Row(id="customer-grid", className="g-3"),
            html.Div(id="selected-customer", className="mt-4")
        ], width=9)
    ]),
    dbc.Modal([
        dbc.ModalHeader("Edit Customer"),
        dbc.ModalBody([
            dbc.Input(id="edit-name", placeholder="Name", className="mb-2"),
            dbc.Input(id="edit-email", placeholder="Email", className="mb-2"),
            dbc.Input(id="edit-address", placeholder="Solana Address", className="mb-2"),
            dbc.Input(id="edit-street", placeholder="Street", className="mb-2"),
            dbc.Input(id="edit-city", placeholder="City", className="mb-2"),
            dbc.Input(id="edit-state", placeholder="State", className="mb-2"),
            dbc.Input(id="edit-zip", placeholder="Zip/Postal Code", className="mb-2"),
            dbc.Input(id="edit-custom", placeholder="Custom Field", className="mb-2"),
            dbc.Input(id="edit-country", placeholder="Country", className="mb-2"),
        ]),
        dbc.ModalFooter([
            dbc.Button("Save", id="save-edit", color="success"),
            dbc.Button("Cancel", id="cancel-edit", color="secondary")
        ])
    ], id="edit-modal", is_open=False)
], fluid=True, style={'background': 'linear-gradient(135deg, #f9fafc, #e6f0fa)'})

# Callbacks
@app.callback(
    Output("customer-grid", "children"),
    [Input("search-input", "value"),
     Input("status-filter", "value"),
     Input("city-filter", "value"),
     Input("state-filter", "value"),
     Input("reset-filters", "n_clicks")])
def update_customer_grid(search, status, city, state, reset):
    ctx = dash.callback_context
    if ctx.triggered and "reset-filters" in [x['prop_id'] for x in ctx.triggered]:
        return [dbc.Col(create_customer_card(row), width=4) for index, row in customers_df.iterrows()]
    filtered_df = customers_df.copy()
    if search:
        filtered_df = filtered_df[
            filtered_df['name'].str.contains(search, case=False) |
            filtered_df['email'].str.contains(search, case=False) |
            filtered_df['address'].str.contains(search, case=False)
        ]
    if status != "All":
        filtered_df = filtered_df[filtered_df['sub_status'] == status]
    if city != "All":
        filtered_df = filtered_df[filtered_df['city'] == city]
    if state != "All":
        filtered_df = filtered_df[filtered_df['state'] == state]
    return [dbc.Col(create_customer_card(row), width=4) for index, row in filtered_df.iterrows()]

def create_customer_card(row):
    status_color = {'active': '#28a745', 'canceled': '#dc3545', 'trialing': '#ffc107', 'None': '#6c757d'}
    return dbc.Card([
        dbc.CardHeader(html.H4(row['name'], style={'color': '#04837b'})),
        dbc.CardBody([
            html.P(f"Email: {row['email']}"),
            html.P(f"Address: {row['address']}"),
            html.P(f"Physical: {row['street']}, {row['city']}, {row['state']} {row['zip_code']}"),
            html.P(f"Country: {row['country']}"),
            html.P(f"Custom: {row['custom_field']}"),
            html.P(f"Balance: ${row['solana_balance']} USDC", style={'color': '#04837b'}),
            html.P(f"Status: ", style={'display': 'inline'}),
            html.Span(row['sub_status'], className=f"badge bg-{status_color.get(row['sub_status'].lower(), 'secondary')}", style={'color': 'white' if row['sub_status'].lower() in ['active', 'canceled'] else 'black'}),
            html.P(f"Created: {row['created_at']}"),
        ]),
        dbc.CardFooter([
            dbc.Button("Edit", id={"type": "edit-button", "index": row['id']}, color="primary", className="me-2"),
            dbc.Button("Invoice", id={"type": "invoice-button", "index": row['id']}, color="info", className="me-2"),
            dbc.Button("Verify on Solana", id={"type": "verify-button", "index": row['id']}, color="warning")
        ])
    ], style={'margin-bottom': '1rem', 'transition': 'transform 0.3s', 'box-shadow': '0 4px 8px rgba(0,0,0,0.1)'}, className="hover-card")

@app.callback(
    Output("edit-modal", "is_open"),
    Output("edit-name", "value"),
    Output("edit-email", "value"),
    Output("edit-address", "value"),
    Output("edit-street", "value"),
    Output("edit-city", "value"),
    Output("edit-state", "value"),
    Output("edit-zip", "value"),
    Output("edit-custom", "value"),
    Output("edit-country", "value"),
    [Input({"type": "edit-button", "index": ALL}, "n_clicks")],
    [State({"type": "edit-button", "index": ALL}, "id")])
def open_edit_modal(n_clicks, ids):
    ctx = dash.callback_context
    if not ctx.triggered:
        return False, "", "", "", "", "", "", "", "", ""
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    index = json.loads(button_id.replace("'", '"'))['index']
    customer = c.execute("SELECT name, email, address, street, city, state, zip_code, custom_field, country FROM customers WHERE id = ?", (index,)).fetchone()
    return True, customer[0], customer[1], customer[2], customer[3], customer[4], customer[5], customer[6], customer[7], customer[8]

@app.callback(
    Output("edit-modal", "is_open", allow_duplicate=True),
    Output({"type": "edit-button", "index": MATCH}, "n_clicks"),
    [Input("save-edit", "n_clicks")],
    [Input("cancel-edit", "n_clicks")],
    [State("edit-name", "value")],
    [State("edit-email", "value")],
    [State("edit-address", "value")],
    [State("edit-street", "value")],
    [State("edit-city", "value")],
    [State("edit-state", "value")],
    [State("edit-zip", "value")],
    [State("edit-custom", "value")],
    [State("edit-country", "value")],
    [State({"type": "edit-button", "index": MATCH}, "id")])
def save_or_cancel_edit(save_clicks, cancel_clicks, name, email, address, street, city, state, zip_code, custom_field, country, id):
    ctx = dash.callback_context
    if not ctx.triggered:
        return False, 0
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    index = json.loads(id.replace("'", '"'))['index']
    if "save-edit" in button_id and save_clicks:
        c.execute("UPDATE customers SET name = ?, email = ?, address = ?, street = ?, city = ?, state = ?, zip_code = ?, custom_field = ?, country = ? WHERE id = ?",
                  (name, email, address, street, city, state, zip_code, custom_field, country, index))
        conn.commit()
        log_audit(1, "edited_customer", f"ID: {index}")  # Hardcoded user_id for now
        return False, 0
    elif "cancel-edit" in button_id and cancel_clicks:
        return False, 0
    return False, 0

@app.callback(
    Output("selected-customer", "children"),
    [Input({"type": "invoice-button", "index": ALL}, "n_clicks")],
    [Input({"type": "verify-button", "index": ALL}, "n_clicks")],
    [State({"type": "invoice-button", "index": ALL}, "id")],
    [State({"type": "verify-button", "index": ALL}, "id")])
def handle_actions(invoice_clicks, verify_clicks, invoice_ids, verify_ids):
    ctx = dash.callback_context
    if not ctx.triggered:
        return ""
    prop_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if "invoice-button" in prop_id:
        index = json.loads(invoice_ids[[i for i, x in enumerate(invoice_clicks) if x][0]].replace("'", '"'))['index']
        subs = c.execute("SELECT id, amount FROM subscriptions WHERE customer_id = ?", (index,)).fetchone()
        if subs:
            sub_id, amount = subs
            due_date = (datetime.now() + timedelta(days=30)).isoformat()
            c.execute("INSERT INTO invoices (sub_id, date, amount, status, due_date) VALUES (?, ?, ?, ?, ?)",
                      (sub_id, datetime.now().isoformat(), amount, "open", due_date))
            conn.commit()
            log_audit(1, "created_invoice", f"Customer ID: {index}, Amount: {amount}")
            return html.Div(f"Invoice created for ${amount} USDC, due on {due_date}", className="alert alert-success")
        return html.Div("No subscription found for this customer.", className="alert alert-danger")
    elif "verify-button" in prop_id:
        index = json.loads(verify_ids[[i for i, x in enumerate(verify_clicks) if x][0]].replace("'", '"'))['index']
        customer = c.execute("SELECT name FROM customers WHERE id = ?", (index,)).fetchone()
        return html.Div(f"Mock verification for {customer[0]}: Data hashed on Solana (ID: {index})", className="alert alert-info")
    return ""

# Remove the ALL constant if not defined
ALL = None

if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8050)