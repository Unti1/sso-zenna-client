"""Pydantic модели для SSO клиента"""

from typing import Optional
from pydantic import BaseModel, Field


class PKCEParams(BaseModel):
    """PKCE параметры для OAuth 2.0"""

    code_verifier: str = Field(..., description="Code verifier для PKCE")
    code_challenge: str = Field(..., description="Code challenge для PKCE")
    state: str = Field(..., description="State parameter для CSRF защиты")


class TokenResponse(BaseModel):
    """Ответ с токенами"""

    access_token: str = Field(..., description="Access token")
    token_type: str = Field(default="Bearer", description="Тип токена")
    expires_in: int = Field(..., description="Время жизни токена в секундах")
    refresh_token: Optional[str] = Field(
        None, description="Refresh token (только для пользователей)")
    scope: Optional[str] = Field(None, description="Разрешения (scopes)")


class UserInfo(BaseModel):
    """Информация о пользователе"""

    id: int = Field(..., description="ID пользователя")
    email: str = Field(..., description="Email пользователя")
    name: str = Field(..., description="Имя пользователя")
    surname: str = Field(..., description="Фамилия пользователя")
    lastname: Optional[str] = Field(None, description="Отчество пользователя")
    scopes: list[str] = Field(default_factory=list,
                              description="Список разрешений пользователя")


class ServiceInfo(BaseModel):
    """Информация о сервисе"""

    client_id: str = Field(..., description="Уникальный идентификатор клиента")
    name: Optional[str] = Field(None, description="Название сервиса")


class ServicesList(BaseModel):
    """Список доступных сервисов"""

    services: list[ServiceInfo] = Field(...,
                                        description="Список всех активных микросервисов")


class AuthorizeResponse(BaseModel):
    """Ответ на запрос авторизации"""

    session_id: str = Field(...,
                            description="ID сессии для последующего логина")
    message: str = Field(..., description="Сообщение для клиента")


class LoginResponse(BaseModel):
    """Ответ на запрос логина"""

    success: bool = Field(..., description="Успешность операции")
    message: str = Field(..., description="Сообщение")
    authorization_code: str = Field(...,
                                    description="Authorization code для обмена на токены")
    state: str = Field(..., description="State parameter для проверки")
