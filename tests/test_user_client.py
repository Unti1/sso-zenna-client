"""Тесты UserClient и базовых ручек (pkce-params, /me, services, logout)."""

import pytest

from sso_zenna import UserClient
from sso_zenna.models import TokenResponse, UserInfo, PKCEParams, ServicesList


class TestUserClientPkceAndServices:
    """PKCE-параметры и публичные ручки без авторизации."""

    async def test_get_pkce_params(self, user_client: UserClient):
        """Получение PKCE-параметров от сервера."""
        params = await user_client.get_pkce_params()
        assert isinstance(params, PKCEParams)
        assert params.code_verifier
        assert params.code_challenge
        assert params.state

    async def test_get_available_services(self, user_client: UserClient):
        """Ручка /services — список доступных микросервисов."""
        result = await user_client.get_available_services()
        assert isinstance(result, ServicesList)
        assert hasattr(result, "services")
        assert isinstance(result.services, list)


class TestUserClientAuthAndMe:
    """Полный цикл авторизации и ручка /me."""

    async def test_full_auth_flow_returns_tokens(
        self,
        user_client: UserClient,
        user_login: str,
        user_password: str,
    ):
        """full_auth_flow возвращает TokenResponse с access и refresh токенами."""
        if not user_login or not user_password:
            pytest.skip("В .env.test задайте login и password для тестов авторизации")
        token = await user_client.full_auth_flow(login=user_login, password=user_password)
        assert isinstance(token, TokenResponse)
        assert token.access_token
        assert token.token_type
        assert token.expires_in > 0
        assert token.refresh_token

    async def test_me_after_auth_returns_user_info(
        self,
        user_client: UserClient,
        user_login: str,
        user_password: str,
    ):
        """После авторизации ручка /me возвращает UserInfo."""
        if not user_login or not user_password:
            pytest.skip("В .env.test задайте login и password для тестов авторизации")
        await user_client.full_auth_flow(login=user_login, password=user_password)
        me = await user_client.get_current_user()
        assert isinstance(me, UserInfo)
        assert me.id
        assert me.email
        assert me.name
        assert me.surname

    async def test_logout_clears_tokens(
        self,
        user_client: UserClient,
        user_login: str,
        user_password: str,
    ):
        """logout отзывает refresh и очищает токены у клиента."""
        if not user_login or not user_password:
            pytest.skip("В .env.test задайте login и password для тестов авторизации")
        await user_client.full_auth_flow(login=user_login, password=user_password)
        assert user_client.get_access_token()
        assert user_client.get_refresh_token()
        result = await user_client.logout()
        assert result
        assert user_client.get_access_token() is None
        assert user_client.get_refresh_token() is None
