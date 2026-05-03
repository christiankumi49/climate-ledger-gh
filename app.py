import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
import numpy as np
import requests
import sqlite3
import smtplib
import re
import matplotlib.pyplot as plt
from datetime import datetime
from email.mime.text import MIMEText
from fpdf import FPDF
import os
import threading 

# --- 1. CORE ARCHITECTURE & PERSISTENCE ---
def get_db_path():
    if os.path.isdir('/tmp') and os.access('/tmp', os.W_OK):
        return '/tmp/climate_audit.db'
    return 'climate_audit.db'

DB_PATH = get_db_path()

def init_db():
    """Initializes the database and migrates columns if they are missing."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            # Create tables with all necessary columns
            c.execute('''CREATE TABLE IF NOT EXISTS alerts
                         (id INTEGER PRIMARY KEY, timestamp TEXT, region TEXT, 
                          loss_ghs REAL, recipient TEXT, status TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS api_cache
                         (region TEXT PRIMARY KEY, temp_avg REAL, rain_sum REAL, last_updated TEXT)''')
            
            # --- MIGRATION LOGIC: Adds missing columns to existing DB files ---
            c.execute("PRAGMA table_info(alerts)")
            existing_columns = [col[1] for col in c.fetchall()]
            
            if 'recipient' not in existing_columns:
                c.execute("ALTER TABLE alerts ADD COLUMN recipient TEXT")
            if 'status' not in existing_columns:
                c.execute("ALTER TABLE alerts ADD COLUMN status TEXT")
                
            conn.commit()
    except sqlite3.Error as e:
        st.error(f"Database Initialization Failed: {e}")

def update_api_cache(region, temp, rain):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT OR REPLACE INTO api_cache VALUES (?, ?, ?, ?)",
                         (region, temp, rain, datetime.now().isoformat()))
    except sqlite3.Error as e:
        st.sidebar.warning(f"⚠️ Cache write failed: {e}")

def get_fallback_data(region):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT temp_avg, rain_sum FROM api_cache WHERE region=?", (region,)).fetchone()
            return row if row else (31.5, 5.0)
    except sqlite3.Error:
        return (31.5, 5.0)

# --- 2. THE SCIENTIFIC ENGINE ---
REGRESSION_COEFFS = {
    "Northern": {"t_slope": -0.028, "r_threshold": 10.0, "intercept": 2.45, "sigma": 2.8},
    "Ashanti": {"t_slope": -0.022, "r_threshold": 25.0, "intercept": 2.80, "sigma": 2.1},
    "Greater Accra": {"t_slope": -0.031, "r_threshold": 15.0, "intercept": 1.95, "sigma": 2.4}
}

def run_stochastic_simulation(region, base_temp, actual_rain, iterations=1000):
    coeffs = REGRESSION_COEFFS[region]
    temp_regimes = np.random.normal(base_temp, coeffs['sigma'], iterations)
    rain_penalty = max(0, (coeffs['r_threshold'] - actual_rain) / coeffs['r_threshold'] * 0.2)
    yield_sim = np.maximum(
        0.1,
        coeffs['intercept'] + (coeffs['t_slope'] * np.maximum(0, temp_regimes - 30) * 5) - rain_penalty
    )
    loss_dist = (coeffs['intercept'] - yield_sim) / coeffs['intercept']
    return np.percentile(loss_dist, 50), np.percentile(loss_dist, 95)

def classify_risk(p50):
    if p50 > 0.4: return "CRITICAL"
    elif p50 > 0.25: return "HIGH"
    elif p50 > 0.1: return "MODERATE"
    return "LOW"

# --- 3. PROFESSIONAL PDF GENERATOR ---
class AuditPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'PRIVATE & CONFIDENTIAL: CLIMATE RISK AUDIT', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 5, 'Risk Management Division', 0, 1, 'C')
        ref_num = datetime.now().strftime("REF-%Y%m%d-%H%M")
        self.cell(0, 5, f'Audit Reference: {ref_num}', 0, 1, 'C')
        self.ln(10)

    def generate_report(self, data):
        self.add_page()
        self.set_font('Arial', '', 9)
        self.cell(0, 10, f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 0, 1, 'R')
        
        self.set_fill_color(240, 240, 240)
        self.set_font('Arial', 'B', 11)
        self.cell(70, 10, ' Audit Field', 1, 0, 'L', 1)
        self.cell(120, 10, ' Details', 1, 1, 'L', 1)
        
        self.set_font('Arial', '', 11)
        for field, detail in data.items():
            self.cell(70, 10, f" {field}", 1, 0, 'L')
            if field == "Risk Status" and detail == "CRITICAL":
                self.set_text_color(220, 0, 0)
                self.set_font('Arial', 'B', 11)
                self.cell(120, 10, f" {detail}", 1, 1, 'L')
                self.set_text_color(0, 0, 0)
                self.set_font('Arial', '', 11)
            else:
                self.cell(120, 10, f" {detail}", 1, 1, 'L')

def create_pdf_bytes(report_data):
    pdf = AuditPDF()
    pdf.generate_report(report_data)
    return pdf.output(dest='S').encode('latin-1')

# --- 4. AUTHENTICATION HANDLER ---
def load_auth():
    try:
        raw_creds = st.secrets['credentials']
        if hasattr(raw_creds, "to_dict"):
            credentials = raw_creds.to_dict()
        else:
            credentials = {k: dict(v) for k, v in raw_creds.items()}
        
        authenticator = stauth.Authenticate(
            credentials,
            st.secrets['cookie']['name'],
            st.secrets['cookie']['key'],
            int(st.secrets['cookie']['expiry_days'])
        )
        return authenticator
    except Exception as e:
        st.error(f"Secrets Configuration Error: {str(e)}")
        st.stop()

# --- 5. ACTION LOOP: ASYNC SECURE ALERT PROTOCOL ---
def validate_email(email):
    return re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email) is not None

def send_alert_async_worker(recipient_input, region, loss_ghs):
    recipients = [e.strip() for e in recipient_input.split(",") if validate_email(e.strip())]
    if not recipients:
        return

    try:
        msg_text = f"OFFICIAL RISK ADVISORY\n\nAsset Region: {region}\nCalculated Exposure: GHS {loss_ghs/1e6:.2f}M"
        with smtplib.SMTP(st.secrets["email"]["smtp_server"], int(st.secrets["email"]["smtp_port"]), timeout=10) as server:
            server.starttls()
            server.login(st.secrets["email"]["sender"], st.secrets["email"]["password"])
            
            for email in recipients:
                msg = MIMEText(msg_text)
                msg['Subject'] = f"🚨 Enterprise Risk Trigger: {region}"
                msg['From'] = st.secrets["email"]["sender"]
                msg['To'] = email
                server.send_message(msg)
                
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("INSERT INTO alerts (timestamp, region, loss_ghs, recipient, status) VALUES (?, ?, ?, ?, ?)",
                                 (datetime.now().isoformat(), region, loss_ghs, email, "SENT"))
    except Exception as e:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO alerts (timestamp, region, loss_ghs, recipient, status) VALUES (?, ?, ?, ?, ?)",
                         (datetime.now().isoformat(), region, loss_ghs, recipient_input, f"FAILED: {str(e)[:50]}"))

# --- 6. MAIN DASHBOARD APPLICATION ---
def main():
    st.set_page_config(page_title="Enterprise Climate Ledger", layout="wide")
    init_db()
    
    if "authentication_status" not in st.session_state:
        st.session_state["authentication_status"] = None
        
    authenticator = load_auth()
    authenticator.login(location='main')

    if st.session_state["authentication_status"]:
        user_data = st.secrets['credentials']['usernames'][st.session_state['username']]
        user_role = user_data.get('role', 'viewer') 

        st.sidebar.title(f"Welcome, {st.session_state['name']}")
        st.sidebar.caption(f"Role: {user_role.upper()}")
        authenticator.logout(location='sidebar')
        st.sidebar.divider()
        
        client_name = st.sidebar.text_input("Client/Company Name", value="Global Agribusiness Ltd")
        st.sidebar.subheader("💎 Asset Valuation")
        custom_ha = st.sidebar.number_input("Total Hectares", value=10000)
        yield_per_ha = st.sidebar.number_input("Expected Yield (t/ha)", value=2.5)
        custom_val = st.sidebar.number_input("Value per Tonne (GHS)", value=15000)
        user_email = st.sidebar.text_input("Alert Destination (separate by commas)", value="audit@enterprise.com")

        REGIONS = {
            "Northern": {"lat": 9.40, "lon": -0.84},
            "Ashanti": {"lat": 6.67, "lon": -1.57},
            "Greater Accra": {"lat": 5.60, "lon": -0.18}
        }
        
        @st.cache_data(ttl=600)
        def fetch_data():
            res = {}
            for k, m in REGIONS.items():
                try:
                    url = f"https://api.open-meteo.com/v1/forecast?latitude={m['lat']}&longitude={m['lon']}&daily=temperature_2m_max,precipitation_sum&timezone=auto"
                    response = requests.get(url, timeout=5)
                    response.raise_for_status()
                    d = response.json().get('daily', {})
                    temps, rain = d.get('temperature_2m_max', []), d.get('precipitation_sum', [])
                    if not temps or not rain: raise ValueError()
                    t, r = np.mean(temps), np.sum(rain)
                    update_api_cache(k, t, r)
                    res[k] = (t, r, "LIVE")
                except:
                    st.sidebar.caption(f"ℹ️ {k}: using cached data")
                    t, r = get_fallback_data(k)
                    res[k] = (t, r, "CACHED")
            return res

        st.title(f"🏛️ {client_name}: Climate Ledger")
        batch = fetch_data()
        st.table(pd.DataFrame([{"Region": k, "Temp": f"{v[0]:.1f}C", "Rain": f"{v[1]:.1f}mm", "Source": v[2]} for k, v in batch.items()]).set_index("Region"))
        st.divider()

        selected = st.selectbox("Select Asset for Deep Dive Audit", list(REGIONS.keys()))
        t_base, r_base, _ = batch[selected]
        p50, p95 = run_stochastic_simulation(selected, t_base, r_base)
        
        exposure = (custom_ha * yield_per_ha * custom_val) * p50
        risk_level = classify_risk(p50)
        recommendation = 'Deploy Irrigation' if r_base < 12 else 'Standard Mitigation'

        st.subheader(f"Risk Assessment: {risk_level} {'🔴' if risk_level == 'CRITICAL' else '🟢'}")

        col_l, col_r = st.columns([2, 1])
        with col_l:
            c1, c2 = st.columns(2)
            c1.metric("Asset Exposure", f"GHS {exposure/1e6:.2f}M")
            c2.metric("P95 Tail Risk", f"{p95*100:.1f}%")
            st.info(f"📋 Recommendation: {recommendation}")

        with col_r:
            fig, ax = plt.subplots(figsize=(5, 3))
            sim_data = np.random.normal(t_base, REGRESSION_COEFFS[selected]['sigma'], 1000)
            ax.hist(sim_data, bins=30, color='#1B4F72', edgecolor='white')
            ax.set_title(f"{selected} Temperature Variance")
            st.pyplot(fig)

        report_data = {
            "Client": client_name, "Region": selected, "Risk Status": risk_level,
            "Exposure": f"GHS {exposure/1e6:.2f}M", "Temp": f"{t_base:.1f}C",
            "Rain": f"{r_base:.1f}mm", "Recommendation": recommendation
        }

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if user_role == 'admin':
                if st.button("🚀 Transmit Institutional Alert", use_container_width=True):
                    if "@" in user_email:
                        thread = threading.Thread(target=send_alert_async_worker, args=(user_email, selected, exposure))
                        thread.start()
                        st.toast(f"Transmission protocol initiated", icon="📨")
                        st.info(f"System: Dispatching alert for {selected} region...")
                    else:
                        st.error("Please enter valid email(s).")
            else:
                st.button("🚀 Transmit Institutional Alert (Restricted)", disabled=True, use_container_width=True)

        with btn_col2:
            pdf_bytes = create_pdf_bytes(report_data)
            st.download_button(
                label="📄 Download Audit Report (PDF)",
                data=pdf_bytes,
                file_name=f"Climate_Audit_{selected}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        # --- THE AUDIT LEDGER & SYNC FUNCTION ---
        st.divider()
        col_ledger, col_refresh = st.columns([4, 1])
        with col_ledger:
            st.subheader("🔍 Institutional Audit Ledger")
        with col_refresh:
            if st.button("🔄 Sync Ledger", use_container_width=True):
                st.rerun() 

        with sqlite3.connect(DB_PATH) as conn:
            try:
                query = """
                    SELECT 
                        strftime('%H:%M:%S', timestamp) AS 'Time Sent', 
                        region AS 'Region', 
                        recipient AS 'Sent To', 
                        status AS 'Status',
                        printf('GHS %.2fM', loss_ghs/1000000) AS 'Exposure'
                    FROM alerts 
                    ORDER BY id DESC 
                    LIMIT 10
                """
                df_ledger = pd.read_sql_query(query, conn)
                
                if not df_ledger.empty:
                    st.dataframe(df_ledger, use_container_width=True, hide_index=True)
                else:
                    st.warning("No records found. Send an alert to populate the ledger.")
            except Exception as e:
                st.error(f"Ledger Sync Error: {str(e)}")

    elif st.session_state["authentication_status"] is False:
        st.error('Username/password is incorrect')
    elif st.session_state["authentication_status"] is None:
        st.warning('Please enter your institutional credentials')

if __name__ == "__main__":
    main()
