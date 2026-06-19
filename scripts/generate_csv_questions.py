"""Generate MCQs from author-book.csv and append them to the generated questions files."""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "author-book.csv"
JSON_OUT = ROOT / "data" / "generated_questions.json"
JS_OUT = ROOT / "data" / "generated_questions.js"

SOURCE_LABEL = "Author-Book CSV"
UNIT_LABEL = "csv"


def load_pairs() -> list[dict]:
    pairs = []
    with CSV_PATH.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            book = row["Book"].strip()
            author = row["Author"].strip()
            if book and author:
                pairs.append({"book": book, "author": author})
    return pairs


def make_questions(pairs: list[dict]) -> list[dict]:
    books = [p["book"] for p in pairs]
    authors = [p["author"] for p in pairs]
    questions = []

    for i, pair in enumerate(pairs):
        rng = random.Random(f"csv-{i}")

        # Q1: "इस पुस्तक के लेखक कौन हैं?" (book → author)
        wrong_authors = [a for a in authors if a != pair["author"]]
        distractors = rng.sample(wrong_authors, min(3, len(wrong_authors)))
        if len(distractors) == 3:
            opts = [pair["author"]] + distractors
            rng.shuffle(opts)
            questions.append({
                "id": f"csv-{i:04d}-a",
                "unit": UNIT_LABEL,
                "source": SOURCE_LABEL,
                "question": {"hi": f"'{pair['book']}' पुस्तक के लेखक कौन हैं?"},
                "options": [{"hi": o} for o in opts],
                "answerIndex": opts.index(pair["author"]),
                "explanation": {"hi": f"'{pair['book']}' के लेखक {pair['author']} हैं।"},
            })

        # Q2: "इस लेखक ने कौन-सी पुस्तक लिखी?" (author → book)
        wrong_books = [b for b in books if b != pair["book"]]
        distractors2 = rng.sample(wrong_books, min(3, len(wrong_books)))
        if len(distractors2) == 3:
            opts2 = [pair["book"]] + distractors2
            rng.shuffle(opts2)
            questions.append({
                "id": f"csv-{i:04d}-b",
                "unit": UNIT_LABEL,
                "source": SOURCE_LABEL,
                "question": {"hi": f"'{pair['author']}' द्वारा लिखित पुस्तक कौन-सी है?"},
                "options": [{"hi": o} for o in opts2],
                "answerIndex": opts2.index(pair["book"]),
                "explanation": {"hi": f"{pair['author']} ने '{pair['book']}' पुस्तक लिखी।"},
            })

    return questions


def main() -> int:
    pairs = load_pairs()
    new_qs = make_questions(pairs)

    # Load existing questions
    existing: list[dict] = []
    if JSON_OUT.exists():
        existing = json.loads(JSON_OUT.read_text(encoding="utf-8"))

    # Remove old csv questions (if regenerating)
    existing = [q for q in existing if q.get("unit") != UNIT_LABEL]
    combined = existing + new_qs

    JSON_OUT.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
    JS_OUT.write_text(
        "window.GENERATED_QUESTIONS = " + json.dumps(combined, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )

    print(f"CSV questions generated: {len(new_qs)}")
    print(f"Total questions now: {len(combined)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
