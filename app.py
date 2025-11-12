# app.py  — Single-mode: Images (2s) → Sliders + Result estimate
# Includes Google Sheets saving + a debug sidebar

import time
import uuid
import random
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd
import streamlit as st

# ======================== CONFIG ========================
IMAGE_DIR = Path("images")     # put your images here
MAX_IMAGES = 30                # cap (you can change)
SHOW_SECONDS = 2.0             # exact exposure in seconds
EMOTIONS = [
    "Angry", "Happy", "Sad", "Scared",
    "Surprised", "Neutral", "Disgusted", "Contempt",
]
RATING_MIN, RATING_MAX, RATING_DEFAULT = 0, 100, 0

# Optional Google Sheets (safe to leave empty locally)
try:
    SHEET_URL = st.secrets["google_sheets"]["sheet_url"]
except Exception:
    SHEET_URL = ""
# ========================================================

st.set_page_config(page_title="2-Second Image Emotion Survey", layout="centered")

# --- DEBUG STATUS PANEL (sidebar) ---
with st.sidebar:
    st.header("Data Save Status")
    # Is sheet_url set?
    st.write("Sheet URL set:", bool(SHEET_URL))

    # Do we see a service account email?
    try:
        sa_email = st.secrets["google_service_account"]["client_email"]
        st.write("Service account:", sa_email)
    except Exception:
        st.write("Service account:", "(not loaded)")

    # --- Current participant info (debug panel) ---
    st.subheader("Current participant fields")
    st.write("participant_id:", st.session_state.get("participant_id"))
    st.write("name:", st.session_state.get("name"))
    st.write("age:", st.session_state.get("age"))
    st.write("gender:", st.session_state.get("gender"))
    st.write("nationality:", st.session_state.get("nationality"))

# -------------------- Google Sheets I/O (optional) --------------------
def get_worksheet():
    """
    Returns an authorized gspread worksheet for appending rows.
    Requires Streamlit secrets to contain:
      [google_sheets]
      sheet_url = "..."
      [google_service_account]
      ... (service account JSON fields)
    If secrets are missing, returns None (no-op).
    """
    if not SHEET_URL:
        st.warning("Sheets: SHEET_URL is empty; skipping connection.")
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
        # Use or create a worksheet named "responses"
        try:
            ws = sh.worksheet("responses")
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title="responses", rows=2000, cols=40)
            # Header row — matches the rows we append below
            ws.append_row([
                "study_id", "participant_id", "consented", "consent_timestamp_iso",
                "name", "age", "gender", "nationality",
                "trial_index", "order_index", "image_file",
                "rating_angry", "rating_happy", "rating_sad", "rating_scared",
                "rating_surprised", "rating_neutral", "rating_disgusted", "rating_contempt",
                "result_estimate",
                "response_timestamp_iso"
            ])
        st.success("✔ Connected to Google Sheet.")
        return ws
    except Exception as e:
        st.error(f"Google Sheets connection error: {type(e).__name__}: {e}")
        st.info("Common fixes: share the Sheet with the service account (Editor), enable Google Sheets + Drive APIs, and check secrets formatting.")
        return None



def append_row_to_sheet(ws, row: Dict[str, Any]):
    """Append a single trial row to Google Sheets (safe no-op if ws is None)."""
    if ws is None:
        st.warning("Sheets: no worksheet; not writing.")
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
        st.toast("Saved to Google Sheet ✅", icon="✅")
    except Exception as e:
        st.error(f"Failed to append to Google Sheets: {e}")

# -------------------- Helpers --------------------
def load_images(dirpath: Path, max_n: int) -> List[Path]:
    if not dirpath.exists():
        return []
    exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    files = [p for p in sorted(dirpath.iterdir()) if p.suffix.lower() in exts]
    return files[:max_n]

