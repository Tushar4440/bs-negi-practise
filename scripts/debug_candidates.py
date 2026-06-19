from pathlib import Path
import re
from generate_questions import split_sentences, candidate_phrases

root = Path(__file__).resolve().parents[1]
text_path = root / 'extracted_text' / 'unit_1.txt'
text = text_path.read_text(encoding='utf-8', errors='ignore')
sentences = split_sentences(text)
for i, s in enumerate(sentences[:10], 1):
    print(f"Sentence {i}: {s}")
    phrases = candidate_phrases(s)
    for p in phrases:
        print(f"  - {p}")
    print()
