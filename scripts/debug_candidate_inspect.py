from pathlib import Path
import scripts.generate_questions as g
ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / 'extracted_text' / 'unit_1.txt').read_text(encoding='utf-8', errors='ignore')
sents = g.split_sentences(text)
print('Total sentences', len(sents))
for i, s in enumerate(sents[:20], 1):
    print('---', i)
    print(s)
    print('candidates=', g.candidate_phrases(s))
    print()
