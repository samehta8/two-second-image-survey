# app.py
import time
import uuid
import random
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd
import streamlit as st

# ======================== CONFIG ========================
IMAGE_DIR = Path("images")
MAX_IMAGES = 30
SHOW_SECONDS = 2.0
EMOTIONS = [
    "Angry", "Happy", "Sad", "Scared",
    "Surprised", "Neutral", "Disgusted", "Contempt",
]
RATING_MIN, RATING_MAX, RATING_DEFAULT = 0, 100, 0

# Google Sheets (optional)
try:
    SHEET_URL = st.secrets["google_sheets"]["sheet_url"]
except Exception:
    SHEET_URL = ""
# ========================================================

st.set_page_config(page_title="2-Second Image Emotion Survey", layout="centered")

# -------------------- Google Sheets I/O (optional) --------------------
def get_worksheet():
    if not SHEET_URL:
        return None
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        sa_info = st.secrets["google_service_account"]
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_info(sa_info, scopes=scopes)
        gc = gspread.authorize(credentials)
        sh = gc.open_by_url(SHEET_URL)
        try:
            ws = sh.worksheet("responses")
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title="responses", rows=2000, cols=40)
            ws.append_row([
                "study_id", "participant_id", "consented", "consent_timestamp_iso",
                "name", "age", "gender", "nationality",
                "trial_index", "order_index", "image_file",
                "rating_angry", "rating_happy", "rating_sad", "rating_scared",
                "rating_surprised", "rating_neutral", "rating_disgusted", "rating_contempt",
                "result_estimate",
                "response_timestamp_iso"
            ])
        return ws
    except Exception:
        return None


def append_row_to_sheet(ws, row: Dict[str, Any]):
    if ws is None:
        return
    ordered = [
        row.get("study_id", ""),
        row.get("participant_id", ""),
        row.get("consented", False),
        row.get("consent_timestamp_iso", ""),
        row.get("name", ""),
        row.get("age", ""),
        row.get("gender", ""),
        row.get("nationality", ""),
        row.get("trial_index", ""),
        row.get("order_index", ""),
        row.get("image_file", ""),
        row.get("rating_angry", ""),
        row.get("rating_happy", ""),
        row.get("rating_sad", ""),
        row.get("rating_scared", ""),
        row.get("rating_surprised", ""),
        row.get("rating_neutral", ""),
        row.get("rating_disgusted", ""),
        row.get("rating_contempt", ""),
        row.get("result_estimate", ""),
        row.get("response_timestamp_iso", ""),
    ]
    try:
        ws.append_row(ordered, value_input_option="RAW")
    except Exception:
        pass

# -------------------- Helpers --------------------
def load_images(dirpath: Path, max_n: int) -> List[Path]:
    if not dirpath.exists():
        return []
    exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    files = [p for p in sorted(dirpath.iterdir()) if p.suffix.lower() in exts]
    return files[:max_n]

def init_state():
    ss = st.session_state
    ss.setdefault("phase", "consent")
    ss.setdefault("study_id", "image_emotion_survey_v4")

    ss.setdefault("images", load_images(IMAGE_DIR, MAX_IMAGES))
    ss.setdefault("order", [])
    ss.setdefault("idx", 0)
    ss.setdefault("show_started_at", None)

    ss.setdefault("consented", False)
    ss.setdefault("consent_timestamp_iso", "")
    ss.setdefault("participant_id", "")
    ss.setdefault("name", "")
    ss.setdefault("age", 0)
    ss.setdefault("gender", "")
    ss.setdefault("nationality", "")

    ss.setdefault("responses", [])
    ss.setdefault("ws", None)

def generate_participant_id() -> str:
    return uuid.uuid4().hex[:8].upper()

def randomize_order(n: int, seed: str) -> List[int]:
    rng = random.Random(seed)
    order = list(range(n))
    rng.shuffle(order)
    return order

def ratings_to_dict(sliders: Dict[str, int]) -> Dict[str, int]:
    return {
        "rating_angry": sliders["Angry"],
        "rating_happy": sliders["Happy"],
        "rating_sad": sliders["Sad"],
        "rating_scared": sliders["Scared"],
        "rating_surprised": sliders["Surprised"],
        "rating_neutral": sliders["Neutral"],
        "rating_disgusted": sliders["Disgusted"],
        "rating_contempt": sliders["Contempt"],
    }

def can_start_demographics() -> bool:
    ss = st.session_state
    return bool(
        ss.name.strip()
        and ss.gender.strip()
        and ss.nationality.strip()
        and isinstance(ss.age, int)
        and ss.age > 0
    )

def advance(phase: str):
    st.session_state.phase = phase
    st.rerun()

