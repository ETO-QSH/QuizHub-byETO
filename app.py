from flask import Flask, render_template, request, redirect, session, jsonify, send_file, make_response
from werkzeug.security import check_password_hash, generate_password_hash
from export import save_questions_to_word
from urllib.parse import quote
from pathlib import Path
import webbrowser
import random
import socket
import json
import sys
import re

if getattr(sys, 'frozen', False):
    RES_BASE = Path(sys._MEIPASS)
    APP_DIR = Path(sys.executable).parent
else:
    RES_BASE = APP_DIR = Path(__file__).parent

APP = Flask(__name__, static_folder=str(RES_BASE / "static"), template_folder=str(RES_BASE / "templates"))
APP.secret_key = "change-me-to-a-secure-random-key"
USERNAME_RE = re.compile(r'^[A-Za-z0-9]+$')

USERS_FILE = APP_DIR / "users.json"
USER_DATA_DIR = APP_DIR / "user_data"
USER_DATA_DIR.mkdir(exist_ok=True)

if not USERS_FILE.exists():
    USERS_FILE.write_text(json.dumps({"users": {}, "order": []}, ensure_ascii=False, indent=2), encoding='utf-8')
with USERS_FILE.open(encoding='utf-8') as f:
    USERS_DATA = json.load(f)

DB_FILE = RES_BASE / "database.json"
with DB_FILE.open(encoding='utf-8') as f:
    db = json.load(f)

SECOND_DB_FILE = RES_BASE / "dataset.json"
with SECOND_DB_FILE.open(encoding='utf-8') as f:
    db2 = json.load(f)

QUESTIONS = {}
UNIT_LIST = {}
for unit, types in db.items():
    for tname, qlist in types.items():
        for q in qlist:
            uid = q.get('uid')
            if not uid:
                continue
            q['unit'] = unit
            q['type'] = tname
            QUESTIONS[uid] = q
            UNIT_LIST.setdefault(unit, []).append(uid)

QUESTIONS2 = {}
UNIT_LIST2 = {}

for kind, groups in db2.items():
    if kind == "单选":
        for g in groups:
            idx = g.get("group_index", 1)
            unit_name = f"单选题 Part{idx}"
            uids = []
            for q in g.get("questions", []):
                uid = q.get("uid")
                if not uid:
                    continue
                QUESTIONS2[uid] = {
                    "uid": uid,
                    "question": q.get("question"),
                    "options": q.get("options", {}),
                    "answer": q.get("answer"),
                    "unit": unit_name,
                    "type": "选择题"
                }
                uids.append(uid)
            UNIT_LIST2.setdefault(unit_name, []).extend(uids)

    elif kind == "判断":
        for g in groups:
            idx = g.get("group_index", 1)
            unit_name = f"判断题 Part{idx}"
            uids = []
            for q in g.get("questions", []):
                uid = q.get("uid")
                if not uid:
                    continue
                QUESTIONS2[uid] = {
                    "uid": uid,
                    "question": q.get("question"),
                    "options": {"√": "正确", "×": "错误"},
                    "answer": q.get("answer"),
                    "unit": unit_name,
                    "type": "判断题"
                }
                uids.append(uid)
            UNIT_LIST2.setdefault(unit_name, []).extend(uids)

EXP_DB = RES_BASE / "exp_db.json"
if EXP_DB.exists():
    with EXP_DB.open(encoding='utf-8') as f:
        EXPS_DB = json.load(f)
        
EXP_DS = RES_BASE / "exp_ds.json"
if EXP_DS.exists():
    with EXP_DS.open(encoding='utf-8') as f:
        EXPS_DS = json.load(f)


def reload_users():
    global USERS_DATA
    with USERS_FILE.open(encoding='utf-8') as f:
        USERS_DATA = json.load(f)


def save_users():
    with USERS_FILE.open('w', encoding='utf-8') as f:
        json.dump(USERS_DATA, f, ensure_ascii=False, indent=2)


