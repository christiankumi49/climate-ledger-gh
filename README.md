🌍 Climate Risk Intelligence System
An enterprise-grade platform designed to bridge the gap between Meteorology and Financial Risk Management. This tool converts real-time atmospheric data into actionable financial insights for large-scale agribusiness and institutional stakeholders.

🚀 Key Capabilities
Predictive Analytics: Estimates agricultural yield loss by modeling regional responses to temperature and rainfall fluctuations.

Stochastic Risk Modeling: Employs Monte Carlo Simulations to quantify uncertainty, providing both median exposure (P50) and extreme tail risk (P95).

Institutional Audit Ledger: A persistent SQL-based tracking system that logs all dispatched alerts for transparency and compliance.

Real-Time Alerts: Dispatches automated risk triggers via a secure background SMTP protocol to multiple stakeholders.

Professional Reporting: Generates structured, confidential PDF audit reports for decision-support and mitigation planning.

🧠 The Intelligence Engine
Data Ingestion: Fetches live localized weather parameters (maximum temperature and cumulative precipitation) via the Open-Meteo API.

Regional Logic: Applies regression-based coefficients tailored to specific Ghanaian agro-ecological zones (e.g., Northern, Ashanti, and Greater Accra).

Simulation Layer: Executes 1,000+ stochastic iterations to model yield variance based on historical atmospheric deviations.

Financial Quantification: Translates biological yield loss into GHS exposure based on custom asset valuation (Hectares × Yield × Market Price).

Audit Persistence: Automatically migrates and updates the ledger to reflect the transmission status ("SENT" or "FAILED") and recipient details.

🛠️ Tech Stack
Frontend: Streamlit (Dashboard UI)

Data Science: NumPy, Pandas, Matplotlib (Monte Carlo simulations & visualization)

Database: SQLite (SQL persistence for audit logs)

Authentication: streamlit-authenticator (Secure access control for Admins vs. Viewers)

Protocols: SMTP (Secure email dispatch), FPDF (Automated PDF generation)

💼 Institutional Use Cases
Agribusiness: Proactive crop risk monitoring and irrigation deployment planning.

Lending Institutions: Assessing climate-based credit risk for agricultural loans.

Insurance: Quantifying regional exposure for climate-indexed insurance pricing.

Climate Research: Analyzing the financial impact of regional climate variability and Monsoon patterns.

👨‍💻 Author
Christian Kumi
BSc Meteorology & Climate Science — Kwame Nkrumah University of Science and Technology (KNUST)

Building solutions at the intersection of Atmospheric Dynamics, Data Science, and Agro-Finance.

🌐 Live Application
👉 [https://climate-ledger-gh-ech7ntc6dznzutu5qrwq2u.streamlit.app/]

⚠️ Disclaimer
This system is a decision-support tool based on statistical regression models and available meteorological data. It is intended for analytical purposes and does not guarantee exact biological or financial outcomes.