def record_and_next(sliders: Dict[str, int], result_estimate: str):
    ss = st.session_state
    total = len(ss.order)
    i = ss.idx
    order_index = i + 1
    img_idx = ss.order[i]
    img = ss.images[img_idx]
    ratings = ratings_to_dict(sliders)

    row = {
        "study_id": ss.study_id,
        "participant_id": ss.participant_id,
        "consented": ss.consented,
        "consent_timestamp_iso": ss.consent_timestamp_iso,
        "name": ss.name,
        "age": ss.age,
        "gender": ss.gender,
        "nationality": ss.nationality,
        "trial_index": img_idx + 1,
        "order_index": order_index,
        "image_file": img.name,
        **ratings,
        "result_estimate": result_estimate,
        "response_timestamp_iso": datetime.utcnow().isoformat() + "Z",
    }
    ss.responses.append(row)
    append_row_to_sheet(ss.ws, row)

    ss.idx += 1
    ss.show_started_at = None
    ss.phase = "done" if ss.idx >= total else "show"
    st.rerun()

# -------------------- App Flow --------------------
init_state()
total_images = len(st.session_state.images)
if total_images == 0:
    st.error(f"No images found in `{IMAGE_DIR}/`. Add up to {MAX_IMAGES} images and reload.")
    st.stop()

st.progress(st.session_state.idx / total_images if total_images else 0.0)

if st.session_state.ws is None and SHEET_URL:
    st.session_state.ws = get_worksheet()

# ===== CONSENT =====
if st.session_state.phase == "consent":
    st.title("Consent to Participate")
    st.write("""
This study shows a series of images for **2 seconds each**. After each image, 
you will rate several **emotions (0–100)** describing the expression you saw,
and indicate a **Result estimate** (Won / Lost / Unsure).
    """)

    agreed = st.checkbox("I consent to participate.")
    if not st.session_state.participant_id:
        st.session_state.participant_id = generate_participant_id()
    st.caption("A unique participant ID has been generated. You may override it if needed.")
    st.text_input("Participant ID", key="participant_id")

    if st.button("Continue"):
        if not agreed:
            st.error("You must consent to proceed.")
        else:
            st.session_state.consented = True
            st.session_state.consent_timestamp_iso = datetime.utcnow().isoformat() + "Z"
            advance("demographics")

# ===== DEMOGRAPHICS =====
elif st.session_state.phase == "demographics":
    st.title("Participant Information")
    with st.form("demographics"):
        st.text_input("Full name", key="name")
        st.number_input("Age", min_value=1, step=1, key="age", value=st.session_state.age or 18)
        st.selectbox("Gender", ["", "Female", "Male", "Non-binary / Other", "Prefer not to say"], key="gender")
        st.text_input("Nationality", key="nationality")
        submitted = st.form_submit_button("Start survey")
        if submitted:
            if can_start_demographics():
                st.session_state.order = randomize_order(total_images, seed=st.session_state.participant_id)
                st.session_state.idx = 0
                st.session_state.show_started_at = None
                advance("show")
            else:
                st.error("Please complete all fields before starting.")

# ===== SHOW (Stable 2s display) =====
elif st.session_state.phase == "show":
    i = st.session_state.idx
    img_idx = st.session_state.order[i]
    current_img = st.session_state.images[img_idx]

    if st.session_state.show_started_at is None:
        st.session_state.show_started_at = time.time()

    elapsed = time.time() - st.session_state.show_started_at
    remaining = SHOW_SECONDS - elapsed

    st.subheader(f"Image {i+1} of {total_images}")
    st.image(str(current_img), use_container_width=True)

    if remaining > 0:
        # non-blocking timer refresh
        st.markdown(f"<p style='text-align:center;'>Next screen in {remaining:.1f}s...</p>", unsafe_allow_html=True)
        time.sleep(0.1)
        st.rerun()
    else:
        advance("rate")

# ===== RATE =====
elif st.session_state.phase == "rate":
    i = st.session_state.idx
    pos_1based = i + 1
    st.subheader(f"Rate the last image ({pos_1based} of {total_images})")
    st.caption("Rate the emotions and result estimate below.")

    with st.form(key=f"ratings_form_{i}"):
        sliders = {}
        for emo in EMOTIONS:
            sliders[emo] = st.slider(emo, RATING_MIN, RATING_MAX, RATING_DEFAULT, key=f"{emo}_{i}")

        result_estimate = st.radio(
            "Result estimate (what do you think happened in the match?)",
            ["Won", "Lost", "Unsure"],
            horizontal=True,
            index=None,
            key=f"result_{i}",
        )

        submitted = st.form_submit_button("Submit ratings")
        if submitted:
            if result_estimate is None:
                st.error("Please select Won, Lost, or Unsure before continuing.")
            else:
                record_and_next(sliders, result_estimate=result_estimate)

# ===== DONE =====
elif st.session_state.phase == "done":
    st.success("All done — thank you for participating!")
    df = pd.DataFrame(st.session_state.responses)
    st.dataframe(df, use_container_width=True)
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download responses as CSV",
        data=csv,
        file_name=f"survey_responses_{st.session_state.participant_id}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.csv",
        mime="text/csv",
    )
    st.info("You may close this window.")
