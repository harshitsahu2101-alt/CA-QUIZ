import calendar
from datetime import date, timedelta
import json
from google import genai
from google.genai import types
from PIL import Image
import pypdf
import streamlit as st
from supabase import create_client

# Page Setup
st.set_page_config(
    page_title="Banking Prep",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom Zero-Lag Minimalist CSS
st.markdown(
    """
<style>
    /* Suppress Streamlit default headers, deploy badges, and footers */
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
        max-width: 720px; 
    }
    
    .app-title {
        text-align: center;
        font-size: 24px;
        font-weight: 800;
        letter-spacing: 1.2px;
        color: #1e3a8a;
        margin-bottom: 16px;
        text-transform: uppercase;
    }

    /* Google Calendar Navigation Bar */
    .gcal-weekdays {
        background-color: #3b69a8;
        color: #ffffff;
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        text-align: center;
        font-weight: 700;
        font-size: 13px;
        padding: 6px 0px;
    }

    div[data-testid="stHorizontalBlock"] button {
        background-color: #ffffff !important;
        color: #1f2937 !important;
        border: 1px solid #d1d5db !important;
        border-radius: 0px !important;
        padding: 6px 0px !important;
        font-size: 12px !important;
        font-weight: 600 !important;
        min-height: 42px !important;
        margin: 0px !important;
    }
    div[data-testid="stHorizontalBlock"] button:hover {
        background-color: #e0e7ff !important;
        border-color: #3b82f6 !important;
    }

    /* CBT Exam Header Banner */
    .cbt-banner {
        background-color: #2b5797;
        color: white;
        padding: 10px 14px;
        border-radius: 6px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-weight: 600;
        font-size: 14px;
        margin-bottom: 15px;
    }

    .question-panel {
        background: #ffffff;
        padding: 20px;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        min-height: 320px;
    }

    .palette-box {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 14px;
    }

    /* Learning & Summary Card */
    .learning-box {
        background: #f8fafc;
        border: 1px solid #cbd5e1;
        border-left: 5px solid #2563eb;
        padding: 16px 18px;
        border-radius: 0 8px 8px 0;
        margin-top: 15px;
        color: #1e293b;
    }
    .learning-title {
        font-weight: 700;
        font-size: 15px;
        margin-bottom: 8px;
        color: #1e3a8a;
    }

    /* Flashcard Card Layout */
    .flashcard {
        background: #ffffff;
        border: 2px solid #3b82f6;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.08);
        margin-bottom: 20px;
    }

    .todo-card {
        background: #ffffff;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        padding: 16px 20px;
        margin-bottom: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
    }

    div[data-testid="stRadio"] > label { display: none; }
</style>
""",
    unsafe_allow_html=True,
)

# Secrets & Supabase Connection
gemini_key = st.secrets.get("GEMINI_API_KEY", "")
supabase_url = st.secrets.get("SUPABASE_URL", "")
supabase_key = st.secrets.get("SUPABASE_KEY", "")
admin_password = st.secrets.get("ADMIN_PASSWORD", "Harshit@2101")

client = genai.Client(api_key=gemini_key) if gemini_key else None
supabase = (
    create_client(supabase_url, supabase_key)
    if supabase_url and supabase_key
    else None
)


# Cached Database Queries for Zero-Lag Navigation
@st.cache_data(ttl=60)
def fetch_all_dates():
  if not supabase:
    return set(), set()
  q_res = supabase.table("quizzes").select("quiz_date").execute()
  v_res = supabase.table("vocab").select("vocab_date").execute()
  q_dates = {item["quiz_date"] for item in q_res.data} if q_res.data else set()
  v_dates = (
      {item["vocab_date"] for item in v_res.data} if v_res.data else set()
  )
  return q_dates, v_dates


@st.cache_data(ttl=300)
def get_quiz_data(target_date):
  res = (
      supabase.table("quizzes")
      .select("data")
      .eq("quiz_date", str(target_date))
      .execute()
  )
  if res.data and res.data[0].get("data"):
    return json.loads(res.data[0]["data"])
  return []


@st.cache_data(ttl=300)
def get_vocab_data(target_date):
  res = (
      supabase.table("vocab")
      .select("data")
      .eq("vocab_date", str(target_date))
      .execute()
  )
  if res.data and res.data[0].get("data"):
    return json.loads(res.data[0]["data"])
  return []


def extract_pdf_text(uploaded_file):
  reader = pypdf.PdfReader(uploaded_file)
  text = ""
  for page in reader.pages:
    p_text = page.extract_text()
    if p_text:
      text += p_text + "\n"
  return text


# AI Extraction: Exhaustive Banking MCQs with Complete Point Summaries
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
  response = client.models.generate_content(
      model="gemini-3.6-flash",
      contents=prompt,
      config=types.GenerateContentConfig(response_mime_type="application/json"),
  )
  return json.loads(response.text)


# AI Extraction: Vocab Flashcards with Mnemonics
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
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt + f"\nDocument text:\n{text}",
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        ),
    )
  else:
    img = Image.open(file_bytes)
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=[prompt, img],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        ),
    )
  return json.loads(response.text)


