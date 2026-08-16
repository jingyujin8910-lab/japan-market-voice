# KIA Japan Market Voice Dashboard

## UI / UX Redesign Specification v2

**Product Name:** KIA Japan Market Voice Dashboard
**Subtitle:** Japan Social Listening & Consumer Insight
**Platform:** Streamlit
**Primary Device:** Desktop / 16:9 presentation environment
**Primary User:** Japan Marketing Team
**Design Benchmark:** Enterprise Social Listening / Executive Intelligence Dashboard

---

# 1. UI Redesign Objective

현재 MVP는 기능적으로 작동하지만 다음 문제가 존재한다.

1. 상단 Header와 Title 일부가 화면 위쪽에서 잘려 보임
2. 전체적으로 Gray / Muted Teal 위주의 색상이라 화면이 우중충함
3. Chart와 Card의 시각적 위계가 약함
4. Executive Dashboard라기보다 일반적인 내부 분석 Tool처럼 보임
5. KPI / Visualization / AI Insight 중 무엇이 가장 중요한지 한눈에 들어오지 않음
6. AI Market Intelligence가 본 Dashboard의 핵심 기능임에도 시각적으로 충분히 강조되지 않음
7. Streamlit 기본 Component 느낌이 아직 강함

이번 Redesign의 목표는:

> **전문적이면서도 첫 화면에서 시선을 끌고, 발표자가 설명하지 않아도 핵심 내용을 빠르게 이해할 수 있는 Premium Executive Dashboard를 만드는 것**

이다.

사용자가 처음 접속했을 때:

> **“이거 진짜 직접 만든 PoC 맞아?”**

라는 인상을 주는 수준을 목표로 한다.

---

# 2. Overall Design Direction

Design Keywords:

**Premium**
**Executive**
**Modern**
**Clean**
**High Contrast**
**Data-driven**
**Enterprise SaaS**
**Visually Impactful**

전문적으로 보이기 위해 화면을 어둡게 만드는 방식은 사용하지 않는다.

이번 버전에서는 **밝고 선명한 Dashboard**를 기본으로 한다.

---

# 3. Color Philosophy

현재 화면의 Muted Gray / Dark Teal 중심 색상을 폐기한다.

핵심 원칙:

* Background는 매우 밝게
* Card는 White
* Text는 거의 Black에 가까운 Dark Color
* 주요 Data Visualization은 선명한 Accent Color 사용
* Positive / Neutral / Negative를 색으로 즉시 구분
* 한 화면에 너무 많은 색을 사용하지 않음

---

# 4. Main Color Palette

## Background

Primary Background:

```text
#F5F7FA
```

또는 이에 가까운 very light cool gray.

Section Background가 필요한 경우:

```text
#EEF2F6
```

전체 Background를 Dark Gray로 만들지 않는다.

---

## Card Background

```text
#FFFFFF
```

Card와 Background의 차이를 명확히 한다.

---

## Primary Text

```text
#111318
```

Title / KPI / 중요 Text.

---

## Secondary Text

```text
#667085
```

Subtitle / Caption / Metadata.

---

## Main Accent

주요 Chart와 Action에는 깨끗하고 선명한 Blue 계열을 사용한다.

```text
#2563EB
```

Secondary Accent:

```text
#4F46E5
```

기존의 탁한 Teal 위주 사용을 피한다.

---

## Sentiment Colors

Positive:

```text
#16A34A
```

Negative:

```text
#DC2626
```

Neutral:

```text
#94A3B8
```

---

## Supporting Colors

Optional:

```text
Cyan     #0891B2
Purple   #7C3AED
Amber    #D97706
```

Supporting Visualization에서만 제한적으로 사용한다.

---

# 5. Critical Rule — No Gray-on-Gray Dashboard

다음 형태를 피한다.

```text
Gray Background
+
Gray Cards
+
Muted Teal Charts
+
Gray Text
```

현재 MVP가 우중충해 보이는 가장 큰 이유 중 하나다.

반드시:

```text
Light Background
+
Bright White Cards
+
Strong Dark Typography
+
Clear Accent Colors
```

구조로 변경한다.

---

# 6. Global Page Container

Desktop 중심의 최대 Content Width를 유지한다.

권장:

```text
max-width: 1500px ~ 1600px
```

화면 좌우에 충분한 whitespace를 둔다.

전체 Content Padding:

