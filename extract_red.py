import pdfplumber
from pathlib import Path

PDF_PATH = Path(r"习近平新时代中国特色社会主义思想概述 学习通 全 题库及答案 .pdf")
OUT_PATH = Path(r"习概_red.txt")


def is_red(color):
    if not isinstance(color, (list, tuple)) or len(color) < 3:
        return False
    r, g, b = color[0], color[1], color[2]
    return r > 0.8 and g < 0.3 and b < 0.3


lines_out = []

with pdfplumber.open(str(PDF_PATH)) as pdf:
    for page_no, page in enumerate(pdf.pages, start=1):
        chars = page.chars or []
        red_chars = [c for c in chars if is_red(c.get("non_stroking_color"))]
        if not red_chars:
            continue
        red_chars.sort(key=lambda c: (c["top"], c["x0"]))
        cur_top = None
        cur = []
        cur_x = None

        def flush(state):
            if state["cur"]:
                lines_out.append(f"[p{page_no}] " + "".join(state["cur"]))
            state["cur"] = []
            state["cur_top"] = None

        state = {"cur_top": cur_top, "cur": cur, "cur_x": cur_x}

        for c in red_chars:
            top = c["top"]
            if state["cur_top"] is None:
                state["cur_top"] = top
                state["cur"] = [c["text"]]
                state["cur_x"] = c["x1"]
                continue
            if abs(top - state["cur_top"]) > 2:
                flush(state)
                state["cur_top"] = top
                state["cur"] = [c["text"]]
                state["cur_x"] = c["x1"]
            else:
                if c["x0"] - state["cur_x"] > 2:
                    state["cur"].append(" ")
                state["cur"].append(c["text"])
                state["cur_x"] = c["x1"]
        flush(state)

OUT_PATH.write_text("\n".join(lines_out), encoding="utf-8")
print("red lines", len(lines_out), "->", OUT_PATH.resolve())
