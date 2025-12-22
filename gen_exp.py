import json
import requests
from pathlib import Path
import time

DEEPSEEK_API_KEY = "sk-bf509eaac0804066b424825b40647e70"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

BASE = Path(__file__).parent
DB_FILE = BASE / "database.json"
DS_FILE = BASE / "dataset.json"
EXP_FILE_DB = BASE / "exp_db.json"
EXP_FILE_DS = BASE / "exp_ds.json"


def call_deepseek(question, options, answer):
    option_str = "\n".join([f"{k}. {v}" for k, v in (options or {}).items()])
    prompt = f"""
请为以下题目生成一个简短精准的解析（不超过100字）：

题目：{question}

选项：
{option_str}

正确答案：{answer}

要求：
1. 简洁明了，直指要点
2. 说明为什么这是正确答案
3. 避免过长的文字
4. 不用特意重复答案是什么
"""
    try:
        response = requests.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 150
            },
            timeout=30
        )
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        else:
            print(f"API 错误: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"调用 API 异常: {e}")
        return None


def gen_exp_db(src_path: Path, out_path: Path, rate_delay: float = 1.0):
    """处理 database.json 的结构： { unit: { type_name: [q,...], ... }, ... }"""
    if not src_path.exists():
        print(f"找不到 {src_path}")
        return
    with src_path.open(encoding='utf-8') as f:
        db = json.load(f)

    explanations = {}
    total = success = 0

    for unit, types in db.items():
        if not isinstance(types, dict):
            continue
        for tname, qlist in types.items():
            if not isinstance(qlist, list):
                continue
            for q in qlist:
                uid = q.get('uid')
                if not uid:
                    continue
                total += 1
                question = q.get('question', '')
                options = q.get('options', {}) or {}
                answer = q.get('answer', '')
                exp = call_deepseek(question, options, answer)
                if exp:
                    explanations[uid] = exp
                    success += 1
                    print("  ✓ 成功")
                    print(exp)
                else:
                    print("  ✗ 失败")
                time.sleep(rate_delay)

    with out_path.open('w', encoding='utf-8') as f:
        json.dump(explanations, f, ensure_ascii=False, indent=2)
    print(f"完成 DB：共 {total} 题，成功 {success} 题，保存到 {out_path}")


def gen_exp_ds(src_path: Path, out_path: Path, rate_delay: float = 1.0):
    """处理 dataset.json 的结构： { '单选':[groups], '判断':[groups], ... } """
    if not src_path.exists():
        print(f"找不到 {src_path}")
        return
    with src_path.open(encoding='utf-8') as f:
        ds = json.load(f)

    explanations = {}
    total = success = 0

    for kind, groups in ds.items():
        if not isinstance(groups, list):
            continue
        for g in groups:
            qlist = g.get("questions", []) if isinstance(g, dict) else []
            for q in qlist:
                uid = q.get("uid")
                if not uid:
                    continue
                total += 1
                question = q.get("question", "")
                options = q.get("options", {}) or {}
                if (not options) and kind == "判断":
                    options = {"A": "正确", "B": "错误"}
                answer = q.get("answer", "")
                exp = call_deepseek(question, options, answer)
                if exp:
                    explanations[uid] = exp
                    success += 1
                    print("  ✓ 成功")
                    print(exp)
                else:
                    print("  ✗ 失败")
                time.sleep(rate_delay)

    with out_path.open('w', encoding='utf-8') as f:
        json.dump(explanations, f, ensure_ascii=False, indent=2)
    print(f"完成 DS：共 {total} 题，成功 {success} 题，保存到 {out_path}")


if __name__ == "__main__":
    gen_exp_ds(DS_FILE, EXP_FILE_DS)
