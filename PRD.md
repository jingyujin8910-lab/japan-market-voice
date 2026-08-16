# Japan Market Voice Dashboard

## Product Requirements & Implementation Specification

**Version:** MVP 1.0
**Product Type:** Japan-focused Social Listening / Market Voice Dashboard
**Primary User:** Japan Marketing Manager
**Benchmark:** Sprinklr
**Frontend / App Framework:** Streamlit
**Primary Language of UI:** Korean
**Primary Analysis Language:** Japanese
**Deployment Target:** Streamlit Community Cloud

---

# 1. Project Overview

## 1.1 프로젝트 목적

일본 시장에서 특정 브랜드 또는 제품에 대한 온라인 반응을 자동으로 수집·분석하여, 일본 마케팅 담당자가 하나의 Dashboard에서 시장 반응을 빠르게 파악할 수 있도록 한다.

현재 시장 반응을 파악하려면 담당자가 YouTube, Yahoo! JAPAN, X, みんカラ 등 여러 웹사이트를 개별적으로 방문하고 기사, 게시물, 댓글을 직접 읽어야 한다.

이 과정은 반복적이며 1회 분석에 1시간 이상 소요될 수 있다.

본 프로젝트는 이 과정을 다음과 같이 단순화한다.

**기존**

각 사이트 접속
→ 키워드 검색
→ 기간 확인
→ 게시물 확인
→ 댓글 확인
→ 수작업 분류
→ 주요 반응 정리
→ 마케팅 시사점 도출

**목표**

Dashboard 접속
→ Keyword 입력
→ 기간 선택
→ 데이터 수집/조회
→ AI 분석
→ Dashboard 자동 시각화

최종적으로 사용자가 Dashboard 하나만 열어도 원하는 기간 동안 일본 온라인상에서 해당 브랜드/제품에 대해:

* 얼마나 언급되었는지
* 어디에서 많이 언급되었는지
* 반응이 긍정/중립/부정 중 어느 쪽인지
* 어떤 Topic이 많이 등장하는지
* 소비자가 무엇을 좋아하는지
* 무엇을 우려하는지
* 어떤 질문을 반복적으로 하는지
* 구매와 관련하여 어떤 반응을 보이는지
* 마케팅 담당자가 주목해야 할 변화가 무엇인지

빠르게 파악할 수 있도록 한다.

---

# 2. Product Positioning

본 프로젝트는 Sprinklr의 전체 기능을 복제하는 프로젝트가 아니다.

**Japan Market Social Listening Dashboard의 PoC/MVP**를 만드는 것이 목적이다.

MVP에서는 다음 원칙을 따른다.

1. 실제 작동하는 기능을 우선한다.
2. 데이터 수집 안정성을 우선한다.
3. 분석 결과의 신뢰성과 출처 추적 가능성을 중요하게 한다.
4. 발표에서 직관적으로 이해할 수 있는 UI를 만든다.
5. 과도한 기능 확장을 하지 않는다.
6. 구현이 불안정한 Source 하나 때문에 전체 Dashboard가 실패하지 않도록 한다.
7. 실제 데이터가 없는 경우 데이터를 조작하거나 임의 생성하지 않는다.

---

# 3. Target User

## Primary User

일본 시장을 담당하는 마케팅 실무자.

기술 지식이 없는 사용자도 사용할 수 있어야 한다.

사용자는 Python, API, Database, Prompt 등을 알 필요가 없어야 한다.

사용자가 수행해야 하는 핵심 행동은 최대한 단순해야 한다.

**Keyword 입력 → 기간 선택 → Source 선택 → 분석 실행 → 결과 확인**

---

# 4. Core User Experience

## 4.1 Main Search

Dashboard 상단에 Global Search / Control Panel을 배치한다.

필수 입력값:

### Keyword

텍스트 입력.

예:

* `KIA`
* `キア`
* `PV5`
* `KIA PV5`
* `キア PV5`

하나의 검색에서 복수 검색어를 입력할 수 있도록 확장 가능한 구조로 설계한다.

MVP에서는 단일 Keyword 입력을 기본으로 한다.

### Start Date

분석 시작일.

예:

`2026-01-01`

### End Date

분석 종료일.

예:

`2026-08-16`

기본값은 최근 30일로 설정한다.

End Date는 Start Date보다 이전일 수 없다.

### Source Selection

Checkbox 또는 Multiselect 사용.

선택 가능한 Source:

* All
* YouTube
* Yahoo! JAPAN / News
* X
* みんカラ
* Web

### Action

Primary CTA:

**데이터 수집 및 분석**

사용자가 버튼을 눌렀을 때만 새로운 데이터 수집 작업을 실행한다.

단순 페이지 조회 또는 새로고침으로 외부 API 호출이 발생하지 않도록 한다.

---

# 5. Core Pipeline

전체 시스템은 다음 Pipeline을 따른다.

```text
User Input
    ↓
Input Validation
    ↓
Keyword Normalization
    ↓
Source Selection
    ↓
Data Collection
    ↓
Raw Data Normalization
    ↓
Date Filtering
    ↓
Language / Japan Relevance Filtering
    ↓
Duplicate Removal
    ↓
Data Storage / Cache
    ↓
Gemini AI Analysis
    ↓
Structured Analysis Result
    ↓
Aggregation
    ↓
Visualization
    ↓
AI Marketing Insight
```

각 Source Collector는 독립적으로 동작해야 한다.

예를 들어 X 수집이 실패해도 YouTube와 News 결과는 정상적으로 Dashboard에 표시되어야 한다.

---

# 6. Common Data Schema

모든 Source의 데이터를 가능한 한 하나의 공통 Schema로 변환한다.

최소 Schema:

```text
id
source
content_type
keyword
title
content
author
published_at
collected_at
url
parent_url
engagement_count
language
sentiment
sentiment_score
topics
is_comment
```

필드 설명:

### id

게시물/댓글의 고유 식별자.

### source

다음 중 하나:

```text
youtube
yahoo
x
minkara
web
```

### content_type

예:

```text
video
comment
article
post
blog
review
```

### keyword

수집 시 사용한 검색 Keyword.

### title

**영상**/기사/게시물 제목.

댓글에는 부모 콘텐츠의 제목을 사용할 수 있다.

### content

분석 대상 원문.

### author

공개적으로 제공되는 경우에만 저장.

### published_at

콘텐츠 또는 댓글 게시일.

### collected_at

Dashboard가 데이터를 수집한 시간.

### url

원본 콘텐츠 URL.

### parent_url

댓글의 경우 원본 영상/게시물 URL.

### engagement_count

가능한 경우 좋아요 등의 공개 engagement 정보.

### language

가능한 경우 언어 정보.

### **sentiment**

Gemini 분석 결과:

```text
positive
neutral
negative
unknown
```

### sentiment_score

가능하면 -1.0 ~ +1.0 범위.

### topics

해당 콘텐츠와 관련된 주요 Topic.

### is_comment

댓글이면 true.

---

# 7. Data Collection Requirements

## 7.1 공통 원칙

모든 Collector는 동일한 Interface를 갖도록 설계한다.

Conceptual interface:

```python
collect(
    keyword,
    start_date,
    end_date,
    max_results
)
```

Collector는 가능한 경우 DataFrame 또는 동일한 구조의 Record List를 반환한다.

