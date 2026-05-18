# Code style rules

백엔드 `backend/.claude/code_style.md`를 상속한다. 봇 고유 차이만 여기 기록한다.

## 네이밍 (봇 고유)

- `discord.py` SDK 객체는 `dc_` 접두사로 받는다: `dc_user`, `dc_member`, `dc_channel`, `dc_embed`.
  우리 도메인 객체 `User`(SQLAlchemy 모델)와 헷갈리지 않게 하기 위함.
- 임베드 빌더 함수는 `build_*_embed` 명명: `build_transit_embed`, `build_lunch_embed`, `build_admin_failure_embed`.
- `discord.Embed(...)` 직접 인스턴스화는 임베드 빌더 모듈(`app/notifications/<type>/embeds.py`)에서만. Worker·Sender·Admin은 빌더 함수만 호출.
- 잡 함수는 `run_*_job` 접두사: `run_transit_job`, `run_lunch_job`. APScheduler에 등록되는 코루틴임을 이름으로 드러낸다.
- 큐 작업 객체(dataclass)는 `*Task`: `SendDmTask`, `AdminAlertTask`.

## 디렉터리 (봇 고유)

- `app/notifications/<type>/`는 최대 3파일: `worker.py`, `embeds.py`, `<type>_specific.py`. 그 이상 분리가 필요하면 패키지 깊이를 늘리는 대신 코드 자체를 단순화한다.
- `app/crawlers/<source>/`는 `client.py` 하나로 시작. HTML 파서·정규식이 커지면 `parser.py`로 분리.

## 백엔드 상속 부분

다음은 백엔드 규칙과 동일하므로 여기 다시 적지 않는다 (`backend/.claude/code_style.md` 참고):

- 모듈/함수/변수 `snake_case`, 클래스 `PascalCase`, 상수 `UPPER_SNAKE`.
- import 그룹 순서(stdlib → 외부 → `app.*`), 정렬은 ruff `I`.
- 모든 함수 시그니처에 타입 힌트(반환 `-> None`도 명시). PEP 585 컬렉션 문법(`list[T]`, `dict[K, V]`). `X | None`.
- 함수 길이 50줄·인자 5개 초과 시 분리 검토. 가변 기본 인자 금지.
- 주석은 "왜"만. `TODO(#142): ...`. docstring은 public API에만.
- f-string만 사용. 매직 넘버는 모듈 상수, 매직 문자열은 `StrEnum`.
- `print` 금지, `structlog`만. 키-값 로깅(`logger.info("dm_sent", user_id=..., type=...)`).
- 사용자 노출 텍스트(임베드 title·description)는 한국어 허용. 로그 키, 변수명, 예외 클래스명, 큐 작업의 `code` 필드는 영어.
