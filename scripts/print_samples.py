import json

with open('data/generated_questions.json', encoding='utf-8') as f:
    q = json.load(f)

for i in range(min(10, len(q))):
    it = q[i]
    print(f"{i+1}. {it['id']}")
    print('Q:', it['question']['hi'])
    for idx, opt in enumerate(it['options']):
        print(f"  {idx+1}. {opt['hi']}")
    print('Answer index:', it['answerIndex'])
    print()