def init_state():
    ss = st.session_state
    ss.setdefault("phase", "consent")   # consent -> demographics -> show -> rate -> done
    ss.setdefault("study_id", "image_emotion_survey_v5")

    # images & order
    ss.setdefault("images", load_images(IMAGE_DIR, MAX_IMAGES))
    ss.setdefault("order", [])      # list of indices into images list
    ss.setdefault("idx", 0)         # current index into order

    # show-phase timing
    ss.setdefault("show_started_at", None)  # float epoch seconds

    # participant info
    ss.setdefault("consented", False)
    ss.setdefault("consent_timestamp_iso", "")
    ss.setdefault("participant_id", "")   # auto-generated unless user overrides
    ss.setdefault("name", "")
    ss.setdefault("age", 0)
    ss.setdefault("gender", "")
    ss.setdefault("nationality", "")

    # responses
    ss.setdefault("responses", [])

    # google sheets
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
        "trial_index": img_idx + 1,           # original index in file order (1-based)
        "order_index": order_index,           # position in the randomized sequence (1-based)
        "image_file": img.name,
        **ratings,
        "result_estimate": result_estimate,   # "Won", "Lost", or "Unsure"
        "response_timestamp_iso": datetime.utcnow().isoformat() + "Z",
    }
    ss.responses.append(row)

    # Append immediately to Google Sheets (no-op if ws is None)
    append_row_to_sheet(ss.ws, row)

    # advance index / phase
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

# One-time connect to Sheets (if configured)
if st.session_state.ws is None and SHEET_URL:
    st.session_state.ws = get_worksheet()

# progress bar
st.progress(st.session_state.idx / total_images if total_images else 0.0)

# ===== CONSENT =====
if st.session_state.phase == "consent":
    st.title("Consent to Participate")
    st.write("""
This study shows a series of images for **2 seconds each**. After each image, 
you will rate several **emotions (0–100)** describing the expression you saw,
and indicate a **Result estimate** (Won / Lost / Unsure).  
Your participation is voluntary. You may stop at any time.
    """)

    agreed = st.checkbox("I consent to participate.")

    # Participant ID (auto, but editable)
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
        name_input = st.text_input("Full name", value=st.session_state.get("name", ""))
        age_input = st.number_input(
            "Age", min_value=1, step=1,
            value=int(st.session_state.get("age", 18)) or 18
        )
        gender_choices = ["", "Female", "Male", "Non-binary / Other", "Prefer not to say"]
        gender_input = st.selectbox(
            "Gender",
            gender_choices,
            index=0 if not st.session_state.get("gender") else gender_choices.index(st.session_state.get("gender"))
        )
        nationality_input = st.text_input("Nationality", value=st.session_state.get("nationality", ""))

        submitted = st.form_submit_button("Start survey")
        if submitted:
            # write widget values explicitly into session_state
            st.session_state.name = name_input.strip()
            try:
                st.session_state.age = int(age_input)
            except Exception:
                st.session_state.age = 0
            st.session_state.gender = gender_input.strip()
            st.session_state.nationality = nationality_input.strip()

            if (
                st.session_state.name
                and st.session_state.gender
                and st.session_state.nationality
                and st.session_state.age > 0
            ):
                st.session_state.order = randomize_order(
                    len(st.session_state.images), seed=st.session_state.participant_id
                )
                st.session_state.idx = 0
                st.session_state.show_started_at = None
                advance("show")
            else:
                st.error("Please complete all demographic fields before starting.")


# ===== SHOW (Stable 2s display without autorefresh) =====
elif st.session_state.phase == "show":
    i = st.session_state.idx
    img_idx = st.session_state.order[i]
    current_img = st.session_state.images[img_idx]

    if st.session_state.show_started_at is None:
        st.session_state.show_started_at = time.time()

    elapsed = time.time() - st.session_state.show_started_at
    remaining = SHOW_SECONDS - elapsed

    st.subheader(f"Image {i+1} of {total_images}")
    st.image(str(current_img), width=800)


    if remaining > 0:
        st.caption(f"Next screen in {max(0.0, remaining):.1f}s…")
        time.sleep(0.1)
        st.rerun()
    else:
        advance("rate")

# ===== RATE =====
elif st.session_state.phase == "rate":
    i = st.session_state.idx
    pos_1based = i + 1

    st.subheader(f"Rate the last image ({pos_1based} of {total_images})")
    st.caption("Please rate based on your memory. Move each slider to indicate intensity (0–100).")

    with st.form(key=f"ratings_form_{i}"):
        sliders = {}
        for emo in EMOTIONS:
            sliders[emo] = st.slider(
                emo, RATING_MIN, RATING_MAX, RATING_DEFAULT, key=f"{emo}_{i}"
            )

        # Result estimate (required)
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

    st.button("Back (disabled during study)", disabled=True)

# ===== DONE =====
elif st.session_state.phase == "done":
    st.success("All done — thank you for participating!")
    st.write("Your responses have been recorded.")
    st.info("You may now close this window.")
