import streamlit as st
import streamlit_authenticator as stauth
import yaml
import pandas as pd
import numpy as np
import requests
import sqlite3
import smtplib
import re
import matplotlib.pyplot as plt
import random
from datetime import datetime
from email.mime.text import MIMEText
from fpdf import FPDF
from yaml.loader import SafeLoader

# --- 1. CORE ARCHITECTURE & PERSISTENCE ---
def init_db():
    with sqlite3.connect('climate_audit.db') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS alerts 
                     (id INTEGER PRIMARY KEY, timestamp TEXT, region TEXT, loss_ghs REAL, recipient TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS api_cache 
                     (region TEXT PRIMARY KEY, temp_avg REAL, rain_sum REAL, last_updated TEXT)''')
        conn.commit()

def update_api_cache(region, temp, rain):
    with sqlite3.connect('climate_audit.db') as conn:
        conn.execute("INSERT OR REPLACE INTO api_cache VALUES (?, ?, ?, ?)",
                     (region, temp, rain, datetime.now().isoformat()))

def get_fallback_data(region):
    with sqlite3.connect('climate_audit.db') as conn:
        row = conn.execute("SELECT temp_avg, rain_sum FROM api_cache WHERE region=?", (region,)).fetchone()
        return row if row else (31.5, 5.0)

# --- 2. THE SCIENTIFIC ENGINE ---
REGRESSION_COEFFS = {
    "Northern": {"t_slope": -0.028, "r_threshold": 10.0, "intercept": 2.45, "sigma": 2.8},
    "Ashanti": {"t_slope": -0.022, "r_threshold": 25.0, "intercept": 2.80, "sigma": 2.1},
    "Greater Accra": {"t_slope": -0.031, "r_threshold": 15.0, "intercept": 1.95, "sigma": 2.4}
}

def run_stochastic_simulation(region, base_temp, actual_rain, iterations=1000):
    coeffs = REGRESSION_COEFFS[region]
    temp_regimes = np.random.normal(base_temp, coeffs['sigma'], iterations)
    rain_penalty = 0.15 if actual_rain < coeffs['r_threshold'] else 0.0
    
    yield_sim = np.array([
        max(0.1, coeffs['intercept'] + (coeffs['t_slope'] * max(0, t-30) * 5) - rain_penalty) 
        for t in temp_regimes
    ])
    
    loss_dist = (coeffs['intercept'] - yield_sim) / coeffs['intercept']
    return np.percentile(loss_dist, 50), np.percentile(loss_dist, 95)

def classify_risk(p50):
    if p50 > 0.4: return "CRITICAL 🔴"
    elif p50 > 0.25: return "HIGH 🟠"
    elif p50 > 0.1: return "MODERATE 🟡"
    return "LOW 🟢"

# --- 3. AUTHENTICATION HANDLER ---
def load_auth():
    try:
        with open('config.yaml') as file:
            config = yaml.load(file, Loader=SafeLoader)
        
        authenticator = stauth.Authenticate(
            config['credentials'],
            config['cookie']['name'],
            config['cookie']['key'],
            config['cookie']['expiry_days']
        )
        return authenticator, config
    except FileNotFoundError:
        st.error("Missing config.yaml! Please ensure the file is named correctly.")
        st.stop()

# --- 4. ACTION LOOP: SECURE ALERT PROTOCOL ---
def validate_email(email):
    return re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email) is not None

def execute_alert_protocol(recipient, region, loss_ghs):
    if not validate_email(recipient):
        return False, "❌ Error: Invalid institutional email format."
    try:
        msg = MIMEText(f"OFFICIAL RISK ADVISORY\n\nAsset Region: {region}\nCalculated Exposure: GHS {loss_ghs/1e6:.2f}M\nAudit Reference: {datetime.now().strftime('%Y%m%d%H%M')}")
        msg['Subject'] = f"🚨 Enterprise Risk Trigger: {region}"
        msg['From'] = st.secrets["email"]["sender"]
        msg['To'] = recipient

        with smtplib.SMTP(st.secrets["email"]["smtp_server"], st.secrets["email"]["smtp_port"]) as server:
            server.starttls()
            server.login(st.secrets["email"]["sender"], st.secrets["email"]["password"])
            server.send_message(msg)
        
        with sqlite3.connect('climate_audit.db') as conn:
            conn.execute("INSERT INTO alerts (timestamp, region, loss_ghs, recipient) VALUES (?, ?, ?, ?)",
                         (datetime.now().isoformat(), region, loss_ghs, recipient))
        return True, f"✅ Protocol Executed: Audit Entry Created for {region}."
    except Exception as e:
        return False, f"❌ Protocol Blocked (SMTP): {str(e)[:30]}"

# --- 5. BRANDED REPORTING (DEPLOYMENT EDITION - FIXED) ---
class EnterpriseReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'PRIVATE & CONFIDENTIAL: CLIMATE RISK AUDIT', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 5, 'Risk Management Division', 0, 1, 'C')
        
        ref_id = f"REF-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        self.cell(0, 5, f"Audit Reference: {ref_id}", 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128) 
        # Replaced en-dash with standard hyphen to fix 'latin-1' error
        self.cell(0, 10, 'Confidential - Internal Use Only | Enterprise Climate Ledger v10.0', 0, 0, 'C')

def create_pdf(client, region, risk, exposure, rec, t, r):
    # Clean emojis to prevent encoding errors
    clean_risk = re.sub(r'[^\x00-\x7F]+', '', risk).strip()
    
    pdf = EnterpriseReport()
    pdf.add_page()
    
    pdf.set_font("Arial", 'I', 9)
    gen_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    pdf.cell(180, 5, f"Report Generated: {gen_time}", 0, 1, 'R')
    pdf.ln(2)

    content = [
        ["Audit Field", "Details"], 
        ["Client", client], 
        ["Region", region], 
        ["Risk Status", clean_risk], 
        ["Exposure", f"GHS {exposure/1e6:.2f}M"],
        ["Temp", f"{t:.1f}C"], 
        ["Rain", f"{r:.1f}mm"], 
        ["Recommendation", rec]
    ]
    
    for i, row in enumerate(content):
        if i == 0:
            pdf.set_fill_color(240, 240, 240)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(60, 10, str(row[0]), 1, 0, 'L', fill=True)
            pdf.cell(120, 10, str(row[1]), 1, 1, 'L', fill=True)
        else:
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(60, 10, str(row[0]), 1)
            pdf.set_font("Arial", '', 11)
            
            if row[0] == "Risk Status" and "CRITICAL" in row[1]:
                pdf.set_text_color(200, 0, 0) 
                pdf.set_font("Arial", 'B', 11)
                pdf.cell(120, 10, str(row[1]), 1, 1)
                pdf.set_text_color(0, 0, 0)
            else:
                pdf.cell(120, 10, str(row[1]), 1, 1)
        
    return pdf.output(dest='S').encode('latin-1', errors='ignore')

# --- 6. MAIN DASHBOARD APPLICATION ---
def main():
    st.set_page_config(page_title="Enterprise Climate Ledger", layout="wide")
    init_db()
    
    authenticator, config = load_auth()
    authenticator.login(location='main')

    if st.session_state["authentication_status"]:
        name = st.session_state["name"]
        authenticator.logout(location='sidebar')
        
        st.sidebar.title(f"Welcome, {name}")
        st.sidebar.divider()
        
        client_name = st.sidebar.text_input("Client/Company Name", value="Global Agribusiness Ltd")
        st.sidebar.subheader("💎 Custom Asset Valuation")
        custom_ha = st.sidebar.number_input("Total Hectares", value=10000)
        custom_val = st.sidebar.number_input("Value per Tonne (GHS)", value=15000)
        user_email = st.sidebar.text_input("Alert Destination", value="audit@enterprise.com")

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
                    d = requests.get(url, timeout=5).json()['daily']
                    t, r = np.mean(d['temperature_2m_max']), np.sum(d['precipitation_sum'])
                    update_api_cache(k, t, r)
                    res[k] = (t, r, "LIVE")
                except:
                    t, r = get_fallback_data(k)
                    res[k] = (t, r, "CACHED")
            return res

        st.title(f"🏛️ {client_name}: Climate Ledger")
        batch = fetch_data()

        st.table(pd.DataFrame([{"Region": k, "Temp": f"{v[0]:.1f}C", "Rain": f"{v[1]:.1f}mm", "Source": v[2]} for k, v in batch.items()]).set_index("Region"))

        st.divider()

        selected = st.selectbox("Select Asset for Deep Dive Audit", list(REGIONS.keys()))
        t_base, r_base, status = batch[selected]
        p50, p95 = run_stochastic_simulation(selected, t_base, r_base)
        
        exposure = (custom_ha * 2.5 * custom_val) * p50
        risk_level = classify_risk(p50)

        if "CRITICAL" in risk_level: 
            st.error(f"System Alert: {risk_level}")
        else: 
            st.info(f"System Status: {risk_level}")

        col_l, col_r = st.columns([2, 1])
        with col_l:
            c1, c2 = st.columns(2)
            c1.metric("Asset Exposure", f"GHS {exposure/1e6:.2f}M")
            c2.metric("P95 Tail Risk", f"{p95*100:.1f}%")
            rec = "Deploy Irrigation" if r_base < 12 else "Standard Mitigation"
            st.info(f"📋 Strategic Recommendation: {rec}")

        with col_r:
            fig, ax = plt.subplots(figsize=(5, 3))
            sim_data = np.random.normal(t_base, REGRESSION_COEFFS[selected]['sigma'], 1000)
            ax.hist(sim_data, bins=30, color='#1B4F72', edgecolor='white')
            ax.set_title(f"Variance Profile (σ={REGRESSION_COEFFS[selected]['sigma']})")
            st.pyplot(fig)

        st.divider()
        b1, b2 = st.columns(2)
        with b1:
            if st.button("🚀 Transmit Institutional Alert"):
                s, m = execute_alert_protocol(user_email, selected, exposure)
                if s: 
                    st.success(m)
                    st.rerun()
                else: 
                    st.error(m)
        with b2:
            pdf_bytes = create_pdf(client_name, selected, risk_level, exposure, rec, t_base, r_base)
            st.download_button("📥 Download Branded PDF Report", pdf_bytes, f"Audit_{selected}.pdf", "application/pdf")

        st.divider()
        st.subheader("🔍 Institutional Audit Ledger")
        with sqlite3.connect('climate_audit.db') as conn:
            st.dataframe(pd.read_sql_query("SELECT * FROM alerts ORDER BY id DESC", conn), use_container_width=True, hide_index=True)

    elif st.session_state["authentication_status"] is False:
        st.error('Username/password is incorrect')
    elif st.session_state["authentication_status"] is None:
        st.warning('Please enter your institutional credentials')

if __name__ == "__main__":
    main()