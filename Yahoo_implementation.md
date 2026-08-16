PRD.md, IMPLEMENTATION_PLAN.md, 현재 구현된 Collector Protocol,
Processing Pipeline, Japan Market Guardrail, Gemini Analysis,
Streamlit Dashboard 구조를 기준으로 새로운 상위 Source인
`Yahoo Japan`을 구현해주세요.

이번 Task는 Yahoo Japan ecosystem을 하나의 Source로 추가하는 작업입니다.

기존에 정상 동작 중인 아래 기능은 불필요하게 수정하지 마세요.

- YouTube Collector
- YouTube API
- Gemini model / schema
- RecordAnalysis
- AggregateAnalysis
- Evidence reconciliation
- Japan Market Guardrail
- 현재 Streamlit UI 디자인

========================================
0. 최종 목표
========================================

Dashboard의 Source 구조를 최종적으로 다음처럼 확장할 수 있어야 합니다.

YouTube

Yahoo Japan
├── Yahoo!ニュース
│   ├── News Articles
│   └── ヤフコメ (News Comments)
│
├── Yahoo!知恵袋
│   ├── Questions
│   └── Answers
│
└── Yahoo!リアルタイム検索
    └── Public realtime posts / X-origin public posts

みんカラ (향후 별도 구현)


Dashboard 상위 Source 값은:

source = yahoo_japan

으로 통일하고,

내부 record는 반드시 sub_source로 구분하세요.

허용 sub_source:

- yahoo_news_article
- yahoo_news_comment
- yahoo_chiebukuro_question
- yahoo_chiebukuro_answer
- yahoo_realtime_post


========================================
1. 구현 우선순위
========================================

P0 — 반드시 최대한 구현

1. Yahoo!ニュース 기사 검색/수집
2. Yahoo!ニュース 공개 댓글(ヤフコメ)
3. Yahoo!知恵袋 질문
4. Yahoo!知恵袋 답변

P1 — 위 P0 완료 후 시도

5. Yahoo!リアルタイム検索

Realtime Search는 X API를 직접 사용하지 않는 방식만 검토하세요.

X API Key나 유료 X API를 요구하는 구현은 이번 Task에서 사용하지 마세요.


========================================
2. 매우 중요한 구현 원칙
========================================

Yahoo Japan에 존재한다는 이유만으로 모든 데이터를 분석하지 마세요.

항상 기존 Pipeline을 유지하세요.

Keyword
↓
Yahoo candidate discovery
↓
Entity relevance
↓
Japan Market Scope Guardrail
↓
Language / date filtering
↓
Deduplication
↓
Content classification
↓
eligible dataset
↓
Gemini analysis
↓
Dashboard


예를 들어 Keyword = PV5인 경우:

INCLUDE:

- キアPV5、日本市場へ正式導入
- PV5の日本価格は？
- 日本の充電環境では使いにくそう
- 韓国では発売済み、日本ではいつ発売？
- 日本でPV5を使うならサイズが気になる

EXCLUDE:

- Kia PV5 launches in the United States
- 韓国でPV5販売開始
- Kia expands European factory
- 米国でKia販売台数更新

Yahoo Japan에 올라온 일본어 기사라 하더라도
일본 시장과 무관한 해외시장 전용 내용이면 제외하세요.


========================================
3. Yahoo!ニュース — Article Discovery
========================================

Yahoo News 내부 검색 페이지를 후보 기사 discovery 방식으로
안정적으로 사용할 수 있는지 우선 확인하세요.

예시:

https://news.yahoo.co.jp/search?p=pv5&ei=utf-8

Keyword:

PV5
KIA
キア

QueryPlanner를 재사용하여 최대 3~5개 정도의 Japan-focused
query variant만 생성하세요.

예:

PV5
キア PV5
PV5 日本

KIA
キア
KIA 日本

과도한 query expansion은 금지합니다.


검색 결과에서 가능한 경우 다음을 확보하세요.