def default_ud_section():
    return {
        "by_unit": {},
        "last_choice": {},
        "flags": {"reveal_mode": False, "show_explanations": False},
        "global": {"wrong": [], "star": []},
        "progress": {},
        "current_progress_key": None
    }


def migrate_old_user_data(old):
    new = {"by_unit": {}, "last_choice": {}, "flags": {"reveal_mode": False}, "global": {"wrong": [], "star": []}}
    wrongs = old.get("wrong", []) if isinstance(old, dict) else []
    stars = old.get("star", []) if isinstance(old, dict) else []

    for uid in wrongs:
        if isinstance(uid, str) and '-' in uid:
            unit_idx = uid.split('-', 1)[0]
            unit = new["by_unit"].setdefault(unit_idx, {"studied": [], "wrong": [], "star": [], "last_pos": {"studied": 0, "wrong": 0, "star": 0}})
            if uid not in unit["wrong"]:
                unit["wrong"].append(uid)
            if uid not in new["global"]["wrong"]:
                new["global"]["wrong"].append(uid)

    for uid in stars:
        if isinstance(uid, str) and '-' in uid:
            unit_idx = uid.split('-', 1)[0]
            unit = new["by_unit"].setdefault(unit_idx, {"studied": [], "wrong": [], "star": [], "last_pos": {"studied": 0, "wrong": 0, "star": 0}})
            if uid not in unit["star"]:
                unit["star"].append(uid)
            if uid not in new["global"]["star"]:
                new["global"]["star"].append(uid)

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


def normalize_progress_keys_in_user_data(data):
    changed = False
    for course in ("maogai", "mayuan"):
        sec = data.get(course)
        if not isinstance(sec, dict):
            continue

        prog = sec.get("progress", {})
        for key in list(prog.keys()):
            if not isinstance(key, str):
                continue
            if ':' in key:
                prefix, rest = key.split(':', 1)
                if prefix == 'random':
                    new_key = f"random:{rest}"
                elif prefix in ("maogai", "mayuan", "sequential", "tag"):
                    new_key = rest
                else:
                    continue
                if new_key != key:
                    if new_key not in prog:
                        prog[new_key] = prog.pop(key)
                    else:
                        prog.pop(key, None)
                    changed = True

        cpk = sec.get("current_progress_key")
        if isinstance(cpk, str) and ':' in cpk:
            prefix, rest = cpk.split(':', 1)
            if prefix in ("maogai", "mayuan", "sequential", "tag"):
                sec["current_progress_key"] = rest
                changed = True
        sec["progress"] = prog
    if changed:
        return True
    return False


def get_unit_name_by_uid(uid, course):
    QUESTIONS_X, _ = get_dataset(course)
    q = QUESTIONS_X.get(uid)
    if not q:
        return None
    return q.get('unit')


def load_user_data(username):
    p = USER_DATA_DIR / f"{username}.json"
    if p.exists():
        data = json.load(p.open(encoding='utf-8'))
        if isinstance(data, dict) and ("maogai" in data or "mayuan" in data):
            data.setdefault("maogai", default_ud_section())
            data.setdefault("mayuan", default_ud_section())
            if normalize_progress_keys_in_user_data(data):
                save_user_data(username, data)
            return data

        new = {"maogai": default_ud_section(), "mayuan": default_ud_section()}
        if isinstance(data, dict):
            new["maogai"].update(data)

        normalize_progress_keys_in_user_data(new)
        save_user_data(username, new)
        return new

    data = {"maogai": default_ud_section(), "mayuan": default_ud_section()}
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return data


