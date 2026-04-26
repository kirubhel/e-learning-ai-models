import torch
import numpy as np
import re
import string
import difflib
import librosa
import gruut
import os
import tempfile
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from nemo.collections.asr.models import ASRModel
from Levenshtein import distance as levenshtein_distance
from rapidfuzz import fuzz
from lingua import LanguageDetectorBuilder

# Device Configuration
device = "cuda" if torch.cuda.is_available() else "cpu"

# Load NeMo Model
print(f"Loading ASR model on {device}...")
parakeet = ASRModel.from_pretrained(
    "nvidia/parakeet-tdt-0.6b-v3"
).to(device)
parakeet.eval()

# Initialize Language Detector
print("Initializing Language Detector...")
detector = LanguageDetectorBuilder.from_all_languages().build()

# Constants
PHONETIC_WEIGHT = 0.7
TEXT_WEIGHT = 0.3

# Helper Functions
def detect_language(text, input_type="sentence"):
    if not text.strip():
        return "unknown", 0.0
    try:
        lang = detector.detect_language_of(text)
        if lang is None:
            return "unknown", 0.0
        confidence = detector.compute_language_confidence(text, lang)
        return lang.iso_code_639_1.name.lower(), confidence
    except Exception:
        return "en", 0.5

def clean_text(text):
    return text.translate(
        str.maketrans('', '', string.punctuation)
    ).lower().strip()

def split_targets(text):
    return [
        s.strip()
        for s in re.split(r'(?<=[.!?])\s+', text)
        if s.strip()
    ]

def detect_input_type(text):
    words = text.split()
    sentences = split_targets(text)
    if len(words) == 1:
        return "word"
    if len(sentences) > 1:
        return "paragraph"
    if len(words) <= 4:
        return "phrase"
    return "sentence"

def get_status_color(status):
    return {
        "excellent": "green",
        "needs_practice": "orange",
        "wrong_input": "red",
        "missing": "gray"
    }.get(status, "gray")

def get_confidence_level(score):
    if score > 85:
        return "high"
    elif score > 40:
        return "medium"
    return "low"

def text_to_phonemes(text):
    phones = []
    try:
        for sent in gruut.sentences(text, lang="en-us"):
            for word in sent:
                if word.phonemes:
                    phones.extend(word.phonemes)
    except Exception:
        pass
    return phones

def text_similarity_short(t, h):
    t_c, h_c = clean_text(t), clean_text(h)
    if not h_c:
        return 0.0
    if len(t_c.split()) == 1:
        heard_words = h_c.split()
        return max((fuzz.ratio(t_c, w) for w in heard_words), default=0) / 100.0
    return fuzz.token_set_ratio(t_c, h_c) / 100.0

def hybrid_similarity(t, t_ph, h, h_ph):
    if not h:
        return 0.0
    if clean_text(t) == clean_text(h):
        return 1.0
    
    p_sim = 0
    if t_ph and h_ph:
        all_ph = list(set(t_ph + h_ph))
        mapping = {p: chr(i + 1000) for i, p in enumerate(all_ph)}
        t_str = "".join(mapping[p] for p in t_ph if p in mapping)
        h_str = "".join(mapping[p] for p in h_ph if p in mapping)
        if t_str and h_str:
            p_sim = 1 - (
                levenshtein_distance(t_str, h_str)
                / max(len(t_str), len(h_str))
            )
            
    t_c, h_c = clean_text(t), clean_text(h)
    t_sim = 1 - (
        levenshtein_distance(t_c, h_c)
        / max(len(t_c), len(h_c))
    ) if t_c and h_c else 0
    
    return PHONETIC_WEIGHT * p_sim + TEXT_WEIGHT * t_sim

def load_audio(file_path):
    try:
        audio, sr = librosa.load(file_path, sr=16000, mono=True)
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / (max_val + 1e-8)
        audio, _ = librosa.effects.trim(audio, top_db=20)
        if len(audio) < 8000:
            audio = np.pad(audio, (0, 8000 - len(audio)))
        return audio.astype(np.float32)
    except Exception:
        return None

def extract_word_errors(target_words, heard_words):
    errors = []
    matcher = difflib.SequenceMatcher(None, target_words, heard_words)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            errors.extend(target_words[i1:i2])
    return list(dict.fromkeys(errors))

