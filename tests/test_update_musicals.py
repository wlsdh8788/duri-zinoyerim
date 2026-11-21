"""뮤지컬 선별 기준의 회귀 테스트 (외부 API 호출 없음)."""
import importlib.util
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("update_musicals",ROOT/"scripts"/"update_musicals.py")
mus=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mus)

class MusicalTests(unittest.TestCase):
    def test_bracketed_death_note_title_matches(self):
        self.assertTrue(mus.title_matches("뮤지컬 <데스노트> [서울]",["데스노트"],[]))
        self.assertFalse(mus.title_matches("어린이 뮤지컬 <데스노트>",["데스노트"],["어린이"]))

    def test_celebrity_actor_exact_names(self):
        stars=["김준수","규현","카이"]
        self.assertEqual(mus.recognized_actors("김준수, 조형균, 규현 (라이토)",stars),["김준수","규현"])
        self.assertEqual(mus.recognized_actors("카이라, 아무개",stars),[])

    def test_reject_non_musical_and_no_star(self):
        event={"id":"kopis-PF123456","title":"뮤지컬 <데스노트>","start":"2026-12-01","end":"2027-02-01","province":"서울","city":"서울"}
        root=ET.fromstring("<db><genrenm>뮤지컬</genrenm><prfnm>뮤지컬 &lt;데스노트&gt;</prfnm><prfcast>김준수, 이영미</prfcast></db>")
        valid=mus.build_musical(event,root,["김준수"])
        self.assertEqual(valid["featuredCast"],["김준수"])
        self.assertIn("데스노트",valid["title"])
        root.find("genrenm").text="연극"
        self.assertIsNone(mus.build_musical(event,root,["김준수"]))
        root.find("genrenm").text="뮤지컬"
        self.assertIsNone(mus.build_musical(event,root,["규현"]))

    def test_ticket_link_needs_verified_domain(self):
        root=ET.fromstring("<db><relates><relate><relatenm>예매처</relatenm><relateurl>https://ticketlink.co.kr/product/123</relateurl></relate></relates></db>")
        self.assertIn("ticketlink.co.kr", mus.ticket_url_from_detail(root))
        root.find(".//relateurl").text="https://random.example/123"
        self.assertEqual(mus.ticket_url_from_detail(root),"")

if __name__=="__main__":
    unittest.main()