def save_user_data(username, data):
    p = USER_DATA_DIR / f"{username}.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def get_user_section(username, course, create=True):
    ud_all = load_user_data(username)
    if course not in ud_all:
        if not create:
            return ud_all, None
        ud_all[course] = default_ud_section()
    return ud_all, ud_all[course]


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
        course = request.form.get("course", "maogai") or "maogai"

        if not u or not pw:
            return render_template("login.html", error="用户名或密码不能为空")
        if not USERNAME_RE.match(u) or not USERNAME_RE.match(pw):
            return render_template("login.html", error="用户名和密码只允许字母和数字")

        reload_users()
        user = USERS_DATA.get("users", {}).get(u)

        if user:
            if check_password_hash(user["password"], pw):
                session['user'] = u
                session['course'] = course
                return redirect(f"/dashboard/{course}")
            else:
                return render_template("login.html", error="用户名已存在但密码错误")

        else:
            next_uid = len(USERS_DATA.get("order", [])) + 1
            USERS_DATA.setdefault("users", {})[u] = {"password": generate_password_hash(pw), "uid": next_uid}
            USERS_DATA.setdefault("order", []).append(u)

            save_users()
            session['user'] = u
            session['course'] = course
            return redirect(f"/dashboard/{course}")

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
    next_uid = len(USERS_DATA.get("order", [])) + 1
    USERS_DATA.setdefault("users", {})[u] = {"password": generate_password_hash(pw), "uid": next_uid}
    USERS_DATA.setdefault("order", []).append(u)
    save_users()
    session['user'] = u
    session['course'] = request.form.get("course") or "maogai"
    return jsonify({"ok": True, "uid": next_uid})


@APP.route("/logout")
def logout():
    session.pop('user', None)
    return redirect("/login")


@APP.route("/dashboard")
def dashboard():
    if 'user' not in session:
        return redirect("/login")
    course = session.get('course', 'maogai')
    if course not in ("maogai", "mayuan"):
        course = 'maogai'
    return redirect(f"/dashboard/{course}")


@APP.route("/dashboard/<course>")
def dashboard_course(course):
    if 'user' not in session:
        return redirect("/login")
    if course not in ("maogai", "mayuan"):
        return redirect("/dashboard/maogai")
    session['course'] = course
    QUESTIONS_X, UNIT_LIST_X = get_dataset(course)
    user_info = USERS_DATA.get("users", {}).get(session['user'])
    units = list(UNIT_LIST_X.keys())
    return render_template("dashboard.html", units=units, user_info=user_info, course=course)


def get_dataset(course):
    if course == "mayuan" and QUESTIONS2:
        return QUESTIONS2, UNIT_LIST2
    return QUESTIONS, UNIT_LIST


def get_request_json():
    if request.is_json:
        try:
            return request.get_json(silent=True) or {}
        except Exception:
            return {}
    try:
        text = request.get_data(as_text=True)
        if text:
            return json.loads(text)
    except Exception:
        pass
    try:
        if request.form:
            return request.form.to_dict()
    except Exception:
        pass
    return {}