# State Initializations
if "screen" not in st.session_state:
  st.session_state.screen = "home"
if "selected_ca_date" not in st.session_state:
  st.session_state.selected_ca_date = None
if "selected_vocab_date" not in st.session_state:
  st.session_state.selected_vocab_date = None
if "month_offset" not in st.session_state:
  st.session_state.month_offset = 0
if "card_idx" not in st.session_state:
  st.session_state.card_idx = 0
if "current_q_idx" not in st.session_state:
  st.session_state.current_q_idx = 0

uploaded_ca_dates, uploaded_vocab_dates = fetch_all_dates()

st.markdown('<div class="app-title">Banking Prep</div>', unsafe_allow_html=True)


# Helper: Render Unified Google Calendar
def render_calendar(active_dates_set, on_select_callback):
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

  nav_c1, nav_c2, nav_c3 = st.columns([1, 2, 1])
  with nav_c1:
    if st.button("◀ Prev Month", use_container_width=True):
      st.session_state.month_offset -= 1
      st.rerun()
  with nav_c2:
    st.markdown(
        f"<div style='text-align:center; font-weight:700; font-size:16px;"
        f" padding-top:6px;'>{month_name} {curr_year}</div>",
        unsafe_allow_html=True,
    )
  with nav_c3:
    if st.button("Next Month ▶", use_container_width=True):
      st.session_state.month_offset += 1
      st.rerun()

  st.markdown(
      """
    <div class="gcal-weekdays">
        <div>S</div><div>M</div><div>T</div><div>W</div><div>T</div><div>F</div><div>S</div>
    </div>
    """,
      unsafe_allow_html=True,
  )

  for week in month_matrix:
    d_cols = st.columns(7)
    for i, day in enumerate(week):
      if day == 0:
        d_cols[i].button(
            " ",
            key=f"blank_{curr_year}_{curr_month}_{i}_{week[0]}",
            disabled=True,
        )
      else:
        d_str = f"{curr_year}-{curr_month:02d}-{day:02d}"
        has_item = d_str in active_dates_set
        badge = "🟢" if has_item else "🔴"
        if d_cols[i].button(
            f"{badge} {day}", key=f"btn_{d_str}", use_container_width=True
        ):
          if has_item:
            on_select_callback(d_str)
          else:
            st.toast(f"No content uploaded for {d_str} yet!", icon="🔴")


# ----------------------------------------------------
# 1. HOME SCREEN (3 MINIMAL TILES)
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
    if st.button("📋\n\nTo-Do List", use_container_width=True):
      st.session_state.screen = "todo"
      st.rerun()

