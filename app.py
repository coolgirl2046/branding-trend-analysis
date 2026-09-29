"""Interactive Streamlit dashboard for Mission 1 analysis results."""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
from matplotlib import font_manager
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from dashboard_data import (
    DATA_PATH,
    KEYWORDS,
    build_statistics,
    filter_trend_data,
    load_trend_data,
    selected_data_to_csv,
)


COLORS = {
    "퍼스널브랜딩": "#60A5FA",
    "이미지메이킹": "#34D399",
    "스피치": "#FB7185",
}

WINDOWS_KOREAN_FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/malgun.ttf"),
    Path("C:/Windows/Fonts/gulim.ttc"),
    Path("C:/Windows/Fonts/batang.ttc"),
)


def load_korean_font() -> font_manager.FontProperties:
    """Load an installed Korean font without depending on Matplotlib's cache."""
    for font_path in WINDOWS_KOREAN_FONT_CANDIDATES:
        if font_path.is_file():
            font_manager.fontManager.addfont(str(font_path))
            return font_manager.FontProperties(fname=str(font_path))
    return font_manager.FontProperties(family="sans-serif")


KOREAN_FONT = load_korean_font()


st.set_page_config(
    page_title="브랜딩 검색 관심도 대시보드",
    page_icon="📈",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def get_dashboard_data() -> pd.DataFrame:
    return load_trend_data(DATA_PATH)


def create_trend_figure(
    filtered_data: pd.DataFrame,
    selected_keywords: list[str],
) -> plt.Figure:
    with plt.style.context("dark_background"), plt.rc_context(
        {
            "font.family": KOREAN_FONT.get_name(),
            "axes.unicode_minus": False,
        }
    ):
        figure, axis = plt.subplots(figsize=(14, 6.5))
        figure.patch.set_facecolor("#0B1120")
        axis.set_facecolor("#111827")

        for keyword in selected_keywords:
            color = COLORS[keyword]
            axis.plot(
                filtered_data["날짜"],
                filtered_data[keyword],
                color=color,
                alpha=0.32,
                linewidth=1.1,
                label=f"{keyword} 원자료",
            )
            axis.plot(
                filtered_data["날짜"],
                filtered_data[f"{keyword}_4주이동평균"],
                color=color,
                linewidth=2.4,
                label=f"{keyword} 4주 이동평균",
            )

        axis.set_title(
            "선택 기간의 주간 검색 관심도와 4주 이동평균",
            pad=16,
            fontproperties=KOREAN_FONT,
        )
        axis.set_xlabel("날짜", fontproperties=KOREAN_FONT)
        axis.set_ylabel("상대 검색 관심도 지수", fontproperties=KOREAN_FONT)
        axis.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=12))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        axis.grid(color="#64748B", alpha=0.25)
        axis.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, -0.16),
            ncol=2,
            prop=KOREAN_FONT,
        )
        figure.autofmt_xdate(rotation=35)
        figure.tight_layout()
        return figure


def main() -> None:
    st.title("브랜딩 검색 관심도 대시보드")
    st.caption(
        "네이버 데이터랩의 값은 실제 검색량이 아니라 "
        "조회 조건 안에서 비교하는 상대적 검색 관심도 지수입니다."
    )

    try:
        data = get_dashboard_data()
    except (FileNotFoundError, OSError, ValueError):
        st.error("분석 데이터 파일을 읽거나 검증하지 못했습니다.")
        st.stop()

    minimum_date = data["날짜"].min().date()
    maximum_date = data["날짜"].max().date()

    with st.sidebar:
        st.header("조회 조건")
        start_date = st.date_input(
            "시작일",
            value=minimum_date,
            min_value=minimum_date,
            max_value=maximum_date,
        )
        end_date = st.date_input(
            "종료일",
            value=maximum_date,
            min_value=minimum_date,
            max_value=maximum_date,
        )
        selected_keywords = st.multiselect(
            "키워드",
            options=list(KEYWORDS),
            default=list(KEYWORDS),
        )
        st.info(
            "기간과 키워드를 변경하면 그래프, 통계표, CSV 대상이 함께 갱신됩니다."
        )

    if start_date > end_date:
        st.error("시작일은 종료일보다 늦을 수 없습니다.")
        st.stop()

    if not selected_keywords:
        st.warning("하나 이상의 키워드를 선택해 주세요.")
        st.stop()

    filtered_data = filter_trend_data(
        data,
        start_date,
        end_date,
        selected_keywords,
    )
    if filtered_data.empty:
        st.warning("선택 조건에 해당하는 데이터가 없습니다.")
        st.stop()

    metric_columns = st.columns(4)
    metric_columns[0].metric("주간 관측 시점", f"{len(filtered_data):,}개")
    metric_columns[1].metric("선택 키워드", f"{len(selected_keywords)}개")
    metric_columns[2].metric(
        "조회 시작일",
        f"{filtered_data['날짜'].min():%Y-%m-%d}",
    )
    metric_columns[3].metric(
        "조회 종료일",
        f"{filtered_data['날짜'].max():%Y-%m-%d}",
    )

    st.subheader("시계열 그래프")
    figure = create_trend_figure(filtered_data, selected_keywords)
    st.pyplot(figure, width="stretch")
    plt.close(figure)
    st.caption(
        "4주 이동평균은 전체 시계열에서 먼저 계산한 뒤 선택 기간을 표시하므로, "
        "기간 시작점에서도 가능한 경우 직전 주 데이터가 반영됩니다."
    )

    st.subheader("선택 조건 통계")
    statistics = build_statistics(filtered_data, selected_keywords)
    st.dataframe(
        statistics.style.format(precision=3, na_rep="-"),
        width="stretch",
    )

    csv_bytes = selected_data_to_csv(filtered_data, selected_keywords)
    csv_name = f"branding_trend_{start_date:%Y%m%d}_{end_date:%Y%m%d}.csv"
    st.download_button(
        "선택 데이터 CSV 다운로드",
        data=csv_bytes,
        file_name=csv_name,
        mime="text/csv",
        width="stretch",
    )

    with st.expander("선택 데이터 미리보기"):
        preview = filtered_data[["날짜", *selected_keywords]].copy()
        preview["날짜"] = preview["날짜"].dt.strftime("%Y-%m-%d")
        st.dataframe(preview, width="stretch", hide_index=True)

    st.warning(
        "이 지수는 절대 검색 건수, 시장 규모 또는 검색 점유율을 의미하지 않으며, "
        "관심도 변화의 원인을 데이터만으로 단정할 수 없습니다."
    )


if __name__ == "__main__":
    main()
