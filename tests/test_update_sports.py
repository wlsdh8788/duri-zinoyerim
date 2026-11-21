import importlib.util
import sys
import unittest
from pathlib import Path
from datetime import date
from tempfile import TemporaryDirectory
import json

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("update_sports", ROOT / "scripts" / "update_sports.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class SportsTests(unittest.TestCase):
    def test_parse_official_gangneung_home(self):
        html = """<html><body><h2>경기일정</h2><p>2026 11</p>
        <p>11/21 (토) 16:30</p><p>강릉하이원</p>
        <img alt="강원"><p>강원</p><span>VS</span><img alt="대전">
        <p>대전</p><p>하나은행 K리그1 2026</p></body></html>"""
        fixtures = mod.parse_gangwon_tokens(mod.collect_tokens(html), today=date(2026, 11, 20))
        self.assertEqual(len(fixtures), 1)
        self.assertEqual(fixtures[0]["home"], "강원FC")
        self.assertEqual(fixtures[0]["away"], "대전하나시티즌")
        self.assertEqual(fixtures[0]["localHome"], "강릉")
        self.assertEqual(fixtures[0]["date"], "2026-11-21")

    def test_not_infer_local_venue_from_club(self):
        item = mod.classify({"teamGroup":"gangwon","home":"강원FC","away":"인천 유나이티드","venue":""})
        self.assertTrue(item["isHome"])
        self.assertEqual(item["localHome"], "")
        self.assertEqual(item["ticketStatus"], "unconfirmed")

    def test_overseas_korea_not_domestic(self):
        item = mod.classify({"teamGroup":"national","home":"대한민국","away":"카타르","venue":"카타르 도하"})
        self.assertFalse(item["domesticNational"])
        self.assertFalse(item["ticketInfoUrl"])

    def test_failure_fallback_and_duplicate_merge(self):
        orig = [{"id":"x","teamGroup":"gangwon","date":"2026-11-21","time":"16:30","home":"강원FC","away":"대전하나시티즌","venue":""}]
        fresh = [{"id":"y","teamGroup":"gangwon","date":"2026-11-21","time":"16:30","home":"강원FC","away":"대전하나시티즌","venue":"강릉하이원아레나"}]
        merged, changed=mod.merge(orig,fresh,date(2026,11,20))
        self.assertEqual(len(merged),1)
        self.assertEqual(merged[0]["id"],"x")
        self.assertEqual(merged[0]["localHome"],"강릉")
        self.assertEqual(changed,1)

    def test_ticket_override_requires_official_announcement(self):
        matches=[mod.classify({"id":"x","teamGroup":"gangwon","date":"2026-11-21","home":"강원FC","away":"대전하나시티즌","venue":"강릉"})]
        with TemporaryDirectory() as d:
            file=Path(d)/"ticket.json"
            file.write_text(json.dumps({"matches":{"x":{"ticketOpenAt":"2026-11-18T14:00+09:00","announcementUrl":"https://example.com"}}}))
            self.assertEqual(mod.apply_ticket_overrides(matches,file),0)
            file.write_text(json.dumps({"matches":{"x":{"ticketOpenAt":"2026-11-18T14:00+09:00","announcementUrl":"https://gangwon-fc.com/news/123"}}}))
            self.assertEqual(mod.apply_ticket_overrides(matches,file),1)
            self.assertEqual(matches[0]["ticketStatus"],"announced")

if __name__ == "__main__":
    unittest.main()
