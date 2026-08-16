# みんカラ Source Implementation Specification

PRD.md, IMPLEMENTATION_PLAN.md, 현재 구현된 Collector Protocol,
Processing Pipeline, Japan Market Guardrail, Gemini Analysis,
Streamlit Dashboard 구조를 기준으로 새로운 독립 Source인
`みんカラ`를 구현해주세요.

기존 정상 동작 중인 아래 기능은 불필요하게 수정하지 마세요.

- YouTube Collector
- Yahoo Japan Collector
- Gemini model / schema
- RecordAnalysis
- AggregateAnalysis
- Evidence reconciliation
- 기존 Streamlit UI 디자인

---

# 1. 최종 목표

Dashboard의 새로운 상위 Source:

`みんカラ`

를 추가합니다.

みんカラ는 자동차 사용자 중심 커뮤니티이므로,
본 프로젝트에서는 단순 News Source가 아니라
**Consumer Voice Source**로 취급합니다.

핵심 수집 대상:

1. みんカラ 게시글 / 블로그 / 리뷰 / 사용자 콘텐츠
2. 해당 게시글에 달린 공개 댓글

최종 구조:

みんカラ
├── Posts
└── Comments

---

# 2. 핵심 데이터 분류 원칙

Yahoo News와 달리 みんカラ는 사용자 생성 콘텐츠가 중심이므로
게시글 자체도 Consumer Voice로 취급합니다.

Post:

source = minkara
sub_source = minkara_post
content_type = post
content_group = consumer_voice

Comment:

source = minkara
sub_source = minkara_comment
content_type = comment
content_group = consumer_voice

따라서 게시글과 댓글 모두 다음 분석 대상입니다.

- Positive / Neutral / Negative
- Topic
- Positive Drivers
- Negative Drivers
- Customer Questions
- Purchase Signals
- Purchase Barriers
- Representative VOC
- Marketing Insight

단순 사실 전달형 콘텐츠는 Neutral / Unknown을 허용하세요.

---

# 3. Keyword Search

사용자 입력 Keyword를 기반으로 みんカラ 내 관련 콘텐츠를 찾습니다.

예:

PV5

Query candidate:
- PV5
- キア PV5
- KIA PV5
- PV5 日本
- PV5 キア

KIA

Query candidate:
- KIA
- Kia
- キア
- KIA 日本
- キア 日本

기존 QueryPlanner를 최대한 재사용하세요.

Query 수를 과도하게 늘리지 말고
config에서 최대 query variant 개수를 제한하세요.

---

# 4. Discovery Strategy

먼저 현재 공개 웹에서 다음 구조가
HTTP 기반으로 안정적으로 접근 가능한지 확인하세요.

1. みんカラ 검색 결과
2. 개별 게시글 페이지
3. 게시글 하단 댓글 영역

우선 사용할 수 있는 방식:

- requests
- httpx
- BeautifulSoup4
- JSON-LD
- 공개 HTML metadata

기본적으로 사용하지 말 것:

- Selenium
- Playwright
- browser automation
- login automation
- cookie bypass
- CAPTCHA bypass
- anti-bot bypass
- private endpoint 추측

Streamlit Community Cloud에서 실행 가능한
lightweight HTTP 방식이 우선입니다.

---

# 5. Post Discovery

검색 결과에서 가능한 경우 다음 정보를 확보하세요.

- native post ID
- title
- post URL
- author / username (공개된 경우)
- published_at
- updated_at (가능한 경우)
- category
- vehicle / model metadata
- snippet
- comment count
- query_used

검색 결과를 가져왔다는 이유만으로
바로 분석 대상으로 포함하지 마세요.

반드시 기존 Entity Guardrail과
Japan Market Scope Guardrail을 통과해야 합니다.

---

# 6. Post Detail Collection

Eligible 후보 Post의 상세 페이지에서 가능한 경우:

- title
- body text
- published_at
- author
- vehicle / model information
- category
- tags
- engagement metadata
- comment count
- canonical URL

을 확보하세요.

본문 전체를 분석할 수 있다면 사용하되,
HTML navigation / footer / menu / 광고 영역은 제거하세요.

---

# 7. Parent Post Entity Context

게시글이 명확하게 PV5 / Kia 자동차 콘텐츠라면
해당 게시글의 댓글은 부모 Entity Context를 상속할 수 있습니다.

예:

Parent Post:
「Kia PV5を見てきました」

Comment:
「このサイズなら欲しい」

→ Comment 자체에 PV5가 없어도
eligible parent post의 댓글이므로
PV5 Consumer Voice로 취급 가능

따라서 댓글마다 독립적으로 PV5 token을 요구하지 마세요.

---

# 8. Entity Guardrail

PV5 계열은 기존 deterministic vehicle entity 규칙을 재사용하세요.

Known Kia vehicle entity:

- PV5
- Kia PV5
- KIA PV5
- キア PV5
- PV5 Cargo
- PV5 Passenger
- PV5 WAV

KIA 단독은 기존 strict contextual disambiguation 유지.

みんカラ 검색 결과라는 이유만으로
무관한 게시글을 강제 include하지 마세요.

---

# 9. Japan Market Scope

みんカラ가 일본 자동차 커뮤니티라고 해도
모든 콘텐츠를 자동으로 Japan Market Relevant로 처리하지 마세요.

INCLUDE 예:

- 日本でPV5を見てきた
- PV5の日本価格が気になる
- 日本の駐車場では少し大きい
- 車中泊に使えそう
- 日本の充電環境では少し不安
- 日本導入モデルについて
- 日本のディーラーで展示を見た

EXCLUDE 예:

- 미국시장 PV5 리뷰 단순 공유
- 한국 판매량 기사 복사
- 유럽 출시 소식만 다루는 글
- 자동차와 무관한 KIA acronym

다만 실제 일본 사용자가 해외 사양을
일본시장과 비교하는 내용은 INCLUDE 가능합니다.

---

# 10. Post Date Policy

Post에 실제 published_at이 있으면 사용하세요.

Start Date / End Date를 JST 기준 inclusive로 적용하세요.

published_at을 확보하지 못한 경우:
- 임의 날짜 생성 금지
- published_at = null
- date_source = unknown

Consumer Voice 분석에는 포함 가능하지만
Mention Trend에는 포함하지 않을 수 있습니다.

단, 날짜가 명확히 검색기간 밖이면 제외하세요.

---

# 11. Comment Collection

Eligible Post에 공개 댓글이 존재하면
가능한 범위에서 댓글을 수집하세요.

Comment 최소 필드:

- id
- parent_id
- parent_url
- post_title
- content
- author (공개된 경우)
- published_at
- collected_at
- engagement metadata (가능한 경우)
- language
- url

댓글은:

source = minkara
sub_source = minkara_comment
content_type = comment
content_group = consumer_voice

로 저장하세요.

---

# 12. Comment Date Policy

댓글의 실제 날짜가 있으면 사용하세요.

댓글 날짜가 없고 부모 Post 날짜가 있는 경우:

- published_at = null 유지
- analysis_date = parent_post.published_at
- date_source = parent_post

로 처리할 수 있습니다.

부모 날짜를 댓글의 실제 작성일처럼 저장하지 마세요.

Trend에서는 analysis_date를 사용할 수 있습니다.

---

# 13. Comment Failure Isolation

댓글 수집 실패 때문에 Post까지 버리지 마세요.

예:

Post = SUCCESS
Comments = FAILED

→ Post는 정상 저장
→ Comments만 partial failure

댓글 0개도 정상 Post입니다.

한 Post의 댓글 파싱 실패가
다른 Post 수집에 영향을 주면 안 됩니다.

---

# 14. Content Quality

みんカラ 게시글에는 자동차 관련 잡담, 사진 설명,
짧은 후기, 정비 기록 등이 섞일 수 있습니다.

다음은 Consumer Voice로 유지 가능:

- 장점
- 단점
- 디자인 평가
- 사이즈 평가
- 가격 평가
- 충전 우려
- 캠핑 / 차박
- Cargo 활용
- 주행 경험
- 차량 비교
- 구매 관심
- 구매 포기 이유
- 딜러 / 서비스 경험

다음은 제외 후보:

- 광고만 있는 글
- 의미 없는 링크
- 중복
- Target Entity 무관
- 단순 자동 repost
- 분석 가능한 텍스트 없음

---

# 15. Specific Topic Signals

みんカラ 특성상 다음 Topic을 특히 잘 잡을 수 있도록 합니다.

- Design
- Price
- Size
- Interior Space
- Cargo
- Driving
- Range
- Charging
- Camping
- 車中泊
- Commercial Use
- Customization
- Parts / Accessories
- Dealer / Service
- Purchase Intent
- Purchase Barrier

실제 데이터에 없는 Topic은 생성하지 마세요.

---

# 16. Deduplication

Post 우선순위:

1. native post ID
2. canonical URL
3. normalized title + author + date
4. normalized content hash

Comment 우선순위:

1. native comment ID
2. parent_id + native comment ID
3. parent_id + normalized text hash

서로 다른 사용자가 같은 짧은 표현을 썼다고
자동 중복 처리하지 마세요.

---

# 17. Collection Limits

MVP에서 무제한 수집 금지.

Config 기본값 예:

MAX_MINKARA_QUERIES = 3
MAX_POSTS_PER_QUERY = 10
MAX_COMMENTS_PER_POST = 20

모든 값은 settings/config에서 변경 가능하게 하세요.

---

# 18. HTTP Safety

기존 HTTP infrastructure를 재사용하세요.

필수:

