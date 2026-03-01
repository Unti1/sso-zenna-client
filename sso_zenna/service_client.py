"""Клиент для микросервисного взаимодействия (Client Credentials)"""

import base64
import json
from typing import Any, Dict, Optional

from .base import BaseClient
from .models import TokenResponse, UserInfo, ProfileInfo, TelegramSessionResponse
from .exceptions import TokenError


def _decode_jwt_payload(token: str) -> Dict[str, Any]:
    """
    Декодирует payload JWT без проверки подписи (только чтение полей).
    Токен получен от SSO, используется для извлечения claim service_name.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return {}


class ServiceClient(BaseClient):
    """Клиент для микросервисного взаимодействия с Client Credentials Grant"""

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        api_version: str = "v1",
        timeout: int = 30,
        session=None,
        auto_refresh_token: bool = True,
        default_scope: Optional[str] = None,
    ):
        """
        Инициализация клиента для микросервисов

        Args:
            base_url: Базовый URL API
            client_id: ID микросервиса
            client_secret: Секрет микросервиса
            api_version: Версия API
            timeout: Таймаут запросов
            session: Опциональная aiohttp сессия
            auto_refresh_token: Автоматически обновлять токен при получении 401 ошибки
            default_scope: Scope по умолчанию для автоматического получения токена
        """
        super().__init__(base_url, api_version, timeout, session, auto_refresh_token)
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token: Optional[str] = None
        self.default_scope = default_scope

    async def get_access_token(self, scope: Optional[str] = None) -> TokenResponse:
        """
        Получить access token используя Client Credentials Grant

        Args:
            scope: Запрашиваемые разрешения (разделенные пробелом)

        Returns:
            TokenResponse с access_token
        """
        form_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        if scope:
            form_data["scope"] = scope

        data = await self.post("auth/token", form_data=form_data)
        token_response = TokenResponse(**data)

        # Сохраняем токен
        self._access_token = token_response.access_token

        return token_response

    async def get_current_user(self, access_token: Optional[str] = None) -> UserInfo:
        """
        Получить информацию о текущем пользователе/сервисе

        Args:
            access_token: Access token (если не указан, используется сохраненный)

        Returns:
            UserInfo с информацией (для микросервисов может быть ограниченная информация)
        """
        access_token = access_token or self._access_token

        if not access_token:
            raise TokenError(
                "Access token не найден. Вызовите get_access_token() сначала.")

        data = await self.get("auth/me", access_token=access_token)
        return UserInfo(**data)

    async def get_user_by_token(self, user_access_token: str) -> UserInfo:
        """
        Проверить пользовательский JWT через SSO: GET /auth/me с этим токеном.
        Используется микросервисами для валидации входящего Bearer/cookie без хранения PEM.
        SSO сам проверяет подпись и возвращает данные пользователя.

        Args:
            user_access_token: Токен пользователя (из Authorization или cookie)

        Returns:
            UserInfo с id, email, name и т.д.

        Raises:
            AuthenticationError: если токен невалиден или истёк
        """
        data = await self.get("auth/me", access_token=user_access_token)
        return UserInfo(**data)

    def set_access_token(self, access_token: str):
        """
        Установить access token вручную

        Args:
            access_token: Access token
        """
        self._access_token = access_token

    def _get_access_token(self) -> Optional[str]:
        """Получить текущий access token (для BaseClient)"""
        return self._access_token

    async def _refresh_token(self) -> None:
        """Обновить access token (для авто-рефреша)"""
        await self.get_access_token(self.default_scope)

    def get_token(self) -> Optional[str]:
        """Получить текущий access token"""
        return self._access_token

    def get_token_payload(self, access_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Получить payload текущего JWT токена (без проверки подписи).
        Удобно для чтения полей, вшитых SSO (например service_name).

        Args:
            access_token: Токен (если не указан, используется сохранённый)

        Returns:
            Словарь с полями payload или пустой словарь при ошибке
        """
        token = access_token or self._access_token
        if not token:
            return {}
        return _decode_jwt_payload(token)

    @staticmethod
    def get_user_id_from_token(token: str) -> Optional[int]:
        """
        Извлечь id_user из JWT токена (без проверки подписи).
        Для проверки подписи используйте публичный ключ SSO.
        """
        payload = _decode_jwt_payload(token)
        user_id = payload.get("id_user") or payload.get("sub")
        if user_id is not None:
            try:
                return int(user_id)
            except (ValueError, TypeError):
                pass
        return None

    def get_service_name(self, access_token: Optional[str] = None) -> Optional[str]:
        """
        Получить название сервиса из JWT токена (поле service_name, вшитое SSO).

        Args:
            access_token: Токен (если не указан, используется сохранённый)

        Returns:
            Название сервиса или None, если токена нет или поле отсутствует
        """
        payload = self.get_token_payload(access_token)
        return payload.get("service_name")

    async def request_with_auth(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[dict] = None,
        params: Optional[dict] = None,
        auto_refresh: bool = True,
    ) -> dict:
        """
        Выполнить запрос с автоматической авторизацией

        Args:
            method: HTTP метод (GET, POST, PUT, DELETE)
            endpoint: API endpoint
            json_data: JSON данные для тела запроса
            params: Query параметры
            auto_refresh: Автоматически получать токен, если его нет

        Returns:
            Распарсенный JSON ответ
        """
        access_token = self._access_token

        if not access_token and auto_refresh:
            await self.get_access_token()
            access_token = self._access_token

        if not access_token:
            raise TokenError(
                "Access token не найден. Вызовите get_access_token() сначала.")

        return await self._request(
            method=method,
            endpoint=endpoint,
            access_token=access_token,
            json_data=json_data,
            params=params,
        )

    # --- Методы для бота (users/telegram, profiles, auth/telegram-session). Требуют Bearer с client_id = BOT_CLIENT_ID в SSO. ---

    async def _ensure_token(self) -> None:
        """Получить access token при необходимости."""
        if not self._access_token:
            await self.get_access_token()

    async def create_telegram_user(
        self,
        id: int,
        tz: int = 3,
        phone: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Optional[UserInfo]:
        """Создать или получить пользователя по Telegram ID (POST users/telegram)."""
        await self._ensure_token()
        payload = {"id": id, "tz": tz}
        if phone is not None:
            payload["phone"] = phone
        if name is not None:
            payload["name"] = name
        try:
            data = await self.post(
                "users/telegram",
                json_data=payload,
                access_token=self._access_token,
            )
            return UserInfo(**data)
        except Exception:
            return None

    async def create_telegram_session(self, user_id: int) -> Optional[TelegramSessionResponse]:
        """Создать сессию для web-авторизации (POST auth/telegram-session). Возвращает session_token и auth_url."""
        await self._ensure_token()
        try:
            data = await self.post(
                "auth/telegram-session",
                params={"user_id": user_id},
                access_token=self._access_token,
            )
            return TelegramSessionResponse(**data)
        except Exception:
            return None

    async def update_telegram_user(
        self,
        user_id: int,
        *,
        phone: Optional[str] = None,
        name: Optional[str] = None,
        last_seen: Optional[str] = None,
    ) -> Optional[UserInfo]:
        """Обновить telegram-пользователя (PATCH users/{user_id})."""
        payload = {}
        if phone is not None:
            payload["phone"] = phone
        if name is not None:
            payload["name"] = name
        if last_seen is not None:
            payload["last_seen"] = last_seen
        if not payload:
            return None
        await self._ensure_token()
        try:
            data = await self.patch(
                f"users/{user_id}",
                json_data=payload,
                access_token=self._access_token,
            )
            return UserInfo(**data)
        except Exception:
            return None

    async def get_profile(self, user_id: int) -> Optional[ProfileInfo]:
        """Получить профиль по user_id — Telegram id (GET profiles/{user_id})."""
        await self._ensure_token()
        try:
            data = await self.get(
                f"profiles/{user_id}",
                access_token=self._access_token,
            )
            return ProfileInfo(**data)
        except Exception:
            return None

    async def update_profile(
        self,
        user_id: int,
        *,
        lang: Optional[str] = None,
        name: Optional[str] = None,
        notify_telegram: Optional[bool] = None,
        notify_email: Optional[bool] = None,
        about: Optional[str] = None,
        age: Optional[str] = None,
        weight: Optional[float] = None,
        height: Optional[float] = None,
    ) -> Optional[ProfileInfo]:
        """Обновить профиль (PATCH profiles/{user_id}). Передавать только изменяемые поля."""
        form_data = {}
        if lang is not None:
            form_data["lang"] = lang
        if name is not None:
            form_data["name"] = name
        if notify_telegram is not None:
            form_data["notify_telegram"] = "true" if notify_telegram else "false"
        if notify_email is not None:
            form_data["notify_email"] = "true" if notify_email else "false"
        if about is not None:
            form_data["about"] = about
        if age is not None:
            form_data["age"] = age
        if weight is not None:
            form_data["weight"] = str(weight)
        if height is not None:
            form_data["height"] = str(height)
        if not form_data:
            return await self.get_profile(user_id)
        await self._ensure_token()
        try:
            data = await self.patch(
                f"profiles/{user_id}",
                form_data=form_data,
                access_token=self._access_token,
            )
            return ProfileInfo(**data)
        except Exception:
            return None