```text
Top: 24px 이상
Left / Right: 28px ~ 40px
Bottom: 48px 이상
```

---

# 7. CRITICAL FIX — Header Cropping

현재 화면에서 Main Header 일부가 화면 상단에 잘려 보이는 문제가 존재한다.

이를 반드시 수정한다.

Header는 최소 다음 조건을 만족해야 한다.

```text
min-height: 90px
padding-top: 24px 이상
padding-bottom: 20px 이상
overflow: visible
align-items: center
```

Title line-height는 너무 작게 설정하지 않는다.

```text
line-height: 1.10 ~ 1.20
```

상단 Streamlit container 또는 custom HTML의 negative margin을 사용하지 않는다.

`transform: translateY(...)` 등 Title을 위로 강제로 이동시키는 CSS를 사용하지 않는다.

---

# 8. Header Layout

전체 Header:

```text
┌──────────────────────────────────────────────────────────────┐
│ KIA LOGO        KIA Japan Market Voice Dashboard             │
│                 Japan Social Listening & Consumer Insight    │
│                                            Ready • JST 17:30 │
└──────────────────────────────────────────────────────────────┘
```

---

# 9. KIA Logo

좌측 상단.

파일:

```text
assets/kia_logo.png
```

규칙:

* 로고 비율 유지
* Stretch 금지
* `object-fit: contain`
* 너무 작게 표시하지 않음
* Header 중앙 높이에 맞춰 정렬
* 위쪽이 잘리지 않도록 충분한 Padding 확보

권장 Width:

```text
90 ~ 120px
```

로고 이미지가 존재하지 않는 경우 인터넷에서 임의 다운로드하지 않는다.

---

# 10. Main Title

Title:

# KIA Japan Market Voice Dashboard

Subtitle:

**Japan Social Listening & Consumer Insight**

Main Title은 화면 중앙 또는 좌측 중앙 영역에 배치한다.

기존처럼 Title이 Header 밖으로 튀어나오거나 잘리지 않아야 한다.

권장 Title Size:

```text
28px ~ 34px
```

Font Weight:

```text
700 ~ 800
```

---

# 11. Header Status

우측에 작게 Status 정보를 표시한다.

예:

```text
● READY

Updated
17:31 JST
```

성공 상태의 작은 Indicator 정도만 사용한다.

Status가 Header보다 시선을 뺏지 않도록 한다.

---

# 12. Search Control Panel

Header 아래 별도의 White Search Panel을 구성한다.

Card Style:

* White background
* subtle border
* subtle shadow
* 충분한 padding
* border radius 14~18px

Layout:

```text
Keyword         Start Date       End Date        Sources       CTA
[ PV5       ]   [2026-08-01]    [2026-08-16]    [YouTube]     ANALYZE
```

---

# 13. Search Panel Visual Priority

`ANALYZE MARKET VOICE` 버튼은 가장 눈에 띄는 Control이어야 한다.

Primary Button:

* Main Accent Blue
* White text
* Medium-large size
* Rounded rectangle
* Full contrast

Hover 시 약간 darker.

과도한 Gradient 또는 Glow 사용 금지.

---

# 14. Main Navigation

Source Tabs:

```text
Overview
YouTube
News
X
みんカラ
Raw Data
```

현재 구현 상태:

* Overview → Active
* YouTube → Active
* News → Coming Soon
* X → Coming Soon
* みんカラ → Coming Soon
* Raw Data → Active

Coming Soon은 실제 기능처럼 클릭 가능한 것처럼 보이지 않게 한다.

---

# 15. Executive KPI Section

Search Panel 바로 아래.

4개의 KPI Card를 한 줄에 배치한다.

```text
TOTAL MENTIONS
CONSUMER VOICES
POSITIVE
NEGATIVE
```

또는 Top Source를 마지막 KPI로 사용할 수 있다.

---

# 16. KPI Card Redesign

현재의 평면적인 Card보다 Contrast를 높인다.

Card:

```text
White background
Border: #E5E7EB
Radius: 14px
Shadow: very subtle
Padding: 20px ~ 24px
```

각 Card 상단에 매우 얇은 Accent bar를 사용할 수 있다.

예:

Total Mentions:

```text
Blue
```

Consumer Voice:

```text
Purple
```

Positive:

```text
Green
```

Negative:

```text
Red
```

---

