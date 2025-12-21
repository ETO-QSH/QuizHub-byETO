from flask import Flask, render_template, request, redirect, session, jsonify
from pathlib import Path
import json, random, os, re
from werkzeug.security import check_password_hash, generate_password_hash

APP = Flask(__name__, static_folder="static", template_folder="templates")
APP.secret_key = "change-me-to-a-secure-random-key"

BASE = Path(__file__).parent
DB_FILE = BASE / "database.json"
USERS_FILE = BASE / "users.json"
USER_DATA_DIR = BASE / "user_data"
USER_DATA_DIR.mkdir(exist_ok=True)

USERNAME_RE = re.compile(r'^[A-Za-z0-9]+$')  # 只允许字母数字

# load DB (flat map of uid->question and units list)
if not DB_FILE.exists():
    raise RuntimeError("请先用 parse_db.py 生成 database.json")
with DB_FILE.open(encoding='utf-8') as f:
    db = json.load(f)

QUESTIONS = {}  # uid -> question dict
UNIT_LIST = {}  # unit_name -> [uid,...]
for unit, types in db.items():
    for tname, qlist in types.items():
        for q in qlist:
            # 只使用 uid 字段（parse_db.py 现在保证存在）
            uid = q.get('uid')
            if not uid:
                # 如果旧数据没有 uid，可以跳过或生成，但推荐先用 parse_db.py 重新生成 database.json
                continue
            q['unit'] = unit
            q['type'] = tname
            QUESTIONS[uid] = q
            UNIT_LIST.setdefault(unit, []).append(uid)

# users.json 格式：
# {
#   "users": { "alice": {"password": "<hash>", "uid": 1}, ... },
#   "order": ["alice", "bob"]
# }
if not USERS_FILE.exists():
    USERS_FILE.write_text(json.dumps({"users": {}, "order": []}, ensure_ascii=False, indent=2), encoding='utf-8')
with USERS_FILE.open(encoding='utf-8') as f:
    USERS_DATA = json.load(f)


def reload_users():
    global USERS_DATA
    with USERS_FILE.open(encoding='utf-8') as f:
        USERS_DATA = json.load(f)


def save_users():
    with USERS_FILE.open('w', encoding='utf-8') as f:
        json.dump(USERS_DATA, f, ensure_ascii=False, indent=2)


def migrate_old_user_data(old):
    # old -> new with global lists
    new = {"by_unit": {}, "last_choice": {}, "flags": {"reveal_mode": False}, "global": {"wrong": [], "star": []}}
    wrongs = old.get("wrong", []) if isinstance(old, dict) else []
    stars = old.get("star", []) if isinstance(old, dict) else []
    # distribute to global and unit-level if possible
    for uid in wrongs:
        if isinstance(uid, str) and '-' in uid:
            unit_idx = uid.split('-', 1)[0]
            unit = new["by_unit"].setdefault(unit_idx, {"studied": [], "wrong": [], "star": [],
                                                        "last_pos": {"studied": 0, "wrong": 0, "star": 0}})
            if uid not in unit["wrong"]:
                unit["wrong"].append(uid)
            if uid not in new["global"]["wrong"]:
                new["global"]["wrong"].append(uid)
    for uid in stars:
        if isinstance(uid, str) and '-' in uid:
            unit_idx = uid.split('-', 1)[0]
            unit = new["by_unit"].setdefault(unit_idx, {"studied": [], "wrong": [], "star": [],
                                                        "last_pos": {"studied": 0, "wrong": 0, "star": 0}})
            if uid not in unit["star"]:
                unit["star"].append(uid)
            if uid not in new["global"]["star"]:
                new["global"]["star"].append(uid)
    # migrate progress -> put into studied lists and global last_choice if any
    prog = old.get("progress", {}) if isinstance(old, dict) else {}
    if prog:
        for mode, v in prog.items():
            lst = v.get("list", []) if isinstance(v, dict) else []
            for uid in lst:
                if isinstance(uid, str) and '-' in uid:
                    unit_idx = uid.split('-', 1)[0]
                    unit = new["by_unit"].setdefault(unit_idx, {"studied": [], "wrong": [], "star": [],
                                                                "last_pos": {"studied": 0, "wrong": 0, "star": 0}})
                    if uid not in unit["studied"]:
                        unit["studied"].append(uid)
            break
    return new