# ----------------------------------------------------
# 2. VOCAB HUB (CALENDAR + ADMIN UPLOAD)
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
      v_file = st.file_uploader(
          "Upload Vocab File (PDF / PNG / JPG)", type=["pdf", "png", "jpg"]
      )

      b_u1, b_u2 = st.columns(2)
      with b_u1:
        if st.button(
            "Process & Upload Vocab", type="primary", use_container_width=True
        ):
          if v_file and client and supabase:
            with st.spinner("Analyzing words and generating mnemonics..."):
              try:
                is_p = v_file.name.lower().endswith(".pdf")
                vocab_json = process_vocab_content(v_file, is_p)
                supabase.table("vocab").upsert({
                    "vocab_date": str(target_v_date),
                    "data": json.dumps(vocab_json),
                }).execute()
                st.cache_data.clear()
                st.success(
                    f"Saved {len(vocab_json)} words for {target_v_date}!"
                )
                st.rerun()
              except Exception as e:
                st.error(f"Error: {e}")
      with b_u2:
        if str(target_v_date) in uploaded_vocab_dates:
          if st.button(
              "🗑️ Delete Vocab for Date",
              type="secondary",
              use_container_width=True,
          ):
            supabase.table("vocab").delete().eq(
                "vocab_date", str(target_v_date)
            ).execute()
            st.cache_data.clear()
            st.success(f"Deleted vocab for {target_v_date}.")
            st.rerun()

  st.write("### 📅 Select Date to Review Vocab")

  def open_vocab(selected_date):
    st.session_state.selected_vocab_date = selected_date
    st.session_state.card_idx = 0
    st.session_state.screen = "vocab_flashcards"
    st.rerun()

  render_calendar(uploaded_vocab_dates, open_vocab)

# ----------------------------------------------------
# 3. VOCAB FLASHCARDS VIEW
# ----------------------------------------------------
elif st.session_state.screen == "vocab_flashcards":
  target_date = st.session_state.selected_vocab_date
  words = get_vocab_data(target_date)

  nav_c1, nav_c2 = st.columns([1, 4])
  with nav_c1:
    if st.button("📅 Change Date"):
      st.session_state.screen = "vocab_hub"
      st.rerun()

  if not words:
    st.warning("No words found.")
    st.stop()

  total_words = len(words)
  c_idx = max(0, min(st.session_state.card_idx, total_words - 1))
  item = words[c_idx]

  st.markdown(
      f"""
    <div class="flashcard">
        <div style="font-size:13px; font-weight:700; color:#6b7280; text-transform:uppercase;">
            Word {c_idx + 1} of {total_words} • {item.get('part_of_speech', '')}
        </div>
        <h2 style="color:#1e3a8a; margin: 8px 0 14px 0;">{item['word']}</h2>
        <p style="font-size:16px; color:#1f2937; margin-bottom:14px;"><strong>Meaning:</strong> {item['meaning']}</p>
        <div style="background:#eff6ff; border-left:4px solid #3b82f6; padding:12px; border-radius:0 6px 6px 0; margin-bottom:12px;">
            <strong style="color:#1d4ed8;">🧠 Mnemonic Trick:</strong><br>
            <span style="color:#1e293b;">{item['mnemonic']}</span>
        </div>
        <p style="color:#374151; font-style:italic;"><strong>Example:</strong> "{item['example']}"</p>
        <div style="margin-top:10px; font-size:13px; color:#4b5563;">
            <strong>Synonyms:</strong> {', '.join(item.get('synonyms', []))} | <strong>Antonyms:</strong> {', '.join(item.get('antonyms', []))}
        </div>
    </div>
    """,
      unsafe_allow_html=True,
  )

  f_col1, f_col2, f_col3 = st.columns([1, 2, 1])
  with f_col1:
    if st.button("⬅️ Previous", use_container_width=True) and c_idx > 0:
      st.session_state.card_idx -= 1
      st.rerun()
  with f_col3:
    if (
        st.button("Next ➡️", type="primary", use_container_width=True)
        and c_idx < total_words - 1
    ):
      st.session_state.card_idx += 1
      st.rerun()

