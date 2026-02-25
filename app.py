import streamlit as st
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import json
import PyPDF2
from datetime import datetime

# ==========================================
# 1. PAGE CONFIG & CUSTOM CSS (SaaS Styling)
# ==========================================
st.set_page_config(page_title="AI Career Assistant", page_icon="🚀", layout="wide")

custom_css = """
<style>
    /* SaaS Card Styling */
    .st-emotion-cache-1r6slb0 {
        background-color: #1e1e2f;
        padding: 2rem;
        border-radius: 12px;
        border: 1px solid #333;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .metric-card {
        background: linear-gradient(135deg, #4b6cb7 0%, #182848 100%);
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        color: white;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .metric-value { font-size: 3rem; font-weight: bold; margin: 0; }
    .metric-label { font-size: 1rem; opacity: 0.8; }

    /* Highlight additions/deletions in optimizer */
    .cv-add { color: #00FF00; font-weight: bold; background-color: rgba(0,255,0,0.1); padding: 2px 4px; border-radius: 3px; }
    .cv-del { color: #FF0000; text-decoration: line-through; background-color: rgba(255,0,0,0.1); padding: 2px 4px; border-radius: 3px; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ==========================================
# 2. SESSION STATE INITIALIZATION
# ==========================================
if "cv_text" not in st.session_state:
    st.session_state.cv_text = ""
if "job_history" not in st.session_state:
    st.session_state.job_history = []
if "api_key" not in st.session_state:
    st.session_state.api_key = ""


# ==========================================
# 3. CORE LOGIC (MCP TOOLS)
# ==========================================

def extract_pdf_text(file) -> str:
    """Helper tool to extract text from a PDF upload."""
    try:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return f"Error extracting PDF: {e}"


def fetch_job_details(url: str) -> str:
    """Tool 1: Scrapes job title, company, and description."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Note: LinkedIn heavily relies on dynamic classes or blocks scrapers.
        # This is a generic fallback extractor for text-heavy content.
        paragraphs = soup.find_all(['p', 'li', 'h1', 'h2'])
        content = "\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        return content if len(content) > 100 else "SCRAPE_BLOCKED"
    except Exception as e:
        return "SCRAPE_FAILED"


def compare_skills(cv_text: str, job_desc: str, api_key: str) -> dict:
    """Tool 2: Strict gap analysis returning structured JSON."""
    genai.configure(api_key=api_key)
    system_instruction = (
        "You are a Senior Technical Recruiter and ATS system. Perform a strict gap analysis between the candidate's CV "
        "and the job description. Return ONLY valid JSON in the exact format requested."
    )
    model = genai.GenerativeModel(
        "gemini-1.5-flash",
        system_instruction=system_instruction,
        generation_config={"response_mime_type": "application/json"}
    )

    prompt = f"""
    Analyze this CV against the Job Description.
    Format your response as a JSON object with this exact schema:
    {{
        "match_score": <integer from 0 to 100>,
        "shared_skills": ["<skill1>", "<skill2>"],
        "missing_keywords": ["<keyword1>", "<keyword2>"],
        "role_relevance": "<1-2 sentence summary of candidate fitness>"
    }}

    CV TEXT:
    {cv_text}

    JOB DESCRIPTION:
    {job_desc}
    """
    try:
        response = model.generate_content(prompt)
        return json.loads(response.text)
    except Exception as e:
        return {"error": str(e)}


