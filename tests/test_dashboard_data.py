"""Automated checks for the Mission 1 dashboard data pipeline."""

from __future__ import annotations

import unittest

import pandas as pd

from dashboard_data import (
    DATA_PATH,
    KEYWORDS,
    build_statistics,
    filter_trend_data,
    load_trend_data,
    selected_data_to_csv,
)


class DashboardDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_trend_data(DATA_PATH)

    def test_source_data_matches_notebook_expectations(self) -> None:
        self.assertEqual(len(self.data), 186)
        self.assertEqual(self.data["날짜"].min(), pd.Timestamp("2023-01-02"))
        self.assertEqual(self.data["날짜"].max(), pd.Timestamp("2026-07-20"))
        self.assertEqual(tuple(self.data.columns[:4]), ("날짜", *KEYWORDS))
        for keyword in KEYWORDS:
            self.assertTrue(self.data[keyword].between(0, 100).all())
            self.assertIn(f"{keyword}_4주이동평균", self.data.columns)

    def test_date_and_keyword_filter_is_inclusive(self) -> None:
        filtered = filter_trend_data(
            self.data,
            pd.Timestamp("2024-01-01"),
            pd.Timestamp("2024-01-29"),
            ["퍼스널브랜딩", "스피치"],
        )
        self.assertEqual(filtered["날짜"].min(), pd.Timestamp("2024-01-01"))
        self.assertEqual(filtered["날짜"].max(), pd.Timestamp("2024-01-29"))
        self.assertEqual(len(filtered), 5)
        self.assertNotIn("이미지메이킹", filtered.columns)

    def test_statistics_follow_current_filter(self) -> None:
        selected = ["이미지메이킹"]
        filtered = filter_trend_data(
            self.data,
            pd.Timestamp("2025-01-06"),
            pd.Timestamp("2025-02-24"),
            selected,
        )
        statistics = build_statistics(filtered, selected)
        self.assertEqual(list(statistics.index), selected)
        self.assertEqual(int(statistics.loc["이미지메이킹", "관측 수"]), 8)
        self.assertAlmostEqual(
            float(statistics.loc["이미지메이킹", "평균"]),
            round(float(filtered["이미지메이킹"].mean()), 3),
        )

    def test_csv_contains_only_selected_raw_data(self) -> None:
        selected = ["퍼스널브랜딩", "스피치"]
        filtered = filter_trend_data(
            self.data,
            pd.Timestamp("2026-07-06"),
            pd.Timestamp("2026-07-20"),
            selected,
        )
        csv_bytes = selected_data_to_csv(filtered, selected)
        self.assertTrue(csv_bytes.startswith(b"\xef\xbb\xbf"))
        csv_text = csv_bytes.decode("utf-8-sig")
        self.assertEqual(csv_text.splitlines()[0], "날짜,퍼스널브랜딩,스피치")
        self.assertNotIn("이미지메이킹", csv_text)
        self.assertEqual(len(csv_text.splitlines()), 4)

    def test_invalid_filter_conditions_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            filter_trend_data(
                self.data,
                pd.Timestamp("2025-02-01"),
                pd.Timestamp("2025-01-01"),
                ["스피치"],
            )
        with self.assertRaises(ValueError):
            filter_trend_data(
                self.data,
                self.data["날짜"].min(),
                self.data["날짜"].max(),
                [],
            )


if __name__ == "__main__":
    unittest.main()