@APP.route("/api/start", methods=["POST"])
def api_start():
    if 'user' not in session:
        return jsonify({"error": "not logged"}), 401

    j = get_request_json()
    mode = j.get("mode", "random")
    reveal = bool(j.get("reveal", False))

    tag = j.get("tag")
    username = session['user']
    course = j.get("course") or session.get('course') or "maogai"
    if course not in ("maogai", "mayuan"):
        return jsonify({"error": "invalid course"}), 400

    session['course'] = course
    QUESTIONS_X, UNIT_LIST_X = get_dataset(course)
    ud_all, ud = get_user_section(username, course)

    if mode == "sequential":
        unit_raw = j.get("unit")
        if unit_raw:
            if unit_raw not in UNIT_LIST_X:
                return jsonify({"error": "unit not found", "unit_requested": unit_raw}), 400
            unit_key = unit_raw
        else:
            unit_key = None

        progress_key = unit_key if unit_key else "sequential_all"
        existing = ud.get("progress", {}).get(progress_key)

        if existing:
            ulist = existing.get("list", [])
            pos = existing.get("pos", 0)
            reveal_param = j.get("reveal")

            if reveal_param is None:
                reveal = existing.get("reveal", reveal)
            else:
                reveal = bool(reveal_param)
                ud.setdefault("progress", {}).setdefault(progress_key, {})['reveal'] = reveal
        else:
            ulist = UNIT_LIST_X.get(unit_key, [])
            pos = 0
            ud.setdefault("progress", {})[progress_key] = {"list": ulist, "pos": pos, "reveal": reveal}

        ud["current_progress_key"] = progress_key
        save_user_data(username, ud_all)
        return jsonify({"list": ulist, "pos": pos, "reveal": reveal, "key": progress_key, "mode": mode, "unit": unit_key})

    elif mode == "tag":
        if not tag:
            return jsonify({"error": "tag required for tag mode"}), 400
        if tag == "wrong":
            ulist = ud.get("global", {}).get("wrong", [])[:]
        elif tag == "star":
            ulist = ud.get("global", {}).get("star", [])[:]
        else:
            ulist = []

        progress_key = tag
        ud.setdefault("progress", {})[progress_key] = {"list": ulist, "pos": 0, "reveal": reveal}
        ud["current_progress_key"] = progress_key
        save_user_data(username, ud_all)
        return jsonify({"list": ulist, "pos": 0, "reveal": reveal, "key": progress_key, "mode": mode, "tag": tag})

    else:
        count = int(j.get("count", 50))
        all_uids = list(QUESTIONS_X.keys())
        ulist = random.sample(all_uids, min(count, len(all_uids)))
        progress_key = f"random:{count}"
        ud.setdefault("progress", {})[progress_key] = {"list": ulist, "pos": 0, "reveal": reveal}
        ud["current_progress_key"] = progress_key
        save_user_data(username, ud_all)
        return jsonify({"list": ulist, "pos": 0, "reveal": reveal, "key": progress_key, "mode": mode, "count": count, "course": course})


@APP.route("/quiz")
def quiz_root():
    if 'user' not in session:
        return redirect("/login")
    course = session.get('course', 'maogai')
    if course not in ("maogai", "mayuan"):
        return redirect(f"/login")
    return redirect(f"/quiz/{course}")


@APP.route("/quiz/<course>")
def quiz_page(course):
    if 'user' not in session:
        return redirect("/login")
    if course not in ("maogai", "mayuan"):
        return redirect("/dashboard/maogai")

    session['course'] = course
    QUESTIONS_X, UNIT_LIST_X = get_dataset(course)
    username = session['user']
    ud_all, ud = get_user_section(username, course)
    prog = ud.get("progress", {}) or {}

    if not prog:
        first_unit_canonical = None
        if isinstance(UNIT_LIST_X, dict) and len(UNIT_LIST_X) > 0:
            for k in UNIT_LIST_X.keys():
                first_unit_canonical = k
                break
        if first_unit_canonical:
            default_list = UNIT_LIST_X.get(first_unit_canonical, [])[:]
            progress_key = first_unit_canonical
            ud.setdefault("progress", {})[progress_key] = {"list": default_list, "pos": 0, "reveal": False}
            ud["current_progress_key"] = progress_key
            save_user_data(username, ud_all)

    return render_template("quiz.html", course=course)


@APP.route("/api/question", methods=["GET"])
def api_question():
    if 'user' not in session:
        return jsonify({"error": "not logged"}), 401

    uid = request.args.get("uid")
    reveal = request.args.get("reveal") == "1"
    course = request.args.get("course") or session.get("course")
    if not course or course not in ("maogai", "mayuan"):
        return jsonify({"error": "course required"}), 400

    QUESTIONS_X, _ = get_dataset(course)
    q = QUESTIONS_X.get(uid)
    if not q:
        return jsonify({"error": "no such question in course"}), 404
    out = {"uid": uid, "question": q.get("question"), "options": q.get("options", {}), "type": q.get("type")}

    if reveal:
        out["answer"] = q.get("answer")
    exps = EXPS_DS if course == "mayuan" else EXPS_DB
    if exps and uid in exps:
        out["explanation"] = exps[uid]
    return jsonify(out)