Source별 오류가 전체 앱을 종료시키면 안 된다.

실패 시 다음을 반환하거나 기록한다.

```text
source
status
records_collected
error_type
error_message
collected_at
```

---

# 8. YouTube Collector

## 8.1 목표

사용자가 입력한 Keyword와 기간을 기준으로 관련 YouTube 콘텐츠 및 공개 댓글을 수집한다.

수집 대상:

* Video title
* Video URL
* Video published date
* Channel name (가능한 경우)
* Comment text
* Comment published date (가능한 경우)
* Like count (가능한 경우)

## 8.2 Search Logic

Keyword와 관련된 일본 시장 콘텐츠를 우선한다.

가능한 경우 다음 조건을 활용한다.

* 일본어 콘텐츠
* 일본어 제목/설명
* 일본어 댓글
* 일본 시장과 명백히 관련된 콘텐츠

## 8.3 Date Logic

영상 게시일과 댓글 게시일을 구분한다.

사용자가 지정한 기간에 대한 분석에서는 가능한 경우 **댓글/반응 자체의 게시일**을 우선 기준으로 사용한다.

댓글 게시일 확보가 불가능한 경우 임의로 날짜를 생성하지 않는다.

## 8.4 Collection Limit

PoC 안정성을 위해 한 번의 검색에서 무제한으로 수집하지 않는다.

초기 기본값:

* 최대 관련 영상: 10~20개
* 영상당 댓글: 최대 50~100개

환경 설정으로 변경 가능하도록 한다.

## 8.5 Failure Handling

댓글이 비활성화된 영상은 Skip한다.

영상 하나에서 댓글 수집이 실패하더라도 다른 영상 수집은 계속한다.

---

# 9. Yahoo! JAPAN / Japanese News Collector

## 9.1 목표

Keyword와 관련된 일본 뉴스 및 공개 웹 기사 반응을 수집한다.

수집 대상:

* Article title
* Publisher
* Published date
* Article URL
* Article summary
* Article text 일부 또는 분석 가능한 공개 텍스트
* 공개 댓글이 합법적이고 안정적으로 접근 가능한 경우 댓글

## 9.2 Important Rule

Yahoo! JAPAN 댓글 수집이 기술적으로 불안정하거나 정책상 문제가 있는 경우 **억지로 구현하지 않는다.**

이 경우:

* 기사 데이터는 정상 수집
* 댓글 데이터는 unavailable로 처리
* Dashboard 전체 기능은 정상 유지

---

# 10. みんカラ Collector

## 10.1 목표

Keyword와 관련된 일본 자동차 사용자 반응을 탐색한다.

가능한 대상:

* Blog
* Review
* User post
* Vehicle-related content
* 공개 댓글

수집 필드:

* Title
* Published date
* Content / Summary
* URL
* 공개 댓글이 있는 경우 Comment

## 10.2 Priority

자동차 관련 소비자 경험과 실제 사용 후기를 중요한 VOC 데이터로 취급한다.

다음 유형의 내용을 AI 분석 시 특히 식별한다.

* 실제 사용 경험
* 차량 비교
* 장점
* 단점
* 구매 고려
* 구매 포기 이유
* 가격
* 디자인
* 공간
* 충전
* 주행
* 캠핑/차박
* 상용 활용

---

# 11. X Collector

## 11.1 Purpose

X는 실시간 전체 모니터링 시스템으로 사용하지 않는다.

MVP에서는 필요할 때 명시적으로 데이터를 수집하는 On-demand Source로 사용한다.

## 11.2 Collection Method

X API를 사용하는 구조로 설계한다.

## 11.3 Execution

API 호출은 사용자가 명시적으로 새로운 데이터 수집을 요청했을 때만 실행한다.

다음 행동으로 API가 호출되면 안 된다.

* Dashboard 접속
* 페이지 새로고침
* Tab 이동
* 기존 결과 조회
* Chart 변경

## 11.4 Expected Usage

예상 실행 빈도:

약 월 3회.

1회 최대:

**100 Posts**

월 최대 예상:

**약 300 Posts**

사용하지 않는 기능:

* Continuous Streaming
* Background Monitoring
* Automatic Scheduled Collection

## 11.5 Search Keywords

예:

```text
KIA
キア
PV5
KIA PV5
キア PV5
```

일본어 Post 또는 일본 시장과 관련성이 높은 Post를 우선한다.

## 11.6 Duplicate Prevention

Post ID를 Unique Key로 사용한다.

**이미** 저장된 Post는 중복 저장하지 않는다.

---

# 12. Generic Web Collector

Web Collector는 다른 Source에서 확보하지 못한 일본 공개 웹 콘텐츠를 보완하기 위한 Source다.

MVP에서 전체 인터넷을 무제한 크롤링하려고 하지 않는다.

검색 가능한 공개 페이지를 대상으로:

* title
* source/domain
* published date
* snippet/content
* URL

을 확보한다.

검색 결과의 출처 URL을 반드시 유지한다.

---

# 13. Data Cleaning

수집 완료 후 다음 전처리를 수행한다.

## 13.1 Empty Content

분석 가능한 텍스트가 없는 Record 제거.

## 13.2 Duplicate

우선순위:

1. Source-native ID
2. URL + content hash
3. normalized content hash

를 사용하여 중복 제거한다.

## 13.3 Text Normalization

필요한 범위에서:

* 불필요한 whitespace 제거
* HTML tag 제거
* URL normalization
* Unicode normalization

을 수행한다.

원문 의미를 변경해서는 안 된다.

## 13.4 Date Filter

Start Date ~ End Date 범위 밖의 Record는 분석 대상에서 제외한다.

날짜를 알 수 없는 콘텐츠는 별도 표시하며 임의의 날짜를 부여하지 않는다.

---

# 14. Gemini AI Analysis

## 14.1 Model

Gemini API 사용.

모델 이름은 코드에 여러 곳 하드코딩하지 않고 Config에서 관리한다.

비용과 Rate Limit을 고려하여 Flash 계열 등 적절한 모델을 기본값으로 사용할 수 있도록 한다.

## 14.2 Analysis Strategy

각 댓글마다 Gemini를 개별 호출하지 않는다.

가능한 경우 여러 Record를 Batch로 묶어 분석하여:

* API 호출 수
* latency
* token usage

를 줄인다.

큰 데이터는 적절한 Batch로 나눈다.

---

# 15. AI Output Schema

Gemini의 응답을 자유 형식 텍스트에 의존하지 않는다.

가능한 경우 Structured JSON 형태로 반환받는다.

Conceptual Schema:

```json
{
  "sentiment": {
    "positive": 0,
    "neutral": 0,
    "negative": 0
  },
  "top_topics": [
    {
      "topic": "",
      "count": 0
    }
  ],
  "positive_drivers": [],
  "negative_drivers": [],
  "customer_questions": [],
  "purchase_signals": [],
  "purchase_barriers": [],
  "representative_voc": [],
  "emerging_issues": [],
  "marketing_insights": []
}
```

---

# 16. Sentiment Analysis

각 분석 가능한 Record를 다음 중 하나로 분류한다.

```text
Positive
Neutral
Negative
Unknown
```

풍자, 맥락 부족 등으로 판단이 어려운 경우 억지로 분류하지 않고 `Unknown`을 허용한다.

Dashboard의 Positive / Neutral / Negative 비율 계산 시 Unknown 처리 방식을 명확히 한다.

