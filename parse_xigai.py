import json
import re
from pathlib import Path

RAW_PATH = Path(r"习概_raw.txt")
RED_PATH = Path(r"习概_red.txt")
OUT_PATH = Path(r"xigai.json")
REPORT_PATH = Path(r"xigai_parse_report.txt")

ALLOWED_TYPES = {
    "单项选择题": "单选题",
    "多项选择题": "多选题",
    "判断题": "判断题",
    "填空题": "填空题",
    "简答题": "简答题",
    "论述题": "论述题"
}

CHAPTER_RE = re.compile(r"^(导论\b.*|第\s*\d*\s*章\b.*)")
QTYPE_RE = re.compile(r"^[一二三四五六七八九十]+、\s*(单项选择题|多项选择题|判断题|填空题|简答题|论述题)")
QUESTION_RE = re.compile(r"^\s*(\d+)[\.、]\s*(.*)")
OPTION_MARK_RE = re.compile(r"[（(]([A-G])[）)]\s*")
OPTION_INLINE_RE = re.compile(r"(?:[（(]([A-G])[）)]|([A-G])[\.、\)])\s*")
JUDGE_ANS_RE = re.compile(r"[（(]\s*([√×])\s*[）)]")
PAGE_MARK_RE = re.compile(r"^—\s*\d+\s*—$")
ANSWER_LINE_RE = re.compile(r"^(?:答[:：]|答案[:：]|参考答案[:：]|【参考答案】)")


def clean_toc_unit(text):
    t = re.sub(r"\.{6,}.*$", "", text).strip()
    t = re.sub(r"\s+\d+\s*$", "", t).strip()
    t = re.sub(r"\d+$", "", t).strip()
    return t


def is_noise_line(text):
    if not text:
        return True
    noise_prefixes = (
        "爬取题库", "本栏目", "用前说明", "严禁用于商业用途", "Made by", "搜题码", "刷题码",
        "题库", "目录", "[WARNING:"
    )
    return text.startswith(noise_prefixes)


def clean_line(text):
    t = re.sub(r"—\s*\d+\s*—", "", text).strip()
    if PAGE_MARK_RE.match(t):
        return ""
    return t


def extract_answer_list():
    if not RED_PATH.exists():
        return []
    lines = RED_PATH.read_text(encoding="utf-8").splitlines()
    answers = []
    for raw in lines:
        line = re.sub(r"^\[p\d+\]\s*", "", raw).strip()
        if not line:
            continue
        judge = re.search(r"([√×])\s*$", line)
        if judge:
            answers.append(judge.group(1))
            continue
        letters = re.findall(r"[A-G]", line)
        if letters:
            answers.append("".join(letters))
    return answers


def extract_options_from_line(line):
    matches = list(OPTION_INLINE_RE.finditer(line))
    if not matches:
        return []
    options = []
    for idx, m in enumerate(matches):
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(line)
        key = m.group(1) or m.group(2)
        val = line[start:end].strip()
        if key and val:
            options.append((key, val))
    return options


def split_question_and_options(text):
    matches = list(OPTION_INLINE_RE.finditer(text))
    if not matches:
        return text.strip(), {}
    qtext = text[:matches[0].start()].strip()
    opts = {}
    for key, val in extract_options_from_line(text):
        opts[key] = val
    return qtext, opts


def strip_answer_label(text):
    t = ANSWER_LINE_RE.sub("", text, count=1).strip()
    t = re.sub(r"^[:：]\s*", "", t)
    return t


def normalize_blank(text):
    t = re.sub(r"_{2,}", "____", text)
    if "____" not in t:
        t = t.rstrip("。；; ") + " ____"
    return t


