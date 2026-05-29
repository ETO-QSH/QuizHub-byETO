import json

with open('xigai.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for chapter, types in data.items():
    for qtype, questions in types.items():
        if qtype == '填空题':
            for q in questions:
                if 'question' in q and '____' in q['question']:
                    old = q['question']
                    q['question'] = q['question'].replace(' ____', '').replace('____', '')
                    if old != q['question']:
                        print(f'Fixed {q["uid"]}: [{old[-30:]}] -> [{q["question"][-30:]}]')

with open('xigai.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('Done! All ____ placeholders removed from 填空题.')