---

# 17. Topic Analysis

단순 단어 빈도만 보여주지 않는다.

유사한 표현을 하나의 의미 Topic으로 묶을 수 있도록 한다.

예:

```text
高い
価格が高い
値段が高すぎる
```

→

```text
価格
```

예상 Topic 예시:

* Price
* Design
* Size
* Interior Space
* Cargo
* Charging
* Range
* Driving
* Brand
* Service
* Camping
* Commercial Use

단, 실제 데이터에 없는 Topic을 강제로 생성하지 않는다.

---

# 18. VOC Analysis

VOC에서는 단순 요약보다 **소비자가 실제로 무엇을 말하고 있는지**를 보여준다.

분류:

### Positive Drivers

소비자가 긍정적으로 평가하는 이유.

### Negative Drivers

부정적으로 평가하는 이유.

### Questions

반복적으로 나타나는 질문.

### Purchase Signals

구매 의향 또는 관심을 나타내는 표현.

### Purchase Barriers

구매를 망설이게 하는 요인.

### Emerging Issues

최근 증가하거나 새롭게 나타나는 이슈.

---

# 19. Representative VOC

AI가 대표 VOC를 선정할 때 원문을 임의로 만들어서는 안 된다.

대표 반응은 반드시 실제 수집된 Record에서 가져온다.

가능한 경우 다음을 함께 제공한다.

* Original Japanese
* Korean summary/translation
* Source
* Published date
* Original URL

---

# 20. Marketing Insight

Gemini는 단순 데이터 요약을 넘어 마케팅 담당자가 활용할 수 있는 Insight를 생성한다.

예:

### What consumers like

현재 긍정적으로 반응하는 요소.

### What consumers dislike

현재 불만 또는 우려 요소.

### What consumers want to know

반복 질문 및 정보 부족.

### Purchase barriers

구매 전환을 방해하는 요소.

### Opportunities

마케팅에서 활용할 수 있는 기회.

### Watch Items

향후 지속 관찰할 이슈.

## Critical Rule

AI Insight는 수집된 데이터에 근거해야 한다.

근거가 부족한 경우:

**"현재 수집된 데이터만으로 판단하기 어려움"**

이라고 명시한다.

---

# 21. Dashboard Information Architecture

Dashboard는 다음 영역으로 구성한다.

```text
Overview
YouTube
X
News / Yahoo
みんカラ
Raw Data
AI Insight
```

Streamlit의 Tabs 또는 Navigation을 사용한다.

---

# 22. Global Header

상단에는 다음을 표시한다.

**Japan Market Voice Dashboard**

Subtitle:

**Japan Social Listening & Consumer Voice Intelligence**

검색 Control:

```text
Keyword
Start Date
End Date
Source
[데이터 수집 및 분석]
```

마지막 데이터 갱신 시간도 표시한다.

---

# 23. Overview Dashboard

가장 중요한 Executive Summary 화면이다.

사용자가 30초 안에 시장 상황을 이해할 수 있어야 한다.

## KPI Cards

최소 다음을 표시한다.

### Total Mentions

분석 대상 Record 총 개수.

### Positive %

전체 분석 가능한 Mention 중 Positive 비율.

### Negative %

전체 분석 가능한 Mention 중 Negative 비율.

### Top Source

Mention이 가장 많은 Source.

가능하면 이전 비교 기간 데이터가 있을 경우 증감률도 제공한다.

데이터가 없으면 임의의 증감률을 생성하지 않는다.

---

# 24. Mention Trend

Line Chart.

X-axis:

Date

Y-axis:

Number of Mentions

가능하면 Source별 Toggle을 제공한다.

기간이 길면 적절한 단위로 자동 집계한다.

예:

* 짧은 기간 → Daily
* 긴 기간 → Weekly

---

# 25. Sentiment Visualization

Positive / Neutral / Negative 비율을 직관적으로 표시한다.

Pie/Donut/Bar 중 가독성이 가장 높은 형태를 선택한다.

동시에 기간별 Sentiment Trend도 제공할 수 있다.

---

# 26. Source Distribution

Source별 Mention 비율.

예:

```text
YouTube
X
Yahoo / News
みんカラ
Web
```

---

# 27. Top Topics / Keywords

상위 Topic을 표시한다.

단순 Word Cloud만 사용하지 않는다.

기본은 Horizontal Bar Chart 또는 Ranked List를 사용한다.

Word Cloud는 보조 시각화로만 사용할 수 있다.

---

# 28. Source-specific Views

## YouTube

표시:

* 관련 영상
* 영상 제목
* 게시일
* 댓글 수
* Sentiment
* 주요 Topic
* 대표 댓글
* Original URL

## X

표시:

* Post
* Date
* Sentiment
* Topic
* Engagement
* Original URL

## News / Yahoo

표시:

* Article title
* Publisher
* Date
* Summary
* Sentiment / Topic
* Original URL

## みんカラ

표시:

* Post / Blog title
* Date
* Summary
* Sentiment
* Main Topic
* Original URL

---

# 29. AI Insight Page

이 페이지는 마케팅 담당자를 위한 Executive Insight 화면이다.

다음 Section을 카드 형태로 구성한다.

### Overall Voice

현재 전체 시장 반응 요약.

### Positive Drivers

소비자가 긍정적으로 반응하는 요소.

### Negative Drivers

불만/우려 요소.

### Customer Questions

소비자가 궁금해하는 내용.

### Purchase Signals

구매 관심 신호.

### Purchase Barriers

구매 장애 요인.

### Emerging Topics

최근 나타나는 이슈.

### Marketing Implications

실행 가능한 마케팅 시사점.

---

# 30. Raw Data Explorer

분석 결과만 보여주지 않고 원본 데이터를 확인할 수 있어야 한다.

Table 제공.

필터:

* Source
* Date
* Sentiment
* Topic

가능한 Column:

```text
Date
Source
Title
Content
Sentiment
Topic
URL
```

URL은 클릭 가능한 형태로 제공한다.

---

# 31. Loading UX

수집 및 AI 분석은 시간이 걸릴 수 있으므로 사용자가 앱이 멈췄다고 생각하지 않도록 한다.

Progress 표시:

```text
1. 검색 준비
2. YouTube 데이터 수집
3. News 데이터 수집
4. X 데이터 수집
5. みんカラ 데이터 수집
6. 데이터 정제
7. Gemini 분석
8. Dashboard 생성
```

가능한 경우 Progress Bar 또는 Status Message를 사용한다.

---

# 32. Empty State

검색 전에는 빈 차트를 보여주지 않는다.

다음과 같은 안내를 표시한다.

**키워드와 분석 기간을 설정한 후 '데이터 수집 및 분석'을 실행하세요.**

---

# 33. No Data State

특정 Source에서 데이터가 발견되지 않으면:

**선택한 기간과 키워드에 해당하는 데이터를 찾지 못했습니다.**

라고 표시한다.

0개의 데이터를 AI가 임의 생성해서는 안 된다.

---

# 34. Error Handling

사용자에게 Python traceback을 그대로 노출하지 않는다.

예:

**YouTube 데이터 수집에 실패했습니다. 다른 Source의 분석은 계속 진행합니다.**

개발 로그에는 상세 오류를 기록한다.

---

# 35. Caching