def parse():
    if not RAW_PATH.exists():
        raise FileNotFoundError(RAW_PATH)

    ans_list = extract_answer_list()
    ans_index = 0
    lines = RAW_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()

    # Build chapter list from TOC section before the first page marker
    toc_units = []
    for line in lines:
        s = clean_line(line.strip())
        if not s:
            continue
        if PAGE_MARK_RE.match(s):
            break
        if CHAPTER_RE.match(s):
            toc_units.append(clean_toc_unit(s))

    data = {}
    unit_index_map = {}
    unit_counter_map = {}
    next_unit_idx = 0

    current_unit = None
    current_unit_idx = None
    current_type = None

    current_q = None
    last_option_key = None
    current_answer_lines = []
    in_answer_block = False

    missing_answers = []
    total_questions = 0
    total_with_answer = 0
    total_expected_answers = len(ans_list)
    chapter_index = -1
    chapter_question_count = 0

    def finalize_question():
        nonlocal current_q, last_option_key, total_questions, total_with_answer, ans_index, chapter_question_count
        nonlocal current_answer_lines, in_answer_block
        if not current_q:
            return

        qtext = current_q["question"].strip()
        answer_text = " ".join([x for x in current_answer_lines if x]).strip()
        judge_inline = None
        jm = JUDGE_ANS_RE.search(qtext)
        if jm:
            judge_inline = jm.group(1)
            qtext = JUDGE_ANS_RE.sub("", qtext).strip()

        qtype_label = ALLOWED_TYPES.get(current_type)
        if not qtype_label:
            if current_q.get("options"):
                qtype_label = "单选题"
            elif judge_inline:
                qtype_label = "判断题"
            elif "____" in qtext or "填空" in qtext:
                qtype_label = "填空题"
            elif answer_text:
                qtype_label = "简答题" if "论述" not in qtext else "论述题"
            else:
                qtype_label = "简答题"
        elif qtype_label in ("单选题", "多选题") and not current_q.get("options"):
            if "____" in qtext or "填空" in qtext:
                qtype_label = "填空题"
            elif answer_text:
                qtype_label = "简答题" if "论述" not in qtext else "论述题"

        unit_title = current_unit or "未知单元"

        # finalize answers
        if qtype_label in ("单选题", "多选题", "判断题"):
            ans_token = None
            if ans_index < len(ans_list):
                ans_token = ans_list[ans_index]
                ans_index += 1
            if qtype_label == "判断题" and judge_inline:
                ans_token = judge_inline
            if ans_token:
                if len(ans_token) > 1 and all(ch in "ABCDEFG" for ch in ans_token):
                    current_q["answer"] = list(ans_token)
                    if qtype_label == "单选题":
                        qtype_label = "多选题"
                else:
                    current_q["answer"] = ans_token
                total_with_answer += 1
            else:
                current_q["answer"] = ""
                missing_answers.append(current_q["uid"])
        else:
            if qtype_label == "填空题":
                qtext = normalize_blank(qtext)
            current_q["answer"] = answer_text
            if answer_text:
                total_with_answer += 1

        current_q["question"] = qtext

        if qtype_label == "判断题" and not current_q.get("options"):
            current_q["options"] = {"√": "正确", "×": "错误"}

        data.setdefault(unit_title, {}).setdefault(qtype_label, [])
        data[unit_title][qtype_label].append(current_q)
        total_questions += 1
        chapter_question_count += 1
        current_q = None
        last_option_key = None
        current_answer_lines = []
        in_answer_block = False

    for line in lines:
        s = clean_line(line.strip())
        if not s:
            continue
        if is_noise_line(s):
            continue

        mt = QTYPE_RE.match(s)
        if mt:
            finalize_question()
            current_type = mt.group(1)
            if current_type == "单项选择题":
                if chapter_question_count > 0:
                    chapter_index += 1
                    chapter_question_count = 0
                elif chapter_index < 0:
                    chapter_index = 0
                if chapter_index < len(toc_units):
                    current_unit = toc_units[chapter_index]
                else:
                    current_unit = f"章节{chapter_index + 1}"
                if current_unit not in unit_index_map:
                    unit_index_map[current_unit] = next_unit_idx
                    current_unit_idx = next_unit_idx
                    unit_counter_map[current_unit_idx] = 0
                    next_unit_idx += 1
                else:
                    current_unit_idx = unit_index_map[current_unit]
            continue

        mq = QUESTION_RE.match(s)
        if mq:
            finalize_question()
            if current_unit_idx is None:
                current_unit = current_unit or "未知单元"
                if current_unit not in unit_index_map:
                    unit_index_map[current_unit] = next_unit_idx
                    current_unit_idx = next_unit_idx
                    unit_counter_map[current_unit_idx] = 0
                    next_unit_idx += 1
                else:
                    current_unit_idx = unit_index_map[current_unit]

            seq = unit_counter_map.get(current_unit_idx, 0) + 1
            unit_counter_map[current_unit_idx] = seq
            uid = f"{current_unit_idx}-{seq}"

            qtext, inline_opts = split_question_and_options(mq.group(2).strip())
            current_q = {
                "uid": uid,
                "question": qtext,
                "options": inline_opts,
                "answer": ""
            }
            last_option_key = None
            current_answer_lines = []
            in_answer_block = False
            continue

        if current_q:
            if ANSWER_LINE_RE.match(s):
                in_answer_block = True
                ans = strip_answer_label(s)
                if ans:
                    current_answer_lines.append(ans)
                continue
            if in_answer_block:
                current_answer_lines.append(s)
                continue
            opts = extract_options_from_line(s)
            if opts:
                for key, val in opts:
                    current_q["options"][key] = val
                    last_option_key = key
                continue
            if last_option_key:
                # append to last option if line continues
                current_q["options"][last_option_key] = (current_q["options"][last_option_key] + " " + s).strip()
                continue
            # treat as question continuation
            current_q["question"] = (current_q["question"] + " " + s).strip()

    finalize_question()

    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    report = [
        f"total_questions: {total_questions}",
        f"answered: {total_with_answer}",
        f"missing_answers: {len(missing_answers)}",
        f"red_answers_total: {total_expected_answers}",
        f"red_answers_consumed: {ans_index}",
    ]
    if missing_answers:
        report.append("missing_uids:")
        report.extend(missing_answers)
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")
    print("parsed", total_questions, "questions ->", OUT_PATH.resolve())
    print("report ->", REPORT_PATH.resolve())


if __name__ == "__main__":
    parse()
