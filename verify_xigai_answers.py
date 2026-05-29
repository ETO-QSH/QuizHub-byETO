import json
import os
import re
import time
from pathlib import Path

import requests

DATA_PATH = Path(r"xigai.json")
REPORT_PATH = Path(r"xigai_api_report.txt")

API_KEY = os.environ.get("SILICONFLOW_API_KEY")
API_URL = "https://api.siliconflow.cn/v1/chat/completions"
MODEL = "Qwen/Qwen2.5-32B-Instruct"

ALLOWED = set("ABCD√×")


def clean_answer(text):
    if not text:
        return ""
    t = text.strip().upper()
    t = t.replace("X", "×")
    t = "".join(ch for ch in t if ch in ALLOWED)
    if not t:
        return ""
    # remove duplicates while preserving order
    seen = set()
    out = []
    for ch in t:
        if ch not in seen:
            seen.add(ch)
            out.append(ch)
    return "".join(out)


def call_model(prompt):
    if not API_KEY:
        raise RuntimeError("SILICONFLOW_API_KEY is not set")
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You answer questions by selecting options. Reply only with letters like A or AC, or √/×."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 16,
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    resp = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    return text


def build_prompt(question, options, qtype):
    opt_lines = []
    for k in sorted(options.keys()):
        opt_lines.append(f"{k}. {options[k]}")
    opts = "\n".join(opt_lines)
    return f"题型: {qtype}\n题目: {question}\n选项:\n{opts}\n只返回答案字母或符号。"


def build_prompt_alt(question, options, qtype):
    opt_lines = []
    for k in sorted(options.keys()):
        opt_lines.append(f"{k}: {options[k]}")
    opts = "\n".join(opt_lines)
    return f"Please choose the correct option(s).\nType: {qtype}\nQuestion: {question}\nOptions:\n{opts}\nReturn only letters or √/×."


def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(DATA_PATH)

    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    total_missing = 0
    filled = 0
    conflicts = 0
    skipped = 0
    conflict_list = []

    for unit, types in data.items():
        for qtype, qs in types.items():
            for q in qs:
                if q.get("answer"):
                    continue
                total_missing += 1
                question = q.get("question", "")
                options = q.get("options", {})
                if not question or not options:
                    skipped += 1
                    continue

                prompt1 = build_prompt(question, options, qtype)
                prompt2 = build_prompt_alt(question, options, qtype)

                try:
                    raw1 = call_model(prompt1)
                    ans1 = clean_answer(raw1)
                    raw2 = call_model(prompt2)
                    ans2 = clean_answer(raw2)
                except Exception as exc:
                    skipped += 1
                    conflict_list.append(f"{q.get('uid')} ERROR {exc}")
                    continue

                if not ans1 or not ans2:
                    skipped += 1
                    conflict_list.append(f"{q.get('uid')} EMPTY {raw1} | {raw2}")
                    continue

                if ans1 == ans2:
                    q["answer"] = list(ans1) if len(ans1) > 1 else ans1
                    filled += 1
                else:
                    conflicts += 1
                    conflict_list.append(f"{q.get('uid')} CONFLICT {ans1} vs {ans2}")

                # mild throttling
                time.sleep(0.2)

    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    report = [
        f"missing_total: {total_missing}",
        f"filled: {filled}",
        f"conflicts: {conflicts}",
        f"skipped: {skipped}",
    ]
    if conflict_list:
        report.append("details:")
        report.extend(conflict_list)

    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")
    print("api fill complete ->", REPORT_PATH.resolve())


if __name__ == "__main__":
    main()
