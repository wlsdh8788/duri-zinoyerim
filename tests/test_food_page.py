"""우리두리 강릉 먹거리: 음식별 카테고리·정렬·네이버 링크 유효성."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FOOD_CATEGORIES=["한식","피자","햄버거","돈까스","회","양식","카페"]

class FoodPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((ROOT/"food.json").read_text(encoding="utf-8"))
        cls.main=(ROOT/"index.html").read_text(encoding="utf-8")
        cls.food=(ROOT/"food.html").read_text(encoding="utf-8")
        cls.js=(ROOT/"food.js").read_text(encoding="utf-8")
    def test_gangneung_category_list(self):
        entries=self.data["places"]
        self.assertGreaterEqual(len(entries),20)
        ids=[row["id"] for row in entries]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(self.data["categories"],FOOD_CATEGORIES)
        self.assertEqual(set(item["category"] for item in entries),set(FOOD_CATEGORIES))
        for row in entries:
            for field in ("name","city","category","address","menu","verifiedAt"):
                self.assertTrue(str(row.get(field,"")).strip(),row.get("id"))
            self.assertEqual(row["city"],"강릉")
            self.assertIn(row["category"],FOOD_CATEGORIES)
    def test_no_fake_naver_rating(self):
        for row in self.data["places"]:
            self.assertIsNone(row.get("rating"),row["id"])
            self.assertIsNone(row.get("ratingSource"),row["id"])
        self.assertIn("내 별점순",self.food)
        self.assertIn("personal_scores",self.js)
    def test_food_categories_and_controls(self):
        for name in ["전체",*FOOD_CATEGORIES]:
            self.assertIn('data-food-filter="'+name+'"',self.food)
        for identifier in ("foodSearch","foodCards","foodCount","foodSort","foodResultsTitle","foodCategoryTitle","naverFind","foodSearchForm"):
            self.assertIn('id="'+identifier+'"',self.food)
        self.assertIn('src="./food.js"',self.food)
        self.assertIn('value="my-rating"',self.food)
    def test_no_secret_and_naver_links(self):
        self.assertIn("https://map.naver.com/p/search/",self.js)
        self.assertIn("encodeURIComponent(query.trim())",self.js)
        self.assertNotIn("NAVER_APIHUB_CLIENT_SECRET",self.js)
        self.assertNotIn("NAVER_APIHUB_CLIENT_ID",self.js)
    def test_shared_navigation(self):
        self.assertIn('href="./food.html"',self.main)
        self.assertIn('href="./index.html"',self.food)
        self.assertIn('href="./site-nav.css"',self.main)
        self.assertIn('href="./site-nav.css"',self.food)

if __name__=="__main__":
    unittest.main()
