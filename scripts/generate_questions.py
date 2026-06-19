"""Build app-ready MCQs from OCR text.

The generator creates extractive sentence-based questions:
- The explanation sentence comes directly from OCR text.
- The correct answer is a token/phrase found in that sentence.
- Distractors are other token/phrases found in the same unit OCR text.

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

OCR_BLACKLIST_WORDS = {
    "बॉस्केट", "इंटर्नशिप", "समिट", "नेशनल", "रूम", "टेक", "प्रोग्राम",
    "वूमेन", "इन्फो", "ऑनलाइन", "ऑफलाइन", "कोर्स", "प्रोडक्ट",
}

# Patterns/tokens commonly introduced by OCR or irrelevant short fragments
BLACKLIST_PATTERNS = [
    r"\b(?:anf|t0|AAT|AA T|ww|e\b|0 9|० 9)\b",
    r"[A-Za-z]{2,}",
    r"\b(?:Page|CamScanner|Scanned|Notes)\b",
]

# small stopwords that we avoid keeping as the only words in an option
OPTION_STOPWORDS = {"का", "की", "के", "में", "से", "का", "को", "पर", "और", "या"}

# Heuristics for phrase typing to create meaningful question templates
PLACE_KEYWORDS = {
    "जनपद", "जिला", "नगर", "गाँव", "गांव", "देहरादून", "ऋषिकेश",
    "उत्तराखण्ड", "उत्तराखंड", "उत्तरप्रदेश", "उत्तर प्रदेश", "उत्तरकाशी",
}
ORG_KEYWORDS = {"अकादमी", "विश्वविद्यालय", "संस्था", "संगठन", "अकादमी", "बोर्ड"}
PERSON_SUFFIXES = {"सिंह", "कुमार", "देव", "शर्मा", "कौशल", "प्रसाद"}


def phrase_type(phrase: str) -> str:
    """Simple heuristic classifier for answer phrases.

    Returns one of: 'number', 'place', 'organization', 'person', 'other'.
    """
    if re.search(r"\d", phrase):
        return "number"
    low = phrase
    for kw in PLACE_KEYWORDS:
        if kw in low:
            return "place"
    for kw in ORG_KEYWORDS:
        if kw in low:
            return "organization"
    for suf in PERSON_SUFFIXES:
        if low.endswith(suf):
            return "person"
    return "other"


def normalize_text(text: str) -> str:
    text = re.sub(r"Notes Publication[^।\n]*", " ", text, flags=re.I)
    text = re.sub(r"Scanned with CamScanner", " ", text, flags=re.I)
    text = re.sub(r"---\s*Page\s*\d+\s*---", "\n", text, flags=re.I)
    text = re.sub(r"Page\s*[-–]\s*\d+", " ", text, flags=re.I)
    text = text.replace("|", " ")
    text = re.sub(r"[»>*•©]+", "\n", text)
    text = re.sub(r"[\t\f\v]+", " ", text)
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_sentence(sentence: str) -> str:
    sentence = sentence.strip()
    sentence = sentence.strip(" -:;,.।\t\r\n")
    sentence = re.sub(r"^[^\u0900-\u097F0-9]+", "", sentence)
    sentence = re.sub(r"[^\u0900-\u097F0-9।.!?]+$", "", sentence)
    sentence = re.sub(r"\s+", " ", sentence)
    sentence = re.sub(r"\s*([।.!?])\s*$", r"\1", sentence)
    return sentence


def is_quality_sentence(sentence: str) -> bool:
    if len(sentence) < 70 or len(sentence) > 220:
        return False
    if sentence.count("  ") > 1:
        return False
    if "अध्याय" in sentence or "Page" in sentence or "CamScanner" in sentence:
        return False
    if re.search(r"https?://|www\.|@", sentence):
        return False
    deva = len(re.findall(r"[\u0900-\u097F]", sentence))
    ascii = len(re.findall(r"[A-Za-z0-9]", sentence))
    if deva < 25 or ascii > deva:
        return False
    if len(re.findall(r"[A-Za-z]{3,}", sentence)) > 0:
        return False
    if len(re.findall(r"\d", sentence)) > 10:
        return False
    return True


def split_sentences(text: str) -> list[str]:
    normalized = normalize_text(text)
    pieces = re.split(r"[\r\n]+|(?<=[।.!?])\s+|(?=\s*[०0]\s)", normalized)
    sentences: list[str] = []
    seen: set[str] = set()
    for piece in pieces:
        clean = clean_sentence(piece)
        if not clean:
            continue
        if not is_quality_sentence(clean):
            continue
        if clean in seen:
            continue
        sentences.append(clean)
        seen.add(clean)
    return sentences


def is_ocr_noise(phrase: str) -> bool:
    if re.search(r"[A-Za-z]", phrase):
        return True
    if re.search(r"\b(?:Page|CamScanner|Scanned|Notes|Inch|पोर्ट|प्रो|गडोली|इंटर्नशिप|समिट|वूमेन)\b", phrase, flags=re.I):
        return True
    if any(word in phrase for word in OCR_BLACKLIST_WORDS):
        return True
    if re.search(r"[०-९]{2,}|\d{2,}", phrase) and not re.search(r"\d+\s*(?:वर्ष|साल|दिन|पदक|किमी|मई|अप्रैल|जनवरी|फरवरी|मार्च|दिसम्बर)", phrase):
        return False
    return False


def normalize_phrase(phrase: str) -> str:
    phrase = phrase.strip()
    phrase = re.sub(r"\s+", " ", phrase)
    phrase = re.sub(r"\b([\u0900-\u097F]+)\s+\1\b", r"\1", phrase)
    phrase = re.sub(r"^[^\u0900-\u097F]*(.*?)[^\u0900-\u097F]*$", r"\1", phrase)
    phrase = re.sub(r"\b(का|की|के|में|से|को|पर|और|या)\b$", "", phrase).strip()
    return phrase


def is_good_candidate_phrase(phrase: str) -> bool:
    phrase = normalize_phrase(phrase)
    if not phrase or len(phrase) < 8 or len(phrase) > 32:
        return False
    if is_ocr_noise(phrase):
        return False
    if re.search(r"[A-Za-z]{2,}", phrase):
        return False
    if re.search(r"[^--\u0900-\u097F\s]+", phrase):
        return False
    words = phrase.split()
    if len(words) == 1:
        return len(words[0]) >= 6
    if len(words) > 4:
        return False
    if all(word in COMMON_WORDS for word in words):
        return False
    if words[0] in COMMON_WORDS or words[-1] in COMMON_WORDS:
        return False
    if any(word in OCR_BLACKLIST_WORDS for word in words):
        return False
    if any(len(word) < 3 for word in words if word not in OPTION_STOPWORDS):
        return False
    if re.search(r"\b(का|की|के|में|से|को|पर|और|या)\b", phrase) and len(words) <= 2:
        return False
    return True


def candidate_phrases(sentence: str) -> list[str]:
    candidates: list[tuple[int, int, str]] = []

    for match in re.finditer(r"\b\d{2,4}(?:[.,]\d+)?(?:\s*(?:किमी|किमी\.|वर्ष|साल|दिन|पदक|मई|अप्रैल|जनवरी|फरवरी|मार्च|दिसम्बर))?\b", sentence):
        value = normalize_phrase(match.group(0))
        if len(value) >= 2 and value not in {"00", "000", "202", "2027"} and is_good_candidate_phrase(value):
            candidates.append((match.start(), match.end(), value))

    for match in re.finditer(r"(?:[\u0900-\u097F]{3,}\s+){1,3}[\u0900-\u097F]{3,}", sentence):
        phrase = normalize_phrase(match.group(0))
        if is_good_candidate_phrase(phrase):
            candidates.append((match.start(), match.end(), phrase))

    # Prefer longer non-overlapping phrases to avoid fragments and partial answers
    candidates.sort(key=lambda item: (-(item[1] - item[0]), item[0]))
    selected: list[str] = []
    occupied: list[tuple[int, int]] = []
    for start, end, phrase in candidates:
        if any(start < o_end and end > o_start for o_start, o_end in occupied):
            continue
        if phrase not in selected and sentence.count(phrase) == 1:
            selected.append(phrase)
            occupied.append((start, end))
    return selected


def collect_unit_candidates(sentences: list[str]) -> list[str]:
    pool: list[str] = []
    for sentence in sentences:
        pool.extend(candidate_phrases(sentence))
    counts = {item: pool.count(item) for item in set(pool)}
    return [item for item, count in counts.items() if count <= 4]


def build_phrase_index(sentences: list[str]) -> dict:
    """Map each candidate phrase to the list of sentence indices where it appears."""
    index: dict[str, list[int]] = {}
    for i, sentence in enumerate(sentences):
        for phrase in candidate_phrases(sentence):
            index.setdefault(phrase, []).append(i)
    return index


def classify_answer(answer: str) -> str:
    # simple heuristics to guess entity type from the answer phrase
    if re.search(r"\d{4}|\d+\s*(?:वर्ष|साल|सालों|वर्षों)", answer):
        return "date"
    if re.search(r"\d", answer):
        return "number"
    place_words = ["जिला", "जनपद", "नगर", "गांव", "गाँव", "देहरadून", "देहरादून", "उत्तराखण्ड", "उत्तराखंड", "प्रदेश", "राज्य", "नगरपालिका", "विकास" ]
    for w in place_words:
        if w in answer:
            return "place"
    org_words = ["विद्यालय", "विश्वविद्यालय", "अकादमी", "संस्थान", "संस्था", "कंपनी", "कॉलेज", "विभाग", "संगठन", "समिति", "बोर्ड", "हेल्थ", "अस्पताल"]
    for w in org_words:
        if w in answer:
            return "org"
    # person heuristic: if the sentence context often uses 'ने' after the name
    return "phrase"


def select_distractors(pool: list[str], answer: str, sentence_idx: int | None = None, phrase_index: dict | None = None, k: int = 3) -> list[str]:
    kind = classify_answer(answer)
    candidates = [p for p in pool if p != answer and re.fullmatch(r"[\u0900-\u097F\s\d\-]+", p) and is_good_candidate_phrase(p)]
    # prefer distractors from the same sentence when available
    if phrase_index and sentence_idx is not None:
        same_sentence = [p for p in candidates if sentence_idx in phrase_index.get(p, [])]
        if len(same_sentence) >= k:
            candidates = same_sentence
    # prefer same kind distractors when possible
    same_kind = [p for p in candidates if classify_answer(p) == kind]
    if len(same_kind) >= k:
        candidates = same_kind

    ans_tokens = set(re.findall(r"[\u0900-\u097F]+", answer))
    def score(x: str) -> int:
        s = sanitize_phrase(x)
        sc = abs(len(s) - len(answer)) + abs(s.count(' ') - answer.count(' '))
        dev = len(re.findall(r"[\u0900-\u097F]", s))
        sc += max(0, 8 - dev)
        if re.search(r"[A-Za-z]", x):
            sc += 12
        if re.search(r"\b(?:anf|t0|AAT|AA T|WW|ww)\b", x, flags=re.I):
            sc += 10
        cand_tokens = set(re.findall(r"[\u0900-\u097F]+", s))
        overlap = len(ans_tokens & cand_tokens)
        sc += overlap * 4
        if answer.count(' ') >= 1 and s.count(' ') == 0:
            sc += 10
        if len(re.findall(r"[\u0900-\u097F]+", s)) < 2:
            sc += 8
        if phrase_index and sentence_idx is not None:
            ans_positions = phrase_index.get(answer, [])
            cand_positions = phrase_index.get(x, [])
            if ans_positions and cand_positions:
                min_dist = min(abs(a - c) for a in ans_positions for c in cand_positions)
                sc += min_dist
            else:
                sc += 5
        return sc

    candidates.sort(key=score)
    return candidates[:k]


def sanitize_phrase(p: str) -> str:
    p = p.strip()
    p = re.sub(r"^[^\u0900-\u097F0-9]+", "", p)
    p = re.sub(r"[^\u0900-\u097F0-9\s]+$", "", p)
    p = re.sub(r"\s+", " ", p)
    # remove stray ascii junk
    p = re.sub(r"[A-Za-z]{2,}", "", p)
    p = p.strip()
    return p


def is_blacklisted(p: str) -> bool:
    if not p:
        return True
    for pat in BLACKLIST_PATTERNS:
        if re.search(pat, p, flags=re.I):
            return True
    # too many non-Devanagari chars
    total = len(p)
    deva = len(re.findall(r"[\u0900-\u097F]", p))
    if total > 0 and deva / total < 0.5:
        return True
    return False


def polish_option(opt: str, sentence: str, sentences: list[str] | None = None, phrase_index: dict | None = None) -> str:
    """Apply final heuristics to produce a plausible, exam-style Hindi option."""
    if not opt:
        return ""
    opt = sanitize_phrase(opt)
    if is_blacklisted(opt):
        return ""
    # rewrite with context if helpful
    rewritten = rewrite_option(opt, sentence, sentences=sentences, phrase_index=phrase_index)
    if not rewritten:
        rewritten = opt
    # ensure minimum two meaningful words unless numeric
    words = re.findall(r"[\u0900-\u097F]+", rewritten)
    if not re.fullmatch(r"\d+", rewritten) and len(words) < 2:
        # try to attach preceding noun from sentence
        sent_words = re.findall(r"[\u0900-\u097F]+", sentence)
        if sent_words:
            rewritten = f"{sent_words[0]} {rewritten}"
    # strip leading/trailing stopwords
    parts = rewritten.split()
    while parts and parts[0] in OPTION_STOPWORDS:
        parts.pop(0)
    while parts and parts[-1] in OPTION_STOPWORDS:
        parts.pop()
    rewritten = " ".join(parts)
    if is_blacklisted(rewritten):
        return ""
    return rewritten


def rewrite_option(opt: str, sentence: str, sentences: list[str] | None = None, phrase_index: dict | None = None) -> str:
    """Attempt to produce a more meaningful, grammatical option phrase.

    Strategy:
    - Prefer expanded context where the phrase appears (phrase_index + sentences).
    - Otherwise expand in the current sentence with more surrounding words.
    - Remove stray ASCII, collapse repeats, and ensure minimum word count for clarity.
    """
    sopt = sanitize_phrase(opt)
    if not sopt:
        return sopt

    candidates: list[str] = []
    if phrase_index and sentences:
        positions = phrase_index.get(opt, [])
        for pos in positions[:3]:
            try:
                ctx = sentences[pos]
                exp = sanitize_phrase(expand_in_context(opt, ctx, max_words=8))
                if exp:
                    candidates.append(exp)
            except Exception:
                continue

    # fallback: expand in current sentence
    exp = sanitize_phrase(expand_in_context(opt, sentence, max_words=8))
    if exp:
        candidates.append(exp)

    # prefer the longest candidate (more context -> more meaningful)
    if candidates:
        best = max(candidates, key=lambda x: len(x))
    else:
        best = sopt

    # cleanup repeated tokens and stray short fragments
    best = re.sub(r"\b([\u0900-\u097F]+)\s+\1\b", r"\1", best)
    # ensure at least two words for clarity (unless it's a number)
    if not re.fullmatch(r"\d+", best) and best.count(' ') == 0:
        # try to prepend preceding word from sentence
        words = re.findall(r"[\u0900-\u097F]+", sentence)
        if words:
            # find occurrence of the option token
            parts = re.findall(re.escape(opt), sentence)
            if parts:
                best = best
            else:
                # prepend the immediately preceding Devanagari word if available
                w = words[0]
                best = f"{w} {best}"

    return best


def expand_in_context(option: str, sentence: str, max_words: int = 4) -> str:
    """Try to locate `option` in `sentence` and expand it with surrounding words
    to provide a more complete phrase for options.
    """
    opt = option.strip()
    if not opt:
        return option
    # find exact match
    idx = sentence.find(opt)
    if idx == -1:
        # try a loose match ignoring spaces
        pattern = re.sub(r"\s+", r"\\s+", re.escape(opt))
        m = re.search(pattern, sentence)
        if not m:
            return option
        idx = m.start()
    # expand to words around the match
    words = re.findall(r"\S+", sentence)
    # find the word index containing the match
    cum = 0
    word_idx = 0
    for i, w in enumerate(words):
        start = sentence.find(w, cum)
        end = start + len(w)
        if start <= idx < end:
            word_idx = i
            break
        cum = end
    start_idx = max(0, word_idx - 1)
    end_idx = min(len(words), word_idx + max_words)
    snippet = " ".join(words[start_idx:end_idx])
    return snippet


def extract_question_context(sentence: str, answer: str, max_words: int = 10) -> str:
    """Extract a shorter, focused context around the answer phrase."""
    idx = sentence.find(answer)
    if idx == -1:
        return sentence
    words = re.findall(r"\S+", sentence)
    cum = 0
    word_idx = 0
    for i, w in enumerate(words):
        start = sentence.find(w, cum)
        end = start + len(w)
        if start <= idx < end:
            word_idx = i
            break
        cum = end
    start_idx = max(0, word_idx - max_words // 2)
    end_idx = min(len(words), word_idx + max_words // 2 + 1)
    return " ".join(words[start_idx:end_idx])


def mask_answer(sentence: str, answer: str) -> str:
    """Replace the answer phrase with blanks in the source sentence."""
    if not answer:
        return sentence
    o = sanitize_phrase(answer)
    if o and o in sentence:
        try:
            masked = re.sub(re.escape(o), "_____", sentence, count=1)
        except re.error:
            masked = extract_question_context(sentence, answer)
    else:
        masked = extract_question_context(sentence, answer)
    masked = re.sub(r"\s+", " ", masked).strip()
    return masked


def is_valid_option(p: str) -> bool:
    if not p:
        return False
    # numbers as options are allowed
    if re.fullmatch(r"\d+", p):
        return True
    devanagari_chars = len(re.findall(r"[\u0900-\u097F]", p))
    if devanagari_chars < 6:
        return False
    # avoid very short single-token fragments
    if p.count(' ') == 0 and len(p) < 8:
        return False
    # avoid obvious OCR garbage tokens
    if re.search(r"\b(?:anf|t0|e\b|AAT|AA T|ww)\b", p, flags=re.I):
        return False
    return True


def make_question(unit: int, sentence: str, answer: str, options: list[str], index: int, sentences: list[str] | None = None, phrase_index: dict | None = None) -> dict:
    rng = random.Random(f"{unit}-{index}-{answer}")
    sanitized = [sanitize_phrase(o) for o in options]
    # ensure unique and non-empty
    unique_opts: list[str] = []
    for o in sanitized:
        if o and o not in unique_opts:
            unique_opts.append(o)
    # filter invalid options but keep fallback
    filtered = [o for o in unique_opts if is_valid_option(o)]
    final_opts = filtered if len(filtered) >= 4 else unique_opts
    # try to expand, rewrite and polish each option from sentence context so choices read more fully
    expanded_opts: list[str] = []
    for o in unique_opts:
        polished = polish_option(o, sentence, sentences=sentences, phrase_index=phrase_index)
        if polished and polished not in expanded_opts:
            expanded_opts.append(polished)
    # also polish the original uniques as fallback
    for o in unique_opts:
        p = polish_option(o, sentence, sentences=sentences, phrase_index=phrase_index)
        if p and p not in expanded_opts:
            expanded_opts.append(p)
    # merged list keeps expanded forms first, then fallbacks
    merged_opts = []
    for e in expanded_opts + unique_opts:
        if e and e not in merged_opts:
            merged_opts.append(e)

    # normalize option lengths: if answer is multi-word, prefer multi-word distractors
    if answer.count(' ') >= 1:
        # prefer options with same approximate token count
        expanded_sorted = sorted(merged_opts, key=lambda x: abs(x.count(' ') - answer.count(' ')))
    else:
        expanded_sorted = merged_opts

    # if still short, try to pad with sanitized originals; if not possible, give up
    if len(final_opts) < 4:
        for o in expanded_sorted:
            s = sanitize_phrase(o)
            if s and s not in final_opts and is_valid_option(s):
                final_opts.append(s)
            if len(final_opts) >= 4:
                break
    if len(final_opts) < 4:
        # cannot make a reliable 4-option question
        return None
    shuffled = final_opts[:4]
    rng.shuffle(shuffled)
    answer_s = sanitize_phrase(answer)
    answer_index = shuffled.index(answer_s) if answer_s in shuffled else 0

    q_hi = f"निम्नलिखित वाक्य में सही विकल्प चुनिए: \"{mask_answer(sentence, answer)}\""

    return {
        "id": f"ocr-u{unit}-{index:04d}",
        "unit": unit,
        "source": f"BS Negi OCR Unit {unit}",
        "question": {"hi": q_hi},
        "options": [{"hi": option} for option in shuffled],
        "answerIndex": answer_index,
        "explanation": {"hi": f"मूल वाक्य: {sentence}"},
    }


def generate_for_unit(unit: int, target: int = 120) -> list[dict]:
    text_path = TEXT_DIR / f"unit_{unit}.txt"
    if not text_path.exists():
        return []

    sentences = split_sentences(text_path.read_text(encoding="utf-8", errors="ignore"))
    pool = collect_unit_candidates(sentences)
    phrase_index = build_phrase_index(sentences)
    questions: list[dict] = []
    used_answers: set[tuple[str, str]] = set()
    for si, sentence in enumerate(sentences):
        answers = sorted(candidate_phrases(sentence), key=lambda item: (-item.count(" "), -len(item)))
        for answer in answers:
            if answer not in pool or (sentence, answer) in used_answers:
                continue
            distractors = select_distractors(pool, answer, sentence_idx=si, phrase_index=phrase_index, k=200)
            if len(distractors) < 3:
                continue
            rng = random.Random(f"distractors-{unit}-{len(questions)}-{answer}")
            sample_pool = distractors[:min(30, len(distractors))]
            options = [answer, *rng.sample(sample_pool, 3)]
            q = make_question(unit, sentence, answer, options, len(questions) + 1, sentences=sentences, phrase_index=phrase_index)
            if q is None:
                continue
            questions.append(q)
            used_answers.add((sentence, answer))
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