class StarEvaluator:
    def __init__(self, model, device):
        self.model = model
        self.device = device

    def evaluate(self, audio_path, target_text):
        input_type = detect_input_type(target_text)
        targets = split_targets(target_text)

        audio = load_audio(audio_path)
        if audio is None:
            return {"error": "audio failed"}

        with torch.no_grad():
            # NeMo transcribe returns a list of hypotheses
            hyps = self.model.transcribe([audio])
            hyp = hyps[0]
            # Handle both text objects and strings
            full_heard = hyp.text.lower() if hasattr(hyp, "text") else str(hyp).lower()

        clean_target = clean_text(target_text)
        clean_heard = clean_text(full_heard)

        if input_type in ["word", "phrase"]:
            relevance = fuzz.token_set_ratio(clean_target, clean_heard) / 100.0
            if relevance < 0.3:
                return {
                    "input_type": input_type,
                    "overall_score": 0,
                    "details": [{
                        "segment_index": 1,
                        "target": target_text,
                        "heard": "",
                        "debug_heard": full_heard,
                        "score": 0,
                        "status": "wrong_input",
                        "status_color": "red",
                        "feedback": f"Try saying '{target_text}'",
                        "confidence_level": "low"
                    }]
                }
            sim = text_similarity_short(target_text, full_heard)
            score = sim * 100
            status = "excellent" if score > 85 else "needs_practice"
            return {
                "input_type": input_type,
                "overall_score": round(score, 1),
                "details": [{
                    "segment_index": 1,
                    "target": target_text,
                    "heard": "",
                    "debug_heard": full_heard,
                    "score": round(score, 1),
                    "status": status,
                    "status_color": get_status_color(status),
                    "feedback": "Great job!" if score > 85 else "Try again",
                    "confidence_level": get_confidence_level(score)
                }]
            }

        target_ph_cache = {
            i: text_to_phonemes(t)
            for i, t in enumerate(targets)
        }

        results = [
            {
                "segment_index": i + 1,
                "target": targets[i],
                "heard": "",
                "debug_heard": "",
                "score": 0,
                "status": "missing",
                "status_color": "gray",
                "feedback": "Sentence not detected in speech.",
                "confidence_level": "low"
            }
            for i in range(len(targets))
        ]

        heard_sentences = split_targets(full_heard)
        used_targets = set()

        for hs in heard_sentences:
            clean_hs = clean_text(hs)
            best_score = 0
            best_target_idx = -1

            for i in range(len(targets)):
                if i in used_targets:
                    continue
                score = fuzz.token_set_ratio(
                    clean_text(targets[i]),
                    clean_hs
                ) / 100.0
                if score > best_score:
                    best_score = score
                    best_target_idx = i

            if best_score > 0.6:
                i = best_target_idx
                used_targets.add(i)
                t_words = clean_text(targets[i]).split()
                if len(t_words) <= 3:
                    sim = text_similarity_short(targets[i], hs)
                else:
                    sim = hybrid_similarity(
                        targets[i],
                        target_ph_cache[i],
                        hs,
                        text_to_phonemes(hs)
                    )
                score_val = sim * 100
                errors = extract_word_errors(
                    clean_text(targets[i]).split(),
                    clean_text(hs).split()
                )
                if score_val > 85:
                    status = "excellent"
                    feedback = "Great job! ⭐️"
                elif score_val < 30:
                    status = "needs_practice"
                    score_val = max(score_val, 25)
                    feedback = "Try reading again."
                else:
                    status = "needs_practice"
                    feedback = f"Focus on: {', '.join(errors)}" if errors else "Keep practicing!"
                
                results[i] = {
                    "segment_index": i + 1,
                    "target": targets[i],
                    "heard": "",
                    "debug_heard": hs,
                    "score": round(score_val, 1),
                    "status": status,
                    "status_color": get_status_color(status),
                    "feedback": feedback,
                    "confidence_level": get_confidence_level(score_val)
                }

        valid_scores = [r["score"] for r in results if r["status"] != "missing"]
        overall_score = round(np.mean(valid_scores), 1) if valid_scores else 0

        return {
            "input_type": input_type,
            "overall_score": overall_score,
            "details": results,
            "debug": {
                "full_heard_text": full_heard,
                "heard_sentences": heard_sentences
            }
        }

# -------------------------------
# FASTAPI APP WRAPPER
# -------------------------------
app = FastAPI(title="Star Speech Evaluation Service", version="3.0.0")
templates = Jinja2Templates(directory="templates")
evaluator = StarEvaluator(parakeet, device)

class SegmentDetail(BaseModel):
    segment_index: int
    target: str
    heard: str
    debug_heard: str
    score: float
    status: str
    status_color: str
    feedback: str
    confidence_level: str

class EvaluationResponse(BaseModel):
    input_type: str
    overall_score: float
    details: List[SegmentDetail]
    debug: Optional[Dict[str, Any]] = None

@app.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_speech(
    audio_file: UploadFile = File(...),
    target_word: str = Form(...)
):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(await audio_file.read())
        temp_path = tmp.name

    try:
        result = evaluator.evaluate(temp_path, target_word)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
def health():
    return {"status": "healthy", "device": device, "model": "parakeet-tdt-0.6b-v3"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=9022, reload=False)