# 17. KPI Number Hierarchy

KPI 숫자는 매우 크게 보인다.

예:

# 93

그 아래:

```text
Total Mentions
```

지원 Caption:

```text
Selected period
```

숫자가 Card에서 가장 먼저 눈에 들어와야 한다.

---

# 18. Overview Visual Hierarchy

Overview는 다음 순서로 배치한다.

```text
KPI
↓
Mention Trend + Consumer Sentiment
↓
Source Distribution + Top Topics
↓
AI Market Intelligence
↓
Representative VOC
↓
Detailed / Raw Data
```

---

# 19. Market Voice Trend

Main Visualization 중 가장 큰 Chart.

Title:

# Market Voice Trend

가로 공간의 약 60~65%.

Line Color:

```text
Primary Blue #2563EB
```

Line Width는 충분히 두껍게.

Data Point Marker는 작게.

Gridline은 매우 옅게.

배경은 White.

---

# 20. Consumer Sentiment

Market Voice Trend 오른쪽.

Title:

# Consumer Sentiment

Donut Chart 또는 clean segmented bar.

반드시:

Positive = Green
Neutral = Slate
Negative = Red

각 Segment에 Percent 표시.

Chart 중앙에 Total Consumer Voice를 표시할 수 있다.

예:

```text
81
Voices
```

---

# 21. Source Distribution

Title:

# Voice by Source

Source별 언급량.

기본 Visualization:

Horizontal Bar Chart.

Source마다 색을 지나치게 다르게 하지 않는다.

Main Accent + variation 정도로 구성한다.

---

# 22. Top Topics

Title:

# Top Consumer Topics

기존처럼 단순 Text를 나열하지 않는다.

Horizontal Ranked Bar 또는 Premium Ranked List 사용.

예:

```text
01  가격       ███████████  19
02  디자인     █████████    15
03  충전       ███████      12
04  공간       █████        9
05  차박       ████         7
```

---

# 23. AI Market Intelligence — PRIMARY FEATURE

본 Dashboard의 가장 중요한 차별화 요소다.

기존 화면보다 훨씬 강하게 강조한다.

Section 전용 Header:

# AI Market Intelligence

Subtitle:

**Gemini-powered interpretation of Japan market voice**

Section 앞뒤로 충분한 whitespace를 둔다.

---

# 24. AI Overall Voice Hero Card

AI Intelligence 시작 부분에 가장 큰 Hero Card를 하나 배치한다.

Title:

# Overall Voice

이 Card는 일반 Card와 시각적으로 구분한다.

권장 Style:

```text
Deep Navy / Very Dark Ink background
White text
Large padding
Large border radius
```

예 Background:

```text
#111827
```

이 Section 하나만 Dark Card로 만들어 전체 화면에 Visual Anchor를 만든다.

---

# 25. Overall Voice Content

Gemini Aggregate 결과가 존재하면 실제 결과를 표시한다.

Fallback 상태에서는 일반 Aggregate 내용을 흉내 내지 않는다.

정상 예:

```text
PV5에 대한 일본 소비자 반응은 전반적으로 긍정적이며,
특히 공간 활용성과 디자인에 대한 관심이 높다.

반면 가격과 충전 환경에 대한 우려가 주요 구매 장벽으로 나타난다.
```

2~4문장 이내.

---

# 26. Aggregate Availability

`aggregate_available=true`라면:

* Warning 표시 금지
* Fallback 문구 표시 금지

`aggregate_available=false`일 때만:

작은 Warning Badge를 표시한다.

현재 Aggregate가 정상 작동하는 경우 사용자는 fallback 문구를 보지 않아야 한다.

---

# 27. AI Driver Cards

Overall Voice 아래 3-column Layout.

```text
Positive Drivers
Key Concerns
Purchase Barriers
```

각 Card는 색으로 약하게 구분한다.

---

# 28. Positive Drivers

Accent:

Soft Green.

Header Icon 대신 작은 Dot/Line 사용 가능.

예:

```text
POSITIVE DRIVERS

01  Spacious interior
02  Design
03  Camping utility
04  Cargo flexibility
```

---

# 29. Key Concerns

Accent:

Soft Red.

예:

```text
KEY CONCERNS

01  Price
02  Charging
03  Vehicle size
04  Service network
```

---

# 30. Purchase Barriers

Accent:

Amber / Warm Orange.

