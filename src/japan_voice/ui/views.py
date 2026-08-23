"""Dashboard view helpers with no external side effects."""

from __future__ import annotations

from collections import Counter
from html import escape
from typing import Dict, Iterable, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from japan_voice.analysis.schemas import AnalysisResult, EvidenceFinding
from japan_voice.analysis.service import StructuredAnalysisService
from japan_voice.application.models import RunResult
from japan_voice.domain.enums import CollectorStatus, ContentGroup, ContentType, MinkaraSubSource, Sentiment, Source, YahooSubSource
from japan_voice.ui.metrics import dashboard_metrics, normalize_topic, youtube_video_audit


COLORS = {"positive": "#0B9F75", "neutral": "#AEB7C2", "negative": "#E54444", "unknown": "#DDE2E6"}
CHART_COLORS = ["#3157FF", "#0B9F75", "#F1A33C", "#E54444", "#7B61FF"]


def section(title: str, subtitle: str = "") -> None:
    st.markdown('<div class="section-kicker">Market Intelligence</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-title">{escape(title)}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="section-subtitle">{escape(subtitle)}</div>', unsafe_allow_html=True)


def metric_card(value: str, label: str, note: str = "", accent: str = "#3157FF") -> None:
    st.markdown(
        f'<div class="metric-card" style="--metric-accent:{accent}"><div class="metric-value">{escape(value)}</div>'
        f'<div class="metric-label">{escape(label)}</div><div class="metric-note">{escape(note)}</div></div>', unsafe_allow_html=True,
    )


def _analysis_map(analysis: Optional[AnalysisResult]) -> Dict[str, object]:
    return {item.record_id: item for item in analysis.record_analyses} if analysis else {}


def render_overview(run: RunResult, analysis: Optional[AnalysisResult]) -> None:
    metrics = dashboard_metrics(run, analysis)
    known_total = metrics.consumer_voices

    section("Executive Overview", "일본 시장의 핵심 반응을 한눈에 확인하세요.")
    youtube_videos = sum(
        r.source is Source.YOUTUBE and r.content_type is ContentType.VIDEO
        for r in run.eligible_records
    )
    yahoo_articles = sum(
        r.source is Source.YAHOO_JAPAN and r.content_type is ContentType.ARTICLE
        for r in run.eligible_records
    )
    cols = st.columns(5)
    values = [
        (f"{youtube_videos:,}", "YouTube Videos", "일본시장 적격 영상", "#3157FF"),
        (f"{yahoo_articles:,}", "Yahoo Articles", "일본시장 적격 기사", "#F1A33C"),
        (f"{known_total:,}", "Consumer Voices", "긍정·중립·부정으로 분석된 의견", "#7B61FF"),
        (f"{metrics.positive / known_total:.0%}" if known_total else "—", "Positive Sentiment", f"{metrics.positive:,} positive voices", "#0B9F75"),
        (f"{metrics.negative / known_total:.0%}" if known_total else "—", "Negative Sentiment", f"{metrics.negative:,} negative voices", "#E54444"),
    ]
    for col, (value, label, note, accent) in zip(cols, values):
        with col: metric_card(value, label, note, accent)

    left, right = st.columns([3, 2])
    with left:
        known_ids = set(metrics.consumer_record_ids)
        dated = [r for r in run.consumer_voice_records if r.id in known_ids and (r.analysis_date or r.published_at)]
        if dated:
            frame = pd.DataFrame({"Date": [(r.analysis_date or r.published_at).date() for r in dated], "Source": [r.source.value.title() for r in dated]})
            use_daily = (run.request.end_date - run.request.start_date).days <= 45
            period_column = "Day" if use_daily else "Week"
            frame[period_column] = pd.to_datetime(frame["Date"])
            if not use_daily:
                frame[period_column] = frame[period_column].dt.to_period("W-SUN").dt.start_time
            frame = frame.groupby([period_column, "Source"]).size().reset_index(name="Consumer Voices")
            title = "Daily Consumer Voice Trend" if use_daily else "Weekly Consumer Voice Trend"
            fig = px.line(frame, x=period_column, y="Consumer Voices", color="Source", markers=True, title=title,
                color_discrete_sequence=CHART_COLORS)
            fig.update_traces(line_width=3, marker_size=7)
            _chart_style(fig)
            st.plotly_chart(fig)
        else: st.info("기간 Trend를 표시할 날짜 데이터가 없습니다.")
    with right:
        counts = {"positive": metrics.positive, "neutral": metrics.neutral, "negative": metrics.negative}
        counts = {key: value for key, value in counts.items() if value}
        if counts:
            fig = go.Figure(go.Pie(labels=[k.title() for k in counts], values=list(counts.values()), hole=.72,
                marker_colors=[COLORS[k] for k in counts], textinfo="label+percent"))
            fig.update_layout(title="Consumer Sentiment", showlegend=False, height=390, margin=dict(l=20,r=20,t=60,b=20),
                annotations=[dict(text=f"{known_total}<br>VOICES", x=.5, y=.5, showarrow=False, font_size=18)])
            st.plotly_chart(fig)
        else: st.info("분석 가능한 Consumer Sentiment가 없습니다.")

    left, right = st.columns(2)
    with left:
        if metrics.voices_by_source:
            frame = pd.DataFrame([(source.value.title(), count) for source, count in metrics.voices_by_source.items()], columns=["Source", "Consumer Voices"]).sort_values("Consumer Voices")
            fig = px.bar(frame, x="Consumer Voices", y="Source", orientation="h", title="Consumer Voice by Source", color_discrete_sequence=["#3157FF"])
            _chart_style(fig); st.plotly_chart(fig)
    with right:
        if metrics.topics:
            frame = pd.DataFrame(metrics.topics.most_common(10), columns=["Topic", "Consumer Voices"]).sort_values("Consumer Voices")
            fig = px.bar(frame, x="Consumer Voices", y="Topic", orientation="h", title="Top Consumer Topics", color_discrete_sequence=["#0B9F75"])
            _chart_style(fig); st.plotly_chart(fig)
        else: st.info("표시할 Consumer Topic이 없습니다.")

    render_intelligence(analysis)


