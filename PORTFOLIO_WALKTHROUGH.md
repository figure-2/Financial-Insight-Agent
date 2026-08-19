# Portfolio Walkthrough

이 문서는 채용 검토자가 Financial Insight Agent의 설계와 실행 경계를 약 5분 안에
확인하기 위한 시연 순서입니다.

## 0:00–0:40 · 문제 정의

기업 분석은 금융 리포트, 공시 재무, 시장 시계열처럼 구조와 갱신 주기가 다른 근거를
사용합니다. 이 프로젝트는 각 근거를 회사·기준일·lineage로 결박하고 검증된 claim만
질문별 결과로 승격합니다.

핵심 설계는 다음 세 가지입니다.

1. fresh/stale/missing 판정 뒤 필요한 축만 durable job 대상으로 만듭니다.
2. vector 검색 점수를 authorization으로 사용하지 않고 canonical row로 재검증합니다.
3. 한 축 실패 시 다른 기업 자료로 대체하지 않고 `ready_partial`로 반환합니다.

## 0:40–1:20 · 아키텍처

[아키텍처 다이어그램](docs/assets/architecture.svg)을 왼쪽에서 오른쪽으로 설명합니다.

```text
기업 식별·clarification
→ freshness·durable job
→ bounded acquisition·quarantine
→ canonical Evidence·vector projection
→ 세 capability·citation-bound integrated observation
```

하단의 full system과 public repo 경계를 구분합니다. 공개 저장소에는 provider client,
credential, private PDF, 실제 DB/vector가 없습니다.

## 1:20–2:20 · 공개 데모

```powershell
python -I run.py smoke
python -I run.py serve --port 8765
```

브라우저에서 `http://127.0.0.1:8765/`을 열고 다섯 controlled intent를 확인합니다.
결과에서 Report page/bbox, Financial period/metric/unit, Regulatory article locator,
Market ticker/as-of와 claim citation을 확인합니다.

Docker 실행은 다음과 같습니다.

```powershell
docker compose --env-file docker/portfolio.env.example up --build
```

## 2:20–3:50 · 핵심 코드

1. `company_runtime.py` — canonical identity와 ambiguity
2. `freshness.py` — Report freshness와 negative cache
3. `durable_runtime.py` — idempotent job, lease, revision, restart snapshot
4. `pdf_security.py` — 비신뢰 PDF parser 진입 경계
5. `report_retrieval.py` — vector hit의 canonical readback
6. `financial_pipeline.py` — filing period·unit·receipt lineage
7. `market_pipeline.py` — ordered OHLCV와 결정적 계산
8. `storage_reconciliation.py` — active projection·orphan·legacy quarantine
9. `integrated_analysis.py` — citation pair 기반 교차축 관찰
10. `service_runtime.py` — cache 결과 또는 idempotent 202 job

세부 구현을 나열하기보다 모든 축에서 반복되는 `identity → lineage → readback →
fail-closed` 계약을 강조합니다.

## 3:50–4:30 · 검증

```powershell
python scripts/check.py
```

이 명령은 dependency-free unit test, deterministic smoke, provider/network/model 호출 0을
검증합니다. Docker는 non-root user, read-only filesystem, capability drop 조건으로 별도
실행할 수 있습니다.

## 4:30–5:00 · 주장 경계

공개 실행은 sanitized recorded replay와 synthetic contract test입니다. 실제 다기업
provider 수집, hosted production SLA, 실시간 streaming, 투자 추천을 주장하지 않습니다.
full system의 actual-local 검증 결과는 private artifact를 공개하지 않는 범위에서만
아키텍처 설명에 사용합니다.
