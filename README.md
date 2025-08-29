# EU Matcher MVP

A simple web app that helps users find the **best-fitting EU country** based on:
- Skills
- Spoken languages
- Personal preferences (openness to diversity, budget, climate)

This is a minimal **Flask + SQLite** project to demonstrate a scoring system.  
You can easily expand it with real datasets, richer scoring, and a modern frontend.

---

## Features
- 📝 Input your **skills** and **languages** (comma-separated).
- 🎛️ Adjust sliders for tolerance, budget, and climate preference.
- 🔢 Countries scored and ranked using a **weighted scoring function**.
- 💾 SQLite database with seeded example countries.

---

## Requirements
- Python 3.8+
- `Flask`, `Flask-SQLAlchemy`

---

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/<your-username>/eu-matcher.git
cd eu-matcher

# 2. Set up a virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py

# App runs on http://127.0.0.1:5000

