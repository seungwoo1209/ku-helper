# docs/endpoints

FastAPI 라우터 데코레이터의 `description=` 인자로 **인라인되는** 마크다운 본문 저장소.

## 언제 여기에 파일을 만드나

라우터 description 이 다음 중 하나에 해당할 때만 분리한다 (기준은 `.claude/skills/api-docs-coverage/SKILL.md` 와 동일).

- 표 또는 mermaid 다이어그램 필요
- OAuth callback 같은 시퀀스·인증 흐름 그림
- 8줄 이상 본문
- 코드 블록 2개 이상

위에 해당하지 않으면 description 을 그대로 데코레이터 인자 문자열에 둔다.

## 파일명

라우터 함수명 (= FastAPI default operation_id) 과 동일.

```
backend/app/domains/auth/router.py  →  async def callback(...)
docs/endpoints/callback.md
```

## 작성 규칙

- **H1 금지**. ReDoc 이 operation summary 를 자체 헤더로 렌더하므로 본문은 H2 부터.
- 본문 첫 줄은 의도 한 문장. 그 다음 자유 형식 (표·코드·시퀀스).
- 인증 요건은 빠짐없이 명시한다. 보호 엔드포인트는 401 발생 사유 (`INVALID_TOKEN`, `USER_DELETED`) 까지.
- 한국어 본문, 코드·식별자는 영어.

## 라우터와 연결

라우터 모듈 상단에 `_DOCS_DIR` 상수를 1회 정의하고, `description=` 에 `read_text()` 결과를 넣는다. 경로는 `backend/app/domains/<name>/router.py` 기준 `parents[4]`.

```python
from pathlib import Path

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

## 누가 수정하나

- `.claude/skills/api-docs-coverage` 스킬이 라우터/스키마 변경을 감지하면 필요 시 신설·수정 제안.
- 사람이 직접 편집해도 됨. 단, H1 금지·파일명 규칙은 지켜야 Redocly 렌더가 깔끔하다.
