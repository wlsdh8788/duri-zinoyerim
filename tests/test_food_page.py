"""우리두리 먹거리: 실제 정보 없는 가짜 카드와 깨진 배포를 방지하는 기본 테스트."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class FoodPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((ROOT/"food.json").read_text(encoding="utf-8"))
        cls.main=(ROOT/"index.html").read_text(encoding="utf-8")
        cls.food=(ROOT/"food.html").read_text(encoding="utf-8")
        cls.js=(ROOT/"food.js").read_text(encoding="utf-8")
    def test_verified_initial_shortlist(self):
        entries=self.data["places"]
        self.assertGreaterEqual(len(entries),5)
        ids=[row["id"] for row in entries]
        self.assertEqual(len(ids),len(set(ids)))
        for row in entries:
            for field in ["name","city","address","type","verifiedAt"]:
                self.assertTrue(str(row.get(field,"")).strip(),row.get("id"))
            self.assertEqual(row["city"],"강릉")
            self.assertEqual(row["verifiedAt"],"2026-11-21")
    def test_separate_top_navigation(self):
        self.assertIn('href="./food.html"',self.main)
        self.assertIn('href="./index.html"',self.food)
        self.assertIn('href="./site-nav.css"',self.main)
        self.assertIn('href="./site-nav.css"',self.food)
    def test_search_without_api_credentials(self):
        self.assertIn("map.naver.com/p/search/",self.js)
        self.assertIn("encodeURIComponent(q.trim())",self.js)
        self.assertNotIn("NAVER_APIHUB_CLIENT_SECRET",self.js)
        self.assertNotIn("NAVER_APIHUB_CLIENT_ID",self.js)
    def test_ui_controls_exist(self):
        for identifier in ["foodSearch","foodRegion","foodCards","foodCount","naverFind","foodSearchForm"]:
            self.assertIn('id="'+identifier+'"',self.food)
        self.assertIn('src="./food.js"',self.food)

if __name__=="__main__":
    unittest.main()