def load_user_data(username):
    p = USER_DATA_DIR / f"{username}.json"
    if p.exists():
        data = json.load(p.open(encoding='utf-8'))
        if not ("by_unit" in data and "last_choice" in data and "flags" in data and "global" in data):
            data = migrate_old_user_data(data)
            save_user_data(username, data)
        return data
    data = {"by_unit": {}, "last_choice": {}, "flags": {"reveal_mode": False}, "global": {"wrong": [], "star": []},
            "progress": {}}
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return data


def save_user_data(username, data):
    p = USER_DATA_DIR / f"{username}.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


# 加载解析数据
EXPLANATIONS = {}
EXPLANATION_FILE = BASE / "explanations.json"
if EXPLANATION_FILE.exists():
    with EXPLANATION_FILE.open(encoding='utf-8') as f:
        EXPLANATIONS = json.load(f)


@APP.context_processor
def inject_user():
    return dict(session=session)


@APP.route("/")
def index():
    if 'user' in session:
        return redirect("/dashboard")
    return redirect("/login")


@APP.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        pw = request.form.get("password", "")
        if not u or not pw:
            return render_template("login.html", error="用户名或密码不能为空")
        if not USERNAME_RE.match(u) or not USERNAME_RE.match(pw):
            return render_template("login.html", error="用户名和密码只允许字母和数字")
        reload_users()
        user = USERS_DATA.get("users", {}).get(u)
        if user:
            # 已有用户，校验密码
            if check_password_hash(user["password"], pw):
                session['user'] = u
                return redirect("/dashboard")
            else:
                return render_template("login.html", error="用户名已存在但密码错误")
        else:
            # 用户不存在 -> 自动注册并登录
            next_uid = len(USERS_DATA.get("order", [])) + 1
            USERS_DATA.setdefault("users", {})[u] = {"password": generate_password_hash(pw), "uid": next_uid}
            USERS_DATA.setdefault("order", []).append(u)
            save_users()
            session['user'] = u
            return redirect("/dashboard")
    return render_template("login.html")


@APP.route("/register", methods=["POST"])
def register():
    u = request.form.get("username", "").strip()
    pw = request.form.get("password", "")
    if not u or not pw:
        return jsonify({"error": "用户名或密码不能为空"}), 400
    if not USERNAME_RE.match(u) or not USERNAME_RE.match(pw):
        return jsonify({"error": "用户名和密码只允许字母和数字"}), 400
    reload_users()
    if u in USERS_DATA.get("users", {}):
        return jsonify({"error": "用户名已存在"}), 400
    # 分配顺序 uid（注册顺序，从1开始）
    next_uid = len(USERS_DATA.get("order", [])) + 1
    USERS_DATA.setdefault("users", {})[u] = {"password": generate_password_hash(pw), "uid": next_uid}
    USERS_DATA.setdefault("order", []).append(u)
    save_users()
    session['user'] = u
    return jsonify({"ok": True, "uid": next_uid})


@APP.route("/logout")
def logout():
    session.pop('user', None)
    return redirect("/login")


@APP.route("/dashboard")
def dashboard():
    if 'user' not in session:
        return redirect("/login")
    # 向前端传 units 和用户信息
    user_info = USERS_DATA.get("users", {}).get(session['user'])
    return render_template("dashboard.html", units=list(UNIT_LIST.keys()), user_info=user_info)


@APP.route("/quiz")
def quiz_page():
    if 'user' not in session:
        return redirect("/login")
    return render_template("quiz.html")