# ----------------------------------------------------
# 4. CA QUIZ HUB (CALENDAR + ADMIN UPLOAD)
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
        if st.button(
            "Process & Upload CA Quiz",
            type="primary",
            use_container_width=True,
        ):
          if ca_file and client and supabase:
            with st.spinner("Generating exhaustive exam questions..."):
              try:
                pdf_raw = extract_pdf_text(ca_file)
                quiz_json = process_ca_pdf(pdf_raw)
                supabase.table("quizzes").upsert({
                    "quiz_date": str(target_ca_date),
                    "data": json.dumps(quiz_json),
                }).execute()
                st.cache_data.clear()
                st.success(
                    f"Saved {len(quiz_json)} questions for {target_ca_date}!"
                )
                st.rerun()
              except Exception as e:
                st.error(f"Error: {e}")
      with b_u2:
        if str(target_ca_date) in uploaded_ca_dates:
          if st.button(
              "🗑️ Delete Quiz for Date",
              type="secondary",
              use_container_width=True,
          ):
            supabase.table("quizzes").delete().eq(
                "quiz_date", str(target_ca_date)
            ).execute()
            st.cache_data.clear()
            st.success(f"Deleted quiz for {target_ca_date}.")
            st.rerun()

  st.write("### 📅 Select Date for CA Quiz")

  def open_quiz(selected_date):
    st.session_state.selected_ca_date = selected_date
    st.session_state.current_q_idx = 0
    st.session_state.screen = "ca_exam"
    st.rerun()

  render_calendar(uploaded_ca_dates, open_quiz)