동일한 Keyword + Date Range + Source에 대해 불필요하게 반복 API 호출하지 않도록 한다.

가능하면 Streamlit Cache를 활용한다.

단, 사용자가 명시적으로 새 데이터 수집을 요청할 수 있는 방법을 제공한다.

---

# 36. Storage

MVP에서는 복잡한 Database를 우선 도입하지 않는다.

단, 다음 요구사항을 고려하여 Storage Layer를 추상화한다.

* X 중복 방지
* 이전 분석 결과 재사용
* API 호출 절감
* 향후 DB 확장

로컬 개발에서는 SQLite 등을 사용할 수 있다.

## Important Deployment Constraint

Streamlit Community Cloud의 로컬 파일 시스템을 영구 저장소라고 가정하지 않는다.

배포 환경에서 지속적인 데이터 보존이 반드시 필요해질 경우 외부 persistent storage를 별도 도입할 수 있도록 구조를 분리한다.

MVP에서는 영구 저장이 필수가 아닌 기능 때문에 전체 구현을 복잡하게 만들지 않는다.

---

# 37. Performance

PoC이므로 대규모 데이터 처리를 목표로 하지 않는다.

우선 목표:

**검색 → 수집 → 분석 → Dashboard 표시가 사용자가 기다릴 수 있는 시간 안에 완료될 것.**

불필요한 API 호출을 최소화한다.

Gemini 분석은 Batch 기반으로 수행한다.

---

# 38. Security

다음 규칙을 반드시 준수한다.

## API Keys

절대 코드에 Hard-code하지 않는다.

로컬:

```text
.env
```

배포:

```text
Streamlit Secrets
```

## Git

`.gitignore`에 최소 다음을 포함한다.

```text
.env
.env.*
.streamlit/secrets.toml
__pycache__/
*.pyc
```

실제 Secret을 README, 로그, 오류 메시지에 출력하지 않는다.

---

# 39. Privacy / Data Scope

MVP에서는 공개적으로 접근 가능한 데이터만 사용한다.

회사 내부 데이터는 사용하지 않는다.

민감한 개인정보를 별도로 수집하거나 추론하는 기능을 구현하지 않는다.

---

# 40. Deployment

최종 배포 구조:

```text
Local Development
        ↓
GitHub Repository
        ↓
Streamlit Community Cloud
        ↓
https://xxxxx.streamlit.app
```

배포 완료 후 개인 노트북이 꺼져 있어도 Dashboard가 정상적으로 실행되어야 한다.

---

# 41. Required Project Structure

초기 구현에서는 다음과 유사한 모듈 구조를 사용한다.

```text
japan-market-voice/
│
├── app.py
├── requirements.txt
├── README.md
├── PROJECT.md
├── .gitignore
│
├── collectors/
│   ├── __init__.py
│   ├── youtube.py
│   ├── yahoo_news.py
│   ├── x.py
│   ├── minkara.py
│   └── web.py
│
├── analysis/
│   ├── __init__.py
│   ├── gemini.py
│   ├── sentiment.py
│   ├── topics.py
│   └── insights.py
│
├── processing/
│   ├── __init__.py
│   ├── normalize.py
│   ├── deduplicate.py
│   └── filters.py
│
├── storage/
│   ├── __init__.py
│   └── repository.py
│
├── ui/
│   ├── __init__.py
│   ├── overview.py
│   ├── sources.py
│   ├── insights.py
│   └── raw_data.py
│
└── config/
    └── settings.py
```

Codex는 더 단순하고 유지보수하기 좋은 구조가 명확히 필요하다고 판단할 경우 구조를 조정할 수 있다.

단, Collector / Analysis / UI / Configuration의 책임 분리는 유지한다.

---

# 42. Configuration

다음 값은 가능한 한 Config에서 변경 가능하도록 한다.

```text
Gemini model
YouTube max videos
YouTube comments per video
X max posts
Gemini batch size
Default date range
Request timeout
Cache TTL
```

Magic Number를 여러 파일에 반복해서 Hard-code하지 않는다.

---

# 43. Logging

최소 다음 이벤트를 기록한다.

```text
search_started
collector_started
collector_completed
collector_failed
records_collected
analysis_started
analysis_completed
analysis_failed
dashboard_completed
```

API Key, Secret 등 민감한 값은 로그에 기록하지 않는다.

---

# 44. MVP Priority

개발 우선순위는 다음과 같다.

## P0 — 반드시 작동

1. Streamlit Dashboard 실행
2. Keyword 입력
3. Start / End Date
4. Source 선택
5. 최소 하나 이상의 Source에서 실제 데이터 수집
6. Gemini 실제 분석
7. Sentiment
8. Top Topics
9. VOC
10. AI Insight
11. Trend Visualization
12. Raw Data 확인
13. Streamlit Cloud 배포

## P1 — 가능하면 구현

1. YouTube
2. 일본 News
3. Source별 Dashboard
4. 대표 VOC
5. Cache
6. Data Export

## P2 — P0/P1 완료 후 구현

1. X
2. Yahoo 댓글
3. みんカラ 댓글
4. 복잡한 DB
5. 장기 Historical Monitoring

---

# 45. Scope Reduction Rule

개발 시간이 부족하거나 특정 Source가 불안정하면 다음 순서로 기능을 포기한다.

```text
복잡한 Web Collector
↓
Yahoo 댓글
↓
みんカラ 댓글
↓
X
↓
부가 Visualization
```

다음은 끝까지 유지한다.

```text
Keyword / Date Search
+
실제 Data Collection
+
Gemini Analysis
+
Overview Dashboard
+
VOC
+
AI Insight
+
Raw Source Link
```

**한 개의 안정적인 Source가 실제로 작동하는 것이 네 개의 불안정한 Source보다 중요하다.**

---

# 46. Definition of Done

MVP는 다음 조건을 만족하면 완료된 것으로 본다.

### Functional

* 사용자가 Keyword를 입력할 수 있다.
* Start Date / End Date를 선택할 수 있다.
* Source를 선택할 수 있다.
* 실제 공개 데이터를 최소 하나 이상의 Source에서 가져온다.
* Gemini가 실제 수집 데이터를 분석한다.
* Sentiment 결과가 표시된다.
* 주요 Topic이 표시된다.
* VOC가 표시된다.
* Marketing Insight가 표시된다.
* Mention Trend가 표시된다.
* 원문과 Source URL을 확인할 수 있다.

### Reliability

* Source 하나가 실패해도 전체 Dashboard가 죽지 않는다.
* 데이터가 없으면 데이터가 없다고 표시한다.
* AI가 존재하지 않는 댓글/기사/VOC를 생성하지 않는다.
* API Key가 Client 또는 GitHub에 노출되지 않는다.

### Deployment

* GitHub Repository에서 Streamlit Community Cloud로 배포된다.
* `streamlit.app` URL로 접속 가능하다.
* 개인 개발 PC가 꺼져 있어도 작동한다.
* 새 브라우저 세션에서도 Dashboard가 정상 로드된다.

### Presentation

발표자가 다음 흐름을 실제로 보여줄 수 있다.

```text
Dashboard 접속
↓
PV5 입력
↓
기간 선택
↓
분석 실행
↓
실제 데이터 수집
↓
Sentiment / Topics / Trend 확인
↓
Representative VOC 확인
↓
AI Marketing Insight 확인
```