- article id
- title
- article URL
- publisher
- published_at
- snippet / summary
- category
- comment count
- query_used


Yahoo 카테고리 예:

主要
国内
経済
IT
国際
地域
その他

카테고리는 metadata입니다.

category를 먼저 필터링하여 검색 범위를 제한하지 마세요.

예:

国際 카테고리라도
「韓国では発売済み、日本ではPV5を今秋導入」
이면 INCLUDE할 수 있습니다.

반대로 国内 카테고리라도
Target Entity와 무관하면 EXCLUDE입니다.


========================================
4. Yahoo News Article Schema
========================================

Yahoo News 기사:

source = yahoo_japan
sub_source = yahoo_news_article
content_type = article
content_group = market_content

최소 필드:

- id
- source
- sub_source
- keyword
- query_used
- title
- content / summary
- publisher
- published_at
- collected_at
- url
- category
- comment_count
- entity_match
- japan_market_relevant
- japan_market_score
- japan_scope_reason
- date_eligible
- exclusion_reason
- eligible_for_analysis


News Article 자체는 Consumer Sentiment 계산에서 제외하세요.

기사 활용:

- Total Mentions
- Mention Trend
- Market Topics
- Market Issues
- News Summary
- Market Context

기사 자체를 다음에 사용하지 마세요.

- Consumer Sentiment
- Customer VOC
- Purchase Intent
- Purchase Barrier


========================================
5. ヤフコメ — Yahoo News Comments
========================================

이 기능은 P0이며 매우 중요합니다.

Japan Market Guardrail을 통과한 Yahoo News 기사에
공개 댓글이 존재하면 가능한 범위에서 댓글을 수집하세요.

예:

Article:
「キアPV5、日本市場に参入」

Comment:
「日本では充電インフラがまだ不安」

Article:
market_content

Comment:
consumer_voice


Yahoo News Comment schema:

source = yahoo_japan
sub_source = yahoo_news_comment
content_type = comment
content_group = consumer_voice


최소 필드:

- id
- parent_id
- parent_url
- article_title
- content
- author (공개된 경우)
- published_at (신뢰 가능한 경우)
- collected_at
- reply_count (가능한 경우)
- reaction_empathy
- reaction_naruhodo
- reaction_hmm
- language
- url
- eligible_for_analysis


Yahoo의 일본어 댓글은 본 프로젝트 목적상
Japan Consumer Voice로 취급합니다.

Yahoo Comment는 반드시 다음 분석에 포함하세요.

- Positive / Neutral / Negative
- Topics
- Positive Drivers
- Negative Drivers
- Customer Questions
- Purchase Signals
- Purchase Barriers
- Representative VOC


단:

Yahoo reaction:

共感した
なるほど
うーん

등은 engagement metadata일 뿐입니다.

이 값을 sentiment label로 직접 변환하지 마세요.

Gemini sentiment와 별도로 저장합니다.


========================================
6. Comment Parent Guardrail
========================================

기본적으로 댓글은 Japan Market Relevant Article의 댓글만
Yahoo VOC Dataset에 포함하세요.

예:

Article:
「Kia、米国で販売台数過去最高」

일본시장 내용 없음
→ Article EXCLUDE
→ 해당 댓글도 Yahoo Japan VOC에서 기본 EXCLUDE


반대로:

Article:
「Kia PV5、日本市場へ参入」

Comment:
「価格が高そう」

→ consumer_voice INCLUDE


========================================
7. Comment Failure Isolation
========================================

댓글 수집 실패 때문에 기사까지 버리지 마세요.

예:

Article = SUCCESS
Comments = FAILED

→ Article 유지
→ Yahoo News Comments만 partial failure


댓글 0개:

→ 정상
→ Article 유지


한 기사 댓글 parsing 실패:

→ 다른 기사 댓글 수집 계속


========================================
8. Yahoo!知恵袋
========================================

Yahoo Chiebukuro를 P0 Consumer Voice Source로 구현해주세요.