def _chart_style(fig: go.Figure) -> None:
    fig.update_layout(height=390, plot_bgcolor="white", paper_bgcolor="white", margin=dict(l=25,r=25,t=64,b=25),
        font=dict(color="#475467", family="Arial, sans-serif"), legend_title_text="",
        title_font=dict(size=17,color="#101828"), hoverlabel=dict(bgcolor="#101828",font_color="white",bordercolor="#101828"))
    fig.update_xaxes(showgrid=True, gridcolor="#EEF1F5", zeroline=False, title_text="")
    fig.update_yaxes(showgrid=False)


def _finding_list(items: Iterable[EvidenceFinding], empty: str = "현재 수집된 데이터만으로 판단하기 어려움") -> str:
    values = list(items)
    return "<ul>" + "".join(f"<li>{escape(v.text)}</li>" for v in values) + "</ul>" if values else f"<p>{empty}</p>"


def render_intelligence(analysis: Optional[AnalysisResult]) -> None:
    st.markdown('<div class="ai-zone"><div class="ai-kicker">GEMINI-POWERED INTELLIGENCE</div><div class="ai-title">AI Market Intelligence</div><div class="ai-subtitle">일본 소비자 Voice를 실행 가능한 마케팅 판단으로 전환합니다.</div></div>', unsafe_allow_html=True)
    if analysis is None:
        st.info("AI 분석 결과를 사용할 수 없습니다. 수집된 원본과 Audit 결과는 계속 확인할 수 있습니다.")
        return
    # Also reconcile session-resident results created before this policy was added.
    agg = StructuredAnalysisService.apply_majority_consistency(analysis.aggregate)
    if not analysis.aggregate_available:
        st.info("분석 가능한 Consumer Voice가 없습니다.")
    elif analysis.aggregate_status.value == "gemini":
        st.caption("AI Aggregate")
    else:
        st.caption("Aggregated from analyzed consumer records")
    overall = " ".join(item.text for item in agg.overall_voice) or "현재 수집된 데이터만으로 전체 반응을 판단하기 어려움"
    st.markdown(f'<div class="overall-card"><h4>Overall Voice</h4><p>{escape(overall)}</p></div>', unsafe_allow_html=True)
    cols = st.columns(2)
    cards = [("Positive Drivers", agg.positive_drivers, "intel-positive"), ("Key Concerns", agg.negative_drivers, "intel-negative")]
    for col, (title, items, css_class) in zip(cols, cards):
        with col: st.markdown(f'<div class="intel-card {css_class}"><h4>{title}</h4>{_finding_list(items)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="marketing-card"><h4>Marketing Implications</h4>{_finding_list(agg.marketing_insights)}</div>', unsafe_allow_html=True)
    if agg.representative_voc:
        section("Representative Consumer Voice", "실제 수집 Record를 근거로 검증된 한국어 요약입니다.")
        for voc in agg.representative_voc:
            st.markdown(f'<div class="voc-card"><div class="voc-quote">{escape(voc.korean_summary)}</div><div class="voc-meta">{escape(voc.source.value.title())} · 검증된 원문 기반 요약</div></div>', unsafe_allow_html=True)


