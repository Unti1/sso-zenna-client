"""
SSO Zenna Client - Python клиент для взаимодействия с zenna-sso API

- UserClient: OAuth 2.0 с PKCE (login/password, /me, refresh)
- ServiceClient: Client Credentials для микросервисов (в т.ч. бот: users/telegram, profiles, auth/telegram-session)
- verify_sso_jwt_and_get_user_id: проверка JWT (RS256) для микросервисов
"""

from .user_client import UserClient
from .service_client import ServiceClient
from .jwt_verify import verify_sso_jwt_and_get_user_id
from .models import (
    UserInfo,
    TokenResponse,
    PKCEParams,
    TelegramSessionResponse,
    TelegramUserCreate,
    ProfileInfo,
)
from .exceptions import (
    SSOClientError,
    AuthenticationError,
    AuthorizationError,
    APIError,
    TokenError,
)

__all__ = [
    "UserClient",
    "ServiceClient",
    "verify_sso_jwt_and_get_user_id",
    "UserInfo",
    "TokenResponse",
    "PKCEParams",
    "TelegramSessionResponse",
    "TelegramUserCreate",
    "ProfileInfo",
    "SSOClientError",
    "AuthenticationError",
    "AuthorizationError",
    "APIError",
    "TokenError",
]

__version__ = "0.1.0"

