import json
import requests
from pathlib import Path
import time

# DeepSeek API 配置
DEEPSEEK_API_KEY = "sk-xxxxxx"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

BASE = Path(__file__).parent
DB_FILE = BASE / "database.json"
EXPLANATION_FILE = BASE / "explanations.json"


def call_deepseek(question, options, answer):
    """调用 DeepSeek API 生成解析"""
    # 构建提示词
    option_str = "\n".join([f"{k}. {v}" for k, v in options.items()])
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
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 150
            },
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            explanation = result['choices'][0]['message']['content'].strip()
            return explanation
        else:
            print(f"API 错误: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"调用 API 异常: {e}")
        return None


def generate_all_explanations():
    """遍历所有题目并生成解析"""
    if not DB_FILE.exists():
        print(f"找不到 {DB_FILE}")
        return

    with DB_FILE.open(encoding='utf-8') as f:
        db = json.load(f)

    explanations = {}
    total = 0
    success = 0

    for unit, types in db.items():
        for tname, qlist in types.items():
            for q in qlist:
                uid = q.get('uid')
                if not uid:
                    continue

                total += 1
                question = q.get('question', '')
                options = q.get('options', {})
                answer = q.get('answer', '')

                print(f"[{total}] 正在生成 {uid} 的解析...")

                explanation = call_deepseek(question, options, answer)
                if explanation:
                    explanations[uid] = explanation
                    success += 1
                    print(f"  ✓ 成功")
                    print(explanation)
                else:
                    print(f"  ✗ 失败，跳过")

                # 避免 API 速率限制，间隔请求
                time.sleep(1)

    # 保存解析到文件
    with EXPLANATION_FILE.open('w', encoding='utf-8') as f:
        json.dump(explanations, f, ensure_ascii=False, indent=2)

    print(f"\n完成！共 {total} 题，成功 {success} 题")
    print(f"解析已保存到 {EXPLANATION_FILE}")


if __name__ == "__main__":
    print("开始生成题目解析...")
    generate_all_explanations()
