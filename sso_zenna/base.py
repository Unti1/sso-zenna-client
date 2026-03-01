"""Базовый класс для SSO клиентов"""

from typing import Optional, Dict, Any, List
from urllib.parse import urljoin
from abc import ABC, abstractmethod

import aiohttp
from aiohttp import ClientSession, ClientResponse

from .exceptions import (
    APIError,
    AuthenticationError,
    AuthorizationError,
    TokenError,
)


class BaseClient(ABC):
    """Базовый класс для всех SSO клиентов"""

    def __init__(
        self,
        base_url: str,
        api_version: str = "v1",
        timeout: int = 30,
        session: Optional[ClientSession] = None,
        auto_refresh_token: bool = True,
    ):
        """
        Инициализация базового клиента

        Args:
            base_url: Базовый URL API (например, "http://localhost:8000")
            api_version: Версия API (по умолчанию "v1")
            timeout: Таймаут запросов в секундах
            session: Опциональная aiohttp сессия (если не указана, создается новая)
            auto_refresh_token: Автоматически обновлять токен при получении 401 ошибки
        """
        self.base_url = base_url.rstrip("/")
        self.api_version = api_version
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session = session
        self._own_session = session is None
        self.auto_refresh_token = auto_refresh_token
        self._refreshing = False  # Флаг для предотвращения рекурсивных обновлений

    @property
    def api_base_url(self) -> str:
        """Базовый URL для API endpoints"""
        return urljoin(self.base_url, f"/api/{self.api_version}/")

    @property
    def session(self) -> ClientSession:
        """Получить или создать aiohttp сессию"""
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
            self._own_session = True
        elif self._session.closed:
            # Если сессия закрыта, создаем новую
            self._session = aiohttp.ClientSession(timeout=self.timeout)
            self._own_session = True
        return self._session

    async def close(self):
        """Закрыть сессию (если она была создана клиентом)"""
        if self._own_session and self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self):
        """Поддержка async context manager"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрытие сессии при выходе из context manager"""
        await self.close()

    def _build_url(self, endpoint: str) -> str:
        """Построить полный URL для endpoint"""
        endpoint = endpoint.lstrip("/")
        return urljoin(self.api_base_url, endpoint)

    def _get_headers(self, access_token: Optional[str] = None) -> Dict[str, str]:
        """Получить заголовки для запроса"""
        headers = {"Content-Type": "application/json"}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers

    @abstractmethod
    async def _refresh_token(self) -> None:
        """
        Абстрактный метод для обновления токена.
        Должен быть реализован в дочерних классах.
        """
        pass

    def _get_access_token(self) -> Optional[str]:
        """
        Получить текущий access token.
        Должен быть переопределен в дочерних классах.
        """
        return None

    async def _handle_response(self, response: ClientResponse) -> Dict[str, Any]:
        """
        Обработать HTTP ответ

        Args:
            response: aiohttp ClientResponse

        Returns:
            Распарсенный JSON ответ

        Raises:
            APIError: При ошибках API
            AuthenticationError: При ошибках аутентификации (401)
            AuthorizationError: При ошибках авторизации (403)
        """
        try:
            data = await response.json()
        except aiohttp.ContentTypeError:
            # Если ответ не JSON, пытаемся получить текст
            text = await response.text()
            data = {"detail": text} if text else {
                "detail": "Неизвестная ошибка"}

        if response.status == 401:
            detail = data.get("detail", "Ошибка аутентификации")
            raise AuthenticationError(detail)

        if response.status == 403:
            detail = data.get("detail", "Ошибка авторизации")
            raise AuthorizationError(detail)

        if not response.ok:
            detail = data.get("detail", f"Ошибка API: {response.status}")
            raise APIError(detail, status_code=response.status)

        return data

    async def _request(
        self,
        method: str,
        endpoint: str,
        access_token: Optional[str] = None,
        json_data: Optional[Dict[str, Any]] = None,
        form_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        retry_on_401: bool = True,
    ) -> Dict[str, Any]:
        """
        Выполнить HTTP запрос с автоматическим обновлением токена при 401

        Args:
            method: HTTP метод (GET, POST, etc.)
            endpoint: API endpoint (например, "auth/me")
            access_token: Access token для авторизации (опционально)
            json_data: JSON данные для тела запроса
            form_data: Form data для тела запроса
            params: Query параметры
            retry_on_401: Повторить запрос после обновления токена при 401

        Returns:
            Распарсенный JSON ответ
        """
        # Используем сохраненный токен, если не передан явно
        if access_token is None:
            access_token = self._get_access_token()

        url = self._build_url(endpoint)
        headers = self._get_headers(access_token)

        # Если form_data, меняем Content-Type
        if form_data:
            headers.pop("Content-Type", None)

        try:
            async with self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
                data=form_data,
                params=params,
            ) as response:
                # Если получили 401 и включен авто-рефреш, пытаемся обновить токен
                if (
                    response.status == 401
                    and self.auto_refresh_token
                    and retry_on_401
                    and not self._refreshing
                    and access_token
                ):
                    try:
                        # Пытаемся обновить токен
                        self._refreshing = True
                        await self._refresh_token()
                        # Получаем новый токен
                        new_token = self._get_access_token()
                        if new_token and new_token != access_token:
                            # Повторяем запрос с новым токеном
                            headers = self._get_headers(new_token)
                            if form_data:
                                headers.pop("Content-Type", None)
                            async with self.session.request(
                                method=method,
                                url=url,
                                headers=headers,
                                json=json_data,
                                data=form_data,
                                params=params,
                            ) as retry_response:
                                return await self._handle_response(retry_response)
                    except Exception:
                        # Если обновление не удалось, пробрасываем оригинальную ошибку
                        pass
                    finally:
                        self._refreshing = False

                return await self._handle_response(response)
        finally:
            # Закрываем сессию после взаимодействия (если она наша), чтобы избежать "Unclosed client session"
            if self._own_session and self._session and not self._session.closed:
                await self._session.close()

    async def get(
        self,
        endpoint: str,
        access_token: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        use_auto_refresh: bool = True,
    ) -> Dict[str, Any]:
        """Выполнить GET запрос"""
        return await self._request(
            "GET",
            endpoint,
            access_token=access_token,
            params=params,
            retry_on_401=use_auto_refresh,
        )

    async def post(
        self,
        endpoint: str,
        access_token: Optional[str] = None,
        json_data: Optional[Dict[str, Any]] = None,
        form_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        use_auto_refresh: bool = True,
    ) -> Dict[str, Any]:
        """Выполнить POST запрос"""
        return await self._request(
            "POST",
            endpoint,
            access_token=access_token,
            json_data=json_data,
            form_data=form_data,
            params=params,
            retry_on_401=use_auto_refresh,
        )

    async def put(
        self,
        endpoint: str,
        access_token: Optional[str] = None,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        use_auto_refresh: bool = True,
    ) -> Dict[str, Any]:
        """Выполнить PUT запрос"""
        return await self._request(
            "PUT",
            endpoint,
            access_token=access_token,
            json_data=json_data,
            params=params,
            retry_on_401=use_auto_refresh,
        )

    async def patch(
        self,
        endpoint: str,
        access_token: Optional[str] = None,
        json_data: Optional[Dict[str, Any]] = None,
        form_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        use_auto_refresh: bool = True,
    ) -> Dict[str, Any]:
        """Выполнить PATCH запрос"""
        return await self._request(
            "PATCH",
            endpoint,
            access_token=access_token,
            json_data=json_data,
            form_data=form_data,
            params=params,
            retry_on_401=use_auto_refresh,
        )

    async def delete(
        self,
        endpoint: str,
        access_token: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        use_auto_refresh: bool = True,
    ) -> Dict[str, Any]:
        """Выполнить DELETE запрос"""
        return await self._request(
            "DELETE",
            endpoint,
            access_token=access_token,
            params=params,
            retry_on_401=use_auto_refresh,
        )

    # ========== Админские методы ==========

    # Пользователи
    async def create_user(
        self,
        login: str,
        email: str,
        password: str,
        name: str,
        surname: str,
        lastname: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Создать нового пользователя (требует sso.admin.create)"""
        json_data = {
            "login": login,
            "email": email,
            "password": password,
            "name": name,
            "surname": surname,
        }
        if lastname:
            json_data["lastname"] = lastname
        return await self.post("admin/users", access_token=access_token, json_data=json_data)

    async def get_users(
        self,
        skip: int = 0,
        limit: int = 100,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получить список пользователей (требует sso.admin.read)"""
        return await self.get(
            "admin/users",
            access_token=access_token,
            params={"skip": skip, "limit": limit},
        )

    async def get_user(self, user_id: int, access_token: Optional[str] = None) -> Dict[str, Any]:
        """Получить пользователя по ID (требует sso.admin.read)"""
        return await self.get(f"admin/users/{user_id}", access_token=access_token)

    async def update_user(
        self,
        user_id: int,
        access_token: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Обновить пользователя (требует sso.admin.edit)"""
        return await self.put(f"admin/users/{user_id}", access_token=access_token, json_data=kwargs)

    async def delete_user(self, user_id: int, access_token: Optional[str] = None) -> Dict[str, Any]:
        """Удалить пользователя (требует sso.admin.delete)"""
        return await self.delete(f"admin/users/{user_id}", access_token=access_token)

    # Роли
    async def create_role(
        self,
        name: str,
        display_name: str,
        description: Optional[str] = None,
        client_id: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Создать новую роль (требует sso.admin.create)"""
        json_data = {"name": name, "display_name": display_name}
        if description:
            json_data["description"] = description
        if client_id:
            json_data["client_id"] = client_id
        return await self.post("admin/roles", access_token=access_token, json_data=json_data)

    async def get_roles(
        self,
        skip: int = 0,
        limit: int = 100,
        client_id: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получить список ролей (требует sso.admin.read)"""
        params = {"skip": skip, "limit": limit}
        if client_id:
            params["client_id"] = client_id
        return await self.get("admin/roles", access_token=access_token, params=params)

    async def get_role(self, role_id: int, access_token: Optional[str] = None) -> Dict[str, Any]:
        """Получить роль по ID (требует sso.admin.read)"""
        return await self.get(f"admin/roles/{role_id}", access_token=access_token)

    async def update_role(
        self,
        role_id: int,
        access_token: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Обновить роль (требует sso.admin.edit)"""
        return await self.put(f"admin/roles/{role_id}", access_token=access_token, json_data=kwargs)

    async def delete_role(self, role_id: int, access_token: Optional[str] = None) -> Dict[str, Any]:
        """Удалить роль (требует sso.admin.delete)"""
        return await self.delete(f"admin/roles/{role_id}", access_token=access_token)

    # Разрешения (Scopes)
    async def create_scope(
        self,
        name: str,
        client: str,
        role: str,
        action: str,
        description: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Создать новое разрешение (требует sso.admin.create)"""
        json_data = {
            "client": client,
            "role": role,
            "action": action
        }
        if description:
            json_data["description"] = description
        return await self.post("admin/scopes", access_token=access_token, json_data=json_data)

    async def get_scopes(
        self,
        skip: int = 0,
        limit: int = 100,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получить список разрешений (требует sso.admin.read)"""
        return await self.get(
            "admin/scopes",
            access_token=access_token,
            params={"skip": skip, "limit": limit},
        )

    async def get_scope(self, scope_id: int, access_token: Optional[str] = None) -> Dict[str, Any]:
        """Получить разрешение по ID (требует sso.admin.read)"""
        return await self.get(f"admin/scopes/{scope_id}", access_token=access_token)

    async def update_scope(
        self,
        scope_id: int,
        access_token: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Обновить разрешение (требует sso.admin.edit)"""
        return await self.put(f"admin/scopes/{scope_id}", access_token=access_token, json_data=kwargs)

    async def delete_scope(self, scope_id: int, access_token: Optional[str] = None) -> Dict[str, Any]:
        """Удалить разрешение (требует sso.admin.delete)"""
        return await self.delete(f"admin/scopes/{scope_id}", access_token=access_token)

    # Микросервисы (Clients)
    async def create_client(
        self,
        service_name: str,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Создать новый микросервис (требует sso.admin.create)"""
        return await self.post("admin/clients", access_token=access_token, json_data={"service_name": service_name})

    async def get_clients(
        self,
        skip: int = 0,
        limit: int = 100,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получить список клиентов (требует sso.admin.read)"""
        return await self.get(
            "admin/clients",
            access_token=access_token,
            params={"skip": skip, "limit": limit},
        )

    async def get_client(self, client_id: str, access_token: Optional[str] = None) -> Dict[str, Any]:
        """Получить клиента по ID (требует sso.admin.read)"""
        return await self.get(f"admin/clients/{client_id}", access_token=access_token)

    async def update_client(
        self,
        client_id: str,
        access_token: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Обновить клиента (требует sso.admin.edit)"""
        return await self.put(f"admin/clients/{client_id}", access_token=access_token, json_data=kwargs)

    async def assign_scopes_to_client(
        self,
        client_id: str,
        scope_ids: List[int],
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Назначить разрешения (scopes) клиенту (требует sso.admin.edit)"""
        return await self.post(
            f"admin/clients/{client_id}/scopes",
            access_token=access_token,
            json_data={"scope_ids": scope_ids},
        )

    async def assign_roles_to_client(
        self,
        client_id: str,
        role_ids: List[int],
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Привязать роли к микросервису (клиенту). POST admin/clients/{client_id}/roles, body: role_ids (требует sso.admin.edit)"""
        return await self.post(
            f"admin/clients/{client_id}/roles",
            access_token=access_token,
            json_data={"role_ids": role_ids},
        )

    async def rotate_client_secret(
        self,
        client_id: str,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Ротация client_secret (требует sso.admin.edit)"""
        return await self.post(f"admin/clients/{client_id}/rotate-secret", access_token=access_token)

    # Назначение ролей пользователям
    async def assign_role_to_user(
        self,
        user_id: int,
        role_id: int,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Назначить роль пользователю (требует sso.admin.create)"""
        return await self.post(
            f"admin/user-roles/{user_id}/roles",
            access_token=access_token,
            json_data={"role_id": role_id},
        )

    async def revoke_role_from_user(
        self,
        user_id: int,
        role_id: int,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Отозвать роль у пользователя (требует sso.admin.delete)"""
        return await self.delete(
            f"admin/user-roles/{user_id}/roles/{role_id}",
            access_token=access_token,
        )

    async def get_user_roles(
        self,
        user_id: int,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получить роли пользователя (требует sso.admin.read)"""
        return await self.get(f"admin/user-roles/{user_id}/roles", access_token=access_token)

    async def get_user_scopes(
        self,
        user_id: int,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получить разрешения пользователя (требует sso.admin.read)"""
        return await self.get(f"admin/user-roles/{user_id}/scopes", access_token=access_token)

    async def get_users_with_roles(
        self,
        skip: int = 0,
        limit: int = 100,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получить список пользователей с их ролями (требует sso.admin.read)"""
        return await self.get(
            "admin/user-roles",
            access_token=access_token,
            params={"skip": skip, "limit": limit},
        )

    # Логи
    async def get_role_logs(
        self,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[int] = None,
        search: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получить логи действий с ролями (требует sso.admin.read)"""
        params = {"skip": skip, "limit": limit}
        if user_id:
            params["user_id"] = user_id
        if search:
            params["search"] = search
        return await self.get("logs/role", access_token=access_token, params=params)

    async def get_user_logs(
        self,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[int] = None,
        search: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получить логи действий с пользователями (требует sso.admin.read)"""
        params = {"skip": skip, "limit": limit}
        if user_id:
            params["user_id"] = user_id
        if search:
            params["search"] = search
        return await self.get("logs/user", access_token=access_token, params=params)

    async def get_auth_logs(
        self,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[int] = None,
        search: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получить логи действий авторизации (требует sso.admin.read)"""
        params = {"skip": skip, "limit": limit}
        if user_id:
            params["user_id"] = user_id
        if search:
            params["search"] = search
        return await self.get("logs/auth", access_token=access_token, params=params)

    async def get_service_logs(
        self,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[int] = None,
        search: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получить логи действий сервисов (требует sso.admin.read)"""
        params = {"skip": skip, "limit": limit}
        if user_id:
            params["user_id"] = user_id
        if search:
            params["search"] = search
        return await self.get("logs/service", access_token=access_token, params=params)
