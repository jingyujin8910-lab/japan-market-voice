# Japan Market Voice Dashboard

일본시장 관련 YouTube, Yahoo Japan, みんカラ 공개 데이터를 수집하고 Gemini로 Consumer Voice를 분석하는 Streamlit MVP입니다.

## 로컬 실행

권장 배포 런타임은 Python 3.12입니다.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
cp .env.example .env
```

`.env`에 실제 값을 입력합니다. `.env`는 Git에서 제외됩니다.

```dotenv
GEMINI_API_KEY=your-key
YOUTUBE_API_KEY=your-key
GEMINI_MODEL=gemini-2.5-flash
```

실행 및 테스트:

```bash
PYTHONPATH=src:. pytest -q
streamlit run app.py
```

기본 주소는 `http://localhost:8501`입니다. 외부 수집은 사용자가 분석 버튼을 눌렀을 때만 실행됩니다.

## Streamlit Community Cloud 배포

배포 파일:

- Entry point: `app.py`
- Python dependencies: `requirements.txt`
- Streamlit configuration: `.streamlit/config.toml`
- Secrets: Community Cloud의 App settings에서만 입력

Community Cloud의 **Advanced settings > Secrets**에 다음 TOML을 입력합니다.

```toml
GEMINI_API_KEY = "your-real-gemini-key"
YOUTUBE_API_KEY = "your-real-youtube-key"
GEMINI_MODEL = "gemini-2.5-flash"
```

`X_BEARER_TOKEN`은 현재 구현된 UI에서 사용하지 않으므로 배포 Secret에 넣을 필요가 없습니다. 나머지 실행 설정은 코드의 안전한 기본값을 사용하며 필요할 때만 root-level Secret으로 추가할 수 있습니다.

## Secret 처리 원칙

- 로컬: `.env`
- Community Cloud: App settings의 Secrets
- 우선순위: 환경변수 → Streamlit Secrets
- `.env`, `.env.*`, `.streamlit/secrets.toml`, private key 파일은 Git에서 제외
- API Key와 전체 댓글 원문은 애플리케이션 로그에 기록하지 않음

## 배포 제약

- Community Cloud의 로컬 파일 시스템을 영구 저장소로 사용하지 않습니다.
- 결과는 Streamlit session/cache에 유지되며 앱 재시작 후 사라질 수 있습니다.
- Yahoo Japan과 みんカラ는 공개 HTML 구조 변경이나 접근 정책에 따라 일부 수집이 실패할 수 있습니다.
- Source별 실패는 격리되며 가능한 다른 Source 결과는 계속 표시됩니다.
- YouTube와 Gemini의 quota/rate limit은 각 API 프로젝트 정책을 따릅니다.
