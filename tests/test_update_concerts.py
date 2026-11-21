"""유명 가수 콘서트 데이터 검증: 외부 통신 없이 실행."""
import importlib.util
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("update_concerts",ROOT/"scripts"/"update_concerts.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ConcertTests(unittest.TestCase):
    def test_singer_name_match_and_false_positive(self):
        self.assertTrue(module.matches_name("2026 성시경 연말 콘서트", "성시경"))
        self.assertTrue(module.matches_name("2026 DAY6 World Tour", "DAY6"))
        self.assertFalse(module.matches_name("김태연 전국투어", "태연"))
        self.assertFalse(module.matches_name("2026 나훈아 헌정 콘서트", "성시경"))

    def test_exclude_tribute_and_child(self):
        excluded=["어린이","트리뷰트","헌정","뮤지컬"]
        self.assertTrue(module.exclude("성시경 트리뷰트 콘서트", excluded))
        self.assertTrue(module.exclude("어린이 박효신 노래교실", excluded))
        self.assertFalse(module.exclude("성시경 연말 콘서트", excluded))

    def test_only_popular_music_category_and_artist(self):
        event={"id":"kopis-PF123456","title":"2026 성시경 연말 콘서트",
               "start":"2026-12-01","end":"2026-12-03","province":"서울","city":"서울"}
        db=ET.fromstring("""<db><genrenm>대중음악</genrenm><prfnm>2026 성시경 연말 콘서트</prfnm>
          <prfcast>성시경, 박재정</prfcast><prfpdfrom>2026.12.01</prfpdfrom>
          <prfpdto>2026.12.03</prfpdto><fcltynm>체육관</fcltynm></db>""")
        result=module.make_concert(event,db,["성시경","박재정"],["뮤지컬"])
        self.assertIsNotNone(result)
        self.assertEqual(result["artists"],["성시경","박재정"])
        self.assertEqual(result["start"],"2026-12-01")
        db.find("genrenm").text="뮤지컬"
        self.assertIsNone(module.make_concert(event,db,["성시경"],[]))
        db.find("genrenm").text="대중음악"
        self.assertIsNone(module.make_concert(event,db,["아이유"],[]))

    def test_approved_ticket_source_only(self):
        db=ET.fromstring("""<db><relates><relate><relatenm>인터파크 예매</relatenm>
        <relateurl>https://ticket.interpark.com/goods/202612</relateurl></relate></relates></db>""")
        self.assertIn("ticket.interpark.com",module.ticket_url(db))
        db.find(".//relateurl").text="https://invalid.example/book"
        self.assertEqual(module.ticket_url(db),"")

    def test_date_parser(self):
        self.assertEqual(module.iso_date("2026.12.06"),"2026-12-06")
        self.assertEqual(module.iso_date("2026.13.01"),"")

if __name__=="__main__":
    unittest.main()
