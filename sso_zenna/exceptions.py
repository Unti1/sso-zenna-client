"""Исключения для SSO клиента"""


class SSOClientError(Exception):
    """Базовое исключение для всех ошибок клиента"""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AuthenticationError(SSOClientError):
    """Ошибка аутентификации (401)"""

    def __init__(self, message: str = "Ошибка аутентификации"):
        super().__init__(message, status_code=401)


class AuthorizationError(SSOClientError):
    """Ошибка авторизации (403)"""

    def __init__(self, message: str = "Ошибка авторизации"):
        super().__init__(message, status_code=403)


class APIError(SSOClientError):
    """Ошибка API (4xx, 5xx)"""

    def __init__(self, message: str, status_code: int):
        super().__init__(message, status_code=status_code)


class TokenError(SSOClientError):
    """Ошибка работы с токенами"""

    def __init__(self, message: str = "Ошибка работы с токеном"):
        super().__init__(message)
