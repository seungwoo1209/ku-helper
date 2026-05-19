---
name: api-docs-coverage
description: Use whenever creating or modifying FastAPI route handlers in backend/app/domains/**/router.py, or Pydantic request/response schemas in backend/app/domains/**/schemas.py. Ensures every endpoint, request body, response model, and field carries a sufficient description, examples, intent, and auth requirement so the Redocly-rendered OpenAPI docs (deployed to GitHub Pages via .github/workflows/deploy-openapi-docs.yml) are usable by external developers. Triggers on: adding/renaming/removing route handlers, changing response_model or status_code, adding/modifying Pydantic fields, adding new BaseModel subclasses, or introducing a new domain under backend/app/domains/.
---

# api-docs-coverage

ku-helper backend FastAPI 코드의 OpenAPI 스펙은 Redocly 정적 HTML 로 빌드되어 `https://<owner>.github.io/<repo>/` 에서 외부 개발자에게 공개된다. 이 스킬은 **라우터/스키마 변경 시점에 누락된 문서 항목을 체크리스트로 검토하고, 부족한 부분만 인라인 보강**한다.

## 발동 조건

다음 중 하나에 해당하는 작업을 시작·완료한 직후 발동한다.

- `backend/app/domains/**/router.py` 에 새 `@router.<method>` 데코레이터 추가 또는 기존 데코레이터 인자 변경.
- `backend/app/domains/**/router.py` 의 핸들러 함수명·시그니처·`response_model` 변경.
- `backend/app/domains/**/schemas.py` 에 새 `BaseModel` 서브클래스 추가, 또는 기존 모델의 필드 추가·이름 변경·타입 변경.
- 사용자가 "이 엔드포인트 문서 보강해줘", "redoc 에 example 채워줘" 류 명시 요청.

발동하지 않는 경우: service/repository/models.py 만 수정, 테스트 추가, 단순 import 정리.

## 절대 규칙

- **service/repository/models.py 로 침범하지 않는다.** 비즈니스 로직·DB 스키마·외부 API 호출은 건드리지 않는다.
- **response_model 의 타입을 바꾸지 않는다.** 누락된 필드 추가도 금지. 보강은 description/examples/Field metadata 까지만.
- **새 엔드포인트를 추가하지 않는다.** 변경 범위는 이미 손이 닿은 라우터/스키마 안에서만.
- **인라인 보강이 우선**이다. 분리 기준을 충족하지 않는 한 별도 .md 파일을 만들지 않는다.

## Router 체크리스트

라우터 데코레이터 인자를 항목별로 검토한다. **누락된 항목만** 채운다. 이미 있는 한국어 1줄 docstring 은 그대로 둔다.

| 항목 | 요구 | 실패 신호 |
| --- | --- | --- |
| `summary=` | 30자 이내 한국어 한 줄. 동사형. | 누락 또는 영문 함수명 자동 생성 |
| `description=` | 의도·인증 요건·side effect. 8줄 넘으면 분리 (아래 참고). | 누락, 또는 docstring 한 줄만 fallback 중 |
| `response_description=` | 성공 응답이 무엇을 의미하는지. | 누락, "Successful Response" 자동 문구 |
| `responses=` | 발생 가능 4xx 의 domain code + 한국어 설명 매핑. | 누락 |
| 함수 docstring | 클라이언트 입장 1~2줄 요약. description 이 길어도 docstring 은 짧게 유지. | 누락 |

`responses=` 작성 시 `app/main.py` 의 도메인 예외 → HTTP 핸들러 매핑과 status code·code 값을 일치시킨다. 예: `USER_DELETED` 는 401, `INVALID_NOTIFICATION_CONFIG` 는 422.

### Router 예시 (after)

```python
@router.post(
    "",
    response_model=NotificationRead,
    status_code=201,
    summary="알림 설정 생성",
    description=(
        "현재 사용자에게 새 알림 설정을 등록한다. type 별 config 스키마는 "
        "discriminator 로 분기되며, 동일 type 중복 등록은 허용한다."
    ),
    response_description="생성된 알림 설정 (id, created_at 포함)",
    responses={
        401: {"description": "JWT 누락·만료 또는 USER_DELETED"},
        422: {"description": "config 스키마 검증 실패 (INVALID_NOTIFICATION_CONFIG)"},
    },
)
async def create_notification(...) -> BaseModel:
    """새 알림 설정을 생성한다."""
```

## Schema 체크리스트

`BaseModel` 한 클래스씩 검토한다. **누락된 항목만** 채운다.

| 항목 | 요구 | 실패 신호 |
| --- | --- | --- |
| 클래스 docstring | 도메인 의도 한 단락. F-XX 기능 번호 있으면 명시. | 누락 (단, 외부 미노출 내부 헬퍼 모델은 면제) |
| 필드별 `description` | 도메인 의미, 단위, 범위 근거. | `Field(min_length=1)` 등 제약만 있고 의미 설명 없음 |
| 필드별 `examples=[...]` | 최소 1개. 실제 도메인 값으로. | 누락 |
| 모델 단위 `json_schema_extra={"examples": [...]}` | 전체 payload 1개. Create/Update/Read 응답에 권장. | 누락 |
| `Literal` discriminator 필드 | description 에 각 값의 의미 명시. | "arrival" / "recurring" 만 있고 설명 없음 |

### Schema 예시 (before → after)

**Before** (`notifications/schemas.py`):

```python
class _TransitArrival(BaseModel):
    """F-06 단발 도착 알림: 특정 시각에 N분 전 한 번 발송."""

    mode: Literal["arrival"]
    station_name: str = Field(min_length=1, max_length=50)
    line: str = Field(min_length=1, max_length=20)
    minutes_before: int = Field(ge=1, le=120)
    include_congestion: bool = True
```

