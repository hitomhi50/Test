import json
import os
import random
import re
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

import requests


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
THREADS_TOKEN = os.getenv("THREADS_TOKEN")
THREADS_USER_ID = os.getenv("THREADS_USER_ID")

CONTENT_TOPIC = os.getenv("CONTENT_TOPIC", "self-growth and productivity")
CONTENT_TONE = os.getenv("CONTENT_TONE", "warm, practical, concise")
CONTENT_LANGUAGE = os.getenv("CONTENT_LANGUAGE", "Traditional Chinese")
HASHTAGS = [
    tag.strip() for tag in os.getenv("HASHTAGS", "#AI #DailyThoughts #Threads").split(",") if tag.strip()
]
APPROVAL_MODE = os.getenv("APPROVAL_MODE", "auto").lower()
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
MAX_POST_CHARS = int(os.getenv("MAX_POST_CHARS", "450"))
MIN_POST_WORDS = int(os.getenv("MIN_POST_WORDS", "25"))
MAX_GENERATION_ATTEMPTS = int(os.getenv("MAX_GENERATION_ATTEMPTS", "3"))
MIN_QUALITY_SCORE = float(os.getenv("MIN_QUALITY_SCORE", "0.65"))
BANNED_TERMS = [
    term.strip().lower()
    for term in os.getenv("BANNED_TERMS", "violence,hate,scam,adult").split(",")
    if term.strip()
]
POSTING_RETRIES = int(os.getenv("POSTING_RETRIES", "3"))


def log_event(event: str, **kwargs: Any) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **kwargs,
    }
    print(json.dumps(payload, ensure_ascii=False))


def build_prompt(date_str: str) -> str:
    hashtag_text = " ".join(HASHTAGS)
    return (
        f"You are an expert social media writer. Create one daily Threads post in {CONTENT_LANGUAGE}.\\n"
        f"Topic: {CONTENT_TOPIC}\\n"
        f"Tone: {CONTENT_TONE}\\n"
        f"Date context: {date_str}\\n"
        "Requirements:\\n"
        "1) Plain text only. No markdown, no bullet lists, no links, no image references.\\n"
        "2) 2-4 short paragraphs, practical and specific, with one actionable takeaway.\\n"
        f"3) Keep total length under {MAX_POST_CHARS} characters.\\n"
        "4) Avoid unsafe, hateful, sexual, violent, or deceptive content.\\n"
        f"5) End with these hashtags exactly once: {hashtag_text}\\n"
        "Return only valid JSON with schema: {\"post\":\"...\",\"quality_notes\":\"...\"}."
    )


def parse_json_from_text(raw_text: str) -> Dict[str, str]:
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        raise ValueError("Model response does not contain JSON")
    data = json.loads(match.group(0))
    if "post" not in data:
        raise ValueError("Missing 'post' field in model response")
    return data


def request_gemini_content(prompt: str) -> Dict[str, str]:
    if not GEMINI_API_KEY:
        raise RuntimeError("Missing GEMINI_API_KEY")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    res_data = response.json()

    if "error" in res_data:
        raise RuntimeError(f"Gemini API error: {res_data['error']}")
    if "candidates" not in res_data:
        raise RuntimeError(f"Unexpected Gemini response: {json.dumps(res_data)}")

    raw_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
    return parse_json_from_text(raw_text)


def fetch_recent_threads_texts(token: str) -> List[str]:
    if not THREADS_USER_ID:
        return []
    url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
    try:
        res = requests.get(
            url,
            params={
                "fields": "id,text,timestamp",
                "limit": 10,
                "access_token": token,
            },
            timeout=20,
        )
        res.raise_for_status()
        data = res.json().get("data", [])
        return [item.get("text", "") for item in data if item.get("text")]
    except Exception as exc:
        log_event("recent_posts_fetch_failed", error=str(exc))
        return []


def contains_banned_terms(text: str) -> bool:
    lower = text.lower()
    return any(term in lower for term in BANNED_TERMS)


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.strip(), b.strip()).ratio()


def quality_score(text: str) -> float:
    words = [w for w in re.split(r"\s+", text.strip()) if w]
    paragraphs = [p for p in text.split("\n") if p.strip()]
    has_hashtag = any(tag in text for tag in HASHTAGS)

    length_score = min(len(text) / max(MAX_POST_CHARS, 1), 1.0)
    word_score = min(len(words) / max(MIN_POST_WORDS, 1), 1.0)
    structure_score = 1.0 if 2 <= len(paragraphs) <= 4 else 0.4
    hashtag_score = 1.0 if has_hashtag else 0.2

    return round(0.25 * length_score + 0.35 * word_score + 0.2 * structure_score + 0.2 * hashtag_score, 3)


