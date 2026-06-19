from pathlib import Path

path = Path(__file__).resolve().parents[0] / 'generate_questions.py'
text = path.read_text(encoding='utf-8', errors='replace')

old_regex = 'if re.search(r"[^-\x7f-\x7f\\u0900-\\u097F\\s]+", phrase):'
# There may be literal  chars in the file, so replace by any occurrence of the broken pattern
text = text.replace('if re.search(r"[^-\x7f-\x7f\\u0900-\\u097F\\s]+", phrase):', 'if re.search(r"[^\\u0900-\\u097F\\s\\-\\d]+", phrase):')
text = text.replace('if re.search(r"[^-\x7f-\x7f\u0900-\u097F\s]+", phrase):', 'if re.search(r"[^\\u0900-\\u097F\\s\\-\\d]+", phrase):')
text = text.replace('if re.search(r"[^-\u0900-\u097F\s]+", phrase):', 'if re.search(r"[^\\u0900-\\u097F\\s\\-\\d]+", phrase):')

old_block_start = 'def select_distractors(pool: list[str], answer: str, sentence_idx: int | None = None, phrase_index: dict | None = None, k: int = 3) -> list[str]:'
if old_block_start not in text:
    raise SystemExit('select_distractors block start not found')
parts = text.split(old_block_start)
prefix = parts[0]
rest = old_block_start.join(parts[1:])
# Find end of function by searching for next 'def ' at same indentation
split_at = rest.find('\ndef def ')
if split_at == -1:
    split_at = rest.find('\ndef make_question')
if split_at == -1:
    raise SystemExit('could not find end of select_distractors block')
rest_after = rest[split_at:]
new_block = '''def select_distractors(pool: list[str], answer: str, sentence_idx: int | None = None, phrase_index: dict | None = None, k: int = 3) -> list[str]:
    kind = classify_answer(answer)
    candidates = [p for p in pool if p != answer and re.fullmatch(r"[\u0900-\u097F\s\d\-]+", p) and is_good_candidate_phrase(p)]
    if phrase_index and sentence_idx is not None:
        same_sentence = [p for p in candidates if sentence_idx in phrase_index.get(p, [])]
        if len(same_sentence) >= k:
            candidates = same_sentence
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
        if re.search(r"\b(?:anf|t0|AAT|AA T|WW|ww|प्रो|आरसीएम|टीबीएम|ट्र)\b", x, flags=re.I):
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
'''
text = prefix + old_block_start + rest_after
text = text.replace(old_block_start + rest[0:split_at], old_block_start + new_block, 1)
src = prefix + new_block + rest_after
path.write_text(src, encoding='utf-8')
print('patched')
"