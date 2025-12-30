import os
import re
import json


KEY_PTRN = re.compile(r'^1-(\d+)$')


def new_key(old: str, delta: int, delete: int = None) -> str | None:
    """
    把 1-xxx 的 xxx 部分加 delta，如果命中 delete 则返回 None 表示舍弃
    """
    if old == delete:
        return None
    m = KEY_PTRN.match(old)
    if not m:
        return old  # 非 1-xxx 原样保留
    num = int(m.group(1))
    num += delta
    return f'1-{num}'


def migrate_last_choice(last_choice: dict, delete: int, then_shift_from: int, shift_delta: int):
    """
    对 last_choice 整 dict 执行「先删 delete，再把 >then_shift_from 的编号 +shift_delta」
    返回新的 dict（旧值原样绑定到新 key）
    """
    new_lc = {}
    for k, v in last_choice.items():
        m = KEY_PTRN.match(k)
        if not m:
            # 非 1-xxx 原样保留
            new_lc[k] = v
            continue
        num = int(m.group(1))
        if num == delete:
            continue
        if num > then_shift_from:
            num += shift_delta
        new_k = f'1-{num}'
        new_lc[new_k] = v
    return new_lc


def process_file(path):
    print(f'Processing {path} ...')
    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    if 'mayuan' not in data:
        print('  no "mayuan" key, skip')
        return

    mayuan = data['mayuan']

    # ---------------- 第一轮：删 1-120，>199 减 1 ----------------
    # 1. last_choice 键值一起迁
    if 'last_choice' in mayuan and isinstance(mayuan['last_choice'], dict):
        mayuan['last_choice'] = migrate_last_choice(mayuan['last_choice'], delete=120, then_shift_from=199, shift_delta=-1)

    # 2. by_unit 里的列表
    for part in mayuan.get('by_unit', {}).values():
        for lst_name in ('studied', 'wrong', 'star'):
            if lst_name in part and isinstance(part[lst_name], list):
                part[lst_name] = [
                    new_key(k, -1) if KEY_PTRN.match(k) and int(k.split('-')[1]) > 199 else k
                    for k in part[lst_name] if k != '1-120'
                ]
                # 去掉 None
                part[lst_name] = [k for k in part[lst_name] if k is not None]

    # 3. global 里的 wrong/star 列表
    for gk in ('wrong', 'star'):
        if gk in mayuan.get('global', {}):
            mayuan['global'][gk] = [
                new_key(k, -1) if KEY_PTRN.match(k) and int(k.split('-')[1]) > 199 else k
                for k in mayuan['global'][gk] if k != '1-120'
            ]
            mayuan['global'][gk] = [k for k in mayuan['global'][gk] if k is not None]

    # 4. progress 里各 part 的 list
    for part in mayuan.get('progress', {}).values():
        if 'list' in part and isinstance(part['list'], list):
            part['list'] = [
                new_key(k, -1) if KEY_PTRN.match(k) and int(k.split('-')[1]) > 199 else k
                for k in part['list'] if k != '1-120'
            ]
            part['list'] = [k for k in part['list'] if k is not None]

    # ---------------- 第二轮：删 1-232，>231 再减 1 ----------------
    # 1. last_choice 再次迁移
    if 'last_choice' in mayuan and isinstance(mayuan['last_choice'], dict):
        mayuan['last_choice'] = migrate_last_choice(mayuan['last_choice'], delete=232, then_shift_from=231, shift_delta=-1)

    # 2. by_unit 列表
    for part in mayuan.get('by_unit', {}).values():
        for lst_name in ('studied', 'wrong', 'star'):
            if lst_name in part and isinstance(part[lst_name], list):
                part[lst_name] = [
                    new_key(k, -1) if KEY_PTRN.match(k) and int(k.split('-')[1]) > 231 else k
                    for k in part[lst_name] if k != '1-232'
                ]
                part[lst_name] = [k for k in part[lst_name] if k is not None]

    # 3. global
    for gk in ('wrong', 'star'):
        if gk in mayuan.get('global', {}):
            mayuan['global'][gk] = [
                new_key(k, -1) if KEY_PTRN.match(k) and int(k.split('-')[1]) > 231 else k
                for k in mayuan['global'][gk] if k != '1-232'
            ]
            mayuan['global'][gk] = [k for k in mayuan['global'][gk] if k is not None]

    # 4. progress
    for part in mayuan.get('progress', {}).values():
        if 'list' in part and isinstance(part['list'], list):
            part['list'] = [
                new_key(k, -1) if KEY_PTRN.match(k) and int(k.split('-')[1]) > 231 else k
                for k in part['list'] if k != '1-232'
            ]
            part['list'] = [k for k in part['list'] if k is not None]

    # 写回原文件（如需另存，把 path 换成新名字即可）
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print('  done')


if __name__ == '__main__':
    user_data_dir = r"user_data"
    for name in os.listdir(user_data_dir):
        path = os.path.join(user_data_dir, name)
        if not os.path.isfile(path):
            continue
        process_file(path)
        