@APP.route("/api/answer", methods=["POST"])
def api_answer():
    if 'user' not in session:
        return jsonify({"error": "not logged"}), 401

    j = get_request_json()
    uid = j.get("uid")
    selected = j.get("selected")
    course = j.get("course") or session.get("course")
    if not course or course not in ("maogai", "mayuan"):
        return jsonify({"error": "course required"}), 400

    QUESTIONS_X, _ = get_dataset(course)
    q = QUESTIONS_X.get(uid)
    if not q:
        return jsonify({"error": "no such question in course"}), 404
    correct = q.get("answer")
    username = session['user']
    is_correct = (set(selected or []) == set(correct)) if isinstance(correct, list) else (selected == correct)
    ud_all, ud = get_user_section(username, course)

    unit_name = q.get('unit') or "未知单元"
    unit = ud.setdefault("by_unit", {}).setdefault(unit_name, {"studied": [], "wrong": [], "star": [], "last_pos": {"studied": 0, "wrong": 0, "star": 0}})
    if not is_correct:
        if uid not in unit["wrong"]:
            unit["wrong"].append(uid)
    else:
        if uid in unit["wrong"]:
            unit["wrong"].remove(uid)
    if uid not in unit["studied"]:
        unit["studied"].append(uid)

    gl = ud.setdefault("global", {"wrong": [], "star": []})
    if not is_correct:
        if uid not in gl["wrong"]:
            gl["wrong"].append(uid)
    else:
        if uid in gl["wrong"]:
            gl["wrong"].remove(uid)

    ud.setdefault("last_choice", {})[uid] = {"correct": is_correct, "selected": selected}
    save_user_data(username, ud_all)
    return jsonify({"correct": is_correct, "answer": correct})


@APP.route("/api/star", methods=["POST"])
def api_star():
    if 'user' not in session:
        return jsonify({"error": "not logged"}), 401

    j = get_request_json()
    uid = j.get("uid")
    action = j.get("action", "toggle")
    course = j.get("course") or session.get("course")
    if not course or course not in ("maogai", "mayuan"):
        return jsonify({"error": "course required"}), 400
    username = session['user']
    ud_all, ud = get_user_section(username, course)

    QUESTIONS_X, _ = get_dataset(course)
    q = QUESTIONS_X.get(uid)
    unit_name = q.get('unit') if q else "未知单元"
    unit = ud.setdefault("by_unit", {}).setdefault(unit_name, {"studied": [], "wrong": [], "star": [], "last_pos": {"studied": 0, "wrong": 0, "star": 0}})
    gl = ud.setdefault("global", {"wrong": [], "star": []})

    if action == "toggle":
        if uid in gl["star"]:
            gl["star"].remove(uid)
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
    save_user_data(username, ud_all)
    return jsonify({"starred": state})


@APP.route("/api/clear_unit", methods=["POST"])
def api_clear_unit():
    if 'user' not in session:
        return jsonify({"error": "not logged"}), 401
    j = get_request_json()
    unit_name = j.get("unit") or request.form.get("unit")
    course = j.get("course") or session.get("course")
    if not course or course not in ("maogai", "mayuan"):
        return jsonify({"error": "course required"}), 400
    if not unit_name:
        return jsonify({"error": "no unit"}), 400
    QUESTIONS_X, UNIT_LIST_X = get_dataset(course)
    if unit_name not in UNIT_LIST_X:
        return jsonify({"error": "unit not found", "unit_requested": unit_name}), 404
    unit_key = unit_name
    ulist = UNIT_LIST_X.get(unit_key, [])
    if not ulist:
        return jsonify({"error": "unit not found"}), 404
    username = session['user']
    ud_all, ud = get_user_section(username, course)
    if unit_key and unit_key in ud.get("by_unit", {}):
        ud_unit = ud["by_unit"].setdefault(unit_key, {"studied": [], "wrong": [], "star": [], "last_pos": {"studied": 0, "wrong": 0, "star": 0}})
        ud_unit["studied"] = []
        ud_unit["wrong"] = []
        ud_unit["star"] = []
        ud_unit["last_pos"] = {"studied": 0, "wrong": 0, "star": 0}
        lc = ud.get("last_choice", {}) or {}
        for uid in ulist:
            if uid in lc:
                lc.pop(uid, None)
        ud["last_choice"] = lc
        save_user_data(username, ud_all)
        return jsonify({"ok": True})
    return jsonify({"error": "no data for unit"}), 404