# ----------------------------------------------------
# 5. CA CBT EXAM CONSOLE (FULL SCREEN & ZERO LAG)
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
    st.markdown(
        f"""
        <div class="cbt-banner" style="margin-bottom:0px;">
            <span>General / Banking Awareness • {target_date_str}</span>
            <span>Question {curr_idx + 1} of {total_q}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
  with top_b2:
    if st.button("📅 Change Date", use_container_width=True):
      st.session_state.screen = "ca_hub"
      st.rerun()

  st.markdown("<br>", unsafe_allow_html=True)
  left_pane, right_pane = st.columns([2.5, 1])

  with left_pane:
    st.markdown(
        f"""
        <div class="question-panel">
            <h4 style="margin-top:0; color:#1e293b;">Q{curr_idx + 1}. {curr_q['question']}</h4>
        </div>
        """,
        unsafe_allow_html=True,
    )

    saved_choice = user_ans.get(curr_idx)
    chosen = st.radio(
        "Options",
        options=list(range(len(curr_q["options"]))),
        format_func=lambda x: f"({chr(65+x)})  {curr_q['options'][x]}",
        index=saved_choice if saved_choice is not None else None,
        key=f"ca_opt_{target_date_str}_{curr_idx}",
    )

    if chosen is not None:
      user_ans[curr_idx] = chosen
      if chosen == curr_q["correct_index"]:
        st.success("✅ **Correct!**")
      else:
        ans_char = chr(65 + curr_q["correct_index"])
        ans_text = curr_q["options"][curr_q["correct_index"]]
        st.error(
            f"❌ **Incorrect!** Correct Answer: **({ans_char}) {ans_text}**"
        )

      bullets = curr_q.get("news_bullets", [])
      if bullets:
        points_html = "".join(
            [f"<li style='margin-bottom:8px;'>{b}</li>" for b in bullets]
        )
        st.markdown(
            f"""
            <div class="learning-box">
                <div class="learning-title">📖 Complete News Breakdown:</div>
                <ul style="margin:0; padding-left:20px;">
                    {points_html}
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    b_c1, b_c2, b_c3 = st.columns([1, 1, 1])
    with b_c1:
      if st.button("⬅️ Previous", use_container_width=True) and curr_idx > 0:
        st.session_state.current_q_idx -= 1
        st.rerun()
    with b_c2:
      if st.button("Clear Response", use_container_width=True):
        user_ans.pop(curr_idx, None)
        st.rerun()
    with b_c3:
      if (
          st.button("Next ➡️", type="primary", use_container_width=True)
          and curr_idx < total_q - 1
      ):
        st.session_state.current_q_idx += 1
        st.rerun()

  with right_pane:
    st.markdown(
        """
        <div class="palette-box">
            <div style="font-weight:700; text-align:center; margin-bottom:8px;">Question Palette</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    pal_cols = st.columns(4)
    for q_i in range(total_q):
      col = pal_cols[q_i % 4]
      icon = "🟢" if q_i in user_ans else "⚪"
      if col.button(
          f"{icon} {q_i + 1}", key=f"cbt_{q_i}", use_container_width=True
      ):
        st.session_state.current_q_idx = q_i
        st.rerun()

# ----------------------------------------------------
# 6. TO-DO & REVISION PLANNER TILE
# ----------------------------------------------------
elif st.session_state.screen == "todo":
  nav_c1, nav_c2 = st.columns([1, 4])
  with nav_c1:
    if st.button("⬅️ Home"):
      st.session_state.screen = "home"
      st.rerun()

  today_dt = date.today()
  is_sunday = today_dt.weekday() == 6

  st.write(f"### 📋 Daily Targets for {today_dt.strftime('%A, %d %B %Y')}")

  if is_sunday:
    st.markdown(
        """
        <div class="todo-card" style="border-left: 5px solid #eab308;">
            <h4 style="color:#854d0e; margin:0 0 6px 0;">🌟 Sunday Comprehensive Revision</h4>
            <p style="margin:0; color:#713f12;">No new daily CA today! Revise all Current Affairs and Vocab covered from <strong>Monday to Saturday</strong> this week.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
  else:
    yest_dt = today_dt - timedelta(days=1)
    if yest_dt.weekday() == 6:
      yest_dt = yest_dt - timedelta(days=1)

    rep3_dt = today_dt - timedelta(days=3)
    if rep3_dt.weekday() == 6:
      rep3_dt = rep3_dt - timedelta(days=1)

    st.markdown(
        f"""
        <div class="todo-card" style="border-left: 5px solid #2563eb;">
            <h4 style="color:#1e40af; margin:0 0 4px 0;">🎯 Target 1: Today's Fresh CA & Vocab</h4>
            <p style="margin:0; color:#334155;">Complete CA Quiz & Vocab for <strong>{today_dt.strftime('%d %B %Y')}</strong>.</p>
        </div>
        
        <div class="todo-card" style="border-left: 5px solid #0891b2;">
            <h4 style="color:#0e7490; margin:0 0 4px 0;">🔁 Target 2: Day-1 Spaced Revision</h4>
            <p style="margin:0; color:#334155;">Revise CA Quiz & Vocab of <strong>{yest_dt.strftime('%d %B %Y')}</strong>.</p>
        </div>
        
        <div class="todo-card" style="border-left: 5px solid #9333ea;">
            <h4 style="color:#7e22ce; margin:0 0 4px 0;">🔄 Target 3: Day-3 Spaced Revision</h4>
            <p style="margin:0; color:#334155;">Revise CA Quiz & Vocab of <strong>{rep3_dt.strftime('%d %B %Y')}</strong>.</p>
        </div>

        <div class="todo-card" style="border-left: 5px solid #ea580c;">
            <h4 style="color:#c2410c; margin:0 0 4px 0;">📚 Target 4: Backlog Clearing</h4>
            <p style="margin:0; color:#334155;">Complete <strong>2 Days of Backlog CA</strong> (starting from July sequence, skipping Sundays).</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
