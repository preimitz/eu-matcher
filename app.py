# app.py
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
    languages = db.Column(db.Text)       # JSON list of languages, e.g. ["english","german"]
    sector_scores = db.Column(db.Text)   # JSON dict, e.g. {"tech":0.8,"healthcare":0.4}
    tolerance = db.Column(db.Float)      # 0..1 (higher = more socially tolerant)
    cost_index = db.Column(db.Float)     # 0..1 (higher = more expensive)
    climate = db.Column(db.Float)        # -1..1 (cold -> warm)
    description = db.Column(db.Text)

    def langs(self):
        return json.loads(self.languages or "[]")
    def sectors(self):
        return json.loads(self.sector_scores or "{}")


# ---------- Seed function (run once) ----------
def seed_countries():
    import os

    data_file = os.path.join(os.path.dirname(__file__), "data/countries.json")

    with open(data_file, "r", encoding="utf-8") as f:
        countries_data = json.load(f)

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



# ---------- Simple skill -> sector guess map (MVP) ----------
skill_map = {
    "python": "tech", "django": "tech", "flask": "tech", "data": "tech",
    "java": "tech", "c++": "tech", "nurse": "healthcare", "doctor": "healthcare",
    "chef": "tourism", "hospitality": "tourism", "accountant": "finance",
    "bank": "finance", "manufacturing": "manufacturing", "engineer": "manufacturing"
}
def guess_sector(skill):
    s = skill.lower()
    for k, sector in skill_map.items():
        if k in s:
            return sector
    return None


# ---------- Scoring function ----------
# Default weights (sum to 1.0)
DEFAULT_WEIGHTS = {
    "lang": 0.35,
    "skills": 0.35,
    "tolerance": 0.15,
    "cost": 0.1,
    "climate": 0.05
}

def skill_score(user_skill, country_skills):
    best_match = 0
    for cs in country_skills:
        similarity = fuzz.token_set_ratio(user_skill, cs)
        if similarity > best_match:
            best_match = similarity
    return best_match / 100  # normalize to 0–1

# def compute_match(user_skills, user_languages, prefs, weights=DEFAULT_WEIGHTS):
#     """
#     user_skills: list[str]
#     user_langs: list[str]
#     prefs: dict with keys:
#       - openness (0..1)
#       - budget_pref (0..1)   (0 = prefers cheaper places, 1 = prefers expensive)
#       - climate_pref (-1..1)
#     """
#     results = []
#     countries = Country.query.all()
#     for c in countries:
#         sectors = c.sectors()
# #         # language score: 1 if at least one spoken language is present, else fraction 0..0.5
# #         country_langs = [l.lower() for l in c.langs()]
# #         lang_score = 0.0
# #         for ul in user_langs:
# #             if ul.lower() in country_langs:
# #                 lang_score = 1.0
# #                 break
#         # New language scoring: consider proficiency
#         country_langs = [l.lower() for l in c.langs()]
#         lang_scores = []
#         for lang, prof in user_languages:
#             if lang in country_langs:
#                 # Scale proficiency 0..3 → 0..1
#                 lang_scores.append(prof / 3.0)
#         if lang_scores:
#             lang_score = max(lang_scores)  # take highest match
#         else:
#             lang_score = 0.0


#         # skill score: map each skill to a sector and take average of sector scores
#         skill_scores = []
#         for sk in user_skills:
#             sector = guess_sector(sk)
#             if sector and sector in sectors:
#                 skill_scores.append(float(sectors[sector]))
#             else:
#                 # fallback: use 'general' sector score if available
#                 fallback_score = sectors.get("general", 0.3)  # default to 0.3 if missing
#                 skill_scores.append(float(fallback_score))
#         skill_score = sum(skill_scores) / len(skill_scores) if skill_scores else 0.0

#         # tolerance score: closer to preference is better
#         tolerance_score = 1.0 - abs(prefs.get("openness", 0.5) - c.tolerance)  # 0..1

#         # cost: user budget_pref 0..1 -> prefer lower/higher. We'll compute similarity
#         cost_score = 1.0 - abs(prefs.get("budget_pref", 0.5) - c.cost_index)  # 0..1

#         # climate  -1..1
#         climate_score = 1.0 - abs(prefs.get("climate_pref", 0.0) - c.climate)  # 0..1

