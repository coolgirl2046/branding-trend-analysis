"""Reusable data loading and analysis helpers for the Streamlit dashboard."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
DATA_PATH = PROJECT_DIR / "data" / "datalab.xlsx"

KEYWORDS = ("퍼스널브랜딩", "이미지메이킹", "스피치")
EXPECTED_HEADERS = (
    "날짜",
    "퍼스널브랜딩",
    "날짜",
    "이미지메이킹",
    "날짜",
    "스피치",
)
SOURCE_COLUMNS = (
    "날짜_퍼스널브랜딩",
    "퍼스널브랜딩",
    "날짜_이미지메이킹",
    "이미지메이킹",
    "날짜_스피치",
    "스피치",
)
DATE_COLUMNS = (
    "날짜_퍼스널브랜딩",
    "날짜_이미지메이킹",
    "날짜_스피치",
)


def load_trend_data(path: str | Path = DATA_PATH) -> pd.DataFrame:
    """Load and validate the Naver DataLab workbook using the notebook rules."""

    source_path = Path(path)
    raw = pd.read_excel(
        source_path,
        sheet_name="개요",
        header=None,
        engine="openpyxl",
    )

    if raw.shape[0] < 8 or raw.shape[1] < 6:
        raise ValueError("원본 데이터 구조가 예상보다 작습니다.")

    headers = tuple(raw.iloc[6, :6].tolist())
    if headers != EXPECTED_HEADERS:
        raise ValueError("원본 데이터 헤더 구조가 예상과 다릅니다.")

    clean_source = raw.iloc[7:, :6].copy()
    clean_source.columns = SOURCE_COLUMNS
    clean_source = clean_source.reset_index(drop=True)

    parsed_dates = clean_source[list(DATE_COLUMNS)].apply(
        lambda column: pd.to_datetime(
            column,
            format="%Y-%m-%d",
            errors="coerce",
        )
    )
    if parsed_dates.isna().any().any():
        raise ValueError("날짜 변환에 실패한 데이터가 있습니다.")

    matching_dates = parsed_dates.nunique(axis=1, dropna=False).eq(1)
    if not matching_dates.all():
        raise ValueError("세 키워드의 날짜 열이 서로 일치하지 않습니다.")

    data = pd.DataFrame({"날짜": parsed_dates[DATE_COLUMNS[0]]})
    for keyword in KEYWORDS:
        data[keyword] = pd.to_numeric(clean_source[keyword], errors="coerce")

    if data.isna().any().any():
        raise ValueError("날짜 또는 관심도 값 변환에 실패했습니다.")

    data = data.sort_values("날짜").reset_index(drop=True)
    if data["날짜"].duplicated().any():
        raise ValueError("중복 날짜가 있습니다.")

    date_gaps = data["날짜"].diff().dropna().dt.days
    if not date_gaps.eq(7).all():
        raise ValueError("주간 간격이 아닌 데이터가 있습니다.")

    for keyword in KEYWORDS:
        if not data[keyword].between(0, 100).all():
            raise ValueError("상대 검색 관심도 범위를 벗어난 값이 있습니다.")
        data[f"{keyword}_4주이동평균"] = (
            data[keyword].rolling(window=4, min_periods=4).mean()
        )

    return data


def filter_trend_data(
    data: pd.DataFrame,
    start_date: date | pd.Timestamp,
    end_date: date | pd.Timestamp,
    selected_keywords: Sequence[str],
) -> pd.DataFrame:
    """Return an inclusive date range with selected raw and moving-average data."""

    selected = list(selected_keywords)
    invalid_keywords = [keyword for keyword in selected if keyword not in KEYWORDS]
    if invalid_keywords:
        raise ValueError("지원하지 않는 키워드가 선택되었습니다.")
    if not selected:
        raise ValueError("하나 이상의 키워드를 선택해야 합니다.")

    start = pd.Timestamp(start_date).normalize()
    end = pd.Timestamp(end_date).normalize()
    if start > end:
        raise ValueError("시작일은 종료일보다 늦을 수 없습니다.")

    columns = [
        "날짜",
        *selected,
        *(f"{keyword}_4주이동평균" for keyword in selected),
    ]
    mask = data["날짜"].between(start, end, inclusive="both")
    return data.loc[mask, columns].reset_index(drop=True)


def build_statistics(
    filtered_data: pd.DataFrame,
    selected_keywords: Sequence[str],
) -> pd.DataFrame:
    """Calculate descriptive statistics for the currently filtered data."""

    selected = list(selected_keywords)
    if filtered_data.empty:
        return pd.DataFrame()

    rows: list[dict[str, float | int | str]] = []
    for keyword in selected:
        values = filtered_data[keyword]
        rows.append(
            {
                "키워드": keyword,
                "관측 수": int(values.count()),
                "평균": float(values.mean()),
                "표준편차": float(values.std(ddof=1)),
                "최솟값": float(values.min()),
                "중앙값": float(values.median()),
                "최댓값": float(values.max()),
                "기간 시작값": float(values.iloc[0]),
                "기간 종료값": float(values.iloc[-1]),
                "기간 증감": float(values.iloc[-1] - values.iloc[0]),
            }
        )

    statistics = pd.DataFrame(rows).set_index("키워드")
    numeric_columns = statistics.select_dtypes(include="number").columns
    statistics[numeric_columns] = statistics[numeric_columns].round(3)
    statistics["관측 수"] = statistics["관측 수"].astype(int)
    return statistics


def selected_data_to_csv(
    filtered_data: pd.DataFrame,
    selected_keywords: Sequence[str],
) -> bytes:
    """Export only the selected raw observations as an Excel-friendly UTF-8 CSV."""

    export_data = filtered_data[["날짜", *selected_keywords]].copy()
    export_data["날짜"] = export_data["날짜"].dt.strftime("%Y-%m-%d")
    return export_data.to_csv(index=False).encode("utf-8-sig")