중요:

과거 API가 존재했다고 가정하거나
존재하지 않는 현재 API를 만들어내지 마세요.

현재 공개 웹에서 keyword 검색과 Q&A metadata를
HTTP 기반으로 안정적으로 접근할 수 있는지 먼저 검증하세요.

우선 검토:

- requests / httpx
- BeautifulSoup
- 공개 HTML
- 공개 검색 페이지

금지:

- Selenium
- Playwright
- 로그인 자동화
- Cookie 우회
- CAPTCHA bypass
- Anti-bot bypass
- private endpoint 추측


Keyword 예:

PV5
キア PV5
KIA PV5
キア
KIA 日本
PV5 日本


========================================
9. Chiebukuro Question
========================================

Question:

source = yahoo_japan
sub_source = yahoo_chiebukuro_question
content_type = question
content_group = consumer_voice


최소 필드:

- id
- title
- content
- published_at
- collected_at
- url
- category
- answer_count
- keyword
- query_used


질문 자체도 Consumer Voice입니다.

예:

「PV5は日本ではいくらになりますか？」

→ Customer Question
→ consumer_voice

「日本の駐車場でPV5は大きすぎませんか？」

→ concern
→ consumer_voice


따라서 Question도 Gemini 분석 대상입니다.


========================================
10. Chiebukuro Answers
========================================

Answer:

source = yahoo_japan
sub_source = yahoo_chiebukuro_answer
content_type = answer
content_group = consumer_voice


최소:

- id
- parent_id
- parent_url
- content
- published_at
- collected_at
- reaction / best answer metadata (가능한 경우)


답변도 Consumer Voice로 사용할 수 있습니다.

단순 사실 전달이면 sentiment를 억지로 긍정/부정으로 만들지 말고
Neutral / Unknown을 허용하세요.


========================================
11. Yahoo!リアルタイム検索
========================================

P0가 정상적으로 완료된 이후에만 시도하세요.

목적:

별도 X API를 사용하지 않고
Yahoo Realtime Search가 공개적으로 보여주는 실시간 게시물을
Japan Consumer Voice 보조 Source로 활용 가능한지 확인하는 것입니다.


이번 Task에서 먼저 feasibility를 확인하세요.

확인 항목:

1. keyword 검색 가능 여부
2. 로그인 없이 공개 결과 접근 가능 여부
3. HTTP 기반 접근 가능 여부
4. 게시물 text 확보 가능 여부
5. timestamp 확보 가능 여부
6. 원본 URL 확보 가능 여부
7. engagement metadata 확보 가능 여부
8. Streamlit Community Cloud 호환성


X API를 직접 호출하지 마세요.

X_API_KEY, bearer token, 유료 X API는 이번 구현에 사용하지 않습니다.


========================================
12. Realtime Search 구현 가능 시
========================================

source = yahoo_japan
sub_source = yahoo_realtime_post
content_type = post
content_group = consumer_voice


가능 필드:

- id
- content
- published_at
- collected_at
- url
- origin_platform
- native_post_id
- engagement_count
- language
- query_used


기존 Japan Market Guardrail 적용.

INCLUDE:

「PV5、日本でちょっと気になる」
「キアPV5の日本価格はいくらだろう」
「日本で使うには大きいかも」

EXCLUDE:

미국시장 전용 게시물
한국시장 전용 게시물
자동차와 무관한 KIA
Spam


========================================
13. X 중복 대비
========================================

향후 Direct X Source가 추가될 가능성에 대비하세요.

Yahoo Realtime record에는 가능한 경우:

- origin_platform
- native_post_id
- canonical_url

을 저장하세요.

향후 X API Source가 추가될 경우 동일 게시물을
cross-source deduplication 할 수 있어야 합니다.


========================================
14. Realtime Search 실패 시
========================================

안정적인 공개 접근이 불가능하거나
403 / access denied / anti-bot 등이 발생하면 우회하지 마세요.

