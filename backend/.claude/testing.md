# Testing rules

## 도구

- `pytest`, `pytest-asyncio`(strict mode), `httpx.AsyncClient` (`ASGITransport` 사용)
- 외부 HTTP 모킹: `respx` (Discord API 호출 모킹용)
- 시간 모킹: `time-machine`
- 테스트 DB: 별도 PostgreSQL 인스턴스를 `docker compose -f docker-compose.test.yml up`으로 띄운다.

## 구조

- `tests/` 디렉터리는 `app/` 구조를 미러링한다.
- `tests/conftest.py`: 전역 픽스처(엔진, 세션 팩토리, ASGI 클라이언트, settings 오버라이드).
- 도메인별 `tests/domains/<name>/conftest.py`: 도메인 픽스처(Fake Repository, 도메인 객체 빌더).

## 단위 테스트 (Service)

- Repository는 Fake 구현을 주입한다. 실제 DB를 띄우지 않는다.
- 외부 API는 `respx`로 모킹한다.
- 한 테스트 함수에 assert는 가능하면 하나. 여러 검증이 필요하면 테스트를 나눈다.

## 통합 테스트 (Router)

- `httpx.AsyncClient(transport=ASGITransport(app), base_url="http://test")`로 호출한다.
- DB 의존성은 트랜잭션 롤백 픽스처로 격리한다. 한 테스트의 변경이 다음 테스트로 누설되지 않는다.
- 인증이 필요한 엔드포인트는 `app.dependency_overrides`로 `get_current_user`를 Fake로 교체한다. JWT 발급/디코드 자체를 통합 테스트에서 돌리지 않는다.

## 외부 API 모킹

- Discord OAuth 토큰 교환, `/users/@me`, 길드 가입(`/guilds/.../members/...`) 호출은 전부 `respx`로 모킹한다. 실제 Discord에 요청이 나가면 테스트 실패로 간주한다.
- `respx`의 `assert_all_called=True` 옵션으로 모킹된 호출이 실제 발생했는지 검증한다.

## 픽스처 명명

- 픽스처 이름은 명사: `user`, `notification`, `authed_client`. 동사형(`make_user`) 금지.
- 빌더는 `*_factory` 접미사: `user_factory()`가 `User` 인스턴스를 반환.
- `authed_client`는 인증된 사용자 컨텍스트를 가진 `AsyncClient`를 반환한다.

## 커버리지

- Service 90% 이상, Repository 70% 이상, Router는 happy path와 주요 에러 경로.
- 커버리지 통과만을 위한 의미 없는 테스트(`assert True`, getter 호출) 금지.

## 실행

```bash
uv run pytest                                  # 전체
uv run pytest tests/domains/notifications      # 도메인 단위
uv run pytest -x --ff                          # 실패 우선, 첫 실패에서 중단
uv run pytest --cov=app --cov-report=term      # 커버리지 포함
```