@APP.route("/api/start", methods=["POST"])
def api_start():
    if 'user' not in session:
        return jsonify({"error": "not logged"}), 401
    j = request.json or {}
    mode = j.get("mode", "random")
    reveal = bool(j.get("reveal", False))
    tag = j.get("tag")
    username = session['user']

    ud = load_user_data(username)

    if mode == "sequential":
        unit = j.get("unit")
        progress_key = "sequential" if unit is None else f"sequential:{unit}"
        # 如果已有该单元的进度，恢复之（包括 list 和 pos），否则新建并从头开始
        existing = ud.get("progress", {}).get(progress_key)
        if existing:
            ulist = existing.get("list", [])
            pos = existing.get("pos", 0)
            # 接受前端传入的 reveal（优先），若未传入则使用已有值
            reveal_param = j.get("reveal")
            if reveal_param is None:
                reveal = existing.get("reveal", reveal)
            else:
                reveal = bool(reveal_param)
                # 更新已有进度的 reveal 标志
                ud.setdefault("progress", {}).setdefault(progress_key, {})['reveal'] = reveal
        else:
            ulist = UNIT_LIST.get(unit, [])
            pos = 0
            ud.setdefault("progress", {})[progress_key] = {"list": ulist, "pos": pos, "reveal": reveal}
        # 记录当前进度键
        ud["current_progress_key"] = progress_key
        save_user_data(username, ud)
        return jsonify({"list": ulist, "pos": pos, "reveal": reveal, "key": progress_key, "mode": mode, "unit": unit})

    elif mode == "tag":
        if not tag:
            return jsonify({"error": "tag required for tag mode"}), 400
        # 使用全局列表（global）中的题目，确保只包含 global.wrong 或 global.star
        if tag == "wrong":
            ulist = ud.get("global", {}).get("wrong", [])[:]
        elif tag == "star":
            ulist = ud.get("global", {}).get("star", [])[:]
        else:
            ulist = []
        progress_key = f"tag:{tag}"
        ud.setdefault("progress", {})[progress_key] = {"list": ulist, "pos": 0, "reveal": reveal}
        ud["current_progress_key"] = progress_key
        save_user_data(username, ud)
        return jsonify({"list": ulist, "pos": 0, "reveal": reveal, "key": progress_key, "mode": mode, "tag": tag})

    else:
        # random mode: 默认每次取 50 题，并覆盖 progress，保证每次进入都重新抽题
        count = int(j.get("count", 50))
        all_uids = list(QUESTIONS.keys())
        ulist = random.sample(all_uids, min(count, len(all_uids)))
        progress_key = f"random:{count}"
        ud.setdefault("progress", {})[progress_key] = {"list": ulist, "pos": 0, "reveal": reveal}
        ud["current_progress_key"] = progress_key
        save_user_data(username, ud)
        return jsonify({"list": ulist, "pos": 0, "reveal": reveal, "key": progress_key, "mode": mode, "count": count})


@APP.route("/api/question", methods=["GET"])
def api_question():
    if 'user' not in session:
        return jsonify({"error": "not logged"}), 401
    uid = request.args.get("uid")
    reveal = request.args.get("reveal") == "1"
    q = QUESTIONS.get(uid)
    if not q:
        return jsonify({"error": "no such question"}), 404
    out = {"uid": uid, "question": q.get("question"), "options": q.get("options", {}), "type": q.get("type")}
    if reveal:
        out["answer"] = q.get("answer")
    # 附加解析（若存在）
    if uid in EXPLANATIONS:
        out["explanation"] = EXPLANATIONS[uid]
    return jsonify(out)


@APP.route("/api/answer", methods=["POST"])
def api_answer():
    if 'user' not in session:
        return jsonify({"error": "not logged"}), 401
    j = request.json or {}
    uid = j.get("uid")
    selected = j.get("selected")
    username = session['user']
    q = QUESTIONS.get(uid)
    correct = q.get("answer")
    is_correct = False
    if isinstance(correct, list):
        is_correct = set(selected or []) == set(correct)
    else:
        is_correct = (selected == correct)
    ud = load_user_data(username)
    # update unit-level studied and wrong
    unit_idx = str(uid).split('-', 1)[0] if isinstance(uid, str) and '-' in uid else "0"
    unit = ud.setdefault("by_unit", {}).setdefault(unit_idx, {"studied": [], "wrong": [], "star": [],
                                                              "last_pos": {"studied": 0, "wrong": 0, "star": 0}})
    if not is_correct:
        if uid not in unit["wrong"]:
            unit["wrong"].append(uid)
    else:
        if uid in unit["wrong"]:
            unit["wrong"].remove(uid)
    if uid not in unit["studied"]:
        unit["studied"].append(uid)
    # update global wrong list
    gl = ud.setdefault("global", {"wrong": [], "star": []})
    if not is_correct:
        if uid not in gl["wrong"]:
            gl["wrong"].append(uid)
    else:
        if uid in gl["wrong"]:
            gl["wrong"].remove(uid)
    # record last choice
    ud.setdefault("last_choice", {})[uid] = {"correct": is_correct, "selected": selected}
    save_user_data(username, ud)
    return jsonify({"correct": is_correct, "answer": correct})


