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

공개 코드에는 recorded replay 외에도 특정 기업을 하드코딩하지 않는 canonical company
resolution과 Report freshness 계약이 포함됩니다. 이 계약은 exact name·ticker·alias,
모호성 반환, fresh/stale/missing/negative-cache 상태 전이를 dependency-free 테스트로
검증하지만 실제 provider를 호출하거나 private catalog를 포함하지 않습니다.

storage-neutral durable runtime은 질문 hash와 분석 범위로 idempotent job을 만들고,
lease·revision·허용 상태 전이·restart snapshot을 검증합니다. 공개 구현은 실제
PostgreSQL adapter가 아니라 운영 상태 계약을 재현하는 reference implementation입니다.

Report 공개 파이프라인은 비신뢰 PDF의 parser 진입 조건과 vector hit의 canonical
readback을 분리합니다. 검색 점수만으로 Evidence를 승인하지 않고 company·source
hash·chunk lineage·promotion 상태를 모두 확인한 뒤 질문별 citation locator를 만듭니다.

Financial 공개 파이프라인은 company/ticker, 기간, 공시 유형, 연결·별도, metric,
unit과 receipt version을 보존합니다. 재무 freshness는 Report TTL과 분리되며 공시
version이 달라지면 stale로 판정합니다.

Market 공개 파이프라인은 61~66개 ordered OHLCV row를 검증한 뒤 dataset hash와
20/60-session return, annualized volatility, SMA20/SMA60을 결정적으로 계산합니다.
포함된 테스트 시계열은 synthetic이며 실제 시장 데이터로 표시하지 않습니다.

Storage reconciliation은 canonical chunk와 vector projection metadata를 대조해 active
missing, orphan, lineage mismatch, no-reembedding rebuild 가능 여부와 복구 불가능한
legacy quarantine을 분리합니다. 양쪽 readback 전에는 Evidence를 ready로 승격하지 않습니다.

Integrated service는 세 capability의 ready 축만 조립합니다. Report forecast와 Financial
actual은 양쪽 citation이 있는 structured descriptor로만 비교하며, 원인·투자 판단을 새로
추론하지 않습니다. generic service test는 exact/ambiguous company resolution, 즉시 cache
결과, idempotent 202 job, candidate tamper 차단을 synthetic 상태로 검증합니다.

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
