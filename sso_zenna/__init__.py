"""
SSO Zenna Client - Python клиент для взаимодействия с MS Auth Service API

Этот пакет предоставляет удобные классы для работы с API аутентификации:
- UserClient: для пользовательского взаимодействия (OAuth 2.0 с PKCE)
- ServiceClient: для микросервисного взаимодействия (Client Credentials)
"""

from .user_client import UserClient
from .service_client import ServiceClient
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
    "SSOClientError",
    "AuthenticationError",
    "AuthorizationError",
    "APIError",
    "TokenError",
]

__version__ = "0.1.0"

