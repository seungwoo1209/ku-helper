# Testing rules

## 도구

- `pytest`, `pytest-asyncio`(strict mode)
- 외부 HTTP 모킹: `respx` (서울 공공 API, 학교 사이트, Discord REST 모두)
- 시간 모킹: `time-machine`
- Redis: `fakeredis.aioredis` 우선. 통합 테스트에 실 Redis가 필요한 경우 `db=15` 전용으로 격리하고 매 테스트 시작 시 `flushdb`.
- 테스트 DB: 별도 PostgreSQL을 `docker compose -f docker-compose.test.yml up`으로 띄운다. compose 프로젝트명은 `name: ku-helper-bot-test`로 명시하여 백엔드 테스트 DB와 충돌하지 않게 한다. 포트도 별도(예: 5434).

## 구조

- `tests/` 디렉터리는 `app/` 구조를 미러링한다.
- `tests/conftest.py`: 전역 픽스처(엔진, 세션 팩토리, Redis, settings 오버라이드, fake discord client).
- 도메인별 `tests/notifications/<type>/conftest.py`: Worker 픽스처, 빌더 입력 팩토리.

## DB 격리

백엔드와 동일한 NullPool + commit-skip 패턴을 사용한다.

```python
# tests/conftest.py
@pytest_asyncio.fixture
async def db_session(test_engine):
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        yield session
        # 의도적으로 commit/rollback 생략 — 다음 테스트로 누설 방지
```

봇은 라우터·dependency_override 개념이 없으므로 Worker·Sender에 세션을 직접 주입하는 형태로 테스트한다.

## discord.py 모킹

- SDK 객체(`discord.Client`, `discord.User`, `discord.DMChannel`)는 `unittest.mock.AsyncMock`.
- 우리 래퍼 `DiscordBotClient`는 실제 코드를 통과시키되, 내부에서 호출되는 `dc_client.start()`·`dc_user.create_dm()`·`dc_channel.send()`만 모킹.
- 실제 `discord.Client.start(token)`은 테스트에서 호출하지 않는다 (Discord 실 연결 금지).

## APScheduler

- 스케줄러 자체 동작 검증은 1개의 lifespan 통합 테스트로 충분 (잡 1개 등록 → 트리거 1회 → 종료).
- 그 외에는 잡 함수(`run_transit_job(...)`)를 픽스처가 만든 의존성과 함께 직접 `await` 호출한다. APScheduler를 거치지 않는다.
- 시간에 의존하는 잡은 `time-machine`으로 freeze.

## 큐 워커

큐를 직접 만들고 워커 코루틴을 띄운 뒤 동기화:

```python
queue: asyncio.Queue[SendDmTask] = asyncio.Queue()
worker = asyncio.create_task(run_sender_worker(queue, ...))
await queue.put(task)
await queue.join()
worker.cancel()
```

발송 결과는 `notification_history` row 또는 모킹된 `dc_channel.send` 호출로 검증한다.

## 외부 API 모킹

- 서울 공공 API, 학교 도서관·학식 사이트 호출은 전부 respx.
- `respx.assert_all_called=True`로 모킹된 호출이 실제 발생했는지 검증.
- 실제 호출이 새 나가면 즉시 fail.

## 임베드 빌더

- JSON 직렬화(`embed.to_dict()`) 후 스냅샷 비교. 색상 코드·타임스탬프 포맷 회귀 가드.
- 한국어 텍스트 변경은 일부러 깨지는 것이 정상 — 스냅샷 갱신 PR로 처리.

## 픽스처 명명

- 명사 픽스처: `notification`, `dc_user`, `redis_client`, `db_session`. 동사형(`make_*`) 금지.
- 빌더는 `*_factory`: `notification_factory()`가 `Notification` ORM 인스턴스를 반환.
- 발송 가능한 사용자 컨텍스트는 `active_user`, 탈퇴 사용자는 `deleted_user`로 분리.

## 회귀 가드 우선

다음 회귀가 발생하면 즉시 fail하는 통합 테스트를 한 개씩 유지한다:
- `DELETED` 사용자에게 DM이 발송되는 경로(이중 가드 중 하나가 깨졌을 때).
- `notification_history`가 INSERT되지 않은 채 DM만 발송되는 경로.
- F-14 상태 키가 갱신되지 않아 같은 알림이 두 번 발송되는 경로.

## 커버리지

- Worker 90% 이상, Crawler 80%, Sender 90%, Repository 70%, 임베드 빌더는 스냅샷 1개씩.
- 커버리지 통과만을 위한 의미 없는 테스트(`assert True`, getter 호출) 금지.

## 실행

```bash
uv run pytest                                  # 전체
uv run pytest tests/notifications/transit      # 도메인 단위
uv run pytest -x --ff                          # 실패 우선, 첫 실패에서 중단
uv run pytest --cov=app --cov-report=term      # 커버리지 포함
```
