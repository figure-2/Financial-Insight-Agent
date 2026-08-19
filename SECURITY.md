# Security

## 공개 데이터 경계

공개 replay에는 선택된 근거 projection과 hash-safe locator만 포함합니다.
원문 PDF, provider 원응답, credential, 사용자 경로, 연락처, 세션 정보는
포함하지 않습니다.

## 실행 경계

- 데모 실행 중 외부 provider와 생성 모델 호출 없음
- GET 이외 HTTP method 차단
- 지원하지 않는 기업·질문과 모호한 질문은 reason-only 차단
- 결과의 파일·데이터베이스 영구 저장 없음
- citation과 source hash가 없는 observation 차단
- Docker non-root user, read-only filesystem, capability drop, loopback bind
- vector hit의 company·source·lineage canonical readback

보안 문제를 발견한 경우 공개 이슈에 민감한 값을 붙이지 말고 저장소 소유자에게
비공개 채널로 알리십시오.
