# 🤝 Contributing to PortaGit Station

Thank you for your interest in contributing to **PortaGit Station**! This project aims to simplify Git workflows for developers, and we welcome help of all kinds—from bug reports to new features.

## 🚀 Getting Started

1.  **Fork the Repository:** Create your own fork of the project.
2.  **Clone Locally:** `git clone https://github.com/YOUR_USERNAME/PortaGit-Station.git`
3.  **Install Dependencies:** `pip install -r requirements.txt`
4.  **Run Development Server:** `python app.py`

## 🛠 Project Architecture

*   **Backend:** Flask (Python) with SQLAlchemy for the database and GitPython for Git operations.
*   **Frontend:** Tabler UI (HTML/Bootstrap) with Vanilla JS.
*   **Database:** SQLite (stored in `/data/git_dashboard.db`).
*   **Security:** Fernet encryption for GitHub tokens (keys in `/data/secret.key`).

## 📋 How Can I Help?

### Reporting Bugs
*   Verify the bug isn't already reported in the **Issues**.
*   Provide a clear title and description.
*   Include steps to reproduce, the error message, and your OS (Windows/macOS/Linux).

### Submitting Pull Requests
1.  **Branching:** Create a feature branch from `main` (e.g., `feature/awesome-new-tool`).
2.  **Standards:** 
    *   Follow **PEP 8** for Python.
    *   Use **idiomatic GitPython** methods where possible.
    *   Maintain **cross-platform compatibility** (use `os.path.join`, etc.).
3.  **Portability:** Ensure all data stays within the project folder. Never use hardcoded absolute paths outside the workspace.
4.  **Testing:** Verify your changes locally. If fixing a bug, ensure the original issue is resolved without regressions.

## 🎨 UI & UX Guidelines
*   **Consistency:** Use existing Tabler components. Avoid adding large external CSS/JS libraries.
*   **Aesthetics:** Keep the interface clean, modern, and "alive" with interactive feedback (flash messages, spinners).
*   **Safety:** Always prompt for confirmation before destructive actions (like removing a repository).

## 📄 License
By contributing, you agree that your contributions will be licensed under the **MIT License**.

---
### Developed by [MANORANJAN](https://github.com/manoranjan2050)
*Inspired by the need for speed and simplicity in Git workflows.*