---

# 47. UI / Design Direction

Dashboard는 개발자용 Admin Tool처럼 보이지 않아야 한다.

목표:

**Corporate / Premium / Data-driven / Minimal**

원칙:

* 화면에 과도한 정보를 한 번에 넣지 않는다.
* 핵심 KPI를 상단에 배치한다.
* Chart title은 비개발자가 바로 이해할 수 있게 작성한다.
* 충분한 whitespace를 사용한다.
* 동일한 Card style을 유지한다.
* 숫자 → Trend → 이유 → Raw Voice 순으로 자연스럽게 읽히도록 한다.
* 발표 화면에서 작은 글씨를 최소화한다.
* 모바일보다 Desktop 화면을 우선한다.
* 불필요한 animation을 사용하지 않는다.
* Streamlit 기본 UI를 그대로 나열한 느낌을 최소화한다.

---

# 48. Development Principles for Codex

Codex는 본 문서를 프로젝트의 Source of Truth로 사용한다.

구현 시 다음 원칙을 따른다.

1. 먼저 현재 PROJECT.md 전체를 읽는다.
2. 즉시 모든 기능을 한 번에 구현하지 않는다.
3. 먼저 Architecture와 Implementation Plan을 작성한다.
4. P0 기능부터 구현한다.
5. 각 단계 완료 후 실행 가능한 상태를 유지한다.
6. 외부 Source 접근 방식이 불확실하면 임의의 API 또는 Credential이 존재한다고 가정하지 않는다.
7. Dummy Data로 실제 기능이 구현된 것처럼 가장하지 않는다.
8. Dummy Data가 필요한 경우 명확하게 `DEMO DATA`라고 표시한다.
9. 실제 API Key를 코드에 작성하지 않는다.
10. 오류 발생 시 원인을 확인한 뒤 최소 범위만 수정한다.
11. 기존 정상 기능을 불필요하게 Rewrite하지 않는다.
12. 새로운 Dependency 추가 전 기존 Stack으로 해결 가능한지 확인한다.
13. README에 로컬 실행 및 Streamlit 배포 방법을 작성한다.
14. 코드가 실행 가능한지 직접 확인한다.
15. 기능 구현보다 안정성과 발표 재현성을 우선한다.

---

# 49. First Codex Task

본 문서를 처음 읽은 Codex는 **바로 전체 애플리케이션을 구현하지 않는다.**

먼저 다음 작업만 수행한다.

1. PROJECT.md 전체 요구사항을 분석한다.
2. 구현상 불명확하거나 기술적으로 위험한 부분을 식별한다.
3. 각 Source별 실제 수집 가능성을 평가한다.
4. MVP에서 사용할 구체적인 수집 방법을 제안한다.
5. 필요한 API / Library / Credential을 정리한다.
6. Streamlit Community Cloud 환경에서 작동하지 않을 가능성이 있는 요소를 지적한다.
7. 최종 Architecture를 제안한다.
8. 구현 순서를 P0 → P1 → P2로 정리한다.
9. 아직 코드를 작성하지 않는다.

계획이 승인된 이후 구현을 시작한다.

---

# 50. Ultimate Product Goal

사용자가 매번 여러 사이트를 방문하여 일본 소비자 반응을 직접 읽는 대신,

**Keyword + Period만 입력하면 일본 시장의 온라인 Voice를 한 Dashboard에서 빠르게 이해할 수 있는 도구**

를 만드는 것이 최종 목표다.

본 프로젝트의 성공 기준은 Source의 개수가 아니라,

> **"기존 1시간 이상 걸리던 일본 시장 반응 파악 과정을 몇 분 안에 신뢰할 수 있는 형태로 제공할 수 있는가?"**

이다.
# 51. Critical Japan Market Scope Guardrail

## 51.1 목적

본 Dashboard의 분석 범위는 **일본 시장(Japan Market)** 으로 한정한다.

사용자가 `KIA`, `PV5`, `キア` 등의 Keyword를 검색했을 때 전 세계의 관련 콘텐츠를 모두 수집해서는 안 된다.

예를 들어 다음 콘텐츠는 Keyword와 관련되어 있더라도 분석 대상이 아니다.

```text
CNN: Kia sales increase in the United States
```

```text
Kia PV5 launches in Korea
```

```text
European review of Kia PV5
```

```text
American YouTube review of Kia EV9
```

본 Dashboard가 분석해야 하는 것은 다음이다.

> **일본 온라인 공간에서 생성되거나 일본 시장을 대상으로 하는 Kia/PV5 관련 기사, 영상, 게시물 및 소비자 반응**

따라서 모든 수집 데이터는 Gemini의 Sentiment/VOC 분석 전에 반드시 **Japan Market Scope Guardrail**을 통과해야 한다.

---

# 52. Core Scope Definition

본 프로젝트에서는 MVP 목적상 다음 데이터를 **Japan Consumer Voice**로 간주한다.

### 포함 가능

* 일본어 YouTube 댓글
* Yahoo! JAPAN의 사용자 댓글
* みんカラ의 일본어 사용자 게시물/댓글/리뷰
* 일본어 X Post
* 일본 시장 대상 YouTube 콘텐츠에 달린 일본어 댓글
* 일본 자동차 관련 일본어 사용자 반응

본 프로젝트에서는 이러한 데이터를 실무적으로 **일본 소비자 반응**으로 취급한다.

별도의 국적 추론 시스템을 구축하지 않는다.

---

# 53. 가장 중요한 구분

시스템은 다음 두 질문을 분리해서 판단한다.

## Question A — 콘텐츠 자체가 일본시장 Scope인가?

예:

```text
PV5 日本発売
```

→ YES

```text
Kia PV5 launches in the US
```

→ NO

## Question B — 소비자 반응이 일본어인가?

예:

```text
日本で発売されたら欲しい
```

→ YES

```text
I would buy this in California
```

→ NO

Dashboard의 소비자 반응 분석에는 기본적으로:

```text
Japan Market Content
+
Japanese Consumer Reaction
```

을 우선 사용한다.

---

# 54. Revised Core Pipeline

기존 Pipeline의 `Language / Japan Relevance Filtering`을 다음 구조로 구체화한다.

```text
USER INPUT
Keyword / Date / Source
        ↓
INPUT VALIDATION
        ↓
KEYWORD NORMALIZATION
        ↓
JAPAN-FOCUSED SEARCH QUERY GENERATION
        ↓
SOURCE SEARCH
        ↓
RAW DATA COLLECTION
        ↓
TARGET ENTITY FILTER
        ↓
JAPAN MARKET SCOPE FILTER
        ↓
JAPANESE LANGUAGE FILTER
        ↓
DATE FILTER
        ↓
DUPLICATE / NOISE FILTER
        ↓
FINAL JAPAN DATASET
        ↓
GEMINI ANALYSIS
        ↓
SENTIMENT / TOPIC / VOC
        ↓
DASHBOARD
```

---

# 55. Stage 1 — Japan-Focused Search Query Generation

사용자가 입력한 Keyword를 그대로 검색하는 것을 기본 전략으로 사용하지 않는다.

예를 들어:

```text
KIA
```

만 검색하면 미국, 유럽, 한국 등 전 세계 콘텐츠가 과도하게 포함될 수 있다.

따라서 Source별 검색 단계에서 일본 관련 Query를 생성한다.

