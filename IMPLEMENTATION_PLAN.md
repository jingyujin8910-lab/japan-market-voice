# Japan Market Voice Dashboard — Implementation Plan

## 문서 상태와 전제

- 기준일: 2026-08-16
- 기준 문서: 사용자 메시지에 제공된 PRD 1–102절
- 저장된 `PRD.md`는 검토 시점에 0바이트였다. 따라서 본 계획은 메시지에 포함된 전문을 Source of Truth로 분석했다. 구현 시작 전 IDE의 PRD를 저장하고 이 계획과 다시 대조해야 한다.
- 본 문서는 설계 및 구현 계획만 다룬다. 앱 코드는 포함하지 않는다.
- 외부 서비스의 API, 약관, 가격, quota는 바뀔 수 있으므로 구현 직전과 배포 직전에 재검증한다.

## Executive Summary

이 MVP의 성공 가능성이 가장 높은 범위는 **YouTube Data API v3 + 일본 언론사의 허용된 RSS/공개 피드 + Gemini 분석**이다. YouTube는 검색·영상 메타데이터·공개 댓글을 공식 API로 수집할 수 있고 날짜 및 native ID도 제공한다. 일본 뉴스는 Yahoo! JAPAN 자체 검색/댓글을 안정적인 공식 API로 수집할 수 있다고 확인되지 않았으므로, P0에서는 특정 사이트 스크래핑이 아니라 출처가 명확하고 이용이 허용된 일본 매체 RSS/피드를 수집한다. 화면 명칭도 실제 수집 범위에 맞게 `일본 뉴스`로 두며, Yahoo가 실제로 포함될 때만 `Yahoo! JAPAN`을 표시한다.

X는 공식 API와 Bearer Token이 있을 때만 optional collector로 제공한다. Recent Search는 최근 7일, 과거 전체 검색은 별도 유료 접근이 필요하므로 PRD의 임의 기간 검색을 항상 만족시키지 못한다. みんカラ와 Yahoo 댓글은 공식 수집 API가 확인되지 않았고 HTML/정책 변경 및 차단 위험이 커서 P2 조사 항목으로 둔다. Generic Web은 “인터넷 전체 크롤러”로 만들지 않고, 계약된 검색 API 또는 관리되는 allowlist RSS/페이지에 한정한다.

P0는 한 번의 명시적 submit으로 수집하고, deterministic guardrail로 명백한 포함/제외를 처리한 뒤 모호한 레코드만 Gemini에 분류시킨다. 소비자 감성은 `consumer_voice`만 대상으로 계산하고 기사/영상 메타데이터는 `market_content`로 분리한다. 모든 AI 결과는 Pydantic으로 검증하며 대표 VOC는 실제 `record_id`를 참조하고 서버에서 재검증한다.

배포 앱은 GitHub에서 Streamlit Community Cloud가 실행하므로 개인 PC가 꺼져도 동작한다. 다만 세션, cache, 로컬 SQLite는 영속성을 보장하지 않는다. 발표 재현성이 필요하면 외부 저장소를 도입하거나, 최소 P0에서는 동일 세션과 best-effort cache에 의존하면서 재수집 실패를 명확히 표시해야 한다.

### 권고 MVP 범위

| 범위 | 결정 |
|---|---|
| P0 실제 Source | YouTube 공식 API, allowlist 일본 뉴스 RSS/피드 |
| P0 AI | Gemini 실시간 structured output |
| P0 저장 | session state + TTL cache; 영구 저장 불요 |
| P1 | 뉴스 검색 provider adapter, export, 선택적 외부 persistence |
| P2 | X(credential/비용 승인 후), みんカラ(서면/약관 검토 후), Yahoo 댓글 |
| 제외 | Selenium/Playwright, 무제한 크롤링, 자동 스케줄링, 국적 추론, fabricated demo data |

## Requirements Review: 충돌, 중복, 불명확성

### 충돌 또는 조정이 필요한 요구사항

1. **기본 기간 30일 vs X Recent Search 7일**: X 공식 Recent Search는 최근 7일만 지원한다. 30일 범위는 full-archive 권한/비용이 없으면 충족할 수 없다. UI에서 source capability를 검증하고, 불가능한 범위는 X만 skip하며 이유를 표시해야 한다.
2. **날짜 범위 엄수 vs unknown date Raw Data 유지**: `published_at=null` 레코드는 선택 기간 내인지 증명할 수 없으므로 `date_eligible=false`, 분석 및 trend에서 제외하고 Raw/Audit에만 보관한다.
3. **사용자 버튼 때만 새 호출 vs cache 강제 갱신**: 일반 submit은 cache를 사용할 수 있고, `최신 데이터 다시 수집`은 nonce가 아니라 해당 key의 cached function entry를 명시적으로 clear한 뒤 실행해야 한다. 두 버튼의 의미를 분리한다.
4. **전체 Mention KPI vs consumer sentiment KPI**: Total Mentions는 최종 eligible `market_content + consumer_voice`; 감성 비율은 `consumer_voice` 중 known sentiment만 분모로 한다. Unknown 수와 제외 방식을 별도 표시한다.
5. **일본 뉴스와 Yahoo 명칭**: PRD는 Yahoo/News를 혼용한다. Yahoo 데이터가 없는데 `Yahoo`라고 표시하면 오해를 낳는다. collector ID와 UI label을 분리하고 실제 provider를 노출한다.
6. **단일 공통 schema vs 기사/댓글 의미 차이**: 공통 envelope는 유지하되 `content_group`, `parent_id`, scope/evidence 필드로 의미를 분리한다. 분석 schema는 record와 run summary를 분리한다.
7. **이전 결과 재사용/X 중복 방지 vs 비영속 로컬 저장**: Streamlit Cloud 로컬 SQLite만으로 재시작 이후 중복 방지를 보장할 수 없다. P0의 중복 방지는 한 run/cache 범위이며, cross-run 보장은 외부 DB 선택 시에만 제공한다.
8. **Gemini batch 기반 vs Gemini Batch API**: PRD의 “batch”는 여러 record를 한 번의 동기 요청 payload에 묶는 micro-batching을 뜻해야 한다. 공식 Batch API는 비동기이고 최대 24시간 목표이므로 대화형 MVP 경로에 부적합하다.
9. **분석 언어 일본어 vs UI 언어 한국어**: 입력 근거는 일본어 원문을 보존하고 분류 label은 canonical English enum, 설명/요약은 한국어로 생성한다. 번역문은 원문이 아니다.
10. **AI scope score vs deterministic rule score**: 두 점수를 하나로 덮어쓰지 않는다. `scope_method`, `rule_score`, `ai_score`, `final_scope_decision`을 기록해 감사 가능성을 유지한다.