@APP.route("/api/flags", methods=["GET", "POST"])
def api_flags():
    if 'user' not in session:
        return jsonify({"error": "not logged"}), 401
    username = session['user']
    j = get_request_json()
    course = request.args.get("course") or j.get("course") or session.get("course")
    if not course or course not in ("maogai", "mayuan"):
        return jsonify({"error": "course required"}), 400
    ud_all, ud = get_user_section(username, course)
    if request.method == "GET":
        return jsonify(ud.get("flags", {}))
    for k, v in j.items():
        ud.setdefault("flags", {})[k] = bool(v)
    save_user_data(username, ud_all)
    return jsonify(ud.get("flags", {}))


@APP.route("/api/progress/save", methods=["POST"])
def api_progress_save():
    if 'user' not in session:
        return jsonify({"error": "not logged"}), 401
    j = get_request_json()
    key = j.get("key") or j.get("mode")
    pos = j.get("pos", 0)
    username = session['user']
    if not key:
        return jsonify({"error": "no progress key provided"}), 400
    course = j.get("course") or session.get("course")
    if not course or course not in ("maogai", "mayuan"):
        return jsonify({"error": "course required"}), 400
    ud_all, ud = get_user_section(username, course)
    ud.setdefault("progress", {}).setdefault(key, {})['pos'] = pos
    ud["current_progress_key"] = key
    save_user_data(username, ud_all)
    return jsonify({"ok": True})


@APP.route("/api/user/data", methods=["GET"])
def api_user_data():
    if 'user' not in session:
        return jsonify({"error": "not logged"}), 401
    course = request.args.get("course") or session.get("course")
    username = session['user']
    ud_all = load_user_data(username)
    if course and course in ("maogai", "mayuan"):
        return jsonify(ud_all.get(course, default_ud_section()))
    return jsonify(ud_all)


@APP.route("/api/export", methods=["POST"])
def api_export():
    if 'user' not in session:
        return jsonify({"error": "not logged"}), 401
    j = get_request_json()
    qlist = j.get("qlist", [])
    course = j.get("course")
    second_name = j.get("second_name", "题目列表")
    user = j.get("user")
    if not course or course not in ("maogai", "mayuan"):
        return jsonify({"error": "invalid course"}), 400
    if not user:
        return jsonify({"error": "user required"}), 400
    QUESTIONS_X, _ = get_dataset(course)
    exps = EXPS_DS if course == "mayuan" else EXPS_DB
    questions = []
    for uid in qlist:
        q = QUESTIONS_X.get(uid)
        if not q:
            continue
        question_dict = {
            "uid": uid,
            "question": q.get("question"),
            "answer": q.get("answer"),
            "explain": exps.get(uid, "") if exps else "",
            "options": q.get("options", {})
        }
        questions.append(question_dict)
    first_name = '毛概' if course == 'maogai' else '马原'
    docx_name, docx_path = save_questions_to_word(questions, first_name, second_name, user)
    response = make_response(send_file(docx_path, as_attachment=True, download_name=docx_name))
    response.headers['Content-Disposition'] = f"attachment; filename*=utf-8''{quote(docx_name)}"
    return response


if __name__ == "__main__":
    port = 5000
    host = "0.0.0.0"

    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except Exception:
            print(f"无效端口参数 {sys.argv[1]}，使用默认端口 {port}")
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    webbrowser.open(f"http://{local_ip}:{port}/")
    APP.run(host=host, port=port)