---

# 56. Query Expansion Examples

## User Input

```text
KIA
```

검색 후보:

```text
KIA 日本
KIA 日本市場
KIA 日本発売
KIA 日本販売
キア
キア 日本
キア 日本市場
```

## User Input

```text
PV5
```

검색 후보:

```text
PV5 日本
PV5 日本市場
PV5 日本発売
PV5 日本販売
PV5 キア
キア PV5
KIA PV5 日本
```

## User Input

```text
EV3
```

검색 후보:

```text
EV3 日本
KIA EV3 日本
キア EV3
EV3 日本発売
EV3 日本価格
```

---

# 57. Query Expansion Limit

검색 Query가 과도하게 증가하여 API 호출 또는 수집 시간이 폭증하지 않도록 제한한다.

기본값:

```text
MAX_QUERY_VARIANTS_PER_SOURCE = 5
```

Source 특성에 맞게 가장 효과적인 Query만 사용한다.

중복 결과는 Native ID 또는 URL 기준으로 제거한다.

---

# 58. Important Query Rule

Japan-focused Query에 검색되었다는 이유만으로 데이터를 자동 승인하지 않는다.

예:

```text
Query = KIA 日本
```

검색 결과:

```text
CNN: Kia reports record sales in America
```

이 콘텐츠는 Japan Market Scope Filter에서 제거한다.

즉:

```text
Japan Query
≠
Japan Content
```

이다.

---

# 59. Stage 2 — Target Entity Filter

특히 `KIA`와 같은 짧은 Keyword는 다른 의미의 문자열과 충돌할 수 있다.

따라서 수집된 콘텐츠가 실제 Kia Automotive 관련 콘텐츠인지 확인한다.

다음 표현을 자동차 브랜드 관련 Strong Signal로 활용할 수 있다.

```text
Kia
KIA
キア
PV5
EV3
EV4
EV5
EV6
EV9
PBV
自動車
車
電気自動車
EV
カーゴ
Passenger
Cargo
```

---

# 60. Entity Result

각 Record에 다음 필드를 생성한다.

```text
entity_match
```

허용 값:

```text
target
unrelated
uncertain
```

### target

실제 Kia 또는 사용자가 지정한 자동차/제품 Entity와 관련.

→ 다음 단계 진행.

### unrelated

동명이의어나 완전히 다른 내용.

→ 분석에서 제외.

### uncertain

판단이 어려운 경우.

→ Gemini Lightweight Classification으로 확인 가능.

---

# 61. Stage 3 — Japan Market Scope Filter

이 단계가 본 Dashboard의 핵심 Guardrail이다.

수집된 기사/영상/게시물이 **일본 시장과 실제로 관련되어 있는지** 판단한다.

---

# 62. Japan Market Scope — INCLUDE

다음과 같은 콘텐츠는 분석 대상에 포함한다.

## 일본 출시 / 판매

```text
Kia PV5、日本で発売
```

```text
キア、日本市場でPV5を販売
```

```text
PV5の日本導入が決定
```

## 일본 가격

```text
PV5の日本価格
```

```text
キアPV5、日本では589万円から
```

## 일본 소비자 / 시장

```text
日本市場でのKiaの評価
```

```text
日本でPV5は売れるのか
```

## 일본 이용환경

```text
日本の道路でPV5は使いやすい？
```

```text
日本の充電環境でPV5を使えるか
```

## 일본 정책 / 보조금 / 인프라

```text
日本のEV補助金
```

```text
国内充電インフラ
```

## 일본 공식 활동

```text
Kia Japan
```

```text
Kia PBV Japan
```

```text
日本での試乗イベント
```

---

# 63. Japan Market Scope — EXCLUDE

다음과 같은 콘텐츠는 Keyword와 관련되어 있더라도 기본적으로 제외한다.

## 미국 중심

```text
Kia sales rise in the United States
```

```text
Kia opens new factory in Georgia
```

## 한국 중심

```text
Kia PV5 launches in Korea
```

```text
韓国でPV5販売開始
```

## 유럽 중심

```text
Kia PV5 European launch
```

```text
PV5 launches in Germany
```

## 중국 등 기타 해외

```text
Kia sales in China
```

## 글로벌 기업 뉴스

```text
Kia global operating profit rises
```

일본시장과 직접적인 연결이 없다면 제외한다.

---

# 64. Foreign Market Comparison Exception

해외 내용을 언급한다고 무조건 제외하지 않는다.

다음처럼 **일본시장과 비교하기 위한 내용**이라면 포함한다.

```text
韓国ではすでに販売されているが、
日本ではいつ発売されるのか
```

→ INCLUDE

```text
欧州価格と比較すると、
日本価格は高く感じる
```

→ INCLUDE

반면:

```text
韓国でPV5の販売が好調
```

일본 관련 내용이 전혀 없다면:

→ EXCLUDE

---

# 65. Japan Market Signals

Rule-based Pre-filter에서 다음 표현을 Japan Market Signal로 사용할 수 있다.

```text
日本
日本市場
国内
日本向け
日本仕様
日本導入
日本発売
国内発売
日本販売
日本価格
Kia Japan
キアジャパン
```

자동차 이용 Context:

```text
円
万円
補助金
販売店
ディーラー
試乗
納車
予約
輸入車
商用車
車中泊
日本の道路
日本の充電
```

---

# 66. Important Rule — Japanese Website Is Not Enough

사이트가 일본 사이트라는 이유만으로 기사를 분석에 포함하지 않는다.

예:

```text
Yahoo! JAPAN
```

에 다음 기사가 검색될 수 있다.

```text
キア、米国で過去最高販売
```

이 기사는 일본어이고 Yahoo! JAPAN에 존재하지만 일본시장에 관한 기사가 아니다.

→ 분석 대상에서 제외한다.

---

# 67. Yahoo! JAPAN Article Guardrail

Yahoo 기사에 대해서는 다음 순서로 판단한다.

### Step 1

Kia / Target Product 관련 기사인가?

NO → 제외

### Step 2

기사의 핵심 사건이 일본에서 발생하거나 일본시장을 대상으로 하는가?

YES → 포함

### Step 3

해외 사건이지만 일본시장과 직접 비교하거나 일본시장 영향을 설명하는가?

YES → 포함 가능

### Step 4

단순 해외 뉴스 번역/전재인가?

YES → 제외

---

# 68. Yahoo! JAPAN Comment Rule

MVP에서는 **Yahoo! JAPAN 기사에 달린 일본어 사용자 댓글을 일본 소비자 반응으로 간주한다.**

단, 부모 기사 자체가 Japan Market Scope를 통과한 경우를 우선한다.

즉:

```text
Japan-relevant Yahoo Article
+
Japanese Yahoo Comment
```

→ Japan Consumer Voice

반면 부모 기사가 완전히 미국시장에 관한 기사라면 그 댓글은 본 Dashboard의 일본시장 VOC에 기본적으로 포함하지 않는다.

---

# 69. YouTube Video Scope Guardrail

YouTube에서 가장 중요한 것은 **전 세계 YouTube 결과를 그대로 가져오지 않는 것**이다.

영상 후보를 판단할 때 다음 요소를 활용한다.

```text
Video Title
Description
Channel
Language
Search Query
Published Date
```

---

# 70. YouTube INCLUDE Examples

```text
KIA PV5 日本発売
```

