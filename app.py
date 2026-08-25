"""KIA Japan Voice Intelligence — Streamlit composition root."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import base64
import sys
from typing import Optional, Tuple

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import streamlit as st

from japan_voice.analysis.google_client import GoogleGeminiClient
from japan_voice.analysis.schemas import AnalysisResult
from japan_voice.analysis.service import StructuredAnalysisService
from japan_voice.application.collection_service import CollectionOrchestrator
from japan_voice.application.models import RunResult
from japan_voice.application.pipeline import ProcessingPipeline
from japan_voice.application.video_analyzer import YouTubeVideoAnalyzerCollector, extract_youtube_video_id
from japan_voice.collectors.youtube import YouTubeCollector
from japan_voice.collectors.yahoo_japan import YahooJapanCollector
from japan_voice.collectors.minkara import MinkaraCollector
from japan_voice.config.settings import get_secret, load_settings
from japan_voice.domain.enums import CollectorStatus, Source
from japan_voice.domain.requests import SearchRequest
from japan_voice.infrastructure.http import HttpClient, HttpClientConfig
from japan_voice.ui.theme import CSS
from japan_voice.ui.views import render_minkara, render_overview, render_raw, render_video_analyzer_result, render_yahoo, render_youtube


st.set_page_config(page_title="KIA Japan Market Dashboard", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")
st.markdown(CSS, unsafe_allow_html=True)
SETTINGS = load_settings(load_dotenv_file=True)
ANALYSIS_RESULT_VERSION = 6
VIDEO_ANALYZER_RESULT_VERSION = 6

# Streamlit preserves session_state across source hot-reloads. Do not keep an
# unavailable aggregate produced by an older response contract.
if st.session_state.get("analysis_result_version") != ANALYSIS_RESULT_VERSION:
    previous = st.session_state.get("analysis_result")
    if previous is not None and not previous.aggregate_available:
        st.session_state.pop("analysis_result", None)
        st.session_state.pop("last_successful_run", None)
    st.session_state.analysis_result_version = ANALYSIS_RESULT_VERSION
if st.session_state.get("video_analyzer_result_version") != VIDEO_ANALYZER_RESULT_VERSION:
    st.session_state.pop("video_analyzer_run", None)
    st.session_state.pop("video_analyzer_analysis", None)
    st.session_state.pop("video_analyzer_id", None)
    st.session_state.video_analyzer_result_version = VIDEO_ANALYZER_RESULT_VERSION


@st.cache_data(ttl=SETTINGS.cache_ttl_seconds, max_entries=12, show_spinner=False)
def collect_and_process(keyword: str, start_date: date, end_date: date, max_results: int, source_values: Tuple[str, ...]) -> RunResult:
    selected_sources = [Source(value) for value in source_values]
    request = SearchRequest(keyword=keyword, start_date=start_date, end_date=end_date,
        selected_sources=selected_sources, max_results=max_results)
    http = HttpClient(HttpClientConfig.from_settings(SETTINGS))
    try:
        collectors = []
        if Source.YOUTUBE in selected_sources:
            collectors.append(YouTubeCollector(http=http, settings=SETTINGS, api_key=get_secret("YOUTUBE_API_KEY")))
        if Source.YAHOO_JAPAN in selected_sources:
            collectors.append(YahooJapanCollector(http=http, settings=SETTINGS))
        if Source.MINKARA in selected_sources:
            collectors.append(MinkaraCollector(http=http, settings=SETTINGS))
        collection = CollectionOrchestrator(collectors, max_queries_per_source=SETTINGS.max_query_variants_per_source).collect(request)
        return ProcessingPipeline().process(collection, request)
    finally:
        http.close()


def execute_run(keyword: str, start_date: date, end_date: date, max_results: int, source_values: Tuple[str, ...]) -> Tuple[RunResult, Optional[AnalysisResult]]:
    """Analyze on explicit submit; never reuse a cached aggregate fallback."""
    run = collect_and_process(keyword, start_date, end_date, max_results, source_values)
    if not run.eligible_records or not get_secret("GEMINI_API_KEY"):
        return run, None
    try:
        gemini = GoogleGeminiClient.from_settings(SETTINGS, api_key=get_secret("GEMINI_API_KEY"))
    except Exception:
        return run, None
    try:
        try:
            analysis = StructuredAnalysisService(gemini, batch_size=SETTINGS.gemini_batch_size).analyze(run)
        except Exception:
            # Collection is still a useful result. A provider/schema failure
            # must not turn a completed keyword search into a failed run.
            analysis = None
        return run, analysis
    finally:
        if gemini is not None:
            gemini.close()


@st.cache_data(ttl=SETTINGS.cache_ttl_seconds, max_entries=8, show_spinner=False)
def execute_video_analyzer(video_id: str, result_version: int) -> Tuple[RunResult, Optional[AnalysisResult]]:
    http = HttpClient(HttpClientConfig.from_settings(SETTINGS))
    try:
        run = YouTubeVideoAnalyzerCollector(
            http=http, settings=SETTINGS, api_key=get_secret("YOUTUBE_API_KEY")
        ).collect(video_id)
    finally:
        http.close()
    if not run.consumer_voice_records or not get_secret("GEMINI_API_KEY"):
        return run, None
    try:
        gemini = GoogleGeminiClient.from_settings(SETTINGS, api_key=get_secret("GEMINI_API_KEY"))
    except Exception:
        return run, None
    try:
        try:
            analysis = StructuredAnalysisService(
                gemini, batch_size=SETTINGS.gemini_batch_size
            ).analyze(run)
        except Exception:
            analysis = None
        return run, analysis
    finally:
        gemini.close()


def header() -> None:
    logo = ROOT / "kia_logo.png"
    logo_html = ""
    if logo.exists():
        encoded = base64.b64encode(logo.read_bytes()).decode("ascii")
        logo_html = f'<img class="brand-logo" src="data:image/png;base64,{encoded}" alt="KIA">'
    run = st.session_state.get("last_successful_run")
    updated = run.completed_at.astimezone().strftime("%Y-%m-%d %H:%M") if run else "—"
    status = "Ready" if run else "Awaiting analysis"
    st.markdown(
        f'<div class="brand-shell"><div>{logo_html}</div><div><div class="brand-title">KIA Japan Market Dashboard</div>'
        f'<div class="brand-subtitle">Japan Market Social Listening & Consumer Voice Intelligence</div></div>'
        f'<div class="status-grid"><span class="key">Last updated</span><span class="value">{updated} JST</span>'
        f'<span class="key">Sources</span><span class="value">3 Active</span><span class="key">Status</span>'
        f'<span class="value"><i class="status-ready"></i>{status}</span></div></div>', unsafe_allow_html=True,
    )


header()
today = date.today()
with st.form("market-search", clear_on_submit=False):
    cols = st.columns([2.1, 1.25, 1.25, 1.45, 1.6])
    keyword = cols[0].text_input("Keyword", value=st.session_state.get("keyword", "PV5"), placeholder="Search KIA, PV5, キア...")
    start = cols[1].date_input("Start Date", value=today - timedelta(days=SETTINGS.default_date_range_days))
    end = cols[2].date_input("End Date", value=today)
    selected_labels = cols[3].multiselect("Source", ["YouTube", "Yahoo Japan", "みんカラ"], default=["YouTube", "Yahoo Japan"])
    submitted = cols[4].form_submit_button("ANALYZE MARKET VOICE", width="stretch")

if submitted:
    if not keyword.strip(): st.error("Keyword를 입력해주세요.")
    elif end < start: st.error("End Date는 Start Date보다 빠를 수 없습니다.")
    elif not selected_labels: st.error("하나 이상의 Source를 선택해주세요.")
    else:
        st.session_state.keyword = keyword
        try:
            with st.status("Japan Market Voice 분석을 시작합니다...", expanded=True) as status:
                st.write("Collecting Japan market data...")
                st.write("Filtering Japan-relevant content...")
                st.write("Analyzing consumer voice and generating insights...")
                source_map = {"YouTube": Source.YOUTUBE.value, "Yahoo Japan": Source.YAHOO_JAPAN.value, "みんカラ": Source.MINKARA.value}
                source_values = tuple(source_map[label] for label in selected_labels)
                # Bound interactive runs even when a deployment still carries
                # yesterday's overly large YOUTUBE_MAX_VIDEOS setting.
                run, analysis = execute_run(keyword, start, end, min(SETTINGS.youtube_max_videos, 20), source_values)
                st.session_state.last_successful_run = run
                st.session_state.analysis_result = analysis
                st.session_state.analysis_result_version = ANALYSIS_RESULT_VERSION
                status.update(label="Dashboard가 준비되었습니다.", state="complete", expanded=False)
        except Exception as error:
            # Never expose credentials, response bodies, or a traceback.  A
            # stable error category is enough to distinguish quota, timeout,
            # authentication, and structured-output failures in production.
            safe_type = getattr(error, "error_type", "unknown_error")
            st.error(
                "분석 실행에 실패했습니다. "
                f"오류 유형: {safe_type}. 이전 결과는 유지됩니다."
            )

run = st.session_state.get("last_successful_run")
analysis = st.session_state.get("analysis_result")
tabs = st.tabs(["Overview", "YouTube", "YouTube Video Analyzer", "Yahoo Japan", "みんカラ", "Raw Data"])
with tabs[0]:
    if run is None:
        st.markdown('<div class="empty-shell"><h2>Discover Japan Market Voice</h2><p>브랜드 또는 제품 키워드를 입력하여 일본 온라인 소비자 반응을 분석하세요.</p><p>Try: PV5 / KIA / キア</p></div>', unsafe_allow_html=True)
    else:
        render_overview(run, analysis)
with tabs[1]:
    if run is None: st.info("먼저 Market Voice 분석을 실행해주세요.")
    else: render_youtube(run, analysis)
with tabs[2]:
    st.markdown('<div class="section-kicker">Direct Video Analysis</div><div class="section-title">YouTube Video Analyzer</div><div class="section-subtitle">특정 YouTube 영상의 댓글을 분석해 소비자 반응과 핵심 이슈를 빠르게 확인합니다.</div>', unsafe_allow_html=True)
    with st.form("youtube-video-analyzer-form", clear_on_submit=False):
        video_url = st.text_input("YouTube Video URL", placeholder="https://www.youtube.com/watch?v=VIDEO_ID")
        analyze_video = st.form_submit_button("영상 댓글 분석", width="stretch")
    if analyze_video:
        try:
            video_id = extract_youtube_video_id(video_url)
            with st.status("영상 정보를 확인하고 있습니다...", expanded=True) as analyzer_status:
                st.write("공개 댓글을 수집하고 있습니다...")
                st.write("댓글 감성과 주요 Topic을 분석하고 있습니다...")
                st.write("핵심 인사이트를 생성하고 있습니다...")
                video_run, video_analysis = execute_video_analyzer(video_id, VIDEO_ANALYZER_RESULT_VERSION)
                st.session_state.video_analyzer_run = video_run
                st.session_state.video_analyzer_analysis = video_analysis
                st.session_state.video_analyzer_id = video_id
                analyzer_status.update(label="영상 댓글 분석이 완료되었습니다.", state="complete", expanded=False)
        except ValueError as error:
            st.error(str(error))
        except Exception as error:
            safe_type = getattr(error, "error_type", "unknown_error")
            st.error(f"영상 분석을 완료하지 못했습니다. 오류 유형: {safe_type}")
    video_run = st.session_state.get("video_analyzer_run")
    if video_run is not None:
        render_video_analyzer_result(video_run, st.session_state.get("video_analyzer_analysis"))
with tabs[3]:
    if run is None: st.info("먼저 Market Voice 분석을 실행해주세요.")
    else: render_yahoo(run, analysis)
with tabs[4]:
    if run is None: st.info("먼저 Market Voice 분석을 실행해주세요.")
    else: render_minkara(run, analysis)
with tabs[5]:
    if run is None: st.info("먼저 Market Voice 분석을 실행해주세요.")
    else: render_raw(run, analysis)

if run is not None:
    failed = [r for r in run.collector_results if r.status is CollectorStatus.FAILED]
    for result in failed:
        st.warning(f"{result.source.value.title()} 데이터 수집에 실패했습니다. 오류 유형: {result.error_type or 'unknown_error'}")
    if not run.eligible_records:
        st.info("선택한 기간과 키워드에 해당하는 Japan Market 데이터를 찾지 못했습니다.")