다음처럼 capability만 남기세요.

enabled = false
availability_reason = "No stable public collection method"

Yahoo News / Comments / Chiebukuro는 정상 유지하세요.


========================================
15. Date Guardrail
========================================

사용자가 선택한 Start Date / End Date를 JST 기준으로 적용하세요.

각 record의 실제 published_at을 사용하세요.

날짜 확인 불가능:

published_at = null
date_eligible = false

임의 날짜 생성 금지.

Trend 분석에서는 제외할 수 있으나 Raw Data에는 유지 가능합니다.


========================================
16. Deduplication
========================================

News Article:

1. native article ID
2. canonical URL
3. normalized title + publisher + date
4. content hash


News Comment:

1. native comment ID
2. parent_id + native id
3. parent_id + normalized content hash


Chiebukuro Question:

1. native question ID
2. canonical URL
3. normalized content hash


Chiebukuro Answer:

1. native answer ID
2. parent_id + native answer id
3. parent_id + normalized content hash


Realtime Post:

1. native_post_id
2. canonical_url
3. origin_platform + normalized content hash


주의:

다른 사람이 동일한 짧은 문장을 작성했다는 이유만으로
자동 duplicate 처리하지 마세요.


========================================
17. Collection Limits
========================================

MVP에서는 무제한 수집하지 마세요.

Config 기본값 예:

Yahoo News:
MAX_QUERIES = 3
MAX_ARTICLES_PER_QUERY = 10
MAX_COMMENTS_PER_ARTICLE = 30

Chiebukuro:
MAX_QUERIES = 3
MAX_QUESTIONS_PER_QUERY = 10
MAX_ANSWERS_PER_QUESTION = 10

Realtime Search:
MAX_QUERIES = 2
MAX_POSTS_PER_QUERY = 30


실제 값은 config에서 변경 가능하게 하세요.


========================================
18. HTTP Safety
========================================

기존 HTTP infrastructure를 최대한 재사용하세요.

필수:

- timeout
- bounded retries
- user-agent
- max results
- no infinite pagination

Retry:

429
5xx
timeout/network

No retry:

403
access denied
permission failure


접근 차단을 우회하지 마세요.


========================================
19. Partial Failure
========================================

Sub-source별 실패를 독립적으로 관리하세요.

예:

Yahoo News Articles     SUCCESS
Yahoo News Comments     PARTIAL
Yahoo Chiebukuro        SUCCESS
Yahoo Realtime          UNAVAILABLE

→ Yahoo Japan 전체 = PARTIAL

하지만 성공한 데이터를 Dashboard에 표시해야 합니다.

Yahoo 실패 때문에 YouTube 결과가 사라지면 안 됩니다.


========================================
20. Yahoo Data Classification
========================================

Yahoo market_content:

- yahoo_news_article


Yahoo consumer_voice:

- yahoo_news_comment
- yahoo_chiebukuro_question
- yahoo_chiebukuro_answer
- yahoo_realtime_post


Consumer Sentiment KPI에는 consumer_voice만 사용하세요.


========================================
21. Audit Metrics
========================================

최소:

news_articles_raw
news_articles_eligible

news_comments_raw
news_comments_eligible

chiebukuro_questions_raw
chiebukuro_questions_eligible

chiebukuro_answers_raw
chiebukuro_answers_eligible

realtime_posts_raw
realtime_posts_eligible

entity_excluded
foreign_market_excluded
language_excluded
date_excluded
duplicates_removed

final_yahoo_records
final_yahoo_consumer_voice


========================================
22. Dashboard 준비
========================================

이번 Task에서는 UI 디자인을 전면 수정하지 마세요.

다만 성공적으로 구현된 경우 기존 Coming Soon Yahoo/News 영역을
활성화할 수 있도록 데이터와 view model을 준비하세요.

향후 Yahoo Japan Tab 내부 구조:

Overview

News
- Articles
- Yahoo Comments