### 중복 요구사항

- 51–102절은 5, 13, 16, 19, 35, 39, 42절을 구체화한다. 후반 guardrail을 우선 규칙으로 적용한다.
- 8.3과 79–80의 날짜 규칙, 13.2와 81의 dedupe 규칙, 35와 94–96의 rerun/cache 규칙은 하나의 정책 모듈로 통합한다.
- 14–20과 84–100의 Gemini 규칙은 `scope classification`, `record analysis`, `aggregate insight` 세 계약으로 분리한다.

### 구현 전 명확히 해야 할 사항

- 뉴스 매체 allowlist와 각 피드/본문의 재사용 허용 범위
- 공개 앱 여부, API 비용 상한, 사용자별 rate limiting 필요 여부
- YouTube 댓글은 top-level만인지 replies까지인지(P0 권고: top-level만)
- `max 100 comments/video`가 최신순인지 relevance순인지(P0 권고: 최신순, 기간 필터 후 cap)
- 기사 full text 저장 허용 여부(P0 권고: RSS title/summary만, 원문 링크 유지)
- 동일 키워드 동시 사용자 요청의 비용/중복 호출 정책
- 외부 영속 저장소가 발표 시 필수인지
- Emerging issue를 판정할 최소 표본과 비교 기간. 정의 전에는 단순 “최근 언급”으로 표시하거나 비활성화한다.

## Architecture

단일 Streamlit 프로세스 안의 계층형 모듈 구조를 사용하되 각 collector와 AI provider는 protocol/interface 뒤에 둔다.

```text
Streamlit UI
  -> Application/SearchService (run orchestration)
      -> QueryPlanner
      -> CollectorRegistry -> independent CollectorResult per source
      -> Normalization/Dedupe
      -> GuardrailService (entity -> Japan scope -> language -> date)
      -> GeminiAnalysisService
      -> AggregationService
      -> Repository/Cache adapters
  -> View models -> Overview / Sources / Insights / Raw / Audit
```

핵심 경계:

- `domain`: Pydantic record/run/analysis 모델과 enum. Streamlit, HTTP, Gemini에 의존하지 않는다.
- `collectors`: 외부 source 호출과 raw-to-common mapping만 담당한다.
- `processing`: 정규화, date, entity/scope/language, dedupe를 담당한다.
- `analysis`: Gemini prompt/schema/validation/evidence reconciliation을 담당한다.
- `application`: 부분 실패와 단계 진행, cache 정책을 조율한다.
- `ui`: 상태를 렌더링하며 직접 외부 API를 호출하지 않는다.
- `infrastructure`: secrets, HTTP client, repository, logging을 제공한다.

## Data Flow

1. `st.form`에서 keyword, JST inclusive dates, sources를 입력한다.
2. 입력을 검증하고 immutable `SearchRequest`와 `run_id`를 만든다.
3. QueryPlanner가 source별 최대 5개의 일본 중심 query를 만든다. 원 입력은 보존한다.
4. 선택 collector를 독립 실행한다. 한 source 예외는 `CollectorResult.failed`로 변환한다.
5. raw record를 공통 schema로 정규화하되 원문과 source native ID를 보존한다.
6. target entity rule을 적용한다.
7. parent-child context를 연결한 뒤 Japan scope rule을 적용한다.
8. 명확한 include/exclude는 확정하고 ambiguous만 Gemini scope classifier로 보낸다.
9. 소비자 후보에 일본어 판정을 적용한다. parent가 Japan-relevant인 일본어 댓글은 포함한다.
10. `published_at`을 UTC aware datetime으로 저장하고 JST 경계로 date eligibility를 계산한다.
11. native ID -> canonical URL -> normalized text hash 순으로 중복 제거한다.
12. `eligible_for_analysis=true`를 `market_content`와 `consumer_voice`로 분리한다.
13. consumer records를 micro-batch로 Gemini record analysis에 보내고 검증한다.
14. 검증된 record-level 결과를 Python으로 집계한다. 카운트/비율은 AI가 계산하지 않는다.
15. aggregate evidence IDs와 집계표를 Gemini insight 요청에 보내고 다시 검증한다.
16. session state에 완성된 `RunResult`를 원자적으로 교체하고 화면을 렌더링한다.

실패한 새 run이 기존 성공 결과를 지우지 않도록 `pending_run`과 `last_successful_run`을 분리한다.

## Source-by-Source Feasibility