- timeout
- bounded retry
- user-agent
- max pagination
- no infinite crawling

Retry:
- 429
- 5xx
- timeout / network

No retry:
- 403
- access denied
- permission failure

접근 차단을 우회하지 마세요.

---

# 19. Partial Failure

みんカラ Source 실패가
YouTube / Yahoo 결과를 삭제하면 안 됩니다.

예:

Post collection SUCCESS
Comment collection PARTIAL

→ Minkara overall = PARTIAL
→ 성공 데이터는 Dashboard에 표시

---

# 20. Common Data Schema

기존 ContentRecord schema를 재사용하세요.

Post 최소:

- id
- source = minkara
- sub_source = minkara_post
- content_type = post
- content_group = consumer_voice
- keyword
- query_used
- title
- content
- author
- published_at
- analysis_date
- date_source
- collected_at
- url
- category
- vehicle_metadata
- comment_count
- entity_match
- japan_market_relevant
- japan_market_score
- exclusion_reason
- eligible_for_analysis

Comment 최소:

- id
- source = minkara
- sub_source = minkara_comment
- content_type = comment
- content_group = consumer_voice
- parent_id
- parent_url
- content
- author
- published_at
- analysis_date
- date_source
- collected_at
- url
- eligible_for_analysis

---

# 21. Gemini Integration

기존 Gemini 구조를 그대로 재사용하세요.

새 모델이나 schema를 만들지 마세요.

Post와 Comment 모두 consumer_voice이므로
기존 RecordAnalysis / AggregateAnalysis에 전달 가능합니다.

분석 대상:

- Sentiment
- Topics
- Positive Drivers
- Negative Drivers
- Customer Questions
- Purchase Signals
- Purchase Barriers
- Representative VOC

---

# 22. Dashboard Integration

이번 Task에서는 UI 전체 디자인을 다시 만들지 마세요.

다만 기존 Coming Soon `みんカラ` 탭을
실제 Source로 활성화할 수 있도록 연결하세요.

みんカラ Tab 구조:

Overview

Posts

Comments

Representative VOC

KPI 후보:

- Total Mentions
- Posts
- Comments
- Consumer Voices
- Positive %
- Negative %
- Top Topics

---

# 23. Audit Metrics

최소:

minkara_posts_raw
minkara_posts_eligible

minkara_comments_raw
minkara_comments_eligible

entity_excluded
foreign_market_excluded
language_excluded
date_excluded
duplicates_removed

final_minkara_records
final_minkara_consumer_voice

---

# 24. 필수 테스트

Mock / Contract Test를 작성하세요.

1. Japan-relevant PV5 Post → INCLUDE consumer_voice
2. PV5 Comment with eligible parent → INCLUDE
3. Comment without PV5 token but eligible parent → parent context 상속
4. US-only Kia Post → EXCLUDE
5. Korea-only PV5 Post → EXCLUDE
6. Japan-vs-foreign comparison → INCLUDE
7. unrelated KIA → EXCLUDE
8. Post date missing → analysis 유지 / trend 처리 검증
9. Comment date missing → parent date 상속
10. Post duplicate
11. Comment duplicate
12. Post comments = 0 → 정상
13. Comment parser failure → Post 유지 + PARTIAL
14. 403 → no retry
15. 429 → bounded retry
16. malformed HTML → safe failure
17. empty search result
18. PV5 deterministic entity recognition 유지

기존 전체 테스트도 모두 통과해야 합니다.

---

# 25. 실제 Smoke Test

구현 후 실제 최소 smoke test를 수행하세요.

Keyword:
PV5

Date:
최근 30일

Limit:
Posts <= 5
Comments/Post <= 5

보고:

- Minkara connection success
- raw posts
- eligible posts
- raw comments
- eligible comments
- final consumer_voice
- entity excluded
- foreign market excluded
- collection method
- source status

전체 게시글/댓글 원문은 출력하지 마세요.

---

# 26. 이번 Task에서 수정하지 말 것

- YouTube Collector
- Yahoo Japan Collector
- Gemini model
- Gemini schemas
- AggregateAnalysis
- Evidence reconciliation
- 기존 UI redesign
- X

---

# 27. Completion Report

완료 후 다음만 간단히 보고하세요.

1. みんカラ 실제 수집 성공 여부
2. Post 수집 성공 여부
3. Comment 수집 성공 여부
4. 실제 collection method
5. API/credential 필요 여부
6. 생성/수정 파일
7. 전체 테스트 결과
8. 실제 PV5 smoke test 결과
9. Dashboard Source 활성화 가능 여부
10. 아직 지원하지 않는 기능

중요:

존재하지 않는 API나 endpoint를 임의 생성하지 마세요.

공개적으로 안정적인 접근이 불가능한 경우
억지로 성공했다고 보고하지 말고
실제 실패 지점을 명확하게 보고하세요.