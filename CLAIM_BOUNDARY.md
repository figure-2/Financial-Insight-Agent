# Claim boundary

## 홈페이지·채팅 체험

- 가상기업 A의 합성 리포트·재무·조문·시장 자료를 사용합니다.
- 제한된 질문 유형을 브라우저에서 분기하고 답변을 결정론적으로 구성합니다.
- 출처 상세, 같은 탭의 대화, 직전 질문 유형에 따른 후속 질문을 제공합니다.
- 실시간 데이터·임의 기업 분석·생성 모델 추론·로그인·영구 대화 저장은 실행하지 않습니다.
- Python 근거 처리 모듈의 전체 파이프라인을 채팅에서 실행하는 것은 아닙니다.
- 예시 투자의견·목표가는 합성 출처의 발언이지 실제 투자 추천이 아닙니다.

## 검증 가능한 범위

- 공개 가능한 recorded evidence의 schema, hash, locator 검증
- 다섯 가지 controlled intent의 결정론적 질문 라우팅
- 질문별 citation-bound observation과 축별 근거 투영
- Report 1, Financial 6, Regulatory 1, Market 5 근거 계약
- 외부 provider, 생성 모델, 데이터 저장 없이 실행되는 로컬 데모
- synthetic input으로 검증하는 company resolution, freshness, durable job 상태 머신
- 비신뢰 PDF guard와 canonical vector readback 알고리즘
- filing·OHLCV 정규화, storage reconciliation, citation-bound 통합 계약

## 주장하지 않는 범위

- live 또는 주기적 시장 서비스
- 임의 질문에 답하는 범용 semantic QA
- 범용 다기업 분석 서비스
- 공개 contract test를 actual 다기업 수집 성공으로 해석하는 주장
- 지수 또는 benchmark 분석
- 법적 직접 적용성 확정이나 법률 자문
- 매수·매도·목표가·최적 비중 등 투자 자문
- production readiness
- 사람 검수 gold

모든 출력은 포트폴리오 기술 검토용이며 법률·투자 의사결정의 근거로 사용할
수 없습니다.