예:

```text
PURCHASE BARRIERS

01  Price uncertainty
02  Charging concern
03  Service availability
```

---

# 31. Marketing Implications — Second Hero Element

Title:

# Marketing Implications

Overall Voice 다음으로 중요한 Insight.

일반 Card보다 넓게 표시한다.

예:

```text
01
차박 및 공간 활용성을 핵심 Product Message로 강화

02
가격과 보조금 정보를 명확하게 제공

03
일본 충전 환경에서의 실제 사용 콘텐츠 확대
```

단순 Bullet보다 Numbered Insight 형태를 권장한다.

---

# 32. Emerging Issues

Title:

# Emerging Issues

데이터가 있는 경우만 표시한다.

2~4개 정도.

신뢰할 수 있는 데이터가 없을 경우:

```text
No reliable emerging issue detected for this period.
```

라고 표시한다.

---

# 33. Representative Consumer Voice

AI Insight 아래.

Title:

# Representative Consumer Voice

Card 형식으로 실제 일본어 원문을 강조한다.

예:

```text
YouTube · Positive

「日本でも発売されたら欲しい」

Purchase Intent
```

일본어 Quote는 약간 크게.

Source / Sentiment / Topic은 작은 Badge.

---

# 34. Chart Container Style

모든 Chart를 독립 White Card 안에 넣는다.

Card마다:

* Title
* Optional small caption
* Visualization

구성.

Plotly 기본 toolbar가 발표 화면에서 방해되는 경우 숨길 수 있다.

---

# 35. Chart Color Consistency

기존 Plotly default blue / random palette를 그대로 사용하지 않는다.

Dashboard 전체 Palette를 강제한다.

Trend:

```text
#2563EB
```

Positive:

```text
#16A34A
```

Negative:

```text
#DC2626
```

Neutral:

```text
#94A3B8
```

Secondary Series:

```text
#7C3AED
#0891B2
#D97706
```

---

# 36. White Space

현재 화면보다 Vertical Spacing을 늘린다.

권장:

Section 사이:

```text
32px ~ 48px
```

Card 사이:

```text
16px ~ 20px
```

한 화면을 억지로 꽉 채우지 않는다.

---

# 37. Border Rule

과도한 Border 사용 금지.

권장:

```text
1px solid #E5E7EB
```

또는 Shadow만 사용.

Dark thick border 금지.

---

# 38. Shadow Rule

아주 미세하게 사용.

예:

```text
0 4px 20px rgba(0,0,0,0.05)
```

지나치게 떠 보이는 floating card 금지.

---

# 39. Typography

Main Title:

```text
28~34px / 700~800
```

Section Title:

```text
20~24px / 700
```

Card Title:

```text
13~15px / 600~700
```

KPI:

```text
30~40px / 700~800
```

Body:

```text
14~16px
```

---

# 40. Avoid Tiny Text

현재 화면처럼 작은 Secondary Text가 너무 많아 발표 화면에서 읽기 어려워지지 않도록 한다.

16:9 Presentation에서도 KPI와 Insight를 읽을 수 있어야 한다.

---

# 41. Analyze Loading Experience

실제 분석은 약 40초 이상 걸릴 수 있으므로 단순 Spinner만 표시하지 않는다.

Status Container를 사용한다.

예:

```text
01  Searching Japan market content...
02  Collecting YouTube videos...
03  Collecting consumer comments...
04  Filtering Japan-relevant content...
05  Analyzing consumer sentiment...
06  Generating aggregate market insight...
```

완료된 단계에는 Check 표시.

---

# 42. Loading UX Goal

사용자가:

> “왜 이렇게 오래 걸리지?”

라고 느끼는 대신:

> “실제로 여러 단계의 AI 분석을 수행하고 있구나.”

라고 느끼게 한다.

---

# 43. Empty State

검색 전 첫 화면은 완전히 비어 보이지 않게 한다.

Hero Empty State:

# Discover Japan Market Voice

Subtitle:

```text
Search a brand or product to understand
consumer reactions across Japan.
```

Example:

```text
Try: PV5 / KIA / キア
```

---

# 44. YouTube Tab

현재 실제 작동하는 Source이므로 완성도를 높인다.

상단 Summary:

```text
VIDEOS
COMMENTS
CONSUMER VOICES
POSITIVE
NEGATIVE
```

---

# 45. YouTube Video Cards