| Source | 공식/지원 접근 | Credential | 기간/한계 | Cloud 안정성 | MVP 결정 |
|---|---|---|---|---|---|
| YouTube | Data API v3 `search.list`, `videos.list`, `commentThreads.list` | `YOUTUBE_API_KEY` | search quota가 크고 댓글 비활성/삭제 가능; top-level replies는 별도 호출 | 높음 | P0 |
| 일본 뉴스 | 매체별 공식 RSS/Atom 또는 명시 허용 공개 feed | 보통 없음 | 매체별 coverage/보존기간/본문 이용조건 상이 | 중~높음 | P0 allowlist |
| Yahoo! JAPAN 뉴스 | 안정적인 뉴스 검색/댓글 공식 API를 확인하지 못함 | 확인 불가 | robots/HTML/약관/댓글 UI 변경 위험 | 낮음 | P0 제외, 링크가 공식 feed에 나타날 때만 기사 metadata |
| みんカラ | 공식 검색/댓글 API 확인 못함 | 없음/확인 불가 | 검색 HTML scraping 및 약관·robots 검토 필요 | 낮음 | P2 조사 |
| X | 공식 X API recent/full archive search | Bearer Token, developer project; 비용/권한 | recent 7일, full archive 별도 pay-per-use/Enterprise | API 사용 시 중~높음 | P2 optional |
| Generic Web | 계약된 search API 또는 allowlist RSS | provider별 key 가능 | “전체 웹” coverage 불가, 전문/robots/저작권 제약 | provider 사용 시 중간 | P1 adapter |