#         # final weighted score
#         final = (weights["lang"] * lang_score +
#                  weights["skills"] * skill_score +
#                  weights["tolerance"] * tolerance_score +
#                  weights["cost"] * cost_score +
#                  weights["climate"] * climate_score)
#         results.append({
#             "country": c.name,
#             "score": round(final, 4),
#             "breakdown": {
#                 "lang": round(lang_score, 3),
#                 "skills": round(skill_score, 3),
#                 "tolerance": round(tolerance_score, 3),
#                 "cost": round(cost_score, 3),
#                 "climate": round(climate_score, 3)
#             },
#             "description": c.description
#         })

#     # sort descending by score
#     results.sort(key=lambda r: r["score"], reverse=True)
#     return results

def compute_match(user_skills, user_languages, country):
    """
    Compute a match score for a given country based on:
    - Skills (fuzzy matching against sector_scores)
    - Languages (with proficiency)
    - Country attributes (tolerance, cost of living, climate)
    
    Returns:
      final_score (float), breakdown (dict)
    """
    breakdown = {}
    score = 0
    max_score = 0

    # -------------------------
    # 1. Skills Matching
    # -------------------------
    sectors = country.sectors()  # e.g. {"tech":0.8, "finance":0.6, "general":0.5}
    skill_scores = []
    for skill in user_skills:
        best_sector_score = 0
        for sector_name, weight in sectors.items():
            match_strength = skill_score(skill, [sector_name])
            best_sector_score = max(best_sector_score, match_strength * weight)
        skill_scores.append(best_sector_score)
        max_score += 10
        score += best_sector_score * 10
    breakdown["skills"] = round(sum(skill_scores)/len(skill_scores), 3) if skill_scores else 0.0

    # -------------------------
    # 2. Language Matching
    # -------------------------
    country_langs = [l.lower() for l in country.langs()]
    lang_scores = []
    for lang, prof in user_languages:
        max_score += 3
        if lang in country_langs:
            lang_scores.append(prof)
    lang_score = max(lang_scores)/3.0 if lang_scores else 0.0  # normalized 0–1
    score += max(lang_scores) if lang_scores else 0
    breakdown["lang"] = round(lang_score, 3)

    # -------------------------
    # 3. Tolerance
    # -------------------------
    max_score += 3
    tol = country.tolerance
    score += tol * 3
    breakdown["tolerance"] = round(tol, 3)

    # -------------------------
    # 4. Cost
    # -------------------------
    max_score += 3
    cost = 1 - country.cost_index  # lower cost = better
    score += cost * 3
    breakdown["cost"] = round(cost, 3)

    # -------------------------
    # 5. Climate
    # -------------------------
    max_score += 3
    clim = (country.climate + 1)/2  # normalize -1..1 → 0..1
    score += clim * 3
    breakdown["climate"] = round(clim, 3)

    # -------------------------
    # Final normalized score
    # -------------------------
    final_score = round((score / max_score) * 100, 2) if max_score else 0
    return final_score, breakdown



# ---------- Routes ----------
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/recommend", methods=["POST"])
def recommend():
    # parse inputs from a simple form
    skills_raw = request.form.get("skills", "")
    #langs_raw = request.form.get("languages", "")
    openness = float(request.form.get("openness", 0.5))  # 0..1
    budget_pref = float(request.form.get("budget_pref", 0.5))  # 0..1
    climate_pref = float(request.form.get("climate_pref", 0.0))  # -1..1

    user_skills = [s.strip() for s in skills_raw.split(",") if s.strip()]
    #user_langs = [l.strip() for l in langs_raw.split(",") if l.strip()]
    # Parse dynamic language inputs with proficiency
    user_languages = []
    for i in range(20):  # allow up to 20 entries
        lang = request.form.get(f"language_{i}")
        prof = request.form.get(f"proficiency_{i}")
        if lang and prof:
            user_languages.append((lang.strip().lower(), int(prof)))


#     prefs = {"openness": openness, "budget_pref": budget_pref, "climate_pref": climate_pref}
#     results = compute_match(user_skills, user_languages, prefs)

#     return render_template("results.html", results=results, user_skills=user_skills, user_langs=user_languages, prefs=prefs)

    prefs = {"openness": openness, "budget_pref": budget_pref, "climate_pref": climate_pref}

    results = []
    for country in Country.query.all():
        score, breakdown = compute_match(user_skills, user_languages, country)
        results.append({
        "name": country.name,
        "score": score,
        "breakdown": breakdown,
        "description": country.description
        })

    # sort descending by score
    results.sort(key=lambda x: x["score"], reverse=True)
    
    return render_template(
        "results.html",
        results=results,
        user_skills=user_skills,
        user_langs=user_languages,
        prefs=prefs
    )



# ---------- Utility to init DB ----------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_countries()
    app.run(debug=True)

