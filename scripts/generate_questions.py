"""Build app-ready MCQs from OCR text.

The generator creates extractive cloze questions:
- The explanation sentence comes directly from OCR text.
- The blanked answer is a token/phrase found in that sentence.
- Distractors are other tokens/phrases found in the same unit OCR text.

This keeps questions grounded in the scanned PDFs while avoiding invented facts.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_DIR = ROOT / "extracted_text"
JSON_OUT = ROOT / "data" / "generated_questions.json"
JS_OUT = ROOT / "data" / "generated_questions.js"

COMMON_WORDS = {
    "उत्तराखण्ड", "उत्तराखंड", "हाल", "जिसमें", "किया", "गया", "गई", "है", "हैं",
    "तथा", "द्वारा", "लिए", "रूप", "वर्ष", "जनपद", "राज्य", "भारत", "प्रथम",
    "दूसरा", "तीसरा", "स्थान", "पुरस्कार", "आयोजन", "सम्मानित", "अन्तर्गत",
    "इस", "का", "की", "के", "में", "से", "को", "पर", "और", "या", "ने"
}


def normalize_text(text: str) -> str:
    text = re.sub(r"Notes Publication[^।\n]*", " ", text, flags=re.I)
    text = re.sub(r"Scanned with CamScanner", " ", text, flags=re.I)
    text = re.sub(r"---\s*Page\s*\d+\s*---", "\n", text, flags=re.I)
    text = re.sub(r"Page\s*[-–]\s*\d+", " ", text, flags=re.I)
    text = text.replace("|", " ")
    text = re.sub(r"[»>*•©]+", "\n", text)
    return text


def split_sentences(text: str) -> list[str]:
    normalized = normalize_text(text)
    pieces = re.split(r"[\r\n]+|(?<=[।.!?])\s+|(?=\s*[०0]\s)", normalized)
    sentences: list[str] = []
    seen: set[str] = set()
    for piece in pieces:
        clean = piece.strip(" -:;,.।\t\r\n")
        clean = re.sub(r"\s+", " ", clean)
        if "अध्याय" in clean or "Page" in clean or "CamScanner" in clean:
            continue
        if clean.count("  ") > 2:
            continue
        if 55 <= len(clean) <= 230 and clean not in seen:
            if len(re.findall(r"[\u0900-\u097F]", clean)) >= 18:
                sentences.append(clean)
                seen.add(clean)
    return sentences


def candidate_phrases(sentence: str) -> list[str]:
    candidates: list[str] = []

    for match in re.finditer(r"\b\d{2,4}(?:[.,]\d+)?(?:\s*(?:किमी|किमी\.|वर्ष|रू|पदक|मार्च|मई|फरवरी|अप्रैल|जनवरी|दिसम्बर|दिन))?", sentence):
        value = match.group(0).strip()
        if len(value) >= 2 and value not in {"00", "000", "202", "2027"}:
            candidates.append(value)

    words = re.findall(r"[\u0900-\u097F]{3,}", sentence)
    for size in (3, 2):
        for index in range(0, max(0, len(words) - size + 1)):
            phrase_words = words[index:index + size]
            if any(word in COMMON_WORDS for word in phrase_words):
                continue
            phrase = " ".join(phrase_words)
            if 6 <= len(phrase) <= 42:
                candidates.append(phrase)

    unique: list[str] = []
    for candidate in candidates:
        if candidate not in unique and sentence.count(candidate) == 1:
            unique.append(candidate)
    return unique


def collect_unit_candidates(sentences: list[str]) -> list[str]:
    pool: list[str] = []
    for sentence in sentences:
        pool.extend(candidate_phrases(sentence))
    counts = {item: pool.count(item) for item in set(pool)}
    return [item for item, count in counts.items() if count <= 4]


def make_question(unit: int, sentence: str, answer: str, options: list[str], index: int) -> dict:
    rng = random.Random(f"{unit}-{index}-{answer}")
    shuffled = options[:]
    rng.shuffle(shuffled)
    answer_index = shuffled.index(answer)
    blanked = sentence.replace(answer, "____", 1)
    return {
        "id": f"ocr-u{unit}-{index:04d}",
        "unit": unit,
        "source": f"BS Negi OCR Unit {unit}",
        "question": {
            "en": f"Fill in the blank from BS Negi Unit {unit}: {blanked}",
            "hi": f"BS Negi इकाई {unit} के आधार पर रिक्त स्थान भरिए: {blanked}",
        },
        "options": [{"en": option, "hi": option} for option in shuffled],
        "answerIndex": answer_index,
        "explanation": {
            "en": f"Source OCR sentence: {sentence}",
            "hi": f"स्रोत OCR वाक्य: {sentence}",
        },
    }


def generate_for_unit(unit: int, target: int = 120) -> list[dict]:
    text_path = TEXT_DIR / f"unit_{unit}.txt"
    if not text_path.exists():
        return []

    sentences = split_sentences(text_path.read_text(encoding="utf-8", errors="ignore"))
    pool = collect_unit_candidates(sentences)
    questions: list[dict] = []
    used_blanks: set[tuple[str, str]] = set()

    for sentence in sentences:
        for answer in candidate_phrases(sentence):
            if answer not in pool or (sentence, answer) in used_blanks:
                continue
            distractors = [item for item in pool if item != answer and item not in sentence]
            if len(distractors) < 3:
                continue
            rng = random.Random(f"distractors-{unit}-{len(questions)}-{answer}")
            options = [answer, *rng.sample(distractors, 3)]
            questions.append(make_question(unit, sentence, answer, options, len(questions) + 1))
            used_blanks.add((sentence, answer))
            break
        if len(questions) >= target:
            break
    return questions


def main() -> int:
    all_questions: list[dict] = []
    summary: dict[int, int] = {}
    for unit in range(1, 8):
        questions = generate_for_unit(unit)
        summary[unit] = len(questions)
        all_questions.extend(questions)

    JSON_OUT.write_text(json.dumps(all_questions, ensure_ascii=False, indent=2), encoding="utf-8")
    js = "window.GENERATED_QUESTIONS = "
    js += json.dumps(all_questions, ensure_ascii=False, indent=2)
    js += ";\n"
    JS_OUT.write_text(js, encoding="utf-8")

    for unit, count in summary.items():
        print(f"Unit {unit}: {count} questions")
    print(f"Total: {len(all_questions)} questions")
    print(f"Wrote {JSON_OUT.relative_to(ROOT)} and {JS_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