근거: YouTube의 공식 검색은 최대 50개/요청이며 댓글 API는 최대 100개/요청이고 댓글 비활성 오류를 명시한다. 검색과 quota 정책은 공식 문서를 따른다 ([search.list](https://developers.google.com/youtube/v3/docs/search/list), [commentThreads.list](https://developers.google.com/youtube/v3/docs/commentThreads/list), [quota overview](https://developers.google.com/youtube/v3/getting-started)). X 공식 문서는 recent search 7일과 full archive의 별도 접근을 구분한다 ([X Search Posts](https://docs.x.com/x-api/posts/search/introduction)).

Yahoo Developer Network에 API 포털은 존재하지만 현재 목록만으로 Yahoo News 검색/댓글 수집 API가 있다고 판단할 수 없다 ([Yahoo Developer Network](https://developer.yahoo.co.jp/)). 존재가 확인되지 않은 endpoint를 설계하지 않는다. みんカラ 역시 공식 수집 API를 확인하지 못했으므로 HTML 구조를 사실상 API처럼 취급하지 않는다.

## Source Collection Strategy

### YouTube — P0

접근 방식:

- REST를 `httpx`로 직접 호출하거나 `google-api-python-client`를 사용할 수 있다. MVP는 dependency와 timeout 제어가 단순한 `httpx`를 권고한다.
- 각 query에 `search.list(part=snippet,type=video,q=...,publishedAfter,publishedBefore,relevanceLanguage=ja,regionCode=JP,maxResults=...)`를 사용한다. `regionCode`와 `relevanceLanguage`는 ranking hint이지 Japan scope 보증이 아니다.
- 중복 video ID를 합친 뒤 `videos.list(part=snippet,statistics,id=...)`로 보강한다.
- video title/description/channel을 먼저 scope 판정한다.
- scope 통과 영상은 `commentThreads.list(part=snippet,videoId=...,order=time,textFormat=plainText,maxResults<=100)`으로 top-level 댓글을 가져온다.
- 글로벌/ambiguous 영상은 댓글 text에 명시적 Japan context가 있는 경우만 후보로 가져올 수 있다. 비용 제어를 위해 P0에서는 scope 통과/ambiguous 상위 영상만 댓글 호출한다.
- 댓글 published timestamp를 사용하며 영상 날짜로 대체하지 않는다. `commentsDisabled`, 404, quota 오류는 영상 단위 실패로 기록한다.

Quota 예산을 run 전에 추정한다. query variant 수 × search calls가 지배적이므로 keyword당 3개 query로 시작하고, unique video 10개, 영상당 top-level 댓글 50개를 기본으로 한다. replies 전체 수집은 P1 이후다.

### Yahoo! JAPAN / 일본 뉴스 — P0 범위 축소

- P0 collector는 `feedparser`로 **승인된 일본 매체 RSS/Atom allowlist**만 읽는다.
- URL, title, publisher, published date, 공개 summary를 수집한다. feed가 제공하지 않는 본문은 임의 scraping하지 않는다.
- Yahoo 전용 collector는 구현하더라도 capability가 `disabled/unavailable`인 adapter로 시작하며, 공식 지원 방식 또는 명시 허가를 확인한 뒤 활성화한다.
- Yahoo 검색 결과 HTML 및 댓글 DOM scraping은 P0에서 제외한다. 브라우저 자동화도 사용하지 않는다.
- 기사 source가 Yahoo라 해도 Japan scope를 자동 승인하지 않는다.

### みんカラ — P2 조사

- 공식 API/feed 존재, robots.txt, 이용약관, 요청 허용 범위와 attribution 조건을 먼저 확인한다.
- 허용된 RSS/검색 feed가 확인되면 `feedparser`/`httpx`로 metadata와 공개 excerpt만 수집한다.
- 공식/허용 경로가 없으면 collector를 출시하지 않는다. BeautifulSoup로 검색/댓글을 대량 scrape하거나 Playwright를 배포하는 것은 MVP 해법이 아니다.
- 수동 URL 입력도 요구사항에 없으므로 자동 우회책으로 추가하지 않는다.

### X — P2 optional

- 공식 X API `/2/tweets/search/recent` 또는 권한이 있을 때 full archive를 `httpx`로 호출한다. `lang:ja -is:retweet`와 Japan-focused terms를 결합한다.
- `X_BEARER_TOKEN`이 없으면 source를 disabled로 보여주며 전체 run을 실패시키지 않는다.
- 선택 기간이 7일을 넘고 full archive capability가 없으면 사전 validation에서 X만 unsupported로 표시한다.
- ID, created_at, public_metrics, text, URL을 저장한다. 월 300건은 앱 자체 budget counter로 제한하되, 영구 DB가 없으면 월간 전역 한도를 강제할 수 없다는 한계를 명시한다.
- 비공식 scraping library, browser cookies, 로그인 자동화는 사용하지 않는다.

### Generic Web — P1

- 두 가지 adapter만 허용한다: (a) 계약/credential이 있는 search API, (b) 관리되는 allowlist RSS/Atom.
- 검색 API provider는 결정 전까지 추상 interface만 설계하고 존재하지 않는 endpoint나 무료 quota를 가정하지 않는다.
- 결과 페이지의 snippet과 URL만으로 scope가 불분명하면 Gemini classifier로 보내거나 제외한다. 임의 본문 crawling은 기본값이 아니다.
- `requests/httpx + BeautifulSoup4`는 명시적으로 허용된 정적 문서의 parsing에만 쓰며, 검색엔진 결과 scraping에는 쓰지 않는다.

## API 없이 가능한 기능과 Credential Matrix

| 기능 | API 없이 가능 | 필수/선택 credential |
|---|---:|---|
| Streamlit UI, validation, charts, CSV export | 예 | 없음 |
| normalization, date filter, dedupe, rule guardrail | 예 | 없음 |
| RSS/Atom 일본 뉴스 metadata | 대체로 예 | feed별 조건 확인 |
| YouTube 검색/댓글의 안정적 수집 | 아니오 | `YOUTUBE_API_KEY` |
| Gemini scope/분석/insight | 아니오 | `GEMINI_API_KEY` |
| X search | 아니오 | `X_BEARER_TOKEN` + 적절한 plan/access |
| Yahoo 댓글 | 확인된 공식 방법 없음 | 미정 |
| みんカラ 게시물/댓글 | 확인된 공식 방법 없음 | 미정 |
| Generic Web 검색 | provider 없이는 제한적 | 선택 provider key |

## Japan Market Guardrail Architecture

### 1. Query planning

- NFKC normalization, trim, whitespace collapse를 수행하되 raw keyword도 보존한다.
- 제품 사전은 config data로 관리한다: brand aliases(`KIA`, `Kia`, `キア`), models, vehicle context.
- generic keyword에는 `日本`, `日本市場`, `日本発売`, `日本価格`, `キア` 등을 조합하되 source당 최대 5개, P0 기본 3개로 제한한다.
- 사용자가 이미 일본 qualifier를 넣으면 불필요한 중복 확장을 줄인다.

### 2. Entity disambiguation

- casefold/NFKC 후 exact token/word-boundary match를 적용한다. ASCII `KIA`는 substring match하지 않는다.
- strong target signals: brand alias + model 또는 automotive term.
- strong unrelated signals과 문맥 부재면 `unrelated`; target name만 있고 문맥이 부족하면 `uncertain`이다.
- 제품명(PV5 등)은 configurable aliases와 negative collision corpus로 테스트한다.
- `uncertain`만 Gemini에 보내며 AI 결과와 reason을 저장한다.

### 3. Japan scope rules

- positive signals: 일본 출시/판매/가격/딜러/보조금/도로/충전/시승/납차 등.
- negative foreign-only signals: 미국/한국/유럽/중국 + launch/sales/factory 등이며 Japan signal이 전혀 없는 경우.
- Japan과 해외가 함께 있고 비교/일본 영향 문맥이면 include/ambiguous로 보낸다.
- 일본어 또는 일본 사이트라는 사실만으로 include하지 않는다.
- rule은 `include`, `exclude`, `ambiguous`와 matched evidence spans를 반환한다. 점수 임계치만으로 의미를 숨기지 않는다.

### 4. Parent-child inheritance

- Japan-relevant YouTube video/Yahoo article의 일본어 comment는 comment 자체에 `日本`이 없어도 consumer voice로 포함한다.
- global parent의 comment는 comment 자체에 Japan context + target entity relation이 있어야 포함한다.
- foreign-only parent의 비일본어 comment는 제외한다.
- parent decision과 reason을 child audit에 복사하지 않고 `parent_id`로 참조한다.

### 5. Japanese language detection

- rule first: Hiragana/Katakana presence와 일본어 character ratio. Kanji-only/짧은 댓글(`欲しい`)은 `unknown` 가능성이 있으므로 parent context와 lightweight detector를 결합한다.
- 후보 library: `lingua-language-detector`(ja/non-ja/unknown을 로컬에서 판정, 모델 크기/메모리 배포 테스트 필요). `langdetect`는 짧은 문장 결과가 불안정하므로 주 판정기로 권고하지 않는다.
- `欲しい`, `高い`, `デザイン好き` 같은 짧은 일본어 lexicon test를 둔다. 국적은 추론하지 않으며 결과 의미는 “일본어 온라인 반응”이다.

### 6. Final decision

`eligible_for_analysis`는 entity target, Japan relevance, language/content-group policy, date eligibility, noise/dedupe 조건을 모두 통과할 때만 true다. 제외 우선순위를 고정해 `exclusion_reason`을 하나의 canonical enum으로 기록한다.

## Common Data Schema

DataFrame을 canonical model로 삼지 않고 Pydantic model/list를 진실 원천으로 사용한 뒤 UI에서 DataFrame으로 변환한다.

```text
ContentRecord
  id: str                        # source:native_id 또는 deterministic hash
  source: youtube|yahoo|news|x|minkara|web
  provider: str                  # 실제 publisher/API/feed
  content_type: video|comment|article|post|blog|review
  content_group: market_content|consumer_voice|unknown
  keyword: str
  query_used: str
  native_id: str | null
  parent_id: str | null
  title: str | null
  content: str
  author: str | null
  published_at: aware datetime | null   # UTC storage
  collected_at: aware datetime          # UTC storage
  url: HttpUrl
  parent_url: HttpUrl | null
  engagement_count: int | null
  language: ja|non_ja|unknown
  is_comment: bool
  entity_match: target|unrelated|uncertain
  japan_market_relevant: bool | null
  japan_market_score: float | null
  japan_scope_reason: str | null
  scope_method: rule|gemini|inherited|none
  date_status: known|unknown|invalid
  date_eligible: bool
  duplicate_of: str | null
  exclusion_reason: enum | null
  eligible_for_analysis: bool
  sentiment: positive|neutral|negative|unknown
  sentiment_score: float | null
  topics: list[str]
  raw_metadata: dict               # allowlisted, secret-free fields only
```

별도 모델:

- `SearchRequest`, `QueryPlan`, `CollectorStatus`, `AuditCounts`, `RunResult`
- `RecordAnalysis`, `ScopeClassification`, `AggregateInsight`, `RepresentativeVoc`
- `CollectorResult(records, status, warnings)`로 partial failure를 값으로 표현한다.

Schema version과 collector version을 cache key/result에 포함한다. author는 필요 최소한으로만 보존하며 export에서 숨김 옵션을 둔다.

## 날짜 필터링 방식

- UI date를 `Asia/Tokyo`의 시작일 00:00:00과 종료일 다음 날 00:00:00의 half-open interval `[start, end+1day)`로 변환한다. DST가 없는 JST라도 timezone-aware 처리한다.
- API에는 가능한 경우 UTC RFC3339로 전달하고, 응답은 UTC aware datetime으로 저장한다.
- source timestamp가 date-only이면 source timezone이 명확할 때만 그 날짜로 저장하고 precision metadata를 둔다.
- 댓글은 댓글 날짜, 기사는 기사 날짜, 영상은 영상 날짜를 사용한다. parent 날짜 대체 금지.
- 미래 시각, 파싱 불가, missing은 invalid/unknown으로 분리하고 trend/analysis에서 제외한다.

## 중복 제거 방식

1. `(source, native_id)` exact match
2. query/tracking parameter와 fragment를 제거하고 host/path를 정규화한 canonical URL
3. NFKC + HTML 제거 + whitespace collapse한 원문 SHA-256
4. syndicated news near-duplicate는 P1에서 title similarity + canonical publisher/date로 보수적으로 처리

원본 record를 삭제하기보다 winner에 `duplicate_of`를 연결하고 audit count에 반영한다. 같은 짧은 댓글(`欲しい`)은 서로 다른 native ID/parent에서 독립 voice일 수 있으므로 text hash만으로 cross-parent 제거하지 않는다.

## Gemini Analysis Architecture

공식 `google-genai` SDK와 Pydantic v2를 사용한다. Gemini Structured Outputs는 JSON Schema/Pydantic을 지원하지만 JSON Schema subset이므로 복잡한 validator는 client-side에서 수행한다 ([Gemini Structured Outputs](https://ai.google.dev/gemini-api/docs/structured-output)). 모델명은 `GEMINI_MODEL` config 한 곳에서 설정하고 구현 시 지원 모델 목록을 재확인한다.

### 세 단계 계약

1. `ScopeClassificationBatch`: ambiguous record별 entity, Japan relevance, score, content_group, concise reason.
2. `RecordAnalysisBatch`: record ID별 sentiment, score, normalized topics, driver/question/purchase tags. 기사에는 consumer sentiment를 요구하지 않는다.
3. `AggregateInsight`: Python 집계와 제한된 evidence record를 받아 한국어 insight, evidence IDs, confidence를 반환한다.

### 검증 및 재시도

- `response_mime_type=application/json`과 response schema를 설정한다.
- `model_validate_json` 후 batch의 requested ID set과 returned ID set이 일치하는지 검사한다.
- enum/range/길이, duplicate IDs, unknown IDs를 검사한다.
- representative VOC의 `record_id`가 eligible dataset에 존재하고 quote가 normalized 원문에 실제 포함되는지 검사한다. 불일치 quote는 폐기하며 AI에게 수정 생성시키지 않는다.
- 첫 validation 실패 시 validation error를 축약해 1회 repair retry한다. 총 시도 횟수의 용어를 명확히 `MAX_AI_ATTEMPTS=2`로 둔다. 다시 실패하면 해당 batch만 failed/unknown 처리한다.
- 모델이 낸 counts는 사용하지 않고 Python으로 계산한다.

### 비용/latency 최소화

- deterministic rule로 clear records를 Gemini scope 호출에서 제외한다.
- record ID + 필요한 텍스트만 보내고 URL, author, 중복 metadata는 제외한다.
- batch size는 record 개수뿐 아니라 예상 문자/token budget으로 자른다. 기본 20–40 records에서 실측 후 조정한다.
- 하나의 동기 요청에 여러 records를 넣는 micro-batch를 사용한다. 인터랙티브 경로에서 비동기 Gemini Batch API는 쓰지 않는다. 공식 Batch API는 비긴급 대량 작업용이며 turnaround가 최대 24시간일 수 있다 ([Gemini Batch API](https://ai.google.dev/gemini-api/docs/batch-api)).
- content hash + prompt version + model + schema version으로 record analysis cache key를 만든다.
- aggregate insight는 모든 원문 대신 Python 집계와 각 category의 제한된 evidence sample을 보낸다.
- 429/5xx는 bounded exponential backoff + jitter, `Retry-After` 존중, 총 deadline 내에서만 재시도한다. 실제 rate limit은 project/model/tier별이므로 config 숫자로 단정하지 않는다 ([Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)).

## Streamlit State / Cache Architecture

### 실행 경계

- 모든 search control은 하나의 `st.form` 안에 둔다.
- `수집 및 분석` submit일 때만 orchestration을 호출한다.
- tab/filter/expander는 저장된 `RunResult`의 view만 바꾸며 외부 호출을 하지 않는다.
- `최신 데이터 다시 수집`은 동일 request cache entry를 clear한 뒤 명시적으로 새 run을 시작한다.

### Session State

```text
form_defaults
pending_run
last_successful_run
last_attempt
selected_view_filters
```

Session State는 WebSocket/session에 묶이고 reload로 초기화될 수 있으므로 영속 저장으로 취급하지 않는다 ([Streamlit Session State](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state)).

### Cache

- `st.cache_data(ttl=..., max_entries=...)`: source collection result, deterministic processing, validated AI response.
- key: normalized request + source + collector version + schema/prompt/model version. secret 값은 key/result/log에 넣지 않는다.
- `st.cache_resource`: immutable HTTP client 또는 provider client. 사용자별 credential이 달라질 가능성이 있으면 global resource로 공유하지 않는다.
- cache 결과가 pickle된다는 점 때문에 외부/untrusted pickle을 읽지 않고 앱이 생성한 object만 사용한다 ([st.cache_data](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data)).
- cache stampede 방지를 위해 동일 key에 process-local lock을 둘 수 있으나 multi-instance 전역 보장은 하지 않는다.

## Error Handling Strategy

- collector boundary에서 timeout, auth, quota/rate-limit, upstream 4xx/5xx, parse, no-data를 typed error로 변환한다.
- `asyncio.gather(..., return_exceptions=True)` 또는 bounded thread pool로 source를 독립 실행할 수 있으나 Streamlit cache의 async 제약 때문에 P0는 단순 순차 또는 small thread pool을 권고한다.
- source별 connect/read/overall timeout, 최대 record/page limit, retry policy를 config로 둔다.
- auth/permission/most 4xx는 retry하지 않는다. 429/5xx/network만 bounded retry한다.
- UI에는 source, 상태, 수집 건수, 안전한 메시지만 보이고 traceback은 서버 log에 남긴다.
- 로그 이벤트는 JSON-like structured logging으로 `run_id`, source, duration, count, error_code를 기록하며 content와 secrets는 기본적으로 기록하지 않는다.
- 전체 source가 실패하거나 최종 eligible data가 0이면 Gemini를 호출하지 않는다.
- 일부 analysis batch 실패 시 성공 batch는 표시하고 coverage(`analyzed/eligible`)를 명시한다.
- 새 run 전체 실패 시 `last_successful_run`을 유지하되 결과가 이전 검색임을 눈에 띄게 표시한다.

## Secrets / Security Architecture

`get_secret(name)`의 우선순위는 환경변수 -> `st.secrets`이며 빈 문자열은 missing으로 처리한다. import 시가 아니라 composition root에서 해석해 테스트 가능하게 한다.

- 로컬: `.env`를 `python-dotenv`로 개발 진입점에서만 로드한다.
- Cloud: Streamlit app settings Secrets에 같은 key를 설정한다.
- 필수: `GEMINI_API_KEY`, `YOUTUBE_API_KEY`.
- 선택: `X_BEARER_TOKEN`, future search/storage provider credentials.
- `.env`, `.env.*`, `.streamlit/secrets.toml`, caches, DB, `__pycache__`, `*.pyc`를 gitignore한다. `.env.example`에는 이름만 둔다.
- exception, URL query, telemetry, exported CSV에 secret을 넣지 않는다.
- public deployment라면 submit abuse가 API 비용을 발생시킨다. 최소 cooldown, per-session run 제한, hard record/token budget, provider quota alert가 필요하다. 진정한 사용자 인증/전역 quota enforcement가 필요하면 Community Cloud 기본 공개 앱만으로 충분하지 않을 수 있다.
- 수집 원문은 prompt injection을 포함할 수 있는 untrusted data다. Gemini prompt에서 데이터 delimiter를 사용하고 원문의 지시를 따르지 말라고 명시한다.

## Deployment Risks

1. **비영속 로컬 파일**: local SQLite/cache는 재부팅·redeploy·sleep 후 보존을 보장하지 않는다. 영구 history/X dedupe가 필수면 외부 managed DB를 사용한다.
2. **앱 sleep/restart**: 첫 요청은 cold start가 있고 session/cache가 사라질 수 있다. 발표 전 warm-up과 live smoke test가 필요하다.
3. **제한된 CPU/RAM/time**: browser automation, 큰 NLP 모델, 무제한 DataFrame을 피한다. record cap과 payload budget을 강제한다.
4. **outbound source blocking**: Yahoo/みんカラ가 datacenter IP 또는 robots 정책으로 차단할 수 있다. 이를 우회하지 않고 source failure로 처리한다.
5. **API quota/cost**: YouTube search와 Gemini/X 호출은 공유 project quota를 소비한다. 실행 전 estimated budget과 실행 후 usage count를 audit한다.
6. **dependency/Linux compatibility**: pure-Python/lightweight packages와 pinned compatible ranges를 사용한다. 브라우저 binary/OS-specific package는 제외한다.
7. **request duration**: 여러 source + AI가 UI 요청 안에서 실행된다. P0 cap을 작게 유지하고 단계 progress를 표시한다. background worker가 필요할 규모는 Community Cloud MVP 범위를 벗어난다.
8. **public data rights**: 공개 접근 가능은 재수집/재배포 허가와 같지 않다. snippets, short representative quote, URL 중심으로 최소 저장하고 각 source terms를 검토한다.
9. **app availability**: 개인 PC와 무관하게 Streamlit Cloud에서 실행되지만 플랫폼 장애, sleeping, quota exhaustion까지 “항상 정상”을 보장하지는 않는다.

## Required Dependencies

초기 권고(버전은 구현 시 lock/test):

| Package | 목적 | 단계 |
|---|---|---|
| `streamlit` | UI/state/cache | P0 |
| `pydantic>=2` | domain 및 AI validation | P0 |
| `google-genai` | Gemini official SDK | P0 |
| `httpx` | timeout/retry 가능한 HTTP/API 호출 | P0 |
| `feedparser` | RSS/Atom | P0 |
| `pandas` | table/aggregation bridge | P0 |
| `plotly` 또는 Streamlit native charts | dashboard chart | P0; 하나만 선택 |
| `python-dotenv` | local secrets | P0 dev |
| `beautifulsoup4` | 허용된 HTML excerpt cleanup | 선택/P1 |
| `lingua-language-detector` | 일본어 판별 | 배포 footprint 검증 후 P0 또는 rule fallback |
| `pytest`, `pytest-cov`, `respx` | unit/HTTP contract tests | dev |

`google-api-python-client`, `tenacity`, `orjson`, DB ORM은 필요성이 확인되기 전 추가하지 않는다. HTTP retry는 작은 자체 policy 또는 `httpx` transport wrapper로 충분하다.

## Proposed Project Structure

```text
.
├── app.py
├── PRD.md
├── IMPLEMENTATION_PLAN.md
├── README.md
├── requirements.txt
├── .gitignore
├── .env.example
├── .streamlit/
│   └── config.toml
├── src/japan_voice/
│   ├── config/
│   │   ├── settings.py
│   │   ├── sources.py
│   │   └── vocabularies.py
│   ├── domain/
│   │   ├── enums.py
│   │   ├── records.py
│   │   ├── analysis.py
│   │   └── runs.py
│   ├── application/
│   │   ├── search_service.py
│   │   └── query_planner.py
│   ├── collectors/
│   │   ├── base.py
│   │   ├── youtube.py
│   │   ├── news_rss.py
│   │   ├── x_api.py
│   │   ├── minkara.py
│   │   └── web.py
│   ├── processing/
│   │   ├── normalize.py
│   │   ├── dates.py
│   │   ├── deduplicate.py
│   │   ├── language.py
│   │   └── guardrails.py
│   ├── analysis/
│   │   ├── gemini_client.py
│   │   ├── schemas.py
│   │   ├── prompts.py
│   │   ├── batching.py
│   │   └── evidence.py
│   ├── storage/
│   │   ├── base.py
│   │   └── memory.py
│   ├── infrastructure/
│   │   ├── secrets.py
│   │   ├── http.py
│   │   └── logging.py
│   └── ui/
│       ├── controls.py
│       ├── overview.py
│       ├── sources.py
│       ├── insights.py
│       ├── raw_data.py
│       └── audit.py
└── tests/
    ├── unit/
    ├── contract/
    ├── fixtures/
    └── smoke/
```

P2 collector 파일을 처음부터 빈 stub로 만들 필요는 없다. 구현 시 실제 P0 파일만 생성하고 registry가 capability metadata로 source availability를 표현한다.

## P0 / P1 / P2 Implementation Plan

### P0 — 안정적인 실제 데모

1. PRD 저장본과 본 계획 승인, 뉴스 allowlist/약관 및 credential 확정.
2. domain schema, settings, secret resolver, structured logging 작성.
3. guardrail fixtures와 PRD 필수 10개 test를 먼저 작성.
4. normalization, JST dates, entity/scope rules, language, dedupe 구현.
5. YouTube official collector와 quota/error contract test 구현.
6. 승인된 일본 뉴스 RSS collector 구현. 승인 feed가 없으면 P0 source를 YouTube 단독으로 명시한다.
7. Gemini scope/record/aggregate schemas, micro-batching, validation/evidence reconciliation 구현.
8. orchestration과 partial failure/audit metrics 구현.
9. Streamlit form, progress, empty/no-data/error state와 session/cache 구현.
10. Overview, YouTube/News, Insight, Raw Data, Audit 화면 구현.
11. local integration test, real credential smoke test, cost/latency 측정 및 caps 조정.
12. README/secrets/deployment 설정 후 Community Cloud 배포 smoke test.

P0 exit criteria: 한 source 이상의 실제 데이터, 10개 guardrail test 통과, fabricated VOC 0건, partial failure 시 앱 유지, fresh browser에서 정상 load, 개인 PC off 상태에서 deployed URL 동작.

### P1 — 안정성/가치 확장

1. CSV export와 analysis coverage/audit 다운로드.
2. approved search provider 또는 추가 일본 매체 RSS adapter.
3. YouTube replies/추가 pagination은 quota 예산 안에서 선택 구현.
4. 외부 managed persistence가 승인되면 repository adapter와 migrations/idempotency 추가.
5. previous-period comparison은 실제 저장 데이터와 동일 coverage가 있을 때만 추가.
6. syndicated article near-dedupe 및 topic taxonomy 품질 개선.
7. load/concurrency, cache stampede, quota exhaustion 테스트.

### P2 — 조건부 source 확장

1. X plan/credential/예산 확정 후 recent search; full archive는 권한 확인 후 별도 capability.
2. みんカラ 공식/허용 수집 방법의 법적·기술적 검토 및 배포 proof.
3. Yahoo 기사/댓글의 공식 지원 방식 또는 명시 허가가 확보될 때만 collector 추가.
4. emerging issue는 충분한 historical baseline과 최소 표본 정의 후 구현.

### MVP에서 제외 권고

- Yahoo 댓글, みんカラ 댓글, browser automation
- 무제한 Generic Web crawling
- X full archive를 credential 확인 없이 약속하는 것
- background/continuous monitoring과 scheduler
- 복잡한 DB와 cross-session history(외부 persistence 요구 승인 전)
- word cloud, 과도한 source별 visualization
- 실제 비교 데이터 없는 증감률
- 소비자 국적 추론
- AI가 생성한 representative quote 또는 임의 날짜

## Testing Strategy

### Unit

- PRD의 10개 guardrail 사례를 table-driven test로 고정한다.
- 추가 경계: `KIA` substring collision, Japanese site/foreign-only article, Japan-vs-foreign comparison, short Japanese comment, unknown date, end-date 23:59:59 JST, identical short comments under different parents.
- URL canonicalization, NFKC, source ID dedupe, content hash determinism.
- sentiment denominator가 consumer known sentiment만 사용하는지 검증.
- evidence ID/quote reconciliation과 hallucinated ID rejection.

### Contract

- recorded/synthetic HTTP fixtures로 YouTube success, pagination, commentsDisabled, 403 quota, 429, malformed JSON, timeout을 테스트한다. fixture는 공개 API response shape만 사용하고 실제 개인정보/secret을 넣지 않는다.
- RSS의 missing date, invalid XML, redirect, duplicate entry를 테스트한다.
- Gemini valid JSON, schema mismatch, missing/extra ID, retry success/failure를 mock한다.

### Integration

- credential이 있을 때 소량 live smoke test를 수동/비정기 CI로 실행한다. 일반 PR CI에서 외부 API와 비용 호출은 하지 않는다.
- source A 실패 + source B 성공, 모든 source 실패, no eligible data, 일부 AI batch 실패를 end-to-end 검증한다.
- submit 외 tab/filter interaction에서 collector call count가 증가하지 않는지 확인한다.

### Deployment

- Community Cloud Linux에서 dependency install, cold start, secrets resolution, outbound API, memory, run duration을 검증한다.
- 새 브라우저/session, page reload, app reboot 후 기대 동작을 확인한다.
- 발표 리허설은 실제 `PV5`와 선택 기간으로 수행하며 데이터가 없을 가능성도 no-data UX로 검증한다.

## PRD에 추가해야 할 기술 요소

1. **Run identity와 schema/prompt/collector versioning**: 재현성과 cache invalidation에 필수.
2. **Capability registry**: source별 enabled, credential present, supported date range, reason을 UI에 제공.
3. **Global budgets**: max raw records, max eligible records, max chars/tokens, max elapsed time, estimated API calls.
4. **Data provenance**: provider, query_used, parent_id, scope_method, matched evidence, prompt/model version.
5. **Analysis coverage/confidence**: 전체 eligible 중 분석 성공 비율과 sample size 표시.
6. **Prompt-injection 방어**: 수집 텍스트를 지시가 아닌 데이터로 취급.
7. **Clock/time source**: UTC storage, JST filtering, server clock 이상 검사.
8. **Content retention policy**: 원문/author/cache 보존 기간과 export 범위.
9. **Observability**: duration, counts, quota-related error code, correlation run ID; secret/content redaction.
10. **Concurrency/idempotency**: double-click/동일 request 중복 실행 방지.
11. **Dependency lock and Python version**: Community Cloud와 동일 버전으로 고정 및 smoke test.
12. **Terms/robots review checklist**: source를 enable하기 위한 출시 gate.

## Known Limitations

- 이 시스템은 표본 기반 listening 도구이며 일본 전체 여론이나 소비자 국적을 대표하지 않는다.
- YouTube ranking/API quota와 댓글 availability 때문에 동일 검색도 coverage가 달라질 수 있다.
- RSS는 제공 매체와 보존 기간에 편향되고 댓글을 제공하지 않는 경우가 일반적이다.
- Yahoo/みんカラ가 빠진 P0에서는 PRD에 나열된 source coverage 전체를 달성하지 않는다.
- X recent-only 계정은 7일보다 오래된 기간을 분석할 수 없다.
- rule/LLM scope와 sentiment는 오류 가능성이 있으므로 audit reason, raw link, sample size를 함께 보여야 한다.
- Japanese-language voice는 일본 거주자/국적의 증명이 아니다.
- session/cache만 쓰는 P0에서는 app restart 후 이전 분석과 월간 X dedupe가 사라질 수 있다.
- 기사와 댓글 삭제/수정, API 정책 변경으로 과거 재현성이 완전하지 않다.
- 실시간 사용 경로의 Gemini micro-batching은 API 호출 수를 줄이지만 공식 비동기 Batch API의 할인/별도 quota를 사용하는 것은 아니다.

## Open Questions

구현 승인 전에 결정해야 할 항목:

1. P0 뉴스 allowlist에 포함할 매체와 사용 허가가 확인된 feed URL은 무엇인가?
2. YouTube top-level 댓글만으로 P0를 승인할 것인가?
3. 보유한 Google Cloud project의 YouTube quota와 `YOUTUBE_API_KEY`가 준비되었는가?
4. Gemini billing tier, 월 비용 상한, 사용 가능한 model을 무엇으로 정할 것인가?
5. 앱을 public으로 배포할 것인가? public이면 비용 남용 방지 수준은 어느 정도가 필요한가?
6. 발표 재현을 위해 외부 persistent storage가 반드시 필요한가, 아니면 live 재수집 + cache로 충분한가?
7. X developer access/plan과 full-archive 필요성이 실제로 승인되었는가?
8. Yahoo 및 みんカラ에 대해 조직 차원의 이용약관/수집 승인을 받을 수 있는가?
9. 대표 VOC의 짧은 원문 인용과 author 표시 정책은 무엇인가?
10. Emerging issue를 표시할 최소 표본, 비교 기간, 증가 기준은 무엇인가?

## 승인 권고안

구현은 다음 조건으로 승인하는 것이 안전하다.

- P0 source를 YouTube와 승인된 일본 뉴스 RSS로 한정한다.
- Yahoo 댓글, みんカラ, X, arbitrary web scraping을 P0 완료 조건에서 제거한다.
- 뉴스 feed allowlist가 확정되지 않으면 YouTube 하나로 먼저 Definition of Done을 충족한다.
- guardrail 10개 test와 evidence reconciliation을 UI보다 먼저 완료한다.
- Community Cloud의 session/local disk를 영구 저장소로 간주하지 않는다.
- source capability, sample size, exclusions, analysis coverage를 사용자에게 투명하게 표시한다.

이 범위라면 Source 수보다 실제 작동, Japan relevance, 근거 추적성, 배포 안정성을 우선한다는 PRD의 핵심 원칙과 일치한다.
