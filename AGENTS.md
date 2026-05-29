# QuizHub AI Agent Instructions

Welcome to the QuizHub repository! This file provides essential context for AI agents working in this codebase.

## Project Structure
- This is a Python web application built with **Flask** (`app.py`).
- The application is distributed both as a script and as a compiled executable using **PyInstaller** (`app.spec`).
- **Templates:** Jinja2 HTML templates are located in `templates/`.
- **Static Assets:** CSS and JS are inside `static/`.

## Development & Build Notes
- **Resource Paths:** Be mindful of resource paths. The application handles path resolution dynamically to support PyInstaller's `sys._MEIPASS` when `sys.frozen` is true. Always use `RES_BASE` or `APP_DIR` (as defined in `app.py`) for file I/O instead of relative string paths.
- **Dependencies:** Listed in [`requirements.txt`](requirements.txt). It includes Flask, python-docx, and reportlab.
- **Data storage:** Operates with JSON and txt files for questions/datasets (e.g., `dataset.json`, `database.json`, `exp_db.json`).

## Conventions
- **Routing:** Handled in `app.py`.
- **Exports:** Word document generation and exports are handled by `export.py` and `gen_exp.py`.
- **Code Style:** Standard PEP-8 Python formatting.

*Note: For further details on the project architecture or contribution guidelines, check [`README.md`](README.md).*