@APP.route("/api/star", methods=["POST"])
def api_star():
    if 'user' not in session:
        return jsonify({"error": "not logged"}), 401
    j = request.json or {}
    uid = j.get("uid")
    action = j.get("action", "toggle")
    username = session['user']
    ud = load_user_data(username)
    unit_idx = str(uid).split('-', 1)[0] if isinstance(uid, str) and '-' in uid else "0"
    unit = ud.setdefault("by_unit", {}).setdefault(unit_idx, {"studied": [], "wrong": [], "star": [],
                                                              "last_pos": {"studied": 0, "wrong": 0, "star": 0}})
    gl = ud.setdefault("global", {"wrong": [], "star": []})
    if action == "toggle":
        if uid in gl["star"]:
            gl["star"].remove(uid)
            # also remove unit-level star if present
            if uid in unit["star"]:
                unit["star"].remove(uid)
            state = False
        else:
            gl["star"].append(uid)
            if uid not in unit["star"]:
                unit["star"].append(uid)
            state = True
    else:
        state = uid in gl["star"]
    save_user_data(username, ud)
    return jsonify({"starred": state})


@APP.route("/api/clear_unit", methods=["POST"])
def api_clear_unit():
    if 'user' not in session:
        return jsonify({"error": "not logged"}), 401
    j = request.json or {}
    unit_name = j.get("unit")
    if not unit_name:
        return jsonify({"error": "no unit"}), 400
    # find uid list for this unit
    ulist = UNIT_LIST.get(unit_name, [])
    if not ulist:
        return jsonify({"error": "unit not found"}), 404
    # derive unit_idx from first uid
    first = ulist[0]
    unit_idx = first.split('-', 1)[0] if '-' in first else None
    username = session['user']
    ud = load_user_data(username)
    if unit_idx and unit_idx in ud.get("by_unit", {}):
        # 清除单元内记录：studied、wrong、star 与 last_pos（但不改全局 global）
        ud["by_unit"][unit_idx]["studied"] = []
        ud["by_unit"][unit_idx]["wrong"] = []
        ud["by_unit"][unit_idx]["star"] = []
        ud["by_unit"][unit_idx]["last_pos"] = {"studied": 0, "wrong": 0, "star": 0}
        # 同时删除该单元下的 last_choice 条目（仅单元级历史选择）
        lc = ud.get("last_choice", {})
        to_del = [k for k in lc.keys() if isinstance(k, str) and k.startswith(f"{unit_idx}-")]
        for k in to_del:
            lc.pop(k, None)
        ud["last_choice"] = lc
        save_user_data(username, ud)
        return jsonify({"ok": True})
    return jsonify({"error": "no data for unit"}), 404


@APP.route("/api/flags", methods=["GET", "POST"])
def api_flags():
    if 'user' not in session:
        return jsonify({"error": "not logged"}), 401
    username = session['user']
    ud = load_user_data(username)
    if request.method == "GET":
        return jsonify(ud.get("flags", {}))
    j = request.json or {}
    # allow set {"reveal_mode": true/false, "show_explanations": true/false}
    for k, v in j.items():
        ud.setdefault("flags", {})[k] = bool(v)
    save_user_data(username, ud)
    return jsonify(ud.get("flags", {}))


@APP.route("/api/progress/save", methods=["POST"])
def api_progress_save():
    if 'user' not in session:
        return jsonify({"error": "not logged"}), 401
    j = request.json or {}
    # 优先使用 key（新的方式），兼容旧的 mode 字段
    key = j.get("key") or j.get("mode")
    pos = j.get("pos", 0)
    username = session['user']
    if not key:
        return jsonify({"error": "no progress key provided"}), 400
    ud = load_user_data(username)
    ud.setdefault("progress", {}).setdefault(key, {})['pos'] = pos
    # 同步 current_progress_key（可选，确保一致）
    ud["current_progress_key"] = key
    save_user_data(username, ud)
    return jsonify({"ok": True})


@APP.route("/api/user/data", methods=["GET"])
def api_user_data():
    if 'user' not in session:
        return jsonify({"error": "not logged"}), 401
    ud = load_user_data(session['user'])
    return jsonify(ud)


if __name__ == "__main__":
    APP.run(host="0.0.0.0", debug=True, port=5000)