def render_youtube(run: RunResult, analysis: Optional[AnalysisResult]) -> None:
    records = [r for r in run.eligible_records if r.source.value == "youtube"]
    videos = [r for r in records if r.content_type is ContentType.VIDEO]
    raw_comments = [r for r in run.raw_records if r.source is Source.YOUTUBE and r.content_type is ContentType.COMMENT]
    amap = _analysis_map(analysis)
    known_comments = [r for r in raw_comments if r.id in amap and amap[r.id].sentiment is not Sentiment.UNKNOWN and not r.duplicate_of]
    known = [amap[r.id] for r in known_comments]
    section("YouTube Intelligence", "영상은 Source Content, 댓글은 Consumer Voice로 구분합니다.")
    cols = st.columns(5)
    vals = [(len(videos),"Eligible Videos"),(len(raw_comments),"Raw Comments"),(len(known_comments),"Consumer Voices"),
        (f"{sum(a.sentiment is Sentiment.POSITIVE for a in known)/len(known):.0%}" if known else "—","Positive"),
        (f"{sum(a.sentiment is Sentiment.NEGATIVE for a in known)/len(known):.0%}" if known else "—","Negative")]
    for col,(v,l) in zip(cols,vals):
        with col: metric_card(str(v),l)
    if videos:
        audit = youtube_video_audit(run, analysis)
        rows = []
        for item in audit:
            video = next(v for v in videos if v.native_id == item["video_id"])
            child_ids = {r.id for r in known_comments if r.parent_id == video.id}
            topics = Counter(topic for record_id in child_ids for topic in amap[record_id].topics)
            rows.append({
                "Date": video.published_at.strftime("%Y-%m-%d") if video.published_at else None,
                "Video Title": video.title or "", "Displayed Comments": item["displayed_comment_count"],
                "Comments Collected": item["raw_comments_collected"],
                "Consumer Voices": item["consumer_voice_count"],
                "Sentiment Summary": f"P {item['positive_count']} · N {item['negative_count']} · Neutral {item['neutral_count']} · Unknown {item['unknown_count']}",
                "Top Topics": ", ".join(value for value, _ in topics.most_common(3)),
                "Stop Reason": item["collection_stop_reason"], "URL": str(video.url),
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True,
            column_config={"URL": st.column_config.LinkColumn("Original Link")})
    else: st.info("조건을 통과한 YouTube 영상이 없습니다.")
    if known_comments:
        section("Analyzed Consumer Voices", "Positive·Neutral·Negative로 분류된 공개 댓글")
        st.dataframe(_records_frame(known_comments, amap), width="stretch", hide_index=True, column_config={"URL": st.column_config.LinkColumn("Original Link")})


def render_video_analyzer_result(run: RunResult, analysis: Optional[AnalysisResult]) -> None:
    video = next((r for r in run.market_content_records if r.content_type is ContentType.VIDEO), None)
    if video is None:
        st.error("영상 정보를 표시할 수 없습니다.")
        return
    metadata = video.raw_metadata
    left, right = st.columns([3, 2])
    with left:
        st.video(str(video.url))
    with right:
        st.markdown(f"### {escape(video.title or '')}")
        st.caption(escape(video.author or "Unknown channel"))
        st.write(f"게시일: {video.published_at.strftime('%Y-%m-%d') if video.published_at else '—'}")
        st.write(f"조회수: {metadata.get('view_count') or 0:,}")
        st.write(f"좋아요: {metadata.get('like_count') or 0:,}")
        st.write(f"표시 댓글: {metadata.get('displayed_comment_count') or 0:,}")
    collector_meta = run.collector_results[0].metadata
    if run.collector_results[0].status is CollectorStatus.PARTIAL:
        st.warning("영상 정보는 확인했지만 댓글 일부 또는 전체를 수집하지 못했습니다.")
    if collector_meta.get("collection_stop_reason") == "technical_safety_limit":
        st.info(f"공개 댓글 중 최대 {collector_meta.get('raw_comments_collected', 0):,}건을 분석했습니다.")
    amap = _analysis_map(analysis)
    comments = list(run.consumer_voice_records)
    known = [amap[r.id] for r in comments if r.id in amap and amap[r.id].sentiment is not Sentiment.UNKNOWN]
    counts = Counter(item.sentiment for item in (amap[r.id] for r in comments if r.id in amap))
    voices = counts[Sentiment.POSITIVE] + counts[Sentiment.NEUTRAL] + counts[Sentiment.NEGATIVE]
    cols = st.columns(4)
    values = [
        (len(comments), "Raw Comments"), (voices, "Consumer Voices"),
        (f"{counts[Sentiment.POSITIVE]/voices:.0%}" if voices else "—", "Positive"),
        (f"{counts[Sentiment.NEGATIVE]/voices:.0%}" if voices else "—", "Negative"),
    ]
    for col, (value, label) in zip(cols, values):
        with col: metric_card(str(value), label)
    st.caption(f"Unknown comments: {counts[Sentiment.UNKNOWN]:,}")
    st.caption(
        f"Top-level {collector_meta.get('top_level_comments_collected', 0):,} · "
        f"Replies {collector_meta.get('replies_collected', 0):,}"
    )
    chart_left, chart_right = st.columns(2)
    sentiment_values = {"Positive": counts[Sentiment.POSITIVE], "Neutral": counts[Sentiment.NEUTRAL], "Negative": counts[Sentiment.NEGATIVE]}
    with chart_left:
        if voices:
            fig = go.Figure(go.Pie(labels=list(sentiment_values), values=list(sentiment_values.values()), hole=.72,
                marker_colors=[COLORS["positive"], COLORS["neutral"], COLORS["negative"]], textinfo="label+percent"))
            fig.update_layout(title="Consumer Sentiment", showlegend=False, height=390,
                annotations=[dict(text=f"{voices}<br>VOICES", x=.5, y=.5, showarrow=False, font_size=18)])
            st.plotly_chart(fig)
    with chart_right:
        distribution = sentiment_values | {"Unknown": counts[Sentiment.UNKNOWN]}
        frame = pd.DataFrame(distribution.items(), columns=["Sentiment", "Comments"])
        fig = px.bar(frame, x="Sentiment", y="Comments", title="Comment Sentiment Distribution",
            color="Sentiment", color_discrete_map={"Positive":COLORS["positive"],"Neutral":COLORS["neutral"],"Negative":COLORS["negative"],"Unknown":COLORS["unknown"]})
        _chart_style(fig); fig.update_layout(showlegend=False); st.plotly_chart(fig)
    topic_counts = Counter(normalize_topic(topic) for item in known for topic in item.topics if normalize_topic(topic))
    if topic_counts:
        frame = pd.DataFrame(topic_counts.most_common(10), columns=["Topic", "Comments"]).sort_values("Comments")
        fig = px.bar(frame, x="Comments", y="Topic", orientation="h", title="Top Consumer Topics", color_discrete_sequence=["#0B9F75"])
        _chart_style(fig); st.plotly_chart(fig)
    if analysis and voices:
        agg = StructuredAnalysisService.apply_majority_consistency(analysis.aggregate)
        section("AI Comment Insight", "선택한 영상의 실제 공개 댓글을 근거로 작성했습니다.")
        overall = " ".join(item.text for item in agg.overall_voice)
        st.markdown(f'<div class="overall-card"><h4>Overall Reaction</h4><p>{escape(overall)}</p></div>', unsafe_allow_html=True)
        cols = st.columns(2)
        for col, (title, items, css) in zip(cols, [("Positive Drivers",agg.positive_drivers,"intel-positive"),("Key Concerns",agg.negative_drivers,"intel-negative")]):
            with col: st.markdown(f'<div class="intel-card {css}"><h4>{title}</h4>{_finding_list(items)}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="marketing-card"><h4>Marketing Implications</h4>{_finding_list(agg.marketing_insights)}</div>', unsafe_allow_html=True)
        if agg.representative_voc:
            section("Representative Consumer Voice", "실제 댓글 원문과 검증된 한국어 요약")
            for voc in agg.representative_voc:
                record = next((r for r in comments if r.id == voc.record_id), None)
                item = amap.get(voc.record_id)
                if record:
                    st.markdown(f'<div class="voc-card"><div class="voc-quote">{escape(record.content)}</div><div>{escape(voc.korean_summary)}</div><div class="voc-meta">{item.sentiment.value.title() if item else "Unknown"} · 좋아요 {record.engagement_count or 0}</div></div>', unsafe_allow_html=True)
    if comments:
        section("Comment Explorer", "원문과 한국어 번역을 함께 확인하세요.")
        sentiments = ["all"] + [s.value for s in Sentiment]
        selected_sentiment = st.selectbox("Sentiment", sentiments, key="video_analyzer_sentiment")
        available_topics = sorted({normalize_topic(t) for item in known for t in item.topics if normalize_topic(t)})
        selected_topic = st.selectbox("Topic", ["all"] + available_topics, key="video_analyzer_topic")
        query = st.text_input("댓글 검색", key="video_analyzer_comment_search")
        rows = []
        for record in comments:
            item = amap.get(record.id)
            sentiment = item.sentiment.value if item else "unknown"
            topics = [normalize_topic(t) for t in item.topics] if item else []
            if selected_sentiment != "all" and sentiment != selected_sentiment: continue
            if selected_topic != "all" and selected_topic not in topics: continue
            if query and query.casefold() not in record.content.casefold() and query.casefold() not in (item.translated_ko if item else "").casefold(): continue
            rows.append({"Comment":record.content,"Korean Translation":item.translated_ko if item else "","Sentiment":sentiment.title(),
                "Topic":", ".join(topics),"Likes":record.engagement_count or 0,
                "Published Date":record.published_at.strftime("%Y-%m-%d") if record.published_at else None})
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def render_yahoo(run: RunResult, analysis: Optional[AnalysisResult]) -> None:
    records = [r for r in run.eligible_records if r.source.value == "yahoo_japan"]
    amap = _analysis_map(analysis)
    metrics = dashboard_metrics(run, analysis)
    yahoo_voice_ids = {record_id for record_id in metrics.consumer_record_ids
        if next((r for r in run.consumer_voice_records if r.id == record_id), None) is not None
        and next(r for r in run.consumer_voice_records if r.id == record_id).source is Source.YAHOO_JAPAN}
    groups = {
        "Articles": [r for r in records if r.sub_source is YahooSubSource.NEWS_ARTICLE],
        "Yahoo Comments": [r for r in records if r.sub_source is YahooSubSource.NEWS_COMMENT],
        "知恵袋 Questions": [r for r in records if r.sub_source is YahooSubSource.CHIEBUKURO_QUESTION],
        "知恵袋 Answers": [r for r in records if r.sub_source is YahooSubSource.CHIEBUKURO_ANSWER],
    }
    section("Yahoo Japan Intelligence", "Yahoo!ニュース와 Yahoo!知恵袋의 Japan Market Voice")
    cols = st.columns(5)
    values = [
        (len(records), "Total Yahoo Records"), (len(groups["Articles"]), "Articles"),
        (len(groups["Yahoo Comments"]), "Yahoo Comments"),
        (len(groups["知恵袋 Questions"])+len(groups["知恵袋 Answers"]), "Chiebukuro Q&A"),
        (len(yahoo_voice_ids), "Consumer Voices"),
    ]
    for col, (value, label) in zip(cols, values):
        with col: metric_card(str(value), label, "Eligible records")
    if not records:
        st.info("선택한 기간에 분석 가능한 Yahoo Japan 데이터가 없습니다.")
        return
    yahoo_tabs = st.tabs(list(groups))
    for tab, (label, items) in zip(yahoo_tabs, groups.items()):
        with tab:
            if items:
                st.dataframe(_records_frame(items, amap), width="stretch", hide_index=True,
                    column_config={"URL": st.column_config.LinkColumn("Original Link")})
            else:
                st.info(f"{label} 데이터가 없습니다.")
    st.caption("Yahoo Realtime Search: No stable public collection method · X API 미사용")


def render_minkara(run: RunResult, analysis: Optional[AnalysisResult]) -> None:
    records = [r for r in run.eligible_records if r.source.value == "minkara"]
    posts = [r for r in records if r.sub_source is MinkaraSubSource.POST]
    comments = [r for r in records if r.sub_source is MinkaraSubSource.COMMENT]
    amap = _analysis_map(analysis)
    known = [amap[r.id] for r in records if r.id in amap and amap[r.id].sentiment is not Sentiment.UNKNOWN]
    section("みんカラ Intelligence", "일본 자동차 사용자 게시글과 공개 댓글 Consumer Voice")
    cols = st.columns(5)
    values = [
        (len(records), "Total Records"), (len(known), "Consumer Voices"), (len(comments), "Comments"),
        (f"{sum(a.sentiment is Sentiment.POSITIVE for a in known)/len(known):.0%}" if known else "—", "Positive"),
        (f"{sum(a.sentiment is Sentiment.NEGATIVE for a in known)/len(known):.0%}" if known else "—", "Negative"),
    ]
    for col, (value, label) in zip(cols, values):
        with col: metric_card(str(value), label, "Eligible consumer voice")
    if not records:
        st.info("선택한 기간에 분석 가능한 みんカラ 데이터가 없습니다.")
        return
    post_tab, comment_tab = st.tabs(["Posts", "Comments"])
    with post_tab:
        if posts: st.dataframe(_records_frame(posts, amap), width="stretch", hide_index=True,
            column_config={"URL": st.column_config.LinkColumn("Original Link")})
        else: st.info("Posts 데이터가 없습니다.")
    with comment_tab:
        if comments: st.dataframe(_records_frame(comments, amap), width="stretch", hide_index=True,
            column_config={"URL": st.column_config.LinkColumn("Original Link")})
        else: st.info("Comments 데이터가 없습니다.")


def _records_frame(records, amap) -> pd.DataFrame:
    rows = []
    for r in records:
        item = amap.get(r.id)
        rows.append({"Date": r.published_at.strftime("%Y-%m-%d") if r.published_at else None, "Source": r.source.value,
            "Title": r.title or "", "Content": r.content, "Sentiment": item.sentiment.value if item else "unknown",
            "Topic": ", ".join(item.topics) if item else "", "Japan Scope": r.scope_decision.value, "URL": str(r.url)})
    return pd.DataFrame(rows)


def render_raw(run: RunResult, analysis: Optional[AnalysisResult]) -> None:
    section("Raw Data Explorer", "원본 출처와 Guardrail 판정을 직접 검토하세요.")
    amap = _analysis_map(analysis)
    source_options = sorted({r.source.value for r in run.raw_records})
    selected = st.multiselect("Source filter", source_options, default=source_options)
    records = [r for r in run.raw_records if r.source.value in selected]
    st.dataframe(_records_frame(records, amap), width="stretch", hide_index=True,
        column_config={"URL": st.column_config.LinkColumn("Original URL"), "Content": st.column_config.TextColumn(width="large")})
    with st.expander("Guardrail Quality Audit", expanded=False):
        a = run.audit
        dm = dashboard_metrics(run, analysis)
        metrics = {"Raw Collected":a.raw_collected,"Entity Excluded":a.entity_excluded,"Foreign / Scope Excluded":a.japan_scope_excluded,
            "Language Excluded":a.language_excluded,"Date Excluded":a.date_excluded,"Duplicates Removed":a.duplicates_removed,
            "Final Eligible Records":a.final_eligible,"Consumer Records Before Analysis":a.consumer_voice_count,
            "Analyzed Consumer Voices":dm.consumer_voices,"Unknown Consumer Records":dm.unknown,
            "Market Content":a.market_content_count}
        st.dataframe(pd.DataFrame(metrics.items(), columns=["Metric","Count"]), width="stretch", hide_index=True)
        if dm.warnings:
            st.caption("Internal audit warning: " + ", ".join(dm.warnings))


def render_coming_soon(source: str) -> None:
    st.markdown(f'<div class="coming-soon"><h3>{escape(source)}</h3><p>Coming Soon · 현재 MVP에서는 활성화되지 않은 Source입니다.</p></div>', unsafe_allow_html=True)