def generate_tailored_cv(cv_text: str, job_desc: str, api_key: str) -> str:
    """Tool 3: Rewrites CV to pass ATS, highlighting changes."""
    genai.configure(api_key=api_key)
    system_instruction = (
        "You are an expert Resume Writer optimizing a candidate's CV to bypass ATS filters. "
        "Rewrite the Summary and Professional Experience sections. "
        "CRITICAL INSTRUCTION: You MUST format additions by wrapping them in HTML like this: <span class='cv-add'>new skill here</span>. "
        "You MUST format deletions by wrapping them in HTML like this: <span class='cv-del'>old text here</span>. "
        "Do not use markdown code blocks for the final text, output standard markdown with embedded HTML tags."
    )
    model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system_instruction)

    prompt = f"""
    Tailor the following CV to the target Job Description. Focus on the Professional Summary and Experience bullet points.
    Ensure missing keywords from the job description are naturally integrated.

    CV TEXT:
    {cv_text}

    JOB DESCRIPTION:
    {job_desc}
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating CV: {str(e)}"


# ==========================================
# 4. GUI / WEB INTERFACE
# ==========================================

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Global Settings")
    api_input = st.text_input("Google Gemini API Key", type="password", help="Get this from Google AI Studio")
    if api_input:
        st.session_state.api_key = api_input

    st.divider()
    st.header("📄 Source of Truth (CV)")
    upload_method = st.radio("CV Input Method", ["Upload PDF", "Paste Text"])

    if upload_method == "Upload PDF":
        uploaded_file = st.file_uploader("Upload your current CV", type=['pdf'])
        if uploaded_file is not None:
            if st.button("Extract PDF"):
                with st.spinner("Extracting..."):
                    st.session_state.cv_text = extract_pdf_text(uploaded_file)
                st.success("CV stored successfully!")
    else:
        cv_text_input = st.text_area("Paste your CV text here", height=200)
        if st.button("Save CV"):
            st.session_state.cv_text = cv_text_input
            st.success("CV stored successfully!")

    if st.session_state.cv_text:
        with st.expander("View Stored CV Data"):
            st.caption(st.session_state.cv_text[:500] + "... (truncated)")

# --- MAIN DASHBOARD ---
st.title("🚀 CareerAssistant.ai")
st.markdown("Automate your job application process. Analyze job postings and optimize your CV to beat ATS filters.")

if not st.session_state.api_key:
    st.warning("⚠️ Please enter your Gemini API Key in the sidebar to begin.")
    st.stop()
if not st.session_state.cv_text:
    st.warning("⚠️ Please upload or paste your CV in the sidebar first.")
    st.stop()

# Section 1: Search & Input
st.subheader("1. Job Targeting")
col1, col2 = st.columns([3, 1])
with col1:
    job_url = st.text_input("Target Job URL (LinkedIn, Indeed, etc.)")
with col2:
    # Adding some padding to align the button
    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
    fetch_btn = st.button("Fetch Job", use_container_width=True)

job_desc = st.text_area("Job Description (Auto-filled or paste manually if scrape fails)", height=150, key="manual_jd")

if fetch_btn and job_url:
    with st.spinner("Scraping job data..."):
        scraped_text = fetch_job_details(job_url)
        if scraped_text in ["SCRAPE_BLOCKED", "SCRAPE_FAILED"]:
            st.error(
                "Site blocked the scraper (common with LinkedIn). Please paste the job description manually below.")
        else:
            st.success("Successfully fetched job data!")
            # We use st.rerun to populate the text area via a session state injection,
            # or just instruct user to view it. For simplicity, we assign it directly.
            job_desc = scraped_text
            st.rerun()

# Run Analysis Button
if st.button("⚡ Run Quick Scan & Optimize", type="primary", use_container_width=True):
    if not job_desc:
        st.error("Please provide a job description first.")
    else:
        with st.spinner("Analyzing skills and generating optimized CV..."):
            # Execute Tools
            analysis_json = compare_skills(st.session_state.cv_text, job_desc, st.session_state.api_key)
            optimized_cv_md = generate_tailored_cv(st.session_state.cv_text, job_desc, st.session_state.api_key)

            if "error" in analysis_json:
                st.error(f"Analysis Error: {analysis_json['error']}")
            else:
                # Save to history
                st.session_state.job_history.append({
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "url": job_url if job_url else "Manual Entry",
                    "score": analysis_json.get("match_score", 0)
                })

                # Section 2: Match Score Metrics
                st.divider()
                st.subheader("2. ATS Match Analysis")

                score = analysis_json.get("match_score", 0)
                relevance = analysis_json.get("role_relevance", "N/A")

                score_col, rel_col = st.columns([1, 3])
                with score_col:
                    st.markdown(f"""
                    <div class="metric-card">
                        <p class="metric-value">{score}%</p>
                        <p class="metric-label">Match Score</p>
                    </div>
                    """, unsafe_allow_html=True)
                with rel_col:
                    st.info(f"**Recruiter Assessment:** {relevance}")

                # Section 3: Comparison Table
                st.subheader("3. Skill Gap Comparison")
                comp_col1, comp_col2 = st.columns(2)

                with comp_col1:
                    st.success("✅ Shared Skills (In CV)")
                    for skill in analysis_json.get("shared_skills", []):
                        st.markdown(f"- {skill}")

                with comp_col2:
                    st.error("❌ Missing Keywords (Add to CV)")
                    for keyword in analysis_json.get("missing_keywords", []):
                        st.markdown(f"- {keyword}")

                # Section 4: The Optimizer (Before vs After)
                st.divider()
                st.subheader("4. Tailored CV Optimizer")
                st.caption("Review suggested changes. Green highlights indicate additions, Red indicates deletions.")

                opt_col1, opt_col2 = st.columns(2)
                with opt_col1:
                    st.markdown("### Original CV Segment")
                    st.text_area("Your Source CV", st.session_state.cv_text, height=400, disabled=True)

                with opt_col2:
                    st.markdown("### ATS-Optimized Version")
                    with st.container(border=True):
                        # Rendering the HTML tags generated by Gemini for color highlights
                        st.markdown(optimized_cv_md, unsafe_allow_html=True)

# Section 5: Job List History
st.divider()
st.subheader("5. Analysis History")
if st.session_state.job_history:
    # Convert list of dicts to a quick table
    st.dataframe(st.session_state.job_history, use_container_width=True)
else:
    st.caption("No jobs analyzed yet.")