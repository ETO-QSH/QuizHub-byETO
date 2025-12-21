import re
import json
from pathlib import Path

SRC = Path(r"database.txt")
OUT = SRC.with_suffix(".json")


def normalize_answer_token(tok):
    # 把全角括号内的答案标准化为纯字母或符号字符串
    return re.sub(r'\s+', '', tok).replace('（', '').replace('）', '').replace('(', '').replace(')', '')


def parse():
    text = SRC.read_text(encoding='utf-8')
    lines = [ln.rstrip() for ln in text.splitlines()]

    data = {}
    current_unit = None
    current_unit_key = None
    current_qtype = None
    last_title_candidate = None

    # 单元编号映射：unit title -> index (从0开始)
    unit_index_map = {}
    next_unit_index = 0
    # 单元内部题目计数（用于生成跨题型累加序号），key 使用 unit_idx (int)
    unit_counter_map = {}

    qlist = []  # current unit+qtype question list
    current_q = None
    current_q_ref = None  # 指向当前题对象，供后续 option/answer 填充
    current_unit_idx = None

    qtype_map = {
        '单选题': '单选题',
        '多选题': '多选题',
        '判断题': '判断题'
    }

    # patterns
    chapter_re = re.compile(r'^(第.+章\b.*|导论\b.*|^第.+章.*|^导论\b.*)')
    qtype_re = re.compile(r'^[一二三四五六七八九十]+、\s*(单选题|多选题|判断题)')
    question_re = re.compile(r'^\s*(\d+)[\.\、]\s*(.*)')  # 题号开头
    option_re = re.compile(r'^\s*([A-D])[\.\、\s　]?\s*(.+)')
    answer_in_text_re = re.compile(r'[（\(]\s*([A-D√×]{1,4}|[A-D]{2,4})\s*[）\)]')

    def make_unit_key(title):
        # 取章节的短名：如 "第一章 毛泽东思想..." -> "第一章"，"导论 ..." -> "导论"
        parts = title.strip().split()
        if parts:
            return parts[0]
        # 兜底：只取到第一个空格前的中文标识
        m = re.match(r'^(第[^章]*章|导论)', title)
        return m.group(1) if m else title.strip()

    for ln in lines:
        if not ln.strip():
            continue

        mch = chapter_re.match(ln)
        if mch:
            current_unit = ln.strip()
            current_unit_key = make_unit_key(current_unit)
            # 为该单元分配数字索引（按出现顺序）
            if current_unit not in unit_index_map:
                unit_index_map[current_unit] = next_unit_index
                current_unit_idx = next_unit_index
                next_unit_index += 1
                unit_counter_map[current_unit_idx] = 0
            else:
                current_unit_idx = unit_index_map[current_unit]
            data.setdefault(current_unit, {})
            last_title_candidate = current_unit
            current_qtype = None
            qlist = []
            current_q_ref = None
            continue

        mq = qtype_re.match(ln)
        if mq:
            qtype_label = mq.group(1)
            current_qtype = qtype_map.get(qtype_label, qtype_label)
            if current_unit is None:
                current_unit = last_title_candidate or "未知单元"
                data.setdefault(current_unit, {})
                # ensure unit idx exists
                if current_unit not in unit_index_map:
                    unit_index_map[current_unit] = next_unit_index
                    current_unit_idx = next_unit_index
                    next_unit_index += 1
                    unit_counter_map[current_unit_idx] = 0
                else:
                    current_unit_idx = unit_index_map[current_unit]
            data[current_unit].setdefault(current_qtype, [])
            qlist = data[current_unit][current_qtype]
            current_q_ref = None
            continue

        # 题目行检测 —— 直接创建题对象并立即加入列表，生成 uid（unitIdx-seq）
        mqq = question_re.match(ln)
        if mqq:
            # 新题：立即生成 uid 并 append，后续 option/answer 填充到 current_q_ref
            qnum_in_text = int(mqq.group(1))
            qtext = mqq.group(2).strip()

            # 提取题干中可能的答案标记并替换为占位
            mans = answer_in_text_re.search(qtext)
            ans_token = ''
            if mans:
                ans_token = mans.group(1)
                qtext = answer_in_text_re.sub('（  ）', qtext).strip()

            # 确保有 current_unit_idx
            if current_unit_idx is None:
                # 如果没有章节索引，分配一个临时/新的单元
                utitle = current_unit or last_title_candidate or "未知单元"
                if utitle not in unit_index_map:
                    unit_index_map[utitle] = next_unit_index
                    current_unit_idx = next_unit_index
                    next_unit_index += 1
                    unit_counter_map[current_unit_idx] = 0
                else:
                    current_unit_idx = unit_index_map[utitle]

            # 单元内序号自增
            seq = unit_counter_map.get(current_unit_idx, 0) + 1
            unit_counter_map[current_unit_idx] = seq

            # 生成题对象并立即加入当前 qlist
            qobj = {
                'uid': f"{current_unit_idx}-{seq}",
                'question': qtext,
                'options': {},
                'answer': ans_token
            }
            # append 到当前单元当前题型列表（qlist 已在 qtype 分支设置）
            if qlist is None:
                # 保底：如果未设置题型，放到默认集合
                data.setdefault(current_unit or "未知单元", {}).setdefault("未分类", [])
                qlist = data[current_unit or "未知单元"]["未分类"]
            qlist.append(qobj)
            current_q_ref = qobj
            continue

        # 选项行：直接填充到 current_q_ref（最近创建的题）
        mo = option_re.match(ln)
        if mo and current_q_ref is not None:
            key = mo.group(1).strip()
            val = mo.group(2).strip()
            current_q_ref['options'][key] = val
            continue

        # 在其他行中可能包含答案标注，若当前题没有答案则填充
        mans = answer_in_text_re.search(ln)
        if mans and current_q_ref is not None and (not current_q_ref.get('answer')):
            current_q_ref['answer'] = mans.group(1)
            continue

        # 题目正文延续行，追加到当前题的 question 字段
        if current_q_ref is not None:
            current_q_ref['question'] = (current_q_ref['question'] + ' ' + ln.strip()).strip()

    # 判断题处理及答案规范化（与原逻辑相同）
    for unit, types in data.items():
        for tname, qs in types.items():
            for q in qs:
                if tname == '判断题':
                    if not q.get('options'):
                        q['options'] = {'√': '正确', '×': '错误'}
                    if isinstance(q.get('answer', ''), str):
                        q['answer'] = normalize_answer_token(q.get('answer', ''))
                else:
                    ans = q.get('answer', '')
                    if isinstance(ans, str):
                        a_clean = normalize_answer_token(ans)
                        if a_clean and all(ch in 'ABCD' for ch in a_clean) and len(a_clean) > 1:
                            q['answer'] = list(a_clean)
                        else:
                            q['answer'] = a_clean

    # 写出 JSON
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    total_units = len(data)
    total_q = sum(len(qs) for types in data.values() for qs in types.values())
    print(f"解析完成: 单元 {total_units}, 题目总数 {total_q}, 输出文件: {OUT}")


if __name__ == "__main__":
    parse()
