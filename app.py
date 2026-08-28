import streamlit as st
import pandas as pd
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

st.set_page_config(page_title="R&D ELISA Kit Inventory Manager", layout="wide")
st.title("🔬 Advanced Interactive ELISA Kit Live Stock Ledger")
st.caption("Biological and Development Lab, R&D — Fully Editable Grid View")

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
            
            body = f"""
            Hello Lab Team,
            
            An inventory update has automatically triggered a threshold alert:
            
            • Product Name: {kit_name}
            • Lot Reference: {lot_no}
            • System Calculated Status: {calculated_status}
            • Current Remaining Runs: {remaining}
            
            Please verify stock levels or proceed with procurement replenishment.
            """
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
        # Extract numerical digits or decimals (handles things like "4.5 Time" or "6 times")
        clean_match = re.findall(r"[-+]?\d*\.\d+|\d+", str(remaining_val))
        if not clean_match:
            return "N/A", "NO ALARM", None
            
        val = float(clean_match[0])
        if val <= 0:
            return "CRITICAL", "FLASH / REORDER NOW", val
        elif val <= 2:
            return "LOW STOCK", "REORDER SOON", val
        else:
            return "OK", "OK", val
    except:
        return "N/A", "NO ALARM", None

# --- LOAD CENTRAL CSV DATA SOURCE ---
def load_data():
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

# Initialize session state dataframe to handle edits across refreshes
if 'inventory_df' not in st.session_state:
    st.session_state.inventory_df = load_data()

df = st.session_state.inventory_df

# Map out explicit key columns found in your template layout
exp_col = 'Remaining times of Experiment' if 'Remaining times of Experiment' in df.columns else 'Remaining times of Experiment  '
notes_col = 'Remarks/ Comments' if 'Remarks/ Comments' in df.columns else 'Remarks/ Comments '

# --- METRIC AND ACTION ROW BANNER ---
st.subheader("🛠️ Bulk Operations & Sheet Editor")
col_action1, col_action2 = st.columns([1, 4])

with col_action1:
    # ➕ ADD NEW PRODUCT BUTTON
    if st.button("➕ Add New Blank Row", use_container_width=True):
        next_sl = 1 if df.empty else (pd.to_numeric(df['Sl No.'], errors='coerce').max() + 1)
        if pd.isna(next_sl): next_sl = len(df) + 1
        
        # Structure a blank template row matches original format exactly
        new_row = {col: "" for col in df.columns}
        new_row['Sl No.'] = int(next_sl)
        new_row['Elisa Kit Name'] = "New Kit Template Name"
        new_row['Qty.'] = 1
        new_row[exp_col] = "6 times"
        new_row['Stock Status'] = "OK"
        new_row['Alarm'] = "OK"
        
        st.session_state.inventory_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        st.rerun()

with col_action2:
    st.info("💡 **How to Edit:** Double-click on any cell below to change names, lots, remaining experiments, or comments directly. When done, click **'💾 Commit & Save All Changes'** in the sidebar.")

# --- THE MAIN INTERACTIVE DATA GRID (EXCEL STYLE) ---
# st.data_editor converts the standard grid into a completely responsive, fully editable array
edited_df = st.data_editor(
    df,
    use_container_width=True,
    num_rows="dynamic", # Allows lab users to add/delete rows directly on screen if desired
    hide_index=True,
    column_config={
        "Sl No.": st.column_config.NumberColumn("Sl No.", disabled=True), # Lock sequence numbers
        "Stock Status": st.column_config.TextColumn("Stock Status", disabled=True), # Let python calculate this safely
        "Alarm": st.column_config.TextColumn("Alarm", disabled=True), # Let python calculate this safely
        "Remaining Numeric": st.column_config.TextColumn("Remaining Numeric", disabled=True)
    }
)

# --- SIDEBAR CONTROL PANEL FOR COMMITTING AND TRACKING CHANGE LOGS ---
st.sidebar.header("💾 Sync Data Controller")

if st.sidebar.button("💾 Commit & Save All Changes", use_container_width=True, type="primary"):
    emails_sent_count = 0
    
    # Run through the grid row-by-row to run calculations and detect shifts
    for idx, row in edited_df.iterrows():
        old_remaining = df.loc[idx, exp_col] if idx in df.index else None
        current_remaining = row[exp_col]
        
        # Calculate status flags using our formula engine
        calc_status, calc_alarm, calc_num = compute_stock_status(current_remaining)
        
        edited_df.at[idx, 'Stock Status'] = calc_status
        edited_df.at[idx, 'Alarm'] = calc_alarm
        if 'Remaining Numeric' in edited_df.columns:
            edited_df.at[idx, 'Remaining Numeric'] = str(calc_num) if calc_num is not None else ""

        # Trigger emails ONLY if the user changed the values to a warning state
        if current_remaining != old_remaining and calc_status in ["CRITICAL", "LOW STOCK"]:
            kit_title = row.get('Elisa Kit Name', 'Unnamed Product Entry')
            lot_ref = row.get('Lot no.', 'N/A')
            
            # Fire email notification immediately
            if auto_email_alert(kit_title, lot_ref, current_remaining, calc_status):
                emails_sent_count += 1
                
    # Update local memory registry state
    st.session_state.inventory_df = edited_df
    
    # Overwrite data base ledger file
    with open(CSV_FILENAME, "w", encoding="utf-8") as f:
        f.write('"ELISA KIT IN BIOLOGUCAL AND DEVELOPMENT LAB,R&D",,,,,,,,,,,,,__\n__,,,,,,,,,,,,,,\n')
        edited_df.to_csv(f, index=False)
        
    st.sidebar.success("📊 File system synchronized and saved!")
    if emails_sent_count > 0:
        st.sidebar.info(f"✉️ Outbound alerts complete: {emails_sent_count} critical updates mailed out!")
        
    st.rerun()

# --- DYNAMIC GLOBAL ERROR MONITORING STRIP ---
critical_mask = edited_df['Stock Status'].str.upper().fillna('').str.contains('CRITICAL|FLASH|LOW STOCK')
danger_rows = edited_df[critical_mask]

if not danger_rows.empty:
    st.divider()
    st.error("🚨 **LAB RUNTIME ALERT: CURRENT DEPLOYED RISK INVENTORY** 🚨")
    for _, d_row in danger_rows.iterrows():
        st.warning(f"⚠️ **[{d_row['Stock Status']}]** Item: **{d_row['Elisa Kit Name']}** | Lot: {d_row['Lot no.']} inside ledger reads: **{d_row[exp_col]}** remaining experiments left.")
