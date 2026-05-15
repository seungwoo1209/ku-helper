# Code style rules

## 네이밍

- 모듈/함수/변수: `snake_case`. 클래스: `PascalCase`. 상수: `UPPER_SNAKE`.
- 도메인 모델 이름은 단수형: `User`, `Notification`. 컬렉션 변수는 복수형: `users: list[User]`.
- 비공개는 단일 밑줄 prefix(`_internal_helper`). 더블 밑줄(`__name`) 금지.
- Discord 관련 식별자는 명시한다: `discord_id`, `discord_guild_id`. 단순 `id`로 두지 않는다.
- Pydantic 스키마는 의도를 접미사로 드러낸다: `UserCreate`, `UserUpdate`, `UserRead`.

## Import

- 그룹 순서: stdlib → 외부 라이브러리 → `app.*`. 그룹 사이 빈 줄 1개.
- 정렬은 `ruff` (`I` 규칙)이 강제한다. 수동 정렬 금지.
- 와일드카드(`from x import *`) 금지.
- 순환 import는 `TYPE_CHECKING` 블록으로 해결한다.

## 타입 힌트

- 모든 함수 시그니처에 인자/반환 타입을 적는다. `-> None`도 명시한다.
- 컬렉션은 PEP 585 문법(`list[int]`, `dict[str, User]`). `typing.List`, `typing.Dict` 금지.
- `Optional[X]` 대신 `X | None`.
- `Any`를 추가할 때는 같은 줄 또는 위에 `# type: ignore[<rule>]` 사유 주석을 단다.

## 함수

- 함수 길이가 50줄을 넘으면 분리를 검토한다.
- 인자가 5개를 넘으면 Pydantic 모델 또는 dataclass로 묶는다.
- 기본 인자에 가변 객체(`[]`, `{}`)를 두지 않는다. `None` 후 함수 내부에서 초기화.

## 주석과 docstring

- 코드가 "무엇을" 하는지는 적지 않는다. "왜" 그렇게 했는지만 적는다.
- `TODO`, `FIXME`는 이슈 번호와 함께: `# TODO(#142): retry policy`.
- docstring은 public API(라우터 함수, Service의 public 메서드)에만 단다. private에는 달지 않는다.

## 문자열

- f-string을 기본 사용. `%`, `.format()` 금지.
- 사용자 노출 메시지(에러 응답의 `detail`)는 한국어 허용. 그 외(변수명, 로그 키, `code` 필드)는 영어.

## 매직 값

- 매직 넘버는 모듈 상수로 추출한다.
- 매직 문자열(상태값, 에러 코드)은 `StrEnum`으로 정의한다.

## 로깅

- `structlog`만 사용. `print`, 기본 `logging.getLogger().info(...)` 호출 금지.
- 키-값 로깅: `logger.info("user_created", user_id=user.id, discord_id=user.discord_id)`. 메시지에 문자열 포매팅을 끼워 넣지 않는다.
- 비밀 정보(`token`, `secret`, `password`)는 로그에 포함되지 않는다. `SecretStr`이 1차 방어.