import re
from collections.abc import Iterator

import pytest
import respx
from httpx import Response


@pytest.fixture
def discord_oauth_mocks() -> Iterator[respx.Router]:
    """Discord OAuth + Bot DM 호출을 한 묶음으로 모킹한다."""
    with respx.mock(assert_all_called=False) as router:
        router.post("https://discord.com/api/oauth2/token").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "fake-access",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "refresh_token": "fake-refresh",
                    "scope": "identify applications.commands",
                },
            )
        )
        router.get("https://discord.com/api/users/@me").mock(
            return_value=Response(
                200,
                json={"id": "987654321098765432", "username": "discordian"},
            )
        )
        # 환영 DM. BackgroundTask로 응답 직후 호출되므로 모킹해 둔다.
        router.post("https://discord.com/api/v10/users/@me/channels").mock(
            return_value=Response(200, json={"id": "ch-test-1"})
        )
        router.post(
            re.compile(r"https://discord.com/api/v10/channels/.*/messages")
        ).mock(return_value=Response(200, json={}))
        yield router
