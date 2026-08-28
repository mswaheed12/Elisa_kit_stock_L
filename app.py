import streamlit as st
import pandas as pd

# Set up page styling
st.set_page_config(page_title="R&D ELISA Kit Inventory", layout="wide")
st.title("🔬 ELISA Kit Inventory & Alert Dashboard")
st.caption("Biological and Development Lab, R&D")

# Load your custom inventory template safely
@st.cache_data
def load_data():
    # Reading the CSV file, skipping the top title row to align headers
    df = pd.read_csv("elisa_inventory.csv", skiprows=1)
    # Remove completely empty rows or columns if any exist
    df = df.dropna(how='all').dropna(axis=1, how='all')
    return df

try:
    df = load_data()
    
    # Fill merged kit names down to row entries for accurate searching
    df['Elisa Kit Name'] = df['Elisa Kit Name'].ffill()

    # --- 1. CRITICAL NOTIFICATION BAR ---
    # Filter items marked as CRITICAL or 0 remaining runs
    critical_items = df[df['Stock Status'].str.upper().fillna('') == 'CRITICAL']
    
    if not critical_items.empty:
        st.error("🚨 **CRITICAL ALARM: REORDER NOW** 🚨")
        for idx, row in critical_items.iterrows():
            st.warning(f"**{row['Elisa Kit Name']}** (Lot: {row['Lot no.']}) has **{row['Remaining times of Experiment  ']}** left! Note: {row['Remarks/ Comments ']}")
            
    st.divider()

    # --- 2. SUMMARY METRICS ---
    st.subheader("📋 Stock Overview Summary")
    col1, col2, col3 = st.columns(3)
    
    total_ok = len(df[df['Stock Status'].str.upper().fillna('') == 'OK'])
    total_low = len(df[df['Stock Status'].str.upper().fillna('') == 'LOW STOCK'])
    total_crit = len(critical_items)
    
    col1.metric("Healthy Stock (OK)", total_ok)
    col2.metric("Low Stock (Reorder Soon)", total_low, delta="-Attention", delta_color="inverse")
    col3.metric("Critical Action Needed", total_crit, delta="-Urgent", delta_color="normal")

    # --- 3. INTERACTIVE SEARCH & FILTERS ---
    st.sidebar.header("🔍 Inventory Search Filters")
    search_query = st.sidebar.text_input("Search by Kit Name or Lot #:")
    status_filter = st.sidebar.multiselect("Filter by Stock Status:", options=df['Stock Status'].dropna().unique(), default=df['Stock Status'].dropna().unique())

    # Apply filters to dataset
    filtered_df = df[df['Stock Status'].isin(status_filter)]
    if search_query:
        filtered_df = filtered_df[
            filtered_df['Elisa Kit Name'].str.contains(search_query, case=False, na=False) |
            filtered_df['Lot no.'].astype(str).str.contains(search_query, case=False, na=False)
        ]

    # --- 4. DATA TABLE DISPLAY ---
    st.subheader("📦 Live Stock Ledger")
    # Clean display subset of columns
    display_cols = ['Sl No.', 'Elisa Kit Name', 'Batch No', 'Lot no.', 'Condition', 'Remaining times of Experiment  ', 'Stock Status', 'Remarks/ Comments ']
    st.dataframe(filtered_df[display_cols], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Please check your 'elisa_inventory.csv' format. Error profile: {e}")
