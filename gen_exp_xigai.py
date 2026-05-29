import json
import os
import time
from pathlib import Path

import requests

BASE = Path(__file__).parent
SRC_FILE = BASE / "xigai.json"
OUT_FILE = BASE / "exp_xigai.json"

API_KEY = os.environ.get("SILICONFLOW_API_KEY")
API_URL = "https://api.siliconflow.cn/v1/chat/completions"
MODEL = "Qwen/Qwen2.5-32B-Instruct"


def call_siliconflow(question, options, answer):
    option_str = "\n".join([f"{k}. {v}" for k, v in (options or {}).items()])
    prompt = f"""
请为以下题目生成解析（60-120字，全面且简洁）：

题目：{question}

选项（如无可忽略）：
{option_str}

参考答案：{answer}

要求：
1. 概括关键点并解释理由
2. 不编造不存在的选项或材料
3. 避免空话和冗长表述
"""
    response = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5,
            "max_tokens": 180,
        },
        timeout=60,
    )
    if response.status_code != 200:
        raise RuntimeError(f"API错误: {response.status_code} - {response.text}")
    result = response.json()
    return result["choices"][0]["message"]["content"].strip()


def gen_explanations(rate_delay=0.25, save_every=20):
    if not API_KEY:
        raise RuntimeError("SILICONFLOW_API_KEY is not set")
    if not SRC_FILE.exists():
        raise FileNotFoundError(SRC_FILE)

    data = json.loads(SRC_FILE.read_text(encoding="utf-8"))
    explanations = {}
    if OUT_FILE.exists():
        try:
            explanations = json.loads(OUT_FILE.read_text(encoding="utf-8"))
        except Exception:
            explanations = {}
    if not isinstance(explanations, dict):
        explanations = {}

    total = success = skipped = 0

    def save_progress():
        OUT_FILE.write_text(json.dumps(explanations, ensure_ascii=False, indent=2), encoding="utf-8")

    for unit, types in data.items():
        if not isinstance(types, dict):
            continue
        for tname, qlist in types.items():
            if not isinstance(qlist, list):
                continue
            for q in qlist:
                uid = q.get("uid")
                if not uid:
                    continue
                if uid in explanations:
                    skipped += 1
                    continue
                total += 1
                question = q.get("question", "")
                options = q.get("options", {}) or {}
                answer = q.get("answer", "")
                if not answer:
                    continue
                try:
                    exp = call_siliconflow(question, options, answer)
                except Exception as exc:
                    print(f"{uid} 失败: {exc}")
                    time.sleep(rate_delay)
                    continue
                if exp:
                    explanations[uid] = exp
                    success += 1
                    print(f"{uid} ✓")
                    if success % save_every == 0:
                        save_progress()
                else:
                    print(f"{uid} ✗")
                time.sleep(rate_delay)

    save_progress()
    print(f"完成: {success}/{total} (跳过{skipped}) -> {OUT_FILE}")


if __name__ == "__main__":
    gen_explanations()
