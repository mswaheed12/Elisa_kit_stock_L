import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="R&D ELISA Kit Inventory", layout="wide")
st.title("🔬 ELISA Kit Inventory & Alert Dashboard")
st.caption("Biological and Development Lab, R&D")

@st.cache_data
def load_data():
    # Read raw lines to find where the actual table columns start
    with open("ELISA_KIT_STOCK_ALARM_VBA_READY.csv", "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    
    # Locate the row that contains our target column headers
    header_idx = 0
    for idx, line in enumerate(lines):
        if "Elisa Kit Name" in line or "Sl No." in line:
            header_idx = idx
            break
            
    # Read the CSV starting from that specific valid header row
    df = pd.read_csv("ELISA_KIT_STOCK_ALARM_VBA_READY.csv", skiprows=header_idx)
    
    # Standardize column header spacing and names
    df.columns = df.columns.str.strip()
    
    # Drop rows that are entirely empty or missing critical indices
    df = df.dropna(how='all')
    if 'Sl No.' in df.columns:
        df = df[df['Sl No.'].notna()]
        
    return df

try:
    df = load_data()
    
    # Clean up empty slots caused by merged cells in Excel
    if 'Elisa Kit Name' in df.columns:
        df['Elisa Kit Name'] = df['Elisa Kit Name'].ffill()
    else:
        st.error(f"Could not find 'Elisa Kit Name' column. Available columns are: {list(df.columns)}")
        st.stop()

    # Define standard column safety fallbacks
    status_col = 'Stock Status' if 'Stock Status' in df.columns else ('Alarm' if 'Alarm' in df.columns else None)
    exp_col = 'Remaining times of Experiment' if 'Remaining times of Experiment' in df.columns else 'Remaining times of Experiment  '
    notes_col = 'Remarks/ Comments' if 'Remarks/ Comments' in df.columns else 'Remarks/ Comments '

    # --- 1. CRITICAL NOTIFICATION BAR ---
    if status_col:
        critical_items = df[df[status_col].str.upper().fillna('').str.contains('CRITICAL|FLASH')]
        if not critical_items.empty:
            st.error("🚨 **CRITICAL ALARM: REORDER NOW** 🚨")
            for idx, row in critical_items.iterrows():
                kit_name = row.get('Elisa Kit Name', 'Unknown Kit')
                lot_no = row.get('Lot no.', 'N/A')
                rem_exp = row.get(exp_col, '0')
                notes = row.get(notes_col, 'No notes.')
                st.warning(f"**{kit_name}** (Lot: {lot_no}) has **{rem_exp}** left! Note: {notes}")
    st.divider()

    # --- 2. SUMMARY METRICS ---
    st.subheader("📋 Stock Overview Summary")
    col1, col2, col3 = st.columns(3)
    
    if status_col:
        total_ok = len(df[df[status_col].str.upper().fillna('').str.contains('OK')])
        total_low = len(df[df[status_col].str.upper().fillna('').str.contains('LOW')])
        total_crit = len(df[df[status_col].str.upper().fillna('').str.contains('CRITICAL|FLASH')])
        
        col1.metric("Healthy Stock (OK)", total_ok)
        col2.metric("Low Stock (Reorder Soon)", total_low, delta="-Attention", delta_color="inverse")
        col3.metric("Critical Action Needed", total_crit, delta="-Urgent", delta_color="normal")

    # --- 3. INTERACTIVE SEARCH & FILTERS ---
    st.sidebar.header("🔍 Inventory Search Filters")
    search_query = st.sidebar.text_input("Search by Kit Name or Lot #:")
    
    if status_col and df[status_col].dropna().unique().size > 0:
        status_filter = st.sidebar.multiselect("Filter by Stock Status:", options=df[status_col].dropna().unique(), default=df[status_col].dropna().unique())
        filtered_df = df[df[status_col].isin(status_filter)]
    else:
        filtered_df = df

    if search_query:
        filtered_df = filtered_df[
            filtered_df['Elisa Kit Name'].str.contains(search_query, case=False, na=False) |
            filtered_df['Lot no.'].astype(str).str.contains(search_query, case=False, na=False)
        ]

    # --- 4. DATA TABLE DISPLAY ---
    st.subheader("📦 Live Stock Ledger")
    # Dynamically select readable display columns based on what's present
    all_cols = list(df.columns)
    display_cols = [c for c in ['Sl No.', 'Elisa Kit Name', 'Batch No', 'Lot no.', 'Condition', exp_col, status_col, notes_col] if c in all_cols]
    
    st.dataframe(filtered_df[display_cols], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Please check your CSV format setup. Error profile details: {e}")
