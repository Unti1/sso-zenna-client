"""Тесты ServiceClient и базовых ручек (token, /me)."""

import pytest

from sso_zenna import ServiceClient
from sso_zenna.models import TokenResponse, UserInfo


class TestServiceClientTokenAndMe:
    """Client Credentials: получение токена и ручка /me."""

    async def test_get_access_token(self, sso_service_client: ServiceClient):
        """Получение access token через client_credentials."""
        token = await sso_service_client.get_access_token()
        assert isinstance(token, TokenResponse)
        assert token.access_token
        assert token.token_type
        assert token.expires_in > 0

    async def test_me_after_token_returns_info(self, sso_service_client: ServiceClient):
        """После get_access_token ручка /me возвращает данные (сервис/пользователь)."""
        await sso_service_client.get_access_token()
        me = await sso_service_client.get_current_user()
        assert isinstance(me, UserInfo)
        assert me.id is not None
        assert isinstance(getattr(me, "scopes", []), list)

    async def test_get_token_payload_and_service_name(self, sso_service_client: ServiceClient):
        """get_token_payload и get_service_name возвращают данные из JWT."""
        await sso_service_client.get_access_token()
        payload = sso_service_client.get_token_payload()
        assert isinstance(payload, dict)
        # service_name может быть в payload для client_credentials
        name = sso_service_client.get_service_name()
        # Допускаем None, если бэкенд не кладёт service_name
        assert name is None or isinstance(name, str)
