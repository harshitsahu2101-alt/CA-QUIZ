import calendar
from datetime import date, datetime, timedelta
import json
import base64
import requests
from PIL import Image
import pypdf
import streamlit as st
from supabase import create_client

# Page Setup
st.set_page_config(
    page_title="Banking Prep",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Minimalist Layout CSS
st.markdown("""
<style>
    header[data-testid="stHeader"], #MainMenu, footer, 
    div[data-testid="stToolbar"], div[data-testid="stDecoration"],
    [data-testid="stStatusWidget"], .stDeployButton, .viewerBadge_container__r5tak,
    div[class*="viewerBadge"] {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
    }
    
    .block-container { 
        padding-top: 1rem; 
        padding-bottom: 2rem; 
        max-width: 580px; 
    }
    
    .app-title {
        text-align: center;
        font-size: 22px;
        font-weight: 800;
        letter-spacing: 1px;
        color: #1a73e8;
        margin-bottom: 12px;
        text-transform: uppercase;
    }

    .gcal-card {
        background: #ffffff;
        border: 1px solid #dadce0;
        border-radius: 12px;
        padding: 12px 14px;
        box-shadow: 0 1px 3px rgba(60,64,67,0.12), 0 1px 2px rgba(60,64,67,0.06);
        margin: 10px auto 16px auto;
        max-width: 440px;
    }

    .gcal-weekdays {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        text-align: center;
        font-weight: 700;
        font-size: 12px;
        color: #5f6368;
        margin-bottom: 6px;
    }

    div.gcal-card div[data-testid="stHorizontalBlock"] button {
        background-color: transparent !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 6px !important;
        padding: 0px !important;
        height: 34px !important;
        width: 100% !important;
        min-height: 34px !important;
        max-height: 34px !important;
        margin: 1px auto !important;
    }

    div.gcal-card div[data-testid="stHorizontalBlock"] button:hover {
        background-color: #f1f5f9 !important;
        border-color: #cbd5e1 !important;
    }

    .cbt-banner {
        background-color: #1a73e8;
        color: white;
        padding: 8px 12px;
        border-radius: 6px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-weight: 600;
        font-size: 13px;
        margin-bottom: 12px;
    }

    .question-panel {
        background: #ffffff;
        padding: 16px;
        border: 1px solid #dadce0;
        border-radius: 8px;
        min-height: 240px;
    }

    .palette-box {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 10px;
    }

    .learning-box {
        background: #f8fafc;
        border: 1px solid #cbd5e1;
        border-left: 4px solid #1a73e8;
        padding: 12px 14px;
        border-radius: 0 8px 8px 0;
        margin-top: 12px;
        color: #1e293b;
    }
    .learning-title {
        font-weight: 700;
        font-size: 14px;
        margin-bottom: 6px;
        color: #1a73e8;
    }

    .flashcard {
        background: #ffffff;
        border: 1.5px solid #1a73e8;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06);
        margin-bottom: 16px;
    }

    .todo-card {
        background: #ffffff;
        border-radius: 8px;
        border: 1px solid #dadce0;
        padding: 14px 18px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    div[data-testid="stRadio"] > label { display: none; }
</style>
""", unsafe_allow_html=True)

# Secrets & Supabase Connection
gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()
supabase_url = st.secrets.get("SUPABASE_URL", "").strip()
supabase_key = st.secrets.get("SUPABASE_KEY", "").strip()
admin_password = st.secrets.get("ADMIN_PASSWORD", "Harshit@2101")

supabase = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

# Direct REST Caller for Gemini 3.6 Flash
def call_gemini_rest(prompt_text, inline_data=None):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={gemini_key}"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": gemini_key
    }
    
    parts = [{"text": prompt_text}]
    if inline_data:
        parts.append({
            "inline_data": {
                "mime_type": inline_data["mime_type"],
                "data": inline_data["data"]
            }
        })
        
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=90)
    if response.status_code != 200:
        raise Exception(f"API Error {response.status_code}: {response.text}")
        
    result_json = response.json()
    raw_text = result_json["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(raw_text)

# Database Queries
@st.cache_data(ttl=60)
def fetch_all_dates():
    if not supabase:
        return set(), set()
    try:
        q_res = supabase.table("quizzes").select("quiz_date").execute()
        v_res = supabase.table("vocab").select("vocab_date").execute()
        q_dates = {str(item["quiz_date"]).strip() for item in q_res.data} if q_res.data else set()
        v_dates = {str(item["vocab_date"]).strip() for item in v_res.data} if v_res.data else set()
        return q_dates, v_dates
    except Exception:
        return set(), set()

@st.cache_data(ttl=300)
def get_quiz_data(target_date):
    try:
        res = supabase.table("quizzes").select("data").eq("quiz_date", str(target_date)).execute()
        if res.data and res.data[0].get("data"):
            return json.loads(res.data[0]["data"])
    except Exception:
        pass
    return []

@st.cache_data(ttl=300)
def get_vocab_data(target_date):
    try:
        res = supabase.table("vocab").select("data").eq("vocab_date", str(target_date)).execute()
        if res.data and res.data[0].get("data"):
            return json.loads(res.data[0]["data"])
    except Exception:
        pass
    return []

def extract_pdf_text(uploaded_file):
    reader = pypdf.PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        p_text = page.extract_text()
        if p_text:
            text += p_text + "\n"
    return text

def process_ca_pdf(pdf_text):
    prompt = f"""
    You are an expert Banking Examination Creator (IBPS/SBI PO Mains).
    Task:
    1. Read the provided Current Affairs document thoroughly. Focus strictly on English text (ignore Hindi).
    2. Extract ALL distinct news items, circulars, regulatory announcements, financial outlays, schemes, static GK boxes, and tables without skipping any fact or winner.
    3. Generate an exhaustive set of Multiple Choice Questions (MCQs) covering ALL key numbers, dates, organizations, and facts.
    4. For EVERY question, compile the explanation as an exhaustive, bulleted summary covering the COMPLETE news in the simplest possible learning format:
       - 🎯 Main News: Simple plain-language headline summary.
       - 🔢 Key Figures & Dates: Exact outlay, percentage growth, or deadline.
       - 🏛️ Static GK: Key organization, HQ, President/Minister, or background.
       - 💡 Exam Point: Specific banking/general awareness takeaway.

    Return ONLY a JSON array with this exact structure:
    [
      {{
        "question": "Question text?",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "correct_index": 0,
        "news_bullets": [
          "🎯 Main News: ...",
          "🔢 Key Figures & Dates: ...",
          "🏛️ Static GK: ...",
          "💡 Exam Point: ..."
        ]
      }}
    ]

    Document text:
    {pdf_text}
    """
    return call_gemini_rest(prompt)

def process_vocab_content(file_bytes, is_pdf):
    prompt = """
    You are an expert Vocabulary Builder for Banking & Competitive Exams.
    Task:
    1. Extract all editorial/vocabulary words from the provided content (typically 10-15 words).
    2. For each word, provide:
       - word: The vocabulary word
       - part_of_speech: Noun/Verb/Adj etc.
       - meaning: Simple, crystal-clear definition
       - mnemonic: A highly memorable memory hook, root trick, or fun associative story for instant retention
       - example: A simple, natural everyday sentence showing exact usage
       - synonyms: Array of 2-3 common synonyms
       - antonyms: Array of 2-3 common antonyms

    Return ONLY a JSON array with this exact format:
    [
      {
        "word": "Word",
        "part_of_speech": "Adjective",
        "meaning": "Clear definition",
        "mnemonic": "Memory trick here",
        "example": "Simple example sentence.",
        "synonyms": ["Syn1", "Syn2"],
        "antonyms": ["Ant1", "Ant2"]
      }
    ]
    """
    if is_pdf:
        reader = pypdf.PdfReader(file_bytes)
        text = ""
        for p in reader.pages:
            t = p.extract_text()
            if t:
                text += t + "\n"
        return call_gemini_rest(prompt + f"\nDocument text:\n{text}")
    else:
        b64_data = base64.b64encode(file_bytes.getvalue()).decode('utf-8')
        inline_data = {"mime_type": "image/jpeg", "data": b64_data}
        return call_gemini_rest(prompt, inline_data=inline_data)

# State Initializations
if "screen" not in st.session_state:
    st.session_state.screen = "home"
if "selected_ca_date" not in st.session_state:
    st.session_state.selected_ca_date = None
if "selected_vocab_date" not in st.session_state:
    st.session_state.selected_vocab_date = None
if "selected_todo_date" not in st.session_state:
    st.session_state.selected_todo_date = date(2026, 9, 1)
if "month_offset" not in st.session_state:
    st.session_state.month_offset = 0
if "card_idx" not in st.session_state:
    st.session_state.card_idx = 0
if "current_q_idx" not in st.session_state:
    st.session_state.current_q_idx = 0

uploaded_ca_dates, uploaded_vocab_dates = fetch_all_dates()

st.markdown('<div class="app-title">Banking Prep</div>', unsafe_allow_html=True)

# Backlog Sequence Calculator
def get_backlog_dates_for(selected_dt):
    plan_start = date(2026, 9, 1)
    if selected_dt < plan_start or selected_dt.weekday() == 6:
        return []
    
    working_day_index = 0
    curr = plan_start
    while curr <= selected_dt:
        if curr.weekday() != 6:
            working_day_index += 1
        curr += timedelta(days=1)
        
    backlog_pool = []
    b_curr = date(2026, 6, 1)
    while len(backlog_pool) < (working_day_index * 2):
        if b_curr.weekday() != 6:
            backlog_pool.append(b_curr)
        b_curr += timedelta(days=1)
        
    target_b1_idx = (working_day_index - 1) * 2
    target_b2_idx = target_b1_idx + 1
    
    return [backlog_pool[target_b1_idx], backlog_pool[target_b2_idx]]

# Mini Google Calendar
def render_mini_gcal(active_dates_set, on_select_callback, key_prefix="cal", allow_all=False):
    today = date.today()
    curr_year = today.year
    curr_month = today.month + st.session_state.month_offset
    
    while curr_month > 12:
        curr_month -= 12
        curr_year += 1
    while curr_month < 1:
        curr_month += 12
        curr_year -= 1

    month_name = calendar.month_name[curr_month]
    cal_obj = calendar.Calendar(firstweekday=6)
    month_matrix = cal_obj.monthdayscalendar(curr_year, curr_month)

    st.markdown('<div class="gcal-card">', unsafe_allow_html=True)
    
    nav_c1, nav_c2, nav_c3 = st.columns([1, 4, 1])
    with nav_c1:
        if st.button("‹", key=f"{key_prefix}_prev", use_container_width=True):
            st.session_state.month_offset -= 1
            st.rerun()
    with nav_c2:
        st.markdown(f"<div style='text-align:center; font-weight:700; font-size:14px; color:#3c4043;'>{month_name} {curr_year}</div>", unsafe_allow_html=True)
    with nav_c3:
        if st.button("›", key=f"{key_prefix}_next", use_container_width=True):
            st.session_state.month_offset += 1
            st.rerun()

    st.markdown("""
    <div class="gcal-weekdays">
        <div>S</div><div>M</div><div>T</div><div>W</div><div>T</div><div>F</div><div>S</div>
    </div>
    """, unsafe_allow_html=True)

    for w_idx, week in enumerate(month_matrix):
        d_cols = st.columns(7)
        for i, day in enumerate(week):
            if day == 0:
                d_cols[i].markdown("<div style='height:34px;'></div>", unsafe_allow_html=True)
            else:
                d_obj = date(curr_year, curr_month, day)
                d_str = f"{curr_year}-{curr_month:02d}-{day:02d}"
                has_item = d_str in active_dates_set
                btn_key = f"{key_prefix}_{d_str}_{w_idx}_{i}"
                
                btn_label = f":green[**{day}**]" if has_item else f":red[**{day}**]"
                
                if d_cols[i].button(btn_label, key=btn_key, use_container_width=True):
                    if allow_all or has_item:
                        on_select_callback(d_obj if allow_all else d_str)
                    else:
                        st.toast(f"No content uploaded for {d_str} yet!", icon="🔴")
                        
    st.markdown('</div>', unsafe_allow_html=True)

# ----------------------------------------------------
# 1. HOME SCREEN
# ----------------------------------------------------
if st.session_state.screen == "home":
    t1, t2, t3 = st.columns(3)
    with t1:
        if st.button("📖\n\nDaily Vocab", use_container_width=True):
            st.session_state.screen = "vocab_hub"
            st.rerun()
    with t2:
        if st.button("📝\n\nCA Quiz", use_container_width=True):
            st.session_state.screen = "ca_hub"
            st.rerun()
    with t3:
        if st.button("📋\n\nPlanner", use_container_width=True):
            st.session_state.screen = "todo"
            st.rerun()

# ----------------------------------------------------
# 2. VOCAB HUB
# ----------------------------------------------------
elif st.session_state.screen == "vocab_hub":
    nav_c1, nav_c2 = st.columns([1, 4])
    with nav_c1:
        if st.button("⬅️ Home"):
            st.session_state.screen = "home"
            st.rerun()

    with st.expander("🛠️ Admin Vocab Upload"):
        adm_pass = st.text_input("Password", type="password", key="v_pass")
        if adm_pass == admin_password:
            target_v_date = st.date_input("Target Date", value=date.today())
            v_file = st.file_uploader("Upload Vocab File (PDF / PNG / JPG)", type=["pdf", "png", "jpg"])
            
            b_u1, b_u2 = st.columns(2)
            with b_u1:
                if st.button("Process & Upload Vocab", type="primary", use_container_width=True):
                    if v_file and gemini_key and supabase:
                        with st.spinner("Analyzing words and generating mnemonics..."):
                            try:
                                is_p = v_file.name.lower().endswith(".pdf")
                                vocab_json = process_vocab_content(v_file, is_p)
                                supabase.table("vocab").upsert({
                                    "vocab_date": str(target_v_date),
                                    "data": json.dumps(vocab_json)
                                }).execute()
                                st.cache_data.clear()
                                st.success(f"Saved {len(vocab_json)} words for {target_v_date}!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
            with b_u2:
                if str(target_v_date) in uploaded_vocab_dates:
                    if st.button("🗑️ Delete Vocab for Date", type="secondary", use_container_width=True):
                        supabase.table("vocab").delete().eq("vocab_date", str(target_v_date)).execute()
                        st.cache_data.clear()
                        st.success(f"Deleted vocab for {target_v_date}.")
                        st.rerun()

    st.write("##### 📅 Select Date to Review Vocab")
    def open_vocab(selected_date):
        st.session_state.selected_vocab_date = selected_date
        st.session_state.card_idx = 0
        st.session_state.screen = "vocab_flashcards"
        st.rerun()
        
    render_mini_gcal(uploaded_vocab_dates, open_vocab, key_prefix="vocab_cal")

# ----------------------------------------------------
# 3. VOCAB FLASHCARDS
# ----------------------------------------------------
elif st.session_state.screen == "vocab_flashcards":
    target_date = st.session_state.selected_vocab_date
    words = get_vocab_data(target_date)
    
    nav_c1, nav_c2 = st.columns([1, 4])
    with nav_c1:
        if st.button("📅 Calendar"):
            st.session_state.screen = "vocab_hub"
            st.rerun()
            
    if not words:
        st.warning("No words found.")
        st.stop()
        
    total_words = len(words)
    c_idx = max(0, min(st.session_state.card_idx, total_words - 1))
    item = words[c_idx]
    
    st.markdown(f"""
    <div class="flashcard">
        <div style="font-size:12px; font-weight:700; color:#5f6368; text-transform:uppercase;">
            Word {c_idx + 1} of {total_words} • {item.get('part_of_speech', '')}
        </div>
        <h2 style="color:#1a73e8; margin: 6px 0 12px 0;">{item['word']}</h2>
        <p style="font-size:15px; color:#202124; margin-bottom:12px;"><strong>Meaning:</strong> {item['meaning']}</p>
        <div style="background:#e8f0fe; border-left:4px solid #1a73e8; padding:10px 12px; border-radius:0 6px 6px 0; margin-bottom:12px;">
            <strong style="color:#1967d2;">🧠 Mnemonic Trick:</strong><br>
            <span style="color:#202124; font-size:14px;">{item['mnemonic']}</span>
        </div>
        <p style="color:#3c4043; font-style:italic; font-size:14px;"><strong>Example:</strong> "{item['example']}"</p>
        <div style="margin-top:8px; font-size:12px; color:#5f6368;">
            <strong>Synonyms:</strong> {', '.join(item.get('synonyms', []))} | <strong>Antonyms:</strong> {', '.join(item.get('antonyms', []))}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    f_col1, f_col2, f_col3 = st.columns([1, 2, 1])
    with f_col1:
        if st.button("⬅️ Prev", use_container_width=True) and c_idx > 0:
            st.session_state.card_idx -= 1
            st.rerun()
    with f_col3:
        if st.button("Next ➡️", type="primary", use_container_width=True) and c_idx < total_words - 1:
            st.session_state.card_idx += 1
            st.rerun()

# ----------------------------------------------------
# 4. CA QUIZ HUB
# ----------------------------------------------------
elif st.session_state.screen == "ca_hub":
    nav_c1, nav_c2 = st.columns([1, 4])
    with nav_c1:
        if st.button("⬅️ Home"):
            st.session_state.screen = "home"
            st.rerun()

    with st.expander("🛠️ Admin CA PDF Upload"):
        adm_pass = st.text_input("Password", type="password", key="ca_pass")
        if adm_pass == admin_password:
            target_ca_date = st.date_input("Target Date", value=date.today())
            ca_file = st.file_uploader("Upload Daily CA PDF", type=["pdf"])
            
            b_u1, b_u2 = st.columns(2)
            with b_u1:
                if st.button("Process & Upload CA Quiz", type="primary", use_container_width=True):
                    if ca_file and gemini_key and supabase:
                        with st.spinner("Generating exhaustive exam questions..."):
                            try:
                                pdf_raw = extract_pdf_text(ca_file)
                                quiz_json = process_ca_pdf(pdf_raw)
                                supabase.table("quizzes").upsert({
                                    "quiz_date": str(target_ca_date),
                                    "data": json.dumps(quiz_json)
                                }).execute()
                                st.cache_data.clear()
                                st.success(f"Saved {len(quiz_json)} questions for {target_ca_date}!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
            with b_u2:
                if str(target_ca_date) in uploaded_ca_dates:
                    if st.button("🗑️ Delete Quiz for Date", type="secondary", use_container_width=True):
                        supabase.table("quizzes").delete().eq("quiz_date", str(target_ca_date)).execute()
                        st.cache_data.clear()
                        st.success(f"Deleted quiz for {target_ca_date}.")
                        st.rerun()

    st.write("##### 📅 Select Date for CA Quiz")
    def open_quiz(selected_date):
        st.session_state.selected_ca_date = selected_date
        st.session_state.current_q_idx = 0
        st.session_state.screen = "ca_exam"
        st.rerun()
        
    render_mini_gcal(uploaded_ca_dates, open_quiz, key_prefix="ca_cal")

# ----------------------------------------------------
# 5. CA CBT EXAM CONSOLE
# ----------------------------------------------------
elif st.session_state.screen == "ca_exam":
    target_date_str = st.session_state.selected_ca_date
    questions = get_quiz_data(target_date_str)
    total_q = len(questions)
    
    if total_q == 0:
        st.warning("No questions found.")
        if st.button("⬅️ Back"):
            st.session_state.screen = "ca_hub"
            st.rerun()
        st.stop()
        
    if f"ans_{target_date_str}" not in st.session_state:
        st.session_state[f"ans_{target_date_str}"] = {}
        
    curr_idx = max(0, min(st.session_state.current_q_idx, total_q - 1))
    st.session_state.current_q_idx = curr_idx
    curr_q = questions[curr_idx]
    user_ans = st.session_state[f"ans_{target_date_str}"]

    top_b1, top_b2 = st.columns([3, 1])
    with top_b1:
        st.markdown(f"""
        <div class="cbt-banner" style="margin-bottom:0px;">
            <span>General Awareness • {target_date_str}</span>
            <span>Q{curr_idx + 1}/{total_q}</span>
        </div>
        """, unsafe_allow_html=True)
    with top_b2:
        if st.button("📅 Calendar", use_container_width=True):
            st.session_state.screen = "ca_hub"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    left_pane, right_pane = st.columns([2.5, 1])
    
    with left_pane:
        st.markdown(f"""
        <div class="question-panel">
            <h4 style="margin-top:0; color:#202124; font-size:15px;">Q{curr_idx + 1}. {curr_q['question']}</h4>
        </div>
        """, unsafe_allow_html=True)
        
        saved_choice = user_ans.get(curr_idx)
        chosen = st.radio(
            "Options",
            options=list(range(len(curr_q["options"]))),
            format_func=lambda x: f"({chr(65+x)})  {curr_q['options'][x]}",
            index=saved_choice if saved_choice is not None else None,
            key=f"ca_opt_{target_date_str}_{curr_idx}"
        )
        
        if chosen is not None:
            user_ans[curr_idx] = chosen
            if chosen == curr_q["correct_index"]:
                st.success("✅ **Correct!**")
            else:
                ans_char = chr(65 + curr_q["correct_index"])
                ans_text = curr_q["options"][curr_q["correct_index"]]
                st.error(f"❌ **Incorrect!** Correct Answer: **({ans_char}) {ans_text}**")
            
            bullets = curr_q.get("news_bullets", [])
            if bullets:
                points_html = "".join([f"<li style='margin-bottom:6px;'>{b}</li>" for b in bullets])
                st.markdown(f"""
                <div class="learning-box">
                    <div class="learning-title">📖 Complete News Breakdown:</div>
                    <ul style="margin:0; padding-left:18px; font-size:13.5px;">
                        {points_html}
                    </ul>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        b_c1, b_c2, b_c3 = st.columns([1, 1, 1])
        with b_c1:
            if st.button("⬅️ Prev", use_container_width=True) and curr_idx > 0:
                st.session_state.current_q_idx -= 1
                st.rerun()
        with b_c2:
            if st.button("Clear", use_container_width=True):
                user_ans.pop(curr_idx, None)
                st.rerun()
        with b_c3:
            if st.button("Next ➡️", type="primary", use_container_width=True) and curr_idx < total_q - 1:
                st.session_state.current_q_idx += 1
                st.rerun()

    with right_pane:
        st.markdown("""
        <div class="palette-box">
            <div style="font-weight:700; text-align:center; font-size:12px; margin-bottom:6px;">Palette</div>
        </div>
        """, unsafe_allow_html=True)
        pal_cols = st.columns(4)
        for q_i in range(total_q):
            col = pal_cols[q_i % 4]
            icon = "🟢" if q_i in user_ans else "⚪"
            if col.button(f"{icon}{q_i + 1}", key=f"cbt_{q_i}", use_container_width=True):
                st.session_state.current_q_idx = q_i
                st.rerun()

# ----------------------------------------------------
# 6. TO-DO & REVISION PLANNER
# ----------------------------------------------------
elif st.session_state.screen == "todo":
    nav_c1, nav_c2 = st.columns([1, 4])
    with nav_c1:
        if st.button("⬅️ Home"):
            st.session_state.screen = "home"
            st.rerun()

    st.write("##### 📅 Select Date to View CA Schedule")
    def select_todo_date(chosen_date):
        st.session_state.selected_todo_date = chosen_date
        st.rerun()

    combined_uploaded_dates = uploaded_ca_dates.union(uploaded_vocab_dates)
    render_mini_gcal(combined_uploaded_dates, select_todo_date, key_prefix="todo_cal", allow_all=True)

    selected_dt = st.session_state.selected_todo_date
    is_sunday = selected_dt.weekday() == 6
    plan_start = date(2026, 9, 1)

    st.markdown(f"#### 🎯 CA Schedule for **{selected_dt.strftime('%A, %d %B %Y')}**")

    if selected_dt < plan_start:
        st.info("ℹ️ The fresh schedule starts on **Tuesday, 1 September 2026**. Tap any date from 1 September onwards.")
    elif is_sunday:
        monday_dt = selected_dt - timedelta(days=6)
        saturday_dt = selected_dt - timedelta(days=1)
        if monday_dt < plan_start:
            monday_dt = plan_start
        st.markdown(f"""
        <div class="todo-card" style="border-left: 5px solid #f9ab00;">
            <h4 style="color:#b06000; margin:0 0 6px 0;">🌟 Sunday Weekly Mega Revision</h4>
            <p style="margin:0; color:#202124; font-size:14px; line-height: 1.6;">
                • Revise all <strong>Fresh & Backlog CA</strong> completed from <strong>{monday_dt.strftime('%d %B')}</strong> to <strong>{saturday_dt.strftime('%d %B %Y')}</strong>.<br>
                • <em>No new fresh CA or backlog today.</em>
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        today_backlogs = get_backlog_dates_for(selected_dt)
        b1_str = today_backlogs[0].strftime('%d %B %Y') if today_backlogs else "1 June 2026"
        b2_str = today_backlogs[1].strftime('%d %B %Y') if today_backlogs else "2 June 2026"

        yest_dt = selected_dt - timedelta(days=1)
        if yest_dt.weekday() == 6:
            yest_dt = yest_dt - timedelta(days=1)

        rep3_dt = selected_dt - timedelta(days=3)
        if rep3_dt.weekday() == 6:
            rep3_dt = rep3_dt - timedelta(days=1)

        revision_sections = []

        if yest_dt >= plan_start:
            yest_backlogs = get_backlog_dates_for(yest_dt)
            yb_list = [b.strftime('%d %B %Y') for b in yest_backlogs]
            yb_str = f" + Backlogs ({', '.join(yb_list)})" if yb_list else ""
            revision_sections.append(
                f"• <strong>Day-1 Revision (Done on {yest_dt.strftime('%d %B')}):</strong><br>"
                f"&nbsp;&nbsp;&nbsp;&nbsp;↳ <em>{yest_dt.strftime('%d %B %Y')} Fresh CA{yb_str}</em>"
            )

        if rep3_dt >= plan_start:
            rep3_backlogs = get_backlog_dates_for(rep3_dt)
            r3b_list = [b.strftime('%d %B %Y') for b in rep3_backlogs]
            r3b_str = f" + Backlogs ({', '.join(r3b_list)})" if r3b_list else ""
            revision_sections.append(
                f"• <strong>Day-3 Revision (Done on {rep3_dt.strftime('%d %B')}):</strong><br>"
                f"&nbsp;&nbsp;&nbsp;&nbsp;↳ <em>{rep3_dt.strftime('%d %B %Y')} Fresh CA{r3b_str}</em>"
            )

        if not revision_sections:
            revision_html = "<em>None (Fresh Start Day - No previous revisions)</em>"
        else:
            revision_html = "<br><br>".join(revision_sections)

        st.markdown(f"""
        <div class="todo-card" style="border-left: 5px solid #1a73e8;">
            <h4 style="color:#1a73e8; margin:0 0 8px 0;">📖 CA to Do Today (3 Days Total):</h4>
            <p style="margin:0; color:#202124; font-size:14px; line-height: 1.8;">
                1. <strong>Today's Fresh CA:</strong> {selected_dt.strftime('%d %B %Y')}<br>
                2. <strong>Backlog CA (Day 1):</strong> {b1_str}<br>
                3. <strong>Backlog CA (Day 2):</strong> {b2_str}
            </p>
        </div>
        
        <div class="todo-card" style="border-left: 5px solid #12b5cb;">
            <h4 style="color:#007b83; margin:0 0 8px 0;">🔄 CA to Revise:</h4>
            <p style="margin:0; color:#202124; font-size:14px; line-height: 1.8;">
                {revision_html}
            </p>
        </div>
        """, unsafe_allow_html=True)
