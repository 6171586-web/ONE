import re
import unittest
from decimal import Decimal

from buyback_monitor.hkex import parse_section_two_entry, parse_textual_date


class ParsingTest(unittest.TestCase):
    def test_parse_textual_date(self):
        match = re.search(r"Date Submitted:\s*([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})", "Date Submitted: 12 June 2026")
        self.assertEqual(parse_textual_date(match), "2026-06-12")

    def test_parse_section_two_entry(self):
        text = (
            "Date Submitted: 12 June 2026 Section II 1). 12 June 2026 "
            "2,637,700 On the Exchange HKD 57.85 HKD 54.2 HKD 149,976,456.76 "
            "Total number of shares repurchased 2,637,700"
        )
        entry = parse_section_two_entry(text, "2026-06-12")
        self.assertEqual(
            entry,
            (
                "2026-06-12",
                Decimal("2637700"),
                Decimal("57.85"),
                Decimal("54.2"),
                Decimal("149976456.76"),
                "HKD",
            ),
        )


if __name__ == "__main__":
    unittest.main()
