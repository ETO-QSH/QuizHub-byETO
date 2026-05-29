# PR: 清理仓库中无关的中间处理文件

## 概述

清除了项目开发过程中遗留的大量中间处理文件、原始素材文件以及一次性使用的脚本，使仓库保持干净整洁。这些文件在完成数据提取、解析、清洗、OCR 等阶段性任务后已不再需要，继续保留只会增加仓库体积并造成混乱。

## 删除的文件清单

### 原始素材文件（版权材料，不适合纳入仓库）
- `毛概 - 课程知识点与试题库2025.docx`
- `习近平新时代中国特色社会主义思想概述 学习通 全 题库及答案 .pdf`
- `新-马原客观题题库二.pdf`

### 一次性数据处理脚本
- `parse_db.py` / `parse_ds.py` / `parse_xigai.py` — JSON 数据解析
- `extract_red.py` — 文本提取
- `fix_fill_blanks.py` / `fix_placeholders.py` — 数据清洗与修复
- `ocr_xigai_red_answers.py` — OCR 识别
- `verify_xigai_answers.py` — 答案校验
- `gen_exp.py` / `gen_exp_xigai.py` — AI 解析生成

### 中间数据与临时文件
- `问题.txt` / `database.txt` / `dataset.txt` — 数据库文本转储
- `习概_raw.txt` / `习概_red.txt` / `习概_red_ocr.txt` / `习概_red_ocr_answers.json` — 习概数据中间处理结果
- `xigai_api_report.txt` / `xigai_parse_report.txt` — 处理日志
- `归终.ico` — 无关图标文件

### 重复文件
- `login.html`（根目录重复项，Flask 实际使用的是 `templates/login.html`）

### 其余清理
- 删除 `__pycache__` 缓存目录

## 保留的核心文件

| 文件 | 说明 |
|------|------|
| `app.py` | Flask 主应用 |
| `app.spec` | PyInstaller 打包配置 |
| `export.py` | Word 文档导出逻辑 |
| `database.json` | 毛概题库数据 |
| `dataset.json` | 马原题库数据 |
| `xigai.json` | 习概题库数据 |
| `exp_db.json` / `exp_ds.json` / `exp_xigai.json` | 对应题库的题目解析 |
| `users.json` | 用户数据 |
| `static/` | 前端静态资源（CSS/JS/图片） |
| `templates/` | Jinja2 模板文件 |
| `LICENSE` / `README.md` / `requirements.txt` | 项目文档 |

## 影响

- ✅ 仓库体积显著减小
- ✅ 项目结构更清晰，新人上手更友好
- ❌ 无功能影响，应用正常运行不受影响
- ❌ 无需修改现有代码逻辑

## 验证

清理完成后，执行 `flask run` 应用正常运行，三条课程（毛概/马原/习概）所有功能正常。