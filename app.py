import streamlit as st
import pandas as pd
import smtplib
import re
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

st.set_page_config(page_title="R&D ELISA Kit Inventory Manager", layout="wide")
st.title("🔬 Advanced Interactive ELISA Kit Live Stock Ledger")
st.caption("Biological and Development Lab, R&D — Fully Dynamic Row & Column Editor")

CSV_FILENAME = "ELISA_KIT_STOCK_ALARM_VBA_READY.csv"

# --- AUTOMATED BACKGROUND EMAIL SYSTEM ---
def auto_email_alert(kit_name, lot_no, remaining, calculated_status):
    try:
        smtp_server = st.secrets["email"]["smtp_server"]
        port = st.secrets["email"]["port"]
        sender = st.secrets["email"]["sender_email"]
        password = st.secrets["email"]["sender_password"]
        
        raw_receivers = st.secrets["email"]["receiver_email"]
        receivers_list = [e.strip() for e in raw_receivers.split(",")]
        
        server = smtplib.SMTP(smtp_server, port)
        server.starttls()
        server.login(sender, password)
        
        for receiver in receivers_list:
            msg = MIMEMultipart()
            msg['From'] = sender
            msg['To'] = receiver
            msg['Subject'] = f"⚠️ AUTOMATED LAB STOCK ALERT: {kit_name} is {calculated_status}"
            
            body = f"""Hello Lab Team,

An inventory update on the web dashboard has triggered an immediate threshold alert:

• Product Name: {kit_name}
• Lot Reference: {lot_no}
• System Calculated Status: {calculated_status}
• Current Remaining Runs: {remaining}

Please log into the dashboard or check storage to process replenishment orders."""
            msg.attach(MIMEText(body, 'plain'))
            server.sendmail(sender, receiver, msg.as_string())
            
        server.quit()
        return True
    except Exception as e:
        st.sidebar.error(f"Background email transmission failure: {e}")
        return False

# --- DYNAMIC RULES ENGINE FOR STATUS & ALARMS ---
def compute_stock_status(remaining_val):
    if pd.isna(remaining_val) or str(remaining_val).strip() == "" or str(remaining_val).upper().strip() == "N/A":
        return "N/A", "NO ALARM", None
        
    try:
        clean_match = re.findall(r"[-+]?\d*\.\d+|\d+", str(remaining_val))
        if not clean_match:
            return "N/A", "NO ALARM", None
            
        val = float(clean_match)
        if val <= 0:
            return "CRITICAL", "FLASH / REORDER NOW", val
        elif val <= 2:
            return "LOW STOCK", "REORDER SOON", val
        else:
            return "OK", "OK", val
    except:
        return "N/A", "NO ALARM", None

# --- COLOR HIGHLIGHTING MATRIX FUNCTION ---
def style_row_by_status(row):
    if 'Stock Status' in row.index:
        status = str(row['Stock Status']).upper()
        if 'CRITICAL' in status:
            return ['background-color: #ffcccc; color: black'] * len(row)
        elif 'LOW' in status:
            return ['background-color: #fff2cc; color: black'] * len(row)
        elif 'OK' in status:
            return ['background-color: #e2f0d9; color: black'] * len(row)
    return [''] * len(row)

