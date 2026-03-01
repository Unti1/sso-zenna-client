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
    """Информация о пользователе (из /me, JWT или users/telegram)"""

    id: int = Field(..., description="ID пользователя")
    email: str = Field("", description="Email пользователя (опционально для Telegram)")
    name: str = Field("", description="Имя пользователя")
    surname: str = Field("", description="Фамилия пользователя")
    lastname: Optional[str] = Field(None, description="Отчество пользователя")
    scopes: list[str] = Field(default_factory=list,
                              description="Список разрешений пользователя")
    tz: Optional[int] = Field(None, description="Часовой пояс")
    phone: Optional[str] = Field(None, description="Телефон")
    status: Optional[str] = Field(None, description="Статус подписки")

    model_config = {"extra": "ignore"}


class TelegramSessionResponse(BaseModel):
    """Ответ на создание сессии для Telegram-авторизации"""

    session_token: str = Field(..., description="Токен сессии")
    auth_url: str = Field(..., description="URL для редиректа пользователя")


class ProfileInfo(BaseModel):
    """Профиль пользователя (из SSO GET/PATCH profiles/{user_id})."""

    user_id: int = Field(..., description="ID пользователя (Telegram id)")
    lang: str = Field("EN", description="Язык RU/EN")
    gender: Optional[str] = Field(None, description="Пол")
    email: Optional[str] = Field(None, description="Email")
    notify_telegram: bool = Field(True, description="Уведомления в Telegram")
    notify_email: bool = Field(False, description="Уведомления по email")
    name: Optional[str] = Field(None, description="Имя")
    about: Optional[str] = Field(None, description="О себе")
    age: Optional[str] = Field(None, description="Возраст")
    weight: Optional[float] = Field(None, description="Вес")
    height: Optional[float] = Field(None, description="Рост")

    model_config = {"extra": "ignore"}


class TelegramUserCreate(BaseModel):
    """Данные для создания пользователя из Telegram"""

    id: int = Field(..., description="Telegram user ID")
    tz: int = Field(3, ge=-12, le=12, description="Часовой пояс")
    phone: Optional[str] = Field(None, max_length=32)
    name: Optional[str] = Field(None, max_length=255)


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
