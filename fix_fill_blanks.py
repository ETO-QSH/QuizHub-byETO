import json
import re

with open("xigai.json", "r", encoding="utf-8") as f:
    data = json.load(f)

fix_count = 0

for unit_title, unit_data in data.items():
    for qtype, questions in unit_data.items():
        if qtype != "填空题":
            continue
        for q in questions:
            text = q["question"]
            ans = q["answer"]

            # 只处理 answer 为空 且 末尾没有 ____ 的题目
            if ans == "" and "____" not in text:
                # 情况1：包含 "是指" 关键词，将后面的内容作为答案
                shizhi_match = re.search(r"(是指|即|指的是)([\s]*)(.+)$", text)
                if shizhi_match:
                    prefix = text[:shizhi_match.start()]
                    answer_part = shizhi_match.group(3).strip()
                    # 去掉末尾可能的标点
                    answer_part = answer_part.rstrip("。，；;")
                    q["question"] = prefix + shizhi_match.group(1) + " ____"
                    q["answer"] = answer_part
                    fix_count += 1
                    print(f"  [拆分] {q['uid']}: 题干={q['question']}  答案={q['answer']}")
                else:
                    # 情况2：没有明显分割词，仅在末尾加 ____
                    text = text.rstrip("。，；; ")
                    q["question"] = text + " ____"
                    fix_count += 1
                    print(f"  [加占位符] {q['uid']}: {q['question']}")

with open("xigai.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\n共修复 {fix_count} 道填空题")