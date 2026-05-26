현재 사용자가 수신한 알림 발송 이력을 최신순(`sent_at DESC`)으로 반환한다 (F-17).

응답은 정기 알림(`notifications`) 과 즉시 발송(`immediate_send_requests`) 양쪽에서 비롯된 이력을 합쳐 보여주며, 관리자 장애 알림(F-22) 은 응답에서 제외된다. `type` 은 history 본체 컬럼이 아니라 원천 테이블에서 `COALESCE` 로 도출되므로, 원천이 삭제된(`notification_id IS NULL AND immediate_send_request_id IS NULL`) row 는 응답에서 함께 제외된다.

## 인증

`Authorization: Bearer <access>` 필요. 401 사유는 토큰 누락·만료·서명오류(`INVALID_TOKEN`) 또는 소프트 삭제된 사용자(`USER_DELETED`).

## 쿼리 파라미터

| 이름 | 타입 | 기본값 | 의미 |
| --- | --- | --- | --- |
| `date_from` | `date` (YYYY-MM-DD) | 미지정 시 `date_to - 30d` 로 자동 보정 | 조회 시작일 (UTC 자정 기준 포함). |
| `date_to` | `date` (YYYY-MM-DD) | 미지정 시 현재 시각 | 조회 종료일 (inclusive; 해당 일자 다음 자정까지). |
| `type` | `TRANSIT` \| `LUNCH` \| `LIBRARY` | 없음 | 알림 유형 필터. 없으면 전체. |
| `status` | `SUCCESS` \| `FAILED` | 없음 | 발송 결과 필터. 없으면 전체. |
| `limit` | `int` (1~100) | `100` | 최대 반환 건수. cursor 페이지네이션은 후속 PR. |

## 윈도우 보정 규칙

| 입력 조합 | 적용 윈도우 |
| --- | --- |
| 둘 다 미지정 | `now - 30d ~ now` |
| `date_from` 만 | `date_from ~ date_from + 30d` |
| `date_to` 만 | `date_to - 30d ~ date_to(+1d)` |
| 둘 다 지정 | 입력 그대로 (검증 통과 시) |

## 거절 케이스

- `date_from > date_to` → `422 INVALID_HISTORY_DATE_RANGE`.
- 범위가 30일 초과 → `422 INVALID_HISTORY_DATE_RANGE`.
- `limit` 가 1~100 범위 밖 → FastAPI 기본 `422` (`Query(le=100)`).

## 응답 형태 메모

- `payload` 는 발송 당시 임베드의 raw JSONB 스냅샷이다. 타입별 키 구성은 다르며, 적재 형식의 정식 합의는 `ROADMAP §E-1` 후속 PR 에서 다룬다. 그 전까지 프론트는 `type` 으로 분기한 뒤 키를 읽어 화면을 구성한다.
- `failure_reason` 은 `status == FAILED` 인 row 에만 채워지며, 상위 200자에서 잘려 저장된다. 사용자에 그대로 노출해도 안전한 값으로 정규화돼 있다(F-20).
- `notification_id` / `immediate_send_request_id` 중 정확히 한쪽만 채워진다(둘 다 NULL 인 row 는 응답에서 제외).