가능하면 다음을 표시한다.

* Thumbnail
* Video Title
* Channel
* Published Date
* Collected Comments
* Main Topic
* Link

Thumbnail이 불안정할 경우 무리해서 추가하지 않는다.

---

# 46. YouTube Comments

Table보다 읽기 좋은 Compact Card 또는 Clean Table 사용.

Columns:

```text
Date
Comment
Sentiment
Topic
Likes
```

Comment 원문을 지나치게 길게 표시하지 않는다.

---

# 47. News / X / みんカラ Tabs

현재 미구현이므로:

```text
COMING SOON
```

을 Premium Empty State 형태로 표시한다.

기능이 있는 것처럼 Fake Data를 표시하지 않는다.

---

# 48. Raw Data

Raw Data는 Main UI보다 시각적 우선순위를 낮춘다.

Expandable / detailed table 형태.

필터:

* Source
* Sentiment
* Topic
* Date

---

# 49. Guardrail Audit

Audit는 기술적으로 매우 중요한 기능이지만 Executive Overview에는 작게 표시한다.

별도 Expander 또는 Tab.

예:

```text
Raw Collected             93
Japan Relevant            84
Foreign Excluded           7
Duplicates Removed         2
Final Eligible            81
```

---

# 50. Scroll Experience

첫 화면 기준으로:

Header
Search
KPI
Main Charts

까지 한 화면 또는 한 번의 Scroll 안에서 보여야 한다.

AI Market Intelligence는 그 바로 아래에 위치한다.

---

# 51. Presentation Priority

발표자는 다음 순서로 설명할 수 있어야 한다.

```text
1. PV5 검색
2. 81개 소비자 반응 분석
3. Mention / Sentiment 확인
4. 주요 Topic 확인
5. AI Overall Voice 확인
6. Positive / Negative Driver 설명
7. Marketing Implications 제시
```

UI가 이 Story를 자연스럽게 따라가야 한다.

---

# 52. Streamlit Default Chrome

Streamlit의 기본 UI 느낌을 최소화한다.

가능하면:

```text
Main Menu 숨김
Footer 숨김
Deploy 버튼 등 불필요한 Chrome 최소화
```

단, brittle한 CSS selector 남용은 금지.

---

# 53. Sidebar

MVP에서는 Sidebar를 기본 Navigation으로 사용하지 않는다.

모든 핵심 검색 / 결과는 Main Content 안에 유지한다.

---

# 54. Error Handling UI

Source 하나 실패 시 전체 Red Error 화면 금지.

예:

```text
YouTube   ● Active
News      ○ Coming Soon
X         ○ Coming Soon
みんカラ  ○ Coming Soon
```

Partial Failure는 작은 Status Message만 표시.

---

# 55. Aggregate Failure UI

Aggregate가 실제 실패한 경우에도:

Record-level Sentiment / Topics / Raw Data는 정상 표시한다.

그러나 Aggregate가 성공하면 **어떠한 unavailable warning도 남아 있으면 안 된다.**

---

# 56. UI Functional Freeze Rule

이번 Redesign에서 다음 Backend는 수정하지 않는다.

* YouTube Collector
* SearchRequest
* QueryPlanner
* Japan Guardrail
* Processing Pipeline
* Gemini RecordAnalysis
* AggregateAnalysis
* Evidence Reconciliation
* API Configuration

Redesign Task는 UI / styling / rendering 중심이다.

Backend Logic 변경 금지.

---

# 57. Required Visual Fixes from Current MVP

현재 실제 화면 기준 반드시 수정할 것:

### Fix 1

Header Main Title 상단 잘림 완전 제거.

### Fix 2

Dark / Gray / Muted Teal 중심 Palette 제거.

### Fix 3

Background와 Card 대비 강화.

### Fix 4

KPI 숫자 크기 및 Color hierarchy 강화.

### Fix 5

Plotly 기본 Color Palette 제거.

### Fix 6

AI Market Intelligence를 시각적으로 가장 강한 Section 중 하나로 승격.

### Fix 7

Aggregate가 정상일 때 fallback warning 제거.

### Fix 8

Cards의 여백 및 alignment 통일.

### Fix 9

Charts의 크기와 비율 통일.

### Fix 10

전체적으로 “내부 Tool”이 아니라 “Executive Product”처럼 보이도록 수정.

---

