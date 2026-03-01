import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import json
import PyPDF2
from datetime import datetime
from streamlit_lottie import st_lottie

# ==========================================
# 1. הגדרות אבטחה וחיבור (Secrets Only)
# ==========================================
try:
    # משיכת המפתחות מה-Secrets של השרת בלבד (אבטחה מקסימלית)
    api_key = st.secrets["GOOGLE_API_KEY"]
    serpapi_key = st.secrets.get("SERPAPI_KEY", "")  # אופציונלי לחיפוש משרות
    genai.configure(api_key=api_key)
except Exception:
    st.error("⚠️ שגיאה: מפתח ה-API לא נמצא ב-Secrets. אנא הגדר אותו בניהול האפליקציה.")
    st.stop()

# ==========================================
# 2. עיצוב דף ו-CSS (SaaS Style)
# ==========================================
st.set_page_config(page_title="CareerAssistant.ai Pro", page_icon="🚀", layout="wide")

st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
        padding: 25px;
        border-radius: 15px;
        text-align: center;
        color: white;
    }
    .cv-add { color: #10b981; font-weight: bold; background-color: rgba(16,185,129,0.1); padding: 2px 5px; border-radius: 4px; }
    .cv-del { color: #ef4444; text-decoration: line-through; background-color: rgba(239,68,68,0.1); padding: 2px 5px; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)


# פונקציה לטעינת אנימציות
def load_lottieurl(url):
    try:
        r = requests.get(url)
        return r.json() if r.status_code == 200 else None
    except:
        return None


lottie_scan = load_lottieurl("https://assets5.lottiefiles.com/packages/lf20_5njpX6.json")


# ==========================================
# 3. פונקציות ליבה (MCP Tools)
# ==========================================

def extract_pdf_text(file):
    reader = PyPDF2.PdfReader(file)
    return "\n".join([page.extract_text() for page in reader.pages])


def search_jobs_serp(query):
    """שימוש ב-SerpApi למציאת משרות (עוקף חסימות לינקדאין)"""
    if not serpapi_key:
        return None
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_jobs",
        "q": query,
        "hl": "en",
        "api_key": serpapi_key
    }
    response = requests.get(url, params=params)
    return response.json().get("jobs_results", [])


def analyze_and_optimize(cv_text, job_desc):
    model = genai.GenerativeModel("gemini-1.5-flash")

    # פרומפט משולב לניתוח ושיפור (חוסך זמן וקריאות API)
    prompt = f"""
    Act as a Senior Recruiter. Analyze this CV against the Job Description.
    CV: {cv_text}
    JD: {job_desc}

    Return a JSON with:
    1. "score": int 0-100
    2. "missing": list of keywords
    3. "strengths": list of skills
    4. "optimized_summary": The rewritten summary with changes marked.
    Use <span class='cv-add'>text</span> for additions and <span class='cv-del'>text</span> for deletions.
    """
    response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
    return json.loads(response.text)


# ==========================================
# 4. ממשק משתמש (GUI)
# ==========================================

# --- Sidebar (ללא הזנת API Key) ---
with st.sidebar:
    st_lottie(lottie_scan, height=120)
    st.header("📄 מסמכי מקור")
    uploaded_file = st.file_uploader("העלי קורות חיים (PDF)", type="pdf")

    if uploaded_file and "cv_text" not in st.session_state:
        st.session_state.cv_text = extract_pdf_text(uploaded_file)
        st.success("קורות החיים נטענו!")

# --- Main Tabs ---
if "cv_text" not in st.session_state:
    st.title("🚀 ברוכה הבאה ל-CareerAssistant.ai")
    st.info("כדי להתחיל, העלי את קורות החיים שלך בתפריט הצדדי.")
else:
    tab1, tab2, tab3 = st.tabs(["🔍 חיפוש וניתוח", "📝 אופטימיזציה", "📜 היסטוריה"])

    with tab1:
        st.subheader("מציאת משרה וניתוח התאמה")
        job_query = st.text_input("חיפוש משרה (למשל: Python Developer Tel Aviv)")

        if st.button("חפשי משרות") and serpapi_key:
            jobs = search_jobs_serp(job_query)
            for job in jobs[:3]:  # מציג 3 תוצאות ראשונות
                with st.expander(f"{job['title']} - {job['company_name']}"):
                    st.write(job.get("description", "")[:500] + "...")
                    if st.button("נתח משרה זו", key=job['job_id']):
                        st.session_state.current_jd = job.get("description", "")

        st.divider()
        manual_jd = st.text_area("או הדביקי תיאור משרה כאן:", value=st.session_state.get("current_jd", ""))

        if st.button("⚡ הרץ סריקת התאמה", type="primary"):
            with st.spinner("ה-AI מנתח נתונים..."):
                results = analyze_and_optimize(st.session_state.cv_text, manual_jd)
                st.session_state.last_results = results
                st.rerun()

    with tab2:
        if "last_results" in st.session_state:
            res = st.session_state.last_results

            col1, col2 = st.columns([1, 2])
            with col1:
                st.markdown(f"""<div class="metric-card">
                    <p style="font-size:3rem; margin:0;">{res['score']}%</p>
                    <p>ציון התאמה ATS</p>
                </div>""", unsafe_allow_html=True)

            with col2:
                st.subheader("מילות מפתח חסרות")
                st.write(", ".join(res['missing']))

            st.divider()
            st.subheader("הצעת שיפור לקורות חיים")
            st.markdown(res['optimized_summary'], unsafe_allow_html=True)

            # כפתור הורדה
            clean_text = res['optimized_summary'].replace("<span class='cv-add'>", "").replace("</span>", "")
            st.download_button("הורד גרסה משופרת (Text)", clean_text, "optimized_cv.txt")
        else:
            st.warning("בצעי ניתוח בלשונית החיפוש קודם לכן.")

    with tab3:
        st.write("היסטוריית הניתוחים שלך תופיע כאן בקרוב.")