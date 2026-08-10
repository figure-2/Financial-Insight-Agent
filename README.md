# Financial Insight Agent

근거를 잃지 않고 금융 리포트, 공시 재무, 규제 근거, 시장 지표를 하나의
질문별 결과로 조립하는 포트폴리오 프로토타입입니다.

이 공개 후보는 승인된 비식별 recorded replay만 읽습니다. 실행 중 외부 데이터
provider, 네트워크 API, 생성 모델을 호출하지 않으며 파일이나 데이터베이스에
결과를 쓰지 않습니다.

## 제공 capability

- **Report RAG**: 금융 리포트 근거에 페이지와 bbox locator를 유지합니다.
- **Financial & Regulatory Evidence**: 공시 수치의 기간·지표와 법령 조문 locator를 유지합니다.
- **Market & Portfolio Analytics**: 가격·수익률·변동성·peer·valuation 근거를 질문별로 투영합니다.

공개 replay는 엔씨소프트 한 기업과 다섯 가지 controlled intent만 지원합니다.
질문 표현을 지원 범위에 매핑할 수 없거나 두 intent가 섞이면 추측하지 않고
차단합니다.

## 실행

Python 3.11 이상만 필요합니다.

```powershell
python -I run.py smoke
python -I run.py serve --port 8765
```

브라우저에서 `http://127.0.0.1:8765/`을 열면 질문 선택형 UI를 확인할 수
있습니다. 로컬 서버는 GET 요청만 허용합니다.

## 검증

```powershell
python scripts/check.py
```

검증기는 문법 검사, 단위 테스트, 공개 데모 smoke의 exact rerun을 순서대로
확인합니다. 외부 패키지 설치는 필요하지 않습니다.

## 범위

현재 공개 후보가 보여주는 것은 단일 기업의 recorded replay입니다. 임의의
semantic QA, 실시간 또는 주기적 데이터 갱신, 지수 분석, 법적 적용성 확정,
투자 추천, production 운영, 사람 검수 gold를 주장하지 않습니다.

구조와 핵심 진입점은 [docs/architecture.md](docs/architecture.md), 공개 주장
경계는 [CLAIM_BOUNDARY.md](CLAIM_BOUNDARY.md), 보안 정책은
[SECURITY.md](SECURITY.md)에서 확인할 수 있습니다.
