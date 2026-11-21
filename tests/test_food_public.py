"""Unit tests for official Gangneung restaurant licence directory."""
import unittest
from scripts.update_food_public import category_for, convert_rows, is_open, district_for

def entry(name="강릉 옹심이", address="강원특별자치도 강릉시 교동 123",
          status="영업/정상", kind="한식"):
    return {"사업장명":name, "도로명주소":address, "지번주소":address,
            "영업상태명":status, "상세영업상태명":status,
            "업태구분명":kind}

class PublicFoodTests(unittest.TestCase):
    def test_classification(self):
        self.assertEqual(category_for("강릉돈까스", "한식"), "돈까스")
        self.assertEqual(category_for("나폴리 피자", "경양식"), "피자")
        self.assertEqual(category_for("그린 횟집", "한식"), "회")
        self.assertEqual(category_for("미소카페", "커피숍"), "카페")
        self.assertEqual(category_for("모아나 버거", "패스트푸드"), "햄버거")
        self.assertEqual(category_for("참치초밥", "일식"), "일식")
        self.assertEqual(category_for("교동곱창", "식육(숯불구이)"), "고기")
        self.assertEqual(category_for("떡볶이분식", "한식"), "분식")
        self.assertEqual(category_for("국밥집", "한식"), "한식")

    def test_closed_establishments_excluded(self):
        self.assertTrue(is_open(entry()))
        self.assertFalse(is_open(entry(status="폐업")))
        self.assertFalse(is_open(entry(status="휴업")))
        self.assertFalse(is_open(entry(status="영업정지")))
        self.assertEqual(convert_rows([entry(status="폐업")], "general_restaurants"), [])

    def test_only_gangneung_and_real_address(self):
        rows = [entry(), entry(name="서울집", address="서울특별시 중구 을지로 1"),
                entry(name="무주소", address=""), entry(name="단오제 임시영업부스")]
        converted = convert_rows(rows, "general_restaurants")
        self.assertEqual(len(converted), 1)
        self.assertEqual(converted[0]["city"], "강릉")
        self.assertEqual(converted[0]["district"], "교동")
        self.assertEqual(converted[0]["sourceType"], "official-permit")
        self.assertIsNone(converted[0]["rating"])

    def test_stable_ids(self):
        row = entry()
        self.assertEqual(convert_rows([row], "general_restaurants")[0]["id"],
                         convert_rows([row], "rest_cafes")[0]["id"])

    def test_district(self):
        self.assertEqual(district_for("강원특별자치도 강릉시 주문진읍 해안로 12"),"주문진읍")

if __name__ == "__main__":
    unittest.main()
