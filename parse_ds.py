import re, json
from pathlib import Path

INPUT = Path(r"dataset.txt")
OUT = Path(r"dataset.json")

Q_RE = re.compile(r'^\s*(\d+)[\.\、]?\s*(.*)')  # 题号开头
OPT_RE = re.compile(r'^\s*([A-Z])[\.\、\)\s]+\s*(.*)')  # 选项行开头 A. ...
CHOICE_ANS_RE = re.compile(r'^(?:正确答案|答案)[:：]\s*([A-Z,，\s]+)', re.I)
JUDGE_ANS_RE = re.compile(r'^(?:正确答案|答案)[:：]\s*([√对]|[×xX错]|正确|错误)', re.I)
SECTION_HDR_RE = re.compile(r'^(?:一、|二、|三、|单项选择|单选|多选题|判断题|三、判断题|二、单选题|三、单选题)', re.I)


def normalize_judge(tok):
    if not tok: return None
    tok = tok.strip()
    if tok in ('√', '对', '正确'): return '√'
    if tok in ('×', 'x', 'X', '错', '错误'): return '×'
    return tok


def chunk_list(lst, size=50):
    groups = []
    for i in range(0, len(lst), size):
        groups.append({
            "group_index": i // size + 1,
            "questions": lst[i:i + size]
        })
    return groups


def parse():
    if not INPUT.exists():
        print("输入文件不存在:", INPUT)
        return

    lines = INPUT.read_text(encoding='utf-8', errors='ignore').splitlines()
    n = len(lines)
    i = 0

    choice_list = []
    judge_list = []
    current_section = None  # 'choice' or 'judge' or None

    while i < n:
        line = lines[i].rstrip('\n')
        s = line.strip()

        # detect explicit section headings
        if re.search(r'单项选择|单选题|选择题', s):
            current_section = 'choice'
            i += 1
            continue
        if re.search(r'判断题', s):
            current_section = 'judge'
            i += 1
            continue
        # try to detect question start
        m = Q_RE.match(line)
        if not m:
            i += 1
            continue

        # found question start
        qnum = m.group(1)
        qtext = m.group(2).strip()
        j = i + 1

        # accumulate following non-option, non-answer, non-question lines into question text
        while j < n:
            nxt = lines[j].rstrip('\n')
            nxts = nxt.strip()
            # stop if next is option, next question, answer line, or a section header
            if OPT_RE.match(nxt) or Q_RE.match(nxt) or CHOICE_ANS_RE.match(nxts) or JUDGE_ANS_RE.match(
                    nxts) or SECTION_HDR_RE.match(nxts) or nxts.startswith('正确答案') or nxts.startswith('答案'):
                break
            # otherwise it's continuation of question text -> append
            if nxts:
                qtext += '' + nxts
            j += 1

        # now check if options follow
        options = {}
        answer_choice = None
        answer_judge = None

        # if next lines are options, collect them (including multiline option bodies)
        k = j
        saw_option = False
        while k < n:
            nxt = lines[k].rstrip('\n')
            nxts = nxt.strip()
            # stop if new question or section header or answer line encountered before options
            if Q_RE.match(nxt) or SECTION_HDR_RE.match(nxts):
                break
            om = OPT_RE.match(nxt)
            if om:
                saw_option = True
                key = om.group(1).strip()
                val = om.group(2).strip()
                # collect continuation lines for this option
                t = k + 1
                more = []
                while t < n:
                    peek = lines[t].rstrip('\n')
                    peeks = peek.strip()
                    # stop if next option, next question, answer line, or section header
                    if OPT_RE.match(peek) or Q_RE.match(peek) or CHOICE_ANS_RE.match(peeks) or JUDGE_ANS_RE.match(
                            peeks) or SECTION_HDR_RE.match(peeks) or peeks.startswith('正确答案') or peeks.startswith(
                            '答案'):
                        break
                    if peeks:
                        more.append(peeks)
                    t += 1
                if more:
                    val = val + ' ' + ' '.join(more)
                options[key] = val
                k = t
                continue
            # answer line after options?
            ca = CHOICE_ANS_RE.match(nxts)
            if ca:
                answer_choice = ca.group(1).strip()
                k += 1
                break
            ja = JUDGE_ANS_RE.match(nxts)
            if ja:
                answer_judge = ja.group(1).strip()
                k += 1
                break
            # if line explicitly "正确答案：" or "答案：" with other format
            if nxts.startswith('正确答案') or nxts.startswith('答案'):
                # try to extract after delimiter
                parts = nxts.split('：', 1) if '：' in nxts else nxts.split(':', 1)
                if len(parts) == 2:
                    val = parts[1].strip()
                    if re.match(r'^[A-Z,，\s]+$', val, re.I):
                        answer_choice = val
                    else:
                        answer_judge = val
                k += 1
                break
            # otherwise skip
            k += 1

        # if options were found -> it's choice question; else treat as judge if current_section indicates or answer_judge present
        if saw_option or current_section == 'choice':
            # normalize choice answer
            ans = None
            if answer_choice:
                letters = re.findall(r'[A-Z]', answer_choice.upper())
                ans = letters[0] if letters else answer_choice.strip()
            # But sometimes in dataset the answer is embedded in qtext like "（ B ）" — try to extract
            if not ans:
                m_inline = re.search(r'[（(]\s*([A-D])\s*[）)]', qtext)
                if m_inline:
                    ans = m_inline.group(1)
                    qtext = re.sub(r'[（(]\s*[A-D]\s*[）)]', '', qtext).strip()
            choice_list.append({
                "question": qtext,
                "options": options,
                "answer": ans
            })
            i = k
            continue
        else:
            # judge question: try to get answer_judge from nearby lines or inline
            if not answer_judge:
                # check immediate following lines for "答案：" pattern
                t = j
                while t < n and t < j + 4:
                    nxt = lines[t].strip()
                    ja = JUDGE_ANS_RE.match(nxt)
                    if ja:
                        answer_judge = ja.group(1).strip()
                        break
                    # also check inline in line
                    m_inline = re.search(r'答案[:：]\s*([√对×xX错正确错误])', nxt)
                    if m_inline:
                        answer_judge = m_inline.group(1)
                        break
                    t += 1
            if not answer_judge:
                # try inline in qtext
                m2 = re.search(r'答案[:：]?\s*([√对×xX错正确错误])', qtext)
                if m2:
                    answer_judge = m2.group(1)
                    qtext = re.sub(r'答案[:：]?\s*[√对×xX错正确错误]', '', qtext).strip()
            answer_judge = normalize_judge(answer_judge)
            judge_list.append({
                "question": qtext,
                "answer": answer_judge
            })
            i = k
            continue

    # assign uids
    for idx, q in enumerate(choice_list, start=1):
        q['uid'] = f"1-{idx}"
    for idx, q in enumerate(judge_list, start=1):
        q['uid'] = f"2-{idx}"

    # chunk into groups of 50 and build final structure
    choice_groups = chunk_list(choice_list, 50)
    judge_groups = chunk_list(judge_list, 50)

    out = {
        "单选": choice_groups,
        "判断": judge_groups
    }

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"已生成 {OUT}，单选题 {len(choice_list)} 道，判断题 {len(judge_list)} 道。")


if __name__ == "__main__":
    parse()
