import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import json
import PyPDF2
from datetime import datetime
from streamlit_lottie import st_lottie
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# 1. PAGE CONFIG & SECRETS
# ==========================================
st.set_page_config(page_title="AI Career Assistant", page_icon="🚀", layout="wide")

# הגדרות API ו-Email ב-Secrets
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("🔑 מפתח API חסר ב-Secrets!")
    st.stop()


# ==========================================
# 2. EMAIL LOGIC
# ==========================================
def send_email(target_email, content):
    try:
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        sender_email = st.secrets["EMAIL_USER"]
        sender_password = st.secrets["EMAIL_PASS"]

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = target_email
        msg['Subject'] = "קורות החיים המשופרים שלך מ-CareerAssistant.ai"

        msg.attach(MIMEText(content, 'html'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"שגיאה בשליחת המייל: {e}")
        return False


# ==========================================
# 3. HELPERS & TOOLS
# ==========================================
def load_lottieurl(url):
    r = requests.get(url)
    return r.json() if r.status_code == 200 else None


def extract_pdf_text(file) -> str:
    try:
        reader = PyPDF2.PdfReader(file)
        return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    except:
        return "Error extracting PDF"


def fetch_job_details(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        return "\n".join([p.get_text() for p in soup.find_all(['p', 'li'])])
    except:
        return "SCRAPE_FAILED"


def compare_skills(cv_text, job_desc):
    model = genai.GenerativeModel("gemini-1.5-flash", generation_config={"response_mime_type": "application/json"})
    prompt = f"Analyze CV vs JD. Return JSON: {{'match_score': int, 'shared_skills': [], 'missing_keywords': [], 'role_relevance': str}}. CV: {cv_text} | JD: {job_desc}"
    return json.loads(model.generate_content(prompt).text)


def generate_tailored_cv(cv_text, job_desc):
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"Optimize CV for ATS. Use <span class='cv-add'></span> for additions. CV: {cv_text} | JD: {job_desc}"
    return model.generate_content(prompt).text


# ==========================================
# 4. UI SETUP
# ==========================================
if "job_history" not in st.session_state: st.session_state.job_history = []
if "optimized_cv" not in st.session_state: st.session_state.optimized_cv = ""

lottie_ai = load_lottieurl("https://assets5.lottiefiles.com/packages/lf20_5njpX6.json")
st_lottie(lottie_ai, height=150)
st.title("🚀 CareerAssistant.ai")

# Tabs
tab_search, tab_optimize, tab_history = st.tabs(["🔍 ניתוח", "✨ אופטימיזציה ומייל", "📜 היסטוריה"])

with tab_search:
    job_url = st.text_input("לינק למשרה")
    cv_file = st.file_uploader("העלה CV (PDF)", type=['pdf'])

    if st.button("⚡ ניתוח מהיר", type="primary"):
        if cv_file and job_url:
            with st.spinner("מנתח..."):
                cv_text = extract_pdf_text(cv_file)
                jd_text = fetch_job_details(job_url)
                results = compare_skills(cv_text, jd_text)
                st.session_state.optimized_cv = generate_tailored_cv(cv_text, jd_text)
                st.session_state.job_history.append(
                    {"date": datetime.now().strftime("%d/%m/%Y"), "score": results['match_score']})

                st.metric("ציון התאמה", f"{results['match_score']}%")
                st.write(f"**סיכום:** {results['role_relevance']}")
        else:
            st.warning("נא לספק לינק וקובץ.")

with tab_optimize:
    if st.session_state.optimized_cv:
        st.markdown(st.session_state.optimized_cv, unsafe_allow_html=True)

        st.divider()
        st.subheader("📬 שלח לי את התוצאה למייל")
        user_email = st.text_input("כתובת אימייל")
        if st.button("שלח עכשיו"):
            if send_email(user_email, st.session_state.optimized_cv):
                st.success("המייל נשלח בהצלחה!")
    else:
        st.info("הרץ ניתוח קודם.")

with tab_history:
    st.table(st.session_state.job_history)