```text
キアPV5を日本で試乗
```

```text
PV5 日本仕様をチェック
```

```text
Kia PV5は日本市場で成功する？
```

```text
日本上陸したKia PV5をレビュー
```

→ INCLUDE

---

# 71. YouTube EXCLUDE Examples

```text
Kia PV5 Full Review | USA
```

```text
Kia PV5 Korean Launch
```

```text
Kia PV5 Europe Road Test
```

```text
CNN reviews the new Kia
```

→ 일본시장 Context가 없다면 EXCLUDE

---

# 72. YouTube Comment Rule

Japan Market Scope를 통과한 영상에서 수집된 **일본어 댓글은 일본 소비자 반응으로 간주한다.**

예:

Parent Video:

```text
Kia PV5 日本発売について解説
```

Comment:

```text
欲しい
```

→ INCLUDE

```text
ちょっと高いな
```

→ INCLUDE

```text
デザイン好き
```

→ INCLUDE

댓글 자체에 `日本`이라는 단어가 없어도 된다.

부모 영상이 이미 일본시장 Scope이기 때문이다.

---

# 73. Japanese Comment from Global Video

글로벌 영상에서도 일본어 댓글이 발견될 수 있다.

예:

Parent:

```text
Kia PV5 Global Reveal
```

Comment:

```text
日本でも発売してほしい
```

→ INCLUDE

Comment:

```text
日本でこのサイズは大きすぎるかも
```

→ INCLUDE

Comment:

```text
かっこいい
```

→ 부모 영상도 일본시장 Scope가 아니고 댓글에도 일본 Context가 없음.

MVP에서는 기본적으로 제외 또는 Low Priority 처리한다.

---

# 74. Japanese Language Rule

소비자 Voice 분석 단계에서는 다음 데이터를 일본 소비자 반응 후보로 간주한다.

```text
Japanese-language YouTube Comment
Japanese Yahoo Comment
Japanese X Post
Japanese みんカラ Post / Comment
```

Language Detection 결과는:

```text
ja
non_ja
unknown
```

정도로 단순화할 수 있다.

MVP에서는 일본어 분석에 집중한다.

---

# 75. X Japan Scope

X에서는 다음 두 조건을 우선 사용한다.

### A. Japanese-language Post

그리고 가능하면:

### B. Japan-context Query

예:

```text
KIA 日本
キア
PV5 日本
キア PV5
```

일본어 X Post는 Japan Consumer Voice 후보로 취급한다.

다만 명백하게 다른 국가 시장만 이야기하는 Post는 제외할 수 있다.

---

# 76. みんカラ Scope

みんカラ는 일본 자동차 사용자 커뮤니티이므로 다른 Source보다 강한 Japan Consumer Signal로 취급한다.

다음 데이터는 기본적으로 Japan Consumer Voice 후보로 사용할 수 있다.

```text
Japanese Blog
Japanese Review
Japanese User Post
Japanese Comment
```

Target Keyword와 자동차 Entity가 일치하면 분석에 포함한다.

---

# 77. Consumer Voice vs Article Separation

뉴스 기사와 소비자 댓글을 하나의 Sentiment 계산에 섞지 않는다.

다음 Dataset을 분리한다.

```text
market_content
consumer_voice
```

## market_content

* Yahoo / News 기사
* Web 기사
* 공식 발표

활용:

* Mention Trend
* 주요 시장 Topic
* 기사량
* 시장 이슈

## consumer_voice

* YouTube 댓글
* Yahoo 댓글
* X Post
* みんカラ 글/댓글/리뷰

활용:

* Positive / Neutral / Negative
* VOC
* Positive Drivers
* Negative Drivers
* Purchase Signal
* Purchase Barrier

---

# 78. Consumer Sentiment KPI Rule

Overview의:

```text
Positive %
Neutral %
Negative %
```

는 기본적으로 `consumer_voice` Dataset에서 계산한다.

뉴스 기사의 논조가 소비자 Sentiment에 섞이지 않도록 한다.

---

# 79. Date Guardrail

모든 Source는 사용자가 선택한 기간을 준수한다.

Timezone:

```text
Asia/Tokyo
JST
UTC+09:00
```

Start Date / End Date는 Inclusive.

예:

```text
2026-08-01 00:00:00 JST
~
2026-08-15 23:59:59 JST
```

---

# 80. Unknown Date Rule

게시일을 확인할 수 없는 콘텐츠에 임의 날짜를 부여하지 않는다.

날짜가 없는 데이터는:

```text
published_at = null
date_status = unknown
```

으로 저장한다.

기간 Trend 계산에서는 제외한다.

Raw Data에서는 조회 가능하다.

---

# 81. Duplicate Guardrail

다음 순서로 중복을 제거한다.

1. Native Content ID
2. URL
3. Normalized text hash

동일 기사 Syndication의 경우 가능한 범위에서 중복을 제거한다.

---

# 82. Final Scope Fields

Common Data Schema에 다음 필드를 추가한다.

```text
entity_match
japan_market_relevant
japan_market_score
japan_scope_reason
language
content_group
date_eligible
exclusion_reason
eligible_for_analysis
```

---

# 83. japan_market_score

Japan Market 관련성을:

```text
0.0 ~ 1.0
```

으로 표현할 수 있다.

기본 기준:

```text
>= 0.75
INCLUDE

0.50 ~ 0.74
REVIEW / LOW CONFIDENCE

< 0.50
EXCLUDE
```

Threshold는 Config에서 변경 가능하게 한다.

---

# 84. Japan Scope Classifier

단순 Keyword Rule만으로 어려운 데이터는 Gemini Lightweight Classification을 사용할 수 있다.

Classifier는 다음 JSON 형태로 반환한다.

```json
{
  "entity_match": true,
  "japan_market_relevant": true,
  "japan_market_score": 0.92,
  "content_group": "consumer_voice",
  "reason": "Content discusses PV5 launch and pricing in Japan"
}
```

---

# 85. Gemini Japan Scope Prompt

Classifier Prompt에는 다음 원칙을 명확하게 입력한다.

```text
You are filtering content for a Japan-market social listening dashboard.

The target is NOT global Kia-related content.

Include content when the main subject concerns:
- Japan market
- sales or launch in Japan
- use of the product in Japan
- Japanese pricing
- Japanese dealers
- Japanese infrastructure
- Japanese regulations or subsidies
- Japanese consumer experience
- comparison with foreign markets when Japan is a meaningful part of the comparison

Exclude content when it concerns only:
- United States
- Korea
- Europe
- China
- other foreign markets
- global corporate news

A page being written in Japanese or hosted on a Japanese website is NOT by itself enough to classify an article as Japan-market content.

For consumer comments:
Japanese comments on Japan-market content should be treated as Japan consumer voice.

Do not invent facts.
Return only the requested structured output.
```

---

# 86. Scope Filter Strategy

비용과 속도를 위해 모든 Record를 처음부터 Gemini에 보내지 않는다.

다음 2단계 방식을 사용한다.

```text
Stage A
Cheap Rule-based Filter
        ↓
Clear INCLUDE / EXCLUDE

Stage B
Only ambiguous records
        ↓
Gemini Scope Classifier
```

이를 통해 Gemini API 호출량을 줄인다.

---

# 87. Clear Rule-based INCLUDE

예:

Title:

