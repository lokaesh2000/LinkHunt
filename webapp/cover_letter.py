# webapp/cover_letter.py
import json
import sqlite3
from pathlib import Path
from pdfminer.high_level import extract_text
from openai import OpenAI

# Load configuration
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

DB_PATH = Path(config.get("db_path", "data/jobs.db"))
TABLE_NAME = config.get("jobs_tablename", "jobs")  # use the same table as the legacy app
OPENAI_API_KEY = config.get("OpenAI_API_KEY", "")
OPENAI_MODEL = config.get("OpenAI_Model", "gpt-4o")
RESUME_PATH = config.get("resume_path", "")

def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def _ensure_columns():
    """Ensure the jobs table has a cover_letter column (matches legacy behavior)."""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT count(name) FROM sqlite_master WHERE type='table' AND name=?",
            (TABLE_NAME,)
        )
        if cur.fetchone()[0] != 1:
            return
        cur.execute(f"PRAGMA table_info({TABLE_NAME})")
        existing = {row[1] for row in cur.fetchall()}
        if "cover_letter" not in existing:
            cur.execute(f'ALTER TABLE "{TABLE_NAME}" ADD COLUMN cover_letter TEXT')
        conn.commit()

_ensure_columns()

def _fetch_job(job_id: int):
    query = f"""
        SELECT id, title, company, location, job_description, cover_letter
        FROM {TABLE_NAME}
        WHERE id = ?
    """
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(query, (job_id,)).fetchone()
        return dict(row) if row else {}

def _store_cover_letter(job_id: int, text: str):
    with _connect() as conn:
        conn.execute(
            f'UPDATE "{TABLE_NAME}" SET cover_letter = ? WHERE id = ?',
            (text, job_id)
        )
        conn.commit()

def _read_resume(path: str) -> str | None:
    try:
        return extract_text(path)
    except FileNotFoundError:
        print(f"[ERROR] Resume file not found at: {path}")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to read resume PDF: {e}")
        return None

def _chat_complete(client: OpenAI, prompt: str) -> str | None:
    try:
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"[ERROR] OpenAI completion failed: {e}")
        return None

def generate_and_store_cover_letter(job_id: int):
    """
    Generates (or retrieves existing) cover letter for a job posting using
    the same two-step OpenAI prompt flow as the original app.
    """
    job = _fetch_job(job_id)
    if not job:
        return None

    # Return cached cover letter if present
    if job.get("cover_letter"):
        return job["cover_letter"]

    # Validate API key and resume
    if not OPENAI_API_KEY:
        print("[ERROR] OpenAI API key is empty in config.json (OpenAI_API_KEY).")
        return None

    resume_text = _read_resume(RESUME_PATH)
    if resume_text is None:
        return None

    client = OpenAI(api_key=OPENAI_API_KEY)

    # ----- Step 1 prompt (matches legacy content) -----
    consideration = ""  # kept to match original structure
    user_prompt = (
        "You are a career coach with over 15 years of experience helping job seekers land their dream jobs in tech. "
        "You are helping a candidate to write a cover letter for the below role. Approach this task in three steps. "
        "Step 1. Identify main challenges someone in this position would face day to day. "
        "Step 2. Write an attention grabbing hook for your cover letter that highlights your experience and qualifications "
        "in a way that shows you empathize and can successfully take on challenges of the role. Consider incorporating "
        "specific examples of how you tackled these challenges in your past work, and explore creative ways to express your "
        "enthusiasm for the opportunity. Put emphasis on how the candidate can contribute to company as opposed to just "
        "listing accomplishments. Keep your hook within 100 words or less. "
        "Step 3. Finish writing the cover letter based on the resume and keep it within 250 words. Respond with final cover "
        f'letter only. \n job description: {job.get("job_description","")} '
        f'\n company: {job.get("company","")} '
        f'\n title: {job.get("title","")} '
        f"\n resume: {resume_text}"
    )
    if consideration:
        user_prompt += "\nConsider incorporating that " + consideration

    first_response = _chat_complete(client, user_prompt)
    if first_response is None:
        return None

    # ----- Step 2 refinement prompt (matches legacy content) -----
    user_prompt2 = (
        "You are young but experienced career coach helping job seekers land their dream jobs in tech. "
        "I need your help crafting a cover letter. "
        f'Here is a job description: {job.get("job_description","")} '
        f"\nhere is my resume: {resume_text} "
        f"\nHere's the cover letter I got so far: {first_response} "
        "I need you to help me improve it. Let's approach this in following steps. \n"
        "Step 1. Please set the formality scale as follows: 1 is conversational English, my initial Cover letter draft is 10. "
        "Step 2. Identify three to five ways this cover letter can be improved, and elaborate on each way with at least one thoughtful sentence. "
        "Step 4. Suggest an improved cover letter based on these suggestions with the Formality Score set to 7. "
        "Avoid subjective qualifiers such as drastic, transformational, etc. Keep the final cover letter within 250 words. "
        "Please respond with the final cover letter only."
    )

    final_response = _chat_complete(client, user_prompt2) or first_response

    # Store and return
    _store_cover_letter(job_id, final_response)
    return final_response