知恵袋
- Questions
- Answers

Realtime
- Posts
  (가능한 경우에만)


Yahoo Tab KPI 후보:

- Total Yahoo Mentions
- Articles
- Yahoo Comments
- Chiebukuro Q&A
- Realtime Posts
- Consumer Voices
- Positive %
- Negative %
- Top Topics


========================================
23. Gemini Integration
========================================

기존 Gemini 분석 구조를 재사용하세요.

새 모델이나 schema를 만들지 마세요.


Article:
market_content

Comment / Q&A / Realtime:
consumer_voice


Yahoo consumer_voice는 기존 RecordAnalysis 및 AggregateAnalysis에
통합 가능하도록 Common Data Schema로 변환하세요.


========================================
24. 필수 테스트
========================================

Mock / Contract Test 작성.

News:

1. Japan relevant article → INCLUDE market_content
2. US-only Yahoo article → EXCLUDE
3. Korea-only article → EXCLUDE
4. Korea-Japan comparison → INCLUDE
5. unrelated KIA → EXCLUDE

Comments:

6. Japan article + Japanese comment → INCLUDE consumer_voice
7. Foreign-only parent article comment → EXCLUDE
8. 0 comments → Article 유지
9. Comment parser failure → Article 유지 + partial
10. Comment reactions missing → 정상

Chiebukuro:

11. Japan-market Question → consumer_voice
12. Answer → consumer_voice
13. unrelated KIA question → EXCLUDE
14. Question date missing → 정상 처리
15. Answer metadata missing → 정상

Realtime:

16. public result success → consumer_voice
17. foreign result → EXCLUDE
18. HTTP access denied → unavailable, no bypass

Partial:

19. News success + Comment failure + Chiebukuro success
→ Yahoo overall PARTIAL

20. Realtime unavailable
→ News/Chiebukuro 정상 유지

기존 전체 테스트도 모두 통과해야 합니다.


========================================
25. 실제 Smoke Test
========================================

P0 구현이 완료되면 실제 최소 smoke test를 수행하세요.

Keyword:
PV5

Date:
최근 30일

Limit:

Yahoo News Articles <= 3
Comments/article <= 5

Chiebukuro Questions <= 3
Answers/question <= 3

Realtime Posts <= 5


API Key, prompt, 전체 원문을 출력하지 마세요.


결과 보고:

Yahoo News
- connection success
- raw articles
- eligible articles

Yahoo Comments
- connection success
- raw comments
- eligible consumer voices

Chiebukuro
- connection success
- questions
- answers
- eligible consumer voices

Realtime
- feasible / unavailable
- posts collected
- eligible posts

Total
- final Yahoo records
- final Yahoo consumer voices
- overall source status


========================================
26. 이번 Task에서 절대 수정하지 말 것
========================================

- YouTube Collector
- YouTube API 설정
- Gemini model
- Gemini schemas
- AggregateAnalysis
- Evidence reconciliation
- 기존 Streamlit UI redesign
- みんカラ


========================================
27. 완료 보고
========================================

완료 후 다음만 간단히 보고해주세요.

1. Yahoo News 실제 수집 성공 여부
2. Yahoo News Comment 실제 수집 성공 여부
3. Yahoo Chiebukuro 실제 수집 성공 여부
4. Yahoo Realtime Search feasibility 결과
5. 각 sub-source collection method
6. X API 사용 여부 (이번 Task에서는 반드시 false여야 함)
7. API credential 필요 여부
8. 생성/수정 파일
9. 전체 테스트 결과
10. 실제 PV5 smoke test 결과
11. Yahoo Japan Source를 Dashboard에서 활성화 가능한지
12. 아직 지원하지 않는 기능

중요:
존재하지 않는 API나 endpoint를 임의로 만들지 마세요.
공개적으로 안정적인 접근이 불가능한 기능은 억지로 우회하지 말고
UNAVAILABLE 상태로 정확하게 보고하세요.