```text
キアPV5、日本発売を正式発表
```

Japan Signal + Target Entity가 명확.

→ Gemini Scope Classification 없이 INCLUDE 가능.

---

# 88. Clear Rule-based EXCLUDE

예:

```text
Kia posts record sales in the United States
```

Target = Kia

Foreign Market = US

Japan Signal = None

→ EXCLUDE 가능.

---

# 89. Ambiguous Case

예:

```text
キア、新型PV5を公開
```

일본어이지만 기사 자체가 일본 출시 기사인지 글로벌 공개 기사인지 불명확.

→ Gemini Scope Classifier 사용.

---

# 90. Guardrail Audit

Dashboard 내부에서 수집 품질을 확인할 수 있도록 최소 다음 정보를 기록한다.

```text
Raw Collected
Japan Market Included
Foreign / Irrelevant Excluded
Duplicates Removed
Final Consumer Voice
Final Market Content
```

개발/발표 시 필요하면 Expander로 확인 가능하도록 한다.

---

# 91. Example Audit

```text
Raw Collected              820
Japan Market Relevant      493
Foreign Market Excluded    211
Entity Mismatch             18
Duplicates Removed          42
Final Records              451

Consumer Voice             328
Market / News Content      123
```

---

# 92. Most Important Guardrail Tests

Codex는 다음 Test Case를 반드시 검증한다.

## Test 1

```text
Kia PV5 launches in the United States
```

Expected:

```text
EXCLUDE
```

---

## Test 2

```text
キアPV5、日本で販売開始
```

Expected:

```text
INCLUDE
```

---

## Test 3

```text
韓国でKia PV5販売開始
```

Expected:

```text
EXCLUDE
```

---

## Test 4

```text
韓国では販売済みだが、日本発売はいつ？
```

Expected:

```text
INCLUDE
```

---

## Test 5

Source:

```text
Yahoo! JAPAN
```

Article:

```text
キア、米国市場で販売記録更新
```

Expected:

```text
EXCLUDE
```

---

## Test 6

Source:

```text
Yahoo! JAPAN
```

Article:

```text
キアPV5、日本市場に正式導入
```

Expected:

```text
INCLUDE
```

---

## Test 7

Parent YouTube Video:

```text
Kia PV5 日本発売解説
```

Comment:

```text
欲しい
```

Expected:

```text
INCLUDE AS CONSUMER VOICE
```

---

## Test 8

Parent YouTube Video:

```text
Kia PV5 Global Reveal
```

Comment:

```text
日本でも売ってほしい
```

Expected:

```text
INCLUDE AS CONSUMER VOICE
```

---

## Test 9

Parent YouTube Video:

```text
Kia PV5 USA Review
```

Comment:

```text
Great car!
```

Expected:

```text
EXCLUDE
```

---

## Test 10

みんカラ Japanese User Review:

```text
PV5は車中泊に使いやすそう
```

Expected:

```text
INCLUDE AS CONSUMER VOICE
```

---

# 93. Technical Guardrail — Streamlit Cloud Compatibility

Streamlit Community Cloud에서 안정적으로 동작하는 것을 우선한다.

Collector는 기본적으로 Lightweight HTTP 기반 접근을 우선한다.

권장:

```text
requests
httpx
urllib
feedparser
BeautifulSoup4
Official REST API
RSS
```

다음 Browser Automation은 기본 선택으로 사용하지 않는다.

```text
Selenium
Playwright
Chromium automation
```

Browser Automation은 다른 방법이 없고 실제 Streamlit Cloud 배포 테스트를 통과한 경우에만 예외적으로 사용한다.

---

# 94. Streamlit Rerun Guardrail

외부 데이터 수집은 명시적 버튼 클릭 시에만 실행한다.

권장:

```python
st.form_submit_button("데이터 수집 및 분석")
```

다음 행동으로 API/Collector가 다시 실행되어서는 안 된다.

```text
Tab 이동
Chart Filter 변경
Expander 열기
UI rerender
페이지 단순 조회
```

---

# 95. Session State

한 번의 분석 결과는 `st.session_state`에 보관하여 일반적인 Streamlit rerun에서 유지한다.

예:

```text
search_params
raw_records
filtered_records
analysis_results
collector_status
last_successful_run
```

`st.session_state`는 영구 DB로 간주하지 않는다.

---

# 96. Cache

외부 수집 및 반복 계산에는 `st.cache_data`를 적절히 활용한다.

Cache Key:

```text
keyword
start_date
end_date
sources
collector_version
```

사용자는 필요할 경우:

```text
[최신 데이터 다시 수집]
```

을 통해 명시적으로 Cache를 갱신할 수 있어야 한다.

---

# 97. Partial Failure Guardrail

Source 하나가 실패해도 전체 Dashboard는 정상적으로 동작한다.

예:

```text
YouTube      SUCCESS
Yahoo        SUCCESS
X            FAILED
みんカラ     SUCCESS
```

사용자에게:

```text
X 데이터 수집에 실패했습니다.
나머지 Source의 분석 결과를 표시합니다.
```

라고 표시한다.

---

# 98. Gemini Structured Output

Gemini 응답은 자유 형식 Markdown에 의존하지 않는다.

지원되는 경우 Structured Output을 사용한다.

```text
response_mime_type = application/json
```

JSON Schema 또는 Pydantic Model로 응답 구조를 검증한다.

---

# 99. Gemini Validation Failure

Gemini 출력 Schema 검증 실패 시:

```text
First attempt
↓
Validation failed
↓
Retry
↓
Validation failed again
↓
Mark analysis failed
```

무한 Retry 금지.

기본:

```text
MAX_AI_RETRIES = 2
```

---

# 100. Evidence Guardrail

Gemini가 존재하지 않는 VOC를 생성해서는 안 된다.

Representative VOC는 반드시 실제 수집 데이터의 Record ID와 연결한다.

예:

```json
{
  "record_id": "youtube_comment_103",
  "quote": "日本でも売ってほしい",
  "source": "youtube"
}
```

Record ID가 실제 Dataset에 존재하지 않으면 해당 VOC를 표시하지 않는다.

---

# 101. Secret Resolution

로컬과 Streamlit Cloud에서 동일한 Key 이름을 사용한다.

예:

```text
GEMINI_API_KEY
YOUTUBE_API_KEY
X_BEARER_TOKEN
```

Secret 조회를 하나의 함수로 통합한다.

Concept:

```python
def get_secret(name):
    value = os.getenv(name)

    if value:
        return value

    try:
        return st.secrets.get(name)
    except Exception:
        return None
```

Secret 값 자체는 화면이나 로그에 출력하지 않는다.

---

# 102. Final Guardrail Principle

본 시스템의 핵심 Filter는:

```text
Japanese Language Filter
```

하나가 아니다.

정확한 순서는:

```text
TARGET BRAND
+
JAPAN MARKET SCOPE
+
JAPANESE CONSUMER VOICE
```

이다.

즉 본 Dashboard는:

> **전 세계 Kia 데이터를 가져와 일본어만 골라내는 시스템이 아니라, 처음부터 일본 시장 관련 데이터와 일본 온라인 소비자 Voice만 선별하여 분석하는 시스템**

으로 구현한다.

가장 중요한 원칙:

**Japan Market First.**

**Foreign Market Noise Excluded.**

**Japanese Consumer Voice Prioritized.**