def validate_post(text: str, recent_posts: List[str]) -> Optional[str]:
    if not text.strip():
        return "empty_content"
    if len(text) > MAX_POST_CHARS:
        return "too_long"
    if len(re.split(r"\s+", text.strip())) < MIN_POST_WORDS:
        return "too_short"
    if contains_banned_terms(text):
        return "banned_terms_detected"
    for old in recent_posts:
        if similarity(text, old) >= 0.88:
            return "duplicate_like_recent_post"
    if quality_score(text) < MIN_QUALITY_SCORE:
        return "quality_below_threshold"
    return None


def fallback_post(date_str: str) -> str:
    hashtags = " ".join(HASHTAGS)
    return (
        f"{date_str}，今天不需要把所有事情一次完成。先挑一件最重要、最可行的小任務，"
        "在 25 分鐘內專注完成，結束後再做一次簡短回顧。當你持續堆疊小勝利，"
        "焦慮會下降，掌控感會慢慢回來。"
        f"\n\n今天的行動：寫下你現在要做的第一步，然後立刻開始。\n\n{hashtags}"
    )


def maybe_refresh_threads_token(token: str) -> str:
    enable_refresh = os.getenv("THREADS_REFRESH_ENABLED", "false").lower() == "true"
    if not enable_refresh:
        return token

    refresh_url = "https://graph.threads.net/refresh_access_token"
    try:
        res = requests.get(
            refresh_url,
            params={"grant_type": "th_refresh_token", "access_token": token},
            timeout=15,
        )
        res.raise_for_status()
        payload = res.json()
        refreshed = payload.get("access_token")
        if refreshed:
            log_event("threads_token_refreshed")
            return refreshed
    except Exception as exc:
        log_event("threads_token_refresh_failed", error=str(exc))
    return token


def post_to_threads(content: str, token: str) -> bool:
    if not THREADS_USER_ID or not THREADS_USER_ID.isdigit():
        log_event("invalid_threads_user_id", threads_user_id=THREADS_USER_ID)
        return False

    if DRY_RUN:
        log_event("dry_run_post_preview", content=content)
        return True

    if APPROVAL_MODE == "human":
        log_event("approval_required", content=content)
        return True

    container_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
    publish_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"

    for attempt in range(1, POSTING_RETRIES + 1):
        try:
            container_res = requests.post(
                container_url,
                params={
                    "media_type": "TEXT",
                    "text": content,
                    "access_token": token,
                },
                timeout=20,
            )
            container_res.raise_for_status()
            container_data = container_res.json()
            container_id = container_data.get("id")
            if not container_id:
                raise RuntimeError(f"Missing container id: {container_data}")

            publish_res = requests.post(
                publish_url,
                params={"creation_id": container_id, "access_token": token},
                timeout=20,
            )
            publish_res.raise_for_status()
            publish_data = publish_res.json()
            log_event("post_published", publish_response=publish_data)
            return True
        except Exception as exc:
            log_event("post_attempt_failed", attempt=attempt, error=str(exc))
            if attempt < POSTING_RETRIES:
                time.sleep(2 * attempt)

    return False


def build_daily_post(date_str: str, recent_posts: List[str]) -> str:
    prompt = build_prompt(date_str)

    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        try:
            generated = request_gemini_content(prompt)
            post_text = generated["post"].strip()
            error = validate_post(post_text, recent_posts)
            if error:
                log_event("content_validation_failed", attempt=attempt, reason=error)
                continue
            log_event(
                "content_generated",
                attempt=attempt,
                char_count=len(post_text),
                quality_score=quality_score(post_text),
            )
            return post_text
        except Exception as exc:
            log_event("generation_attempt_failed", attempt=attempt, error=str(exc))

    fallback = fallback_post(date_str)
    log_event("fallback_content_used", char_count=len(fallback))
    return fallback


def main() -> None:
    if not all([GEMINI_API_KEY, THREADS_TOKEN, THREADS_USER_ID]):
        log_event("missing_secrets", required=["GEMINI_API_KEY", "THREADS_TOKEN", "THREADS_USER_ID"])
        return

    date_str = datetime.now().strftime("%Y/%m/%d")
    token = maybe_refresh_threads_token(THREADS_TOKEN)
    recent_posts = fetch_recent_threads_texts(token)
    post_text = build_daily_post(date_str, recent_posts)

    success = post_to_threads(post_text, token)
    log_event(
        "run_finished",
        success=success,
        approval_mode=APPROVAL_MODE,
        dry_run=DRY_RUN,
        content_chars=len(post_text),
    )


if __name__ == "__main__":
    main()
