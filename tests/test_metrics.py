import unittest
from scripts.generate_metrics import aggregate, parse_calendar, render


class MetricsTests(unittest.TestCase):
    def test_calendar_joins_tooltips_by_id_and_sorts_dates(self):
        html = '''<td data-date="2026-10-25" id="b" data-level="0"></td>
        <td id="a" data-level="4" data-date="2026-10-24"></td>
        <tool-tip for="a">1,234 contributions on October 24th.</tool-tip>
        <tool-tip for="b">No contributions on October 25th.</tool-tip>'''
        self.assertEqual(parse_calendar(html), [
            {"date": "2026-10-24", "count": 1234, "level": 4},
            {"date": "2026-10-25", "count": 0, "level": 0},
        ])

    def test_calendar_rejects_unknown_markup_instead_of_inventing_zero(self):
        with self.assertRaises(ValueError):
            parse_calendar('<td id="a" data-date="2026-10-25" data-level="0"></td>')

    def test_aggregation_excludes_forks_and_uses_sao_paulo_push_hour(self):
        data = {
            "repos": [
                {"fork": False, "stars": 2, "forks": 1, "languages": {"Python": 30}},
                {"fork": False, "stars": 0, "forks": 0, "languages": {"Python": 10, "Go": 10}},
                {"fork": True, "stars": 99, "forks": 99, "languages": {"Java": 999}},
            ],
            "events": [
                {"type": "PushEvent", "created_at": "2026-10-25T02:00:00Z"},
                {"type": "CreateEvent", "created_at": "2026-10-25T12:00:00Z"},
            ],
            "days": [{"date": "2026-10-24", "count": 5, "level": 2}],
        }
        result = aggregate(data)
        self.assertEqual(result["languages"], [("Python", 40), ("Go", 10)])
        self.assertEqual(result["hours"][23], 1)
        self.assertEqual(sum(result["hours"]), 1)
        self.assertEqual(result["weekdays"], [0, 0, 0, 0, 0, 0, 5])
        self.assertEqual((result["contributions"], result["stars"], result["forks"]), (5, 2, 1))

    def test_empty_activity_renders_valid_svg_and_escapes_profile_name(self):
        from xml.etree import ElementTree
        data = {"username": "FelipeNCampos", "collected_at": "2026-10-25T03:00:00Z",
                "profile": {"name": "A & <B>", "followers": 2},
                "repos": [], "events": [],
                "days": [{"date": "2026-10-25", "count": 0, "level": 0}]}
        svg = render(data)
        ElementTree.fromstring(svg)
        self.assertIn("A &amp; &lt;B&gt;", svg)
        self.assertIn("Sem eventos de push na amostra", svg)
        self.assertIn("Sem linguagens disponíveis", svg)


if __name__ == "__main__":
    unittest.main()
