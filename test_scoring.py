import unittest
from app import compute_match, Country

class TestScoring(unittest.TestCase):
    def test_language_matching(self):
        country = Country(
            name="Testland",
            languages='["english", "german"]',
            sector_scores='{"tech": 0.8}',
            tolerance=0.8,
            cost_index=0.4,
            climate=0.1,
            description=""
        )
        user_skills = ["python"]
        user_languages = [("english", 3)]
        score, breakdown = compute_match(user_skills, user_languages, country)
        self.assertGreater(score, 0)
        self.assertEqual(breakdown["lang"], 1.0)

if __name__ == "__main__":
    unittest.main()