**After**:

```python
class _TransitArrival(BaseModel):
    """F-06 단발 도착 알림: 특정 시각에 N분 전 한 번 발송한다."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "mode": "arrival",
                    "station_name": "성신여대입구",
                    "line": "4호선",
                    "minutes_before": 10,
                    "include_congestion": True,
                }
            ]
        }
    )

    mode: Literal["arrival"] = Field(
        description="단발 도착 모드. 'arrival' 은 특정 시각 N분 전 1회 발송을 의미한다.",
    )
    station_name: str = Field(
        min_length=1,
        max_length=50,
        description="서울 지하철 역 이름 (한글). 공공 API 의 역명과 일치해야 한다.",
        examples=["성신여대입구"],
    )
    line: str = Field(
        min_length=1,
        max_length=20,
        description="호선 표기. '4호선', '경의중앙선' 등 한글 표기 그대로.",
        examples=["4호선"],
    )
    minutes_before: int = Field(
        ge=1,
        le=120,
        description="도착 N 분 전 알림. 1~120 분 사이.",
        examples=[10],
    )
    include_congestion: bool = Field(
        default=True,
        description="혼잡도 정보 포함 여부. 공공 API 가 데이터를 제공할 때만 유효.",
    )
```

## docs/endpoints/<op_id>.md 분리 기준

description 이 다음 중 **하나라도** 해당하면 별도 마크다운 파일로 분리한다.

- 표 또는 mermaid 다이어그램 필요.
- OAuth callback 같은 시퀀스 다이어그램·인증 흐름 그림.
- 8줄 이상 본문.
- 코드 블록 2개 이상.

파일 위치: `docs/endpoints/<router_function_name>.md`. 라우터 함수명이 FastAPI 의 default operation_id 와 동일하므로 같은 이름을 쓴다.

### 연결 패턴

라우터 모듈 상단에 `_DOCS_DIR` 상수 1회 정의 후, 데코레이터의 `description=` 에 `read_text()` 결과를 넣는다.

```python
from pathlib import Path

# backend/app/domains/<name>/router.py 기준 → docs/endpoints
_DOCS_DIR = Path(__file__).resolve().parents[4] / "docs" / "endpoints"


@router.get(
    "/discord/callback",
    response_model=TokenRead,
    summary="Discord OAuth 콜백",
    description=(_DOCS_DIR / "callback.md").read_text(encoding="utf-8"),
    response_description="자체 JWT (access + refresh)",
)
async def callback(...) -> TokenRead:
    ...
```

`parents[4]` 계산: `backend/app/domains/<name>/router.py` → `backend/` 까지 4단계 → `..` 한 번 더 = repo root. 라우터 파일에서 이 줄을 처음 추가할 때는 실제 경로를 한 번 확인한다.

분리한 .md 파일 작성 시:
- **H1 금지**. ReDoc 이 operation summary 를 자체 헤더로 렌더한다. 본문은 H2 부터.
- 본문 첫 줄은 의도 한 문장. 그 다음 표·코드·시퀀스 자유.
- 인증 요건은 빠짐없이 적는다 (아래 "인증 흐름 메모" 참고).

## 인증 흐름 메모 (모든 endpoint description 에 일관 적용)

- 로그인: Discord OAuth2 Authorization Code, **user-install** (`integration_type=1`). scope = `identify`, `applications.commands`.
- `applications.commands` 는 mutual guild 없이 DM 발송이 가능하도록 user-install 을 성립시키기 위함 (Discord 에러 50278 회피).
- 자체 JWT: HS256. payload = `sub`, `discord_id`, `exp`, `iat`, `jti`. access 30 분, refresh 30 일.
- 보호 엔드포인트는 `Authorization: Bearer <access>` 헤더 필요.
- 401 발생 사유:
  - JWT 누락/만료/서명 오류 — `INVALID_TOKEN`
  - 사용자가 소프트 삭제됨 (`User.status == DELETED`) — `USER_DELETED`
- 새 엔드포인트 description 에는 항상 "인증 필요 여부 + 401 사유" 한 줄 포함.

## 수행 절차

1. `git diff --name-only` 또는 직전 Edit/Write 대상 파일을 식별한다. router.py / schemas.py 가 아니면 스킬 종료.
2. 변경된 파일을 Read 로 전체 확인한다.
3. **router 의 경우**: 변경된 함수마다 Router 체크리스트 5 항목을 통과하는지 검토. 누락만 채운다.
4. **schema 의 경우**: 변경된 클래스마다 Schema 체크리스트 5 항목을 통과하는지 검토. 누락만 채운다.
5. description 이 분리 기준을 충족 → `docs/endpoints/<op_id>.md` 작성 + `read_text()` 인라인 전환. 작성한 .md 는 H1 금지 규칙 준수.
6. 보강 완료 후 사용자에게 안내: "`cd backend && uv run python scripts/regenerate_openapi.py` 로 openapi.json 갱신 후 커밋하세요." (스킬이 직접 실행하지 않는다 — backend Settings 의 더미 env 가 사용자 .env 기반이라 환경 의존성이 있음.)
7. 이번 PR 의 범위 밖에 있는 다른 도메인 (변경하지 않은 파일) 까지 손대지 않는다.

## 출력 형식 (선택)

보강을 마친 뒤 사용자에게 한 줄 요약 보낸다.

```
📘 api-docs-coverage: router N개 / schema M개 보강. docs/endpoints/<op_id>.md K개 신설.
다음 단계: backend/scripts/regenerate_openapi.py 실행 후 커밋.
```

`N`, `M`, `K` 가 모두 0 이면 "보강할 항목 없음" 으로 종료.
