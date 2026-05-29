import json
import re
from pathlib import Path

import cv2
import numpy as np
import pdfplumber
import fitz
import easyocr

PDF_PATH = Path(r"习近平新时代中国特色社会主义思想概述 学习通 全 题库及答案 .pdf")
OUT_TXT = Path(r"习概_red_ocr.txt")
OUT_JSON = Path(r"习概_red_ocr_answers.json")

CHAPTER_10_PAGE = 55
CHAPTER_11_PAGE = 61
CHAPTER_12_PAGE = 66
CHAPTER_13_PAGE = 71

ALLOWED = set("ABCD√×")


def find_page_marker(pdf, page_no):
    marker_re = re.compile(r"—\s*%d\s*—" % page_no)
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        if marker_re.search(text):
            return i
    return None


def mask_red(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    mask1 = cv2.inRange(hsv, (0, 70, 70), (10, 255, 255))
    mask2 = cv2.inRange(hsv, (160, 70, 70), (180, 255, 255))
    mask = cv2.bitwise_or(mask1, mask2)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    out = img.copy()
    out[mask == 0] = 255
    return out, mask


def clean_token(text):
    if not text:
        return ""
    t = text.replace(" ", "").upper()
    t = t.replace("X", "×")
    t = "".join(ch for ch in t if ch in ALLOWED)
    return t


def group_by_line(items, y_threshold=12):
    lines = []
    for bbox, text in items:
        ys = [p[1] for p in bbox]
        y_center = sum(ys) / len(ys)
        xs = [p[0] for p in bbox]
        x_left = min(xs)
        placed = False
        for line in lines:
            if abs(line["y"] - y_center) <= y_threshold:
                line["items"].append((x_left, text))
                line["y"] = (line["y"] + y_center) / 2.0
                placed = True
                break
        if not placed:
            lines.append({"y": y_center, "items": [(x_left, text)]})
    lines.sort(key=lambda l: l["y"])
    return lines


def extract_answers_from_page(reader, page_img):
    masked, _ = mask_red(page_img)
    results = reader.readtext(masked, detail=1, paragraph=False, allowlist="ABCD√×")
    cleaned = []
    for bbox, text, _conf in results:
        t = clean_token(text)
        if not t:
            continue
        cleaned.append((bbox, t))
    if not cleaned:
        return []
    lines = group_by_line(cleaned)
    answers = []
    for line in lines:
        parts = sorted(line["items"], key=lambda x: x[0])
        joined = "".join(p[1] for p in parts)
        joined = clean_token(joined)
        if joined:
            answers.append(joined)
    return answers


def main():
    if not PDF_PATH.exists():
        raise FileNotFoundError(PDF_PATH)

    with pdfplumber.open(str(PDF_PATH)) as pdf:
        p10 = find_page_marker(pdf, CHAPTER_10_PAGE)
        p11 = find_page_marker(pdf, CHAPTER_11_PAGE)
        p12 = find_page_marker(pdf, CHAPTER_12_PAGE)
        p13 = find_page_marker(pdf, CHAPTER_13_PAGE)

    if p10 is None:
        raise RuntimeError("Cannot locate chapter 10 page marker in PDF.")

    start = p10
    end = p13 if p13 is not None else None

    reader = easyocr.Reader(["ch_sim", "en"], gpu=False)
    doc = fitz.open(str(PDF_PATH))

    all_answers = []
    txt_lines = []
    for idx in range(start, end if end is not None else doc.page_count):
        page = doc.load_page(idx)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        answers = extract_answers_from_page(reader, img)
        if answers:
            for ans in answers:
                all_answers.append(ans)
                txt_lines.append(f"[p{idx + 1}] {ans}")

    OUT_TXT.write_text("\n".join(txt_lines), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(all_answers, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ocr answers", len(all_answers), "->", OUT_JSON.resolve())


if __name__ == "__main__":
    main()