# --- LOAD CSV REGISTRY ---
def load_data():
    if not os.path.exists(CSV_FILENAME):
        # Create an emergency skeleton tracking structure if file is wiped or lost
        return pd.DataFrame(columns=['Sl No.', 'Elisa Kit Name', 'Batch No', 'Lot no.', 'Condition', 'Remaining times of Experiment', 'Total In Stock', 'Stock Status', 'Alarm', 'Remarks/ Comments'])
        
    with open(CSV_FILENAME, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    header_idx = 0
    for idx, line in enumerate(lines):
        if "Elisa Kit Name" in line or "Sl No." in line:
            header_idx = idx
            break
    df = pd.read_csv(CSV_FILENAME, skiprows=header_idx)
    df.columns = df.columns.str.strip()
    df = df.dropna(how='all')
    return df

if 'inventory_df' not in st.session_state:
    st.session_state.inventory_df = load_data()

df = st.session_state.inventory_df
exp_col = 'Remaining times of Experiment' if 'Remaining times of Experiment' in df.columns else 'Remaining times of Experiment  '
notes_col = 'Remarks/ Comments' if 'Remarks/ Comments' in df.columns else 'Remarks/ Comments '

st.subheader("🛠️ Custom Structure Operations Manager")
col_action1, col_action2, col_action3 = st.columns(3)

with col_action1:
    # ➕ ADD NEW PRODUCT ROW BUTTON
    if st.button("➕ Add New Blank Row", use_container_width=True):
        next_sl = 1 if df.empty else (pd.to_numeric(df['Sl No.'], errors='coerce').max() + 1)
        if pd.isna(next_sl): next_sl = len(df) + 1
        
        new_row = {col: "" for col in df.columns}
        new_row['Sl No.'] = int(next_sl)
        new_row['Elisa Kit Name'] = "New Kit Name"
        if 'Qty.' in df.columns: new_row['Qty.'] = 1
        if 'Total In Stock' in df.columns: new_row['Total In Stock'] = 1
        if exp_col in df.columns: new_row[exp_col] = "6 times"
        if 'Stock Status' in df.columns: new_row['Stock Status'] = "OK"
        if 'Alarm' in df.columns: new_row['Alarm'] = "OK"
        
        st.session_state.inventory_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        st.rerun()

with col_action2:
    # ➕ DYNAMIC COLUMN INJECTOR POPUP WIDGET
    with st.popover("➕ Add Custom Blank Column", use_container_width=True):
        new_col_name = st.text_input("Enter Column Heading Title Name:", placeholder="e.g., Expiry Date, Storage Location").strip()
        if st.button("Confirm & Inject Column"):
            if new_col_name and new_col_name not in df.columns:
                # Add the column with empty placeholder strings across all existing rows
                df[new_col_name] = ""
                st.session_state.inventory_df = df
                st.success(f"Column '{new_col_name}' injected successfully!")
                st.rerun()
            elif new_col_name in df.columns:
                st.error("A column heading layout with that exact name already exists.")

with col_action3:
    st.info("💡 **Tip:** Double-click cells to modify strings. Use the sidebar controller button to permanently save layout updates to storage.")

# --- THE DYNAMIC GRID CONTROLLER COMPONENT ---
disabled_columns = ["Sl No.", "Stock Status", "Alarm", "Remaining Numeric"]
active_config = {c: st.column_config.TextColumn(c, disabled=True) for c in disabled_columns if c in df.columns}

edited_df = st.data_editor(
    df,
    use_container_width=True,
    num_rows="dynamic",
    hide_index=True,
    column_config=active_config
)

st.sidebar.header("💾 Sync Data Controller")
if st.sidebar.button("💾 Commit & Save All Changes", use_container_width=True, type="primary"):
    emails_sent_count = 0
    
    # Refresh statuses across modified rows dynamically
    if exp_col in edited_df.columns:
        for idx, row in edited_df.iterrows():
            old_remaining = df.loc[idx, exp_col] if idx in df.index else None
            current_remaining = row[exp_col]
            
            calc_status, calc_alarm, calc_num = compute_stock_status(current_remaining)
            
            if 'Stock Status' in edited_df.columns: edited_df.at[idx, 'Stock Status'] = calc_status
            if 'Alarm' in edited_df.columns: edited_df.at[idx, 'Alarm'] = calc_alarm
            if 'Remaining Numeric' in edited_df.columns: edited_df.at[idx, 'Remaining Numeric'] = str(calc_num) if calc_num is not None else ""

            if current_remaining != old_remaining and calc_status in ["CRITICAL", "LOW STOCK"]:
                if auto_email_alert(row.get('Elisa Kit Name', 'Unnamed Product'), row.get('Lot no.', 'N/A'), current_remaining, calc_status):
                    emails_sent_count += 1
                
    st.session_state.inventory_df = edited_df
    
    # Stream downstream grid changes straight back to central storage file database
    with open(CSV_FILENAME, "w", encoding="utf-8") as f:
        f.write('"ELISA KIT IN BIOLOGUCAL AND DEVELOPMENT LAB,R&D",,,,,,,,,,,,,__\n__,,,,,,,,,,,,,,\n')
        edited_df.to_csv(f, index=False)
        
    st.sidebar.success("📊 Matrix database layout synchronized successfully!")
    st.rerun()

# --- COLORIZED QUICK VIEW OVERVIEW MATRIX ---
st.subheader("📊 Color-Coded Quick View Ledger")
styled_ledger = edited_df.style.apply(style_row_by_status, axis=1)
st.dataframe(styled_ledger, use_container_width=True, hide_index=True)
