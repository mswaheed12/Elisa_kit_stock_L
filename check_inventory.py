import os
import re
import sys
import smtplib
import pandas as pd
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

CSV_FILENAME = "ELISA_KIT_STOCK_ALARM_VBA_READY.csv"

def send_scheduled_email(subject, html_body, attach_file=False):
    smtp_server = os.environ.get("SMTP_SERVER", "://gmail.com")
    port = int(os.environ.get("SMTP_PORT", 587))
    sender = os.environ.get("SENDER_EMAIL")
    password = os.environ.get("SENDER_PASSWORD")
    raw_receivers = os.environ.get("RECEIVER_EMAIL")
    
    if not sender or not password or not raw_receivers:
        print("Configuration Error: Missing secure email credentials or recipient variables.")
        return
        
    receivers_list = [e.strip() for e in raw_receivers.split(",")]
    
    server = smtplib.SMTP(smtp_server, port)
    server.starttls()
    server.login(sender, password)
    
    for receiver in receivers_list:
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = receiver
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))
        
        if attach_file and os.path.exists(CSV_FILENAME):
            try:
                with open(CSV_FILENAME, "rb") as attachment:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment.read())
                
                encoders.encode_base64(part)
                timestamp = datetime.now().strftime('%Y-%m-%d')
                attachment_name = f"ELISA_Lab_Inventory_Report_{timestamp}.csv"
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename= {attachment_name}",
                )
                msg.attach(part)
            except Exception as attachment_err:
                print(f"Warning: Failed to append data attachment: {attachment_err}")
        
        server.sendmail(sender, receiver, msg.as_string())
        
    server.quit()
    print("Scheduled email batch dispatch with attachments processed successfully.")

# Parse spreadsheet
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
if 'Elisa Kit Name' in df.columns:
    df['Elisa Kit Name'] = df['Elisa Kit Name'].ffill()

exp_col = 'Remaining times of Experiment' if 'Remaining times of Experiment' in df.columns else 'Remaining times of Experiment  '

critical_rows = df[df['Stock Status'].str.upper().fillna('').str.contains('CRITICAL|FLASH')]
low_rows = df[df['Stock Status'].str.upper().fillna('').str.contains('LOW')]

run_mode = sys.argv[1] if len(sys.argv) > 1 else "scan"

if run_mode == "sunday":
    subject = f"📋 Weekly Lab Inventory Status Report - {datetime.now().strftime('%Y-%m-%d')}"
    html = f"""<h3>Weekly Lab Inventory Overview Status Summary</h3>
    <p>Please find attached the complete raw ledger <b>(.CSV file spreadsheet)</b> for your reference.</p>
    <p>Current operational totals tracking details:</p>
    <ul>
        <li><b>Critical Risk Items:</b> {len(critical_rows)}</li>
        <li><b>Low Stock Tracking Items:</b> {len(low_rows)}</li>
        <li><b>Healthy Active Rows:</b> {len(df) - len(critical_rows) - len(low_rows)}</li>
    </ul>
    """
    if not critical_rows.empty:
        html += "<h4>🚨 Critical Action Required:</h4><table border='1' cellpadding='5' style='border-collapse: collapse;'><tr><th>Product</th><th>Lot</th><th>Runs Left</th></tr>"
        for _, r in critical_rows.iterrows():
            html += f"<tr><td>{r['Elisa Kit Name']}</td><td>{r['Lot no.']}</td><td style='color:red;'>{r[exp_col]}</td></tr>"
        html += "</table>"
        
    send_scheduled_email(subject, html, attach_file=True)

elif run_mode == "scan":
    if not critical_rows.empty or not low_rows.empty:
        subject = "⚠️ 3-Day Automated Inventory Scan Notice"
        html = "<h3>The automated 3-day stock check identified rows requiring attention:</h3>"
        if not critical_rows.empty:
            html += "<h4>🔴 Critical Items (0 Runs Left):</h4><ul>"
            for _, r in critical_rows.iterrows():
                html += f"<li><b>{r['Elisa Kit Name']}</b> (Lot: {r['Lot no.']})</li>"
            html += "</ul>"
        if not low_rows.empty:
            html += "<h4>🟡 Low Stock Items (1-2 Runs Left):</h4><ul>"
            for _, r in low_rows.iterrows():
                html += f"<li><b>{r['Elisa Kit Name']}</b> (Lot: {r['Lot no.']})</li>"
            html += "</ul>"
            
        send_scheduled_email(subject, html, attach_file=False)
