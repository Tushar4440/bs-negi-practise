from pathlib import Path
p = Path(__file__).resolve().parents[0] / 'generate_questions.py'
raw = p.read_bytes()
print('size', len(raw), 'nulls', raw.count(b'\x00'))
idx = raw.find(b'\x00')
print('idx', idx)
for offset in range(-40, 41):
    i = idx + offset
    if i < 0 or i >= len(raw):
        continue
    print(f'{i:05d}: {raw[i]:02x} {raw[i:i+1]!r}')
print('segment', raw[idx-40:idx+60])
