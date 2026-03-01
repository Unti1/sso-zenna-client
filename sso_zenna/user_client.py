"""Клиент для пользовательского взаимодействия (OAuth 2.0 с PKCE)"""

from typing import Optional
import hashlib
import base64
import secrets

from .base import BaseClient
from .models import (
    PKCEParams,
    TokenResponse,
    UserInfo,
    AuthorizeResponse,
    LoginResponse,
    ServicesList,
    TelegramSessionResponse,
    TelegramUserCreate,
)
from .exceptions import TokenError


class UserClient(BaseClient):
    """Клиент для пользовательского взаимодействия с OAuth 2.0 Authorization Code Flow с PKCE"""

    def __init__(
        self,
        base_url: str,
        client_id: str,
        redirect_uri: Optional[str] = None,
        api_version: str = "v1",
        timeout: int = 30,
        session=None,
        auto_refresh_token: bool = True,
    ):
        """
        Инициализация клиента для пользователей

        Args:
            base_url: Базовый URL API
            client_id: ID OAuth клиента
            redirect_uri: URI для редиректа (опционально)
            api_version: Версия API
            timeout: Таймаут запросов
            session: Опциональная aiohttp сессия
            auto_refresh_token: Автоматически обновлять токен при получении 401 ошибки
        """
        super().__init__(base_url, api_version, timeout, session, auto_refresh_token)
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self._pkce_params: Optional[PKCEParams] = None
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None

    @staticmethod
    def _generate_code_verifier() -> str:
        """Генерация code_verifier для PKCE"""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8").rstrip("=")

    @staticmethod
    def _generate_code_challenge(code_verifier: str) -> str:
        """Генерация code_challenge из code_verifier"""
        sha256_hash = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(sha256_hash).decode("utf-8").rstrip("=")

    @staticmethod
    def _generate_state() -> str:
        """Генерация state для CSRF защиты"""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8").rstrip("=")

    async def get_pkce_params(self) -> PKCEParams:
        """
        Получить PKCE параметры от сервера

        Returns:
            PKCEParams с code_verifier, code_challenge и state
        """
        data = await self.get("auth/pkce-params")
        self._pkce_params = PKCEParams(**data)
        return self._pkce_params

    async def authorize(
        self,
        scope: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        pkce_params: Optional[PKCEParams] = None,
    ) -> AuthorizeResponse:
        """
        Инициировать OAuth 2.0 Authorization Code Flow

        Args:
            scope: Запрашиваемые разрешения (разделенные пробелом)
            redirect_uri: URI для редиректа (если не указан, используется из конструктора)
            pkce_params: PKCE параметры (если не указаны, получаются автоматически)

        Returns:
            AuthorizeResponse с session_id для последующего логина
        """
        # Получаем PKCE параметры, если не переданы
        if pkce_params is None:
            if self._pkce_params is None:
                pkce_params = await self.get_pkce_params()
            else:
                pkce_params = self._pkce_params
        else:
            self._pkce_params = pkce_params

        redirect_uri = redirect_uri or self.redirect_uri

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "state": pkce_params.state,
            "code_challenge": pkce_params.code_challenge,
            "code_challenge_method": "S256",
        }

        if redirect_uri:
            params["redirect_uri"] = redirect_uri

        if scope:
            params["scope"] = scope

        data = await self.get("auth/authorize", params=params)
        return AuthorizeResponse(**data)

    async def login(
        self,
        login: str,
        password: str,
        session_id: str,
    ) -> LoginResponse:
        """
        Выполнить аутентификацию пользователя

        Args:
            login: Логин пользователя
            password: Пароль пользователя
            session_id: ID сессии из метода authorize()

        Returns:
            LoginResponse с authorization_code
        """
        json_data = {
            "session_id": session_id,
            "login": login,
            "password": password,
        }

        data = await self.post("auth/login", json_data=json_data)
        return LoginResponse(**data)

    async def exchange_code_for_tokens(
        self,
        authorization_code: str,
        redirect_uri: Optional[str] = None,
        pkce_params: Optional[PKCEParams] = None,
    ) -> TokenResponse:
        """
        Обменять authorization code на токены

        Args:
            authorization_code: Authorization code из метода login()
            redirect_uri: Redirect URI (если не указан, используется из конструктора)
            pkce_params: PKCE параметры (если не указаны, используются сохраненные)

        Returns:
            TokenResponse с access_token и refresh_token
        """
        if pkce_params is None:
            if self._pkce_params is None:
                raise TokenError(
                    "PKCE параметры не найдены. Вызовите get_pkce_params() или authorize() сначала.")
            pkce_params = self._pkce_params

        redirect_uri = redirect_uri or self.redirect_uri

        form_data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "client_id": self.client_id,
            "code_verifier": pkce_params.code_verifier,
        }

        if redirect_uri:
            form_data["redirect_uri"] = redirect_uri

        data = await self.post("auth/token", form_data=form_data)
        token_response = TokenResponse(**data)

        # Сохраняем токены
        self._access_token = token_response.access_token
        self._refresh_token = token_response.refresh_token

        return token_response

    async def refresh_access_token(self, refresh_token: Optional[str] = None) -> TokenResponse:
        """
        Обновить access token используя refresh token

        Args:
            refresh_token: Refresh token (если не указан, используется сохраненный)

        Returns:
            TokenResponse с новым access_token и refresh_token
        """
        refresh_token = refresh_token or self._refresh_token

        if not refresh_token:
            raise TokenError(
                "Refresh token не найден. Выполните авторизацию сначала.")

        form_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
        }

        data = await self.post("auth/token", form_data=form_data)
        token_response = TokenResponse(**data)

        # Обновляем токены
        self._access_token = token_response.access_token
        self._refresh_token = token_response.refresh_token

        return token_response

    async def get_current_user(self, access_token: Optional[str] = None) -> UserInfo:
        """
        Получить информацию о текущем пользователе

        Args:
            access_token: Access token (если не указан, используется сохраненный)

        Returns:
            UserInfo с информацией о пользователе
        """
        access_token = access_token or self._access_token

        if not access_token:
            raise TokenError(
                "Access token не найден. Выполните авторизацию сначала.")

        data = await self.get("auth/me", access_token=access_token)
        return UserInfo(**data)

    async def logout(self, refresh_token: Optional[str] = None) -> dict:
        """
        Выйти из системы и отозвать refresh token

        Args:
            refresh_token: Refresh token для отзыва (если не указан, используется сохраненный)

        Returns:
            Словарь с сообщением об успешном выходе
        """
        refresh_token = refresh_token or self._refresh_token

        if not refresh_token:
            raise TokenError("Refresh token не найден.")

        form_data = {"refresh_token": refresh_token}

        data = await self.post("auth/logout", form_data=form_data)

        # Очищаем токены
        self._access_token = None
        self._refresh_token = None
        self._pkce_params = None

        return data

    async def get_available_services(self) -> ServicesList:
        """
        Получить список всех доступных микросервисов

        Returns:
            ServicesList со списком активных микросервисов
        """
        data = await self.get("auth/services")
        return ServicesList(**data)

    def _get_access_token(self) -> Optional[str]:
        """Получить текущий access token (для BaseClient)"""
        return self._access_token

    async def _refresh_token(self) -> None:
        """Обновить access token используя refresh token (для авто-рефреша)"""
        if not self._refresh_token:
            raise TokenError("Refresh token не найден. Выполните авторизацию сначала.")
        await self.refresh_access_token(self._refresh_token)

    def get_access_token(self) -> Optional[str]:
        """Получить текущий access token"""
        return self._access_token

    def get_refresh_token(self) -> Optional[str]:
        """Получить текущий refresh token"""
        return self._refresh_token

    def set_tokens(self, access_token: str, refresh_token: Optional[str] = None):
        """
        Установить токены вручную

        Args:
            access_token: Access token
            refresh_token: Refresh token (опционально)
        """
        self._access_token = access_token
        if refresh_token:
            self._refresh_token = refresh_token

    async def full_auth_flow(
        self,
        login: str,
        password: str,
        scope: Optional[str] = None,
        redirect_uri: Optional[str] = None,
    ) -> TokenResponse:
        """
        Выполнить полный цикл авторизации (удобный метод)

        Args:
            login: Логин пользователя
            password: Пароль пользователя
            scope: Запрашиваемые разрешения
            redirect_uri: URI для редиректа

        Returns:
            TokenResponse с токенами
        """
        # 1. Получаем PKCE параметры
        pkce_params = await self.get_pkce_params()

        # 2. Инициируем авторизацию
        auth_response = await self.authorize(
            scope=scope,
            redirect_uri=redirect_uri,
            pkce_params=pkce_params,
        )

        # 3. Выполняем логин
        login_response = await self.login(
            login=login,
            password=password,
            session_id=auth_response.session_id,
        )

        # 4. Обмениваем код на токены
        token_response = await self.exchange_code_for_tokens(
            authorization_code=login_response.authorization_code,
            redirect_uri=redirect_uri,
            pkce_params=pkce_params,
        )

        return token_response
