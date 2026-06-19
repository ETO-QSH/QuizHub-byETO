import json
from collections import OrderedDict, defaultdict

INPUT_FILE = "questions_dedup_sorted.json"
OUTPUT_FILE = "database_compatible.json"

TYPE_MAP = {
    "single_choice": "单选题",
    "multiple_choice": "多选题",
    "true_false": "判断题"
}

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    src = json.load(f)

result = OrderedDict()

# 保存章节顺序
chapter_index_map = OrderedDict()

for q in src["questions"]:

    chapter = q["chapter"]

    if chapter not in chapter_index_map:
        chapter_index_map[chapter] = len(chapter_index_map)

    if chapter not in result:
        result[chapter] = {
            "单选题": [],
            "多选题": [],
            "判断题": []
        }

# 每章节统一编号
uid_counter = defaultdict(int)

for q in src["questions"]:

    chapter = q["chapter"]
    chapter_id = chapter_index_map[chapter]

    qtype = TYPE_MAP[q["type"]]

    uid_counter[chapter] += 1

    uid = f"{chapter_id}-{uid_counter[chapter]}"

    # options转换
    if q["type"] == "true_false":

        options = {
            "√": "正确",
            "×": "错误"
        }

    else:

        options = {
            item["label"]: item["text"]
            for item in q["options"]
        }

    # answer转换
    labels = q["answer"].get("labels", [])

    if q["type"] == "single_choice":

        answer = labels[0] if labels else ""

    elif q["type"] == "multiple_choice":

        answer = labels

    elif q["type"] == "true_false":

        if labels:
            answer = labels[0]
        else:
            answer = q["answer"].get("raw", "")

    item = {
        "uid": uid,
        "question": q["question"],
        "options": options,
        "answer": answer
    }

    result[chapter][qtype].append(item)

# 删除空题型（与database保持一致）
for chapter in result:

    result[chapter] = {
        k: v
        for k, v in result[chapter].items()
        if len(v) > 0
    }

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:

    json.dump(
        result,
        f,
        ensure_ascii=False,
        indent=2
    )

print(f"转换完成 -> {OUTPUT_FILE}")