# 58. Desktop Wireframe v2

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  KIA LOGO       KIA Japan Market Voice Dashboard           ● READY     │
│                 Japan Social Listening & Consumer Insight               │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ [ PV5            ] [ Start ] [ End ] [ YouTube ▼ ] [ ANALYZE MARKET ] │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ TOTAL MENTIONS   CONSUMER VOICES     POSITIVE          NEGATIVE         │
│      93                81               58%               13%            │
│                                                                         │
├──────────────────────────────────────┬──────────────────────────────────┤
│                                      │                                  │
│ MARKET VOICE TREND                   │ CONSUMER SENTIMENT               │
│                                      │                                  │
│       ───────╮                       │             ◯                    │
│    ───       ╰────                   │        58% Positive              │
│                                      │                                  │
├──────────────────────────────────────┼──────────────────────────────────┤
│                                      │                                  │
│ VOICE BY SOURCE                      │ TOP CONSUMER TOPICS              │
│ YouTube █████████                    │ 01 Price        █████████        │
│ News    ██                           │ 02 Design       ███████          │
│                                      │ 03 Charging     █████            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                     AI MARKET INTELLIGENCE                              │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ OVERALL VOICE                                                       │ │
│ │                                                                     │ │
│ │ PV5에 대한 일본 소비자 반응은 전반적으로 긍정적이며...            │ │
│ │                                                                     │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│ ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────┐ │
│ │ POSITIVE DRIVERS     │ │ KEY CONCERNS         │ │ PURCHASE BARRIER │ │
│ │ 01 Interior space    │ │ 01 Price             │ │ 01 Charging      │ │
│ │ 02 Design            │ │ 02 Size              │ │ 02 Service       │ │
│ └──────────────────────┘ └──────────────────────┘ └──────────────────┘ │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ MARKETING IMPLICATIONS                                              │ │
│ │                                                                     │ │
│ │ 01  공간 활용성을 핵심 메시지로 강화                               │ │
│ │ 02  가격 및 보조금 정보 제공                                        │ │
│ │ 03  일본 실제 사용 사례 콘텐츠 확대                                │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ Overview │ YouTube │ News │ X │ みんカラ │ Raw Data                   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

# 59. Codex Redesign Instruction

Codex는 본 `UI_SPEC.md`를 UI Redesign의 Source of Truth로 사용한다.

이번 Task에서는 기존 Backend를 Rewrite하지 않는다.

특히:

```text
YouTube
Guardrail
Gemini
Aggregate
Processing
```

로직은 수정하지 않는다.

수정 대상:

```text
app.py
ui/views.py
ui/theme.py
Streamlit layout
Plotly appearance
CSS
UI rendering
```

중심으로 제한한다.

---

# 60. Definition of Done — Redesign

다음 조건을 모두 만족해야 Redesign 완료로 간주한다.

* Header가 더 이상 잘리지 않음
* KIA Logo 정상 표시
* Main Title 완전히 표시
* 전체 화면이 밝고 선명함
* Gray-on-gray 느낌 제거
* KPI가 즉시 눈에 들어옴
* Sentiment 색상 명확
* Mention Trend가 핵심 Chart로 보임
* Top Topics 가독성 향상
* AI Market Intelligence가 강하게 강조됨
* Aggregate 정상일 때 warning 없음
* Overall Voice 정상 표시
* Positive Drivers 정상 표시
* Negative Drivers 정상 표시
* Purchase Barriers 정상 표시
* Marketing Implications 정상 표시
* Emerging Issues 정상 표시
* Representative VOC 정상 표시
* YouTube 상세 화면 정상
* Coming Soon Source 명확
* 기존 Backend 기능 정상
* 기존 전체 테스트 통과
* 실제 PV5 Analyze 이후 UI가 깨지지 않음
* 16:9 발표 화면에서 전문적으로 보임

---

# 61. Final Design Principle

본 Dashboard는 단순히 “예쁜 Streamlit 화면”을 만드는 것이 아니다.

목표는:

> **일본 시장의 온라인 소비자 Voice를 전문적인 Executive Dashboard 형태로 보여주고, 데이터에서 바로 Marketing Action까지 연결하는 것**

이다.

최종 화면은:

**Clean but not boring.**

**Colorful but not playful.**

**Premium but not decorative.**

**Data-rich but immediately understandable.**

이어야 한다.
