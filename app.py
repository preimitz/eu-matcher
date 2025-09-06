import os
import json
from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from fuzzywuzzy import fuzz

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mvp.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------- Models ----------
class Country(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    languages = db.Column(db.Text)       # JSON list of languages
    sector_scores = db.Column(db.Text)   # JSON dict of sector strengths
    tolerance = db.Column(db.Float)      # 0..1
    cost_index = db.Column(db.Float)     # 0..1
    climate = db.Column(db.Float)        # -1..1
    description = db.Column(db.Text)

    def langs(self):
        return json.loads(self.languages or "[]")
    def sectors(self):
        return json.loads(self.sector_scores or "{}")

# ---------- Skill Map ----------
def load_skill_map(filepath="data/skill_map.json"):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "python": "tech", "django": "tech", "flask": "tech", "data": "tech",
            "java": "tech", "c++": "tech", "nurse": "healthcare", "doctor": "healthcare",
            "chef": "tourism", "hospitality": "tourism", "accountant": "finance",
            "bank": "finance", "manufacturing": "manufacturing", "engineer": "manufacturing"
        }

skill_map = load_skill_map()

def guess_sector(skill):
    s = skill.lower()
    for k, sector in skill_map.items():
        if k in s:
            return sector
    return None

def skill_score(user_skill, country_skills):
    best_match = 0
    for cs in country_skills:
        similarity = fuzz.token_set_ratio(user_skill, cs)
        if similarity > best_match:
            best_match = similarity
    return best_match / 100  # normalize to 0–1

# ---------- Seed Countries ----------
def seed_countries():
    try:
        data_file = os.path.join(os.path.dirname(__file__), "data/countries.json")
        with open(data_file, "r", encoding="utf-8") as f:
            countries_data = json.load(f)
    except Exception as e:
        print("Error loading country data:", e)
        return
    for c in countries_data:
        if not Country.query.filter_by(name=c["name"]).first():
            db.session.add(Country(
                name=c["name"],
                languages=json.dumps(c["languages"]),
                sector_scores=json.dumps(c["sector_scores"]),
                tolerance=c["tolerance"],
                cost_index=c["cost_index"],
                climate=c["climate"],
                description=c.get("description", "")
            ))
    db.session.commit()

# ---------- Scoring Function ----------
def compute_match(user_skills, user_languages, country, weights):
    breakdown = {}

    # Skills Matching
    sectors = country.sectors()
    skill_scores = []
    for skill in user_skills:
        best_sector_score = 0
        for sector_name, weight in sectors.items():
            match_strength = skill_score(skill, [sector_name])
            best_sector_score = max(best_sector_score, match_strength * weight)
        skill_scores.append(best_sector_score)
    breakdown["skills"] = round(sum(skill_scores)/len(skill_scores), 3) if skill_scores else 0.0

    # Language Matching
    country_langs = [l.lower() for l in country.langs()]
    lang_scores = []
    for lang, prof in user_languages:
        if lang in country_langs:
            lang_scores.append(prof)
    lang_score = max(lang_scores)/3.0 if lang_scores else 0.0  # normalized
    breakdown["lang"] = round(lang_score, 3)

    # Tolerance
    breakdown["tolerance"] = round(country.tolerance, 3)
    # Cost
    cost = 1 - country.cost_index  # lower cost = better
    breakdown["cost"] = round(cost, 3)
    # Climate
    clim = (country.climate + 1)/2  # normalize
    breakdown["climate"] = round(clim, 3)

    # Weighted total
    final_score = (
        weights["skills"] * breakdown["skills"] +
        weights["lang"] * breakdown["lang"] +
        weights["tolerance"] * breakdown["tolerance"] +
        weights["cost"] * breakdown["cost"] +
        weights["climate"] * breakdown["climate"]
    )
    final_score = round(final_score * 100, 2)
    return final_score, breakdown

# ---------- Routes ----------
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/recommend", methods=["POST"])
def recommend():
    # Parse skills
    skills_raw = request.form.get("skills", "")
    user_skills = [s.strip() for s in skills_raw.split(",") if s.strip()]

    # Parse dynamic language inputs with proficiency
    user_languages = []
    i = 0
    while True:
        lang = request.form.get(f"language_{i}")
        prof = request.form.get(f"proficiency_{i}")
        if lang is None or prof is None:
            break
        lang = lang.strip().lower()
        if lang and prof:
            user_languages.append((lang, int(prof)))
        i += 1

    # Parse sliders and weights
    openness = float(request.form.get("openness", 0.7))
    budget_pref = float(request.form.get("budget_pref", 0.5))
    climate_pref = float(request.form.get("climate_pref", 0.0))

    weights = {
        "skills": float(request.form.get("weight_skills", 0.3)),
        "lang": float(request.form.get("weight_lang", 0.3)),
        "tolerance": float(request.form.get("weight_tolerance", 0.2)),
        "cost": float(request.form.get("weight_cost", 0.1)),
        "climate": float(request.form.get("weight_climate", 0.1)),
    }

    results = []
    for country in Country.query.all():
        score, breakdown = compute_match(user_skills, user_languages, country, weights)
        results.append({
            "name": country.name,
            "score": score,
            "breakdown": breakdown,
            "description": country.description
        })
    results.sort(key=lambda x: x["score"], reverse=True)
    return render_template("results.html", results=results, user_skills=user_skills, user_langs=user_languages)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_countries()
    app.run(debug=True)