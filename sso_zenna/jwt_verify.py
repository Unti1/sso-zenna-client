"""
Проверка JWT токенов SSO (RS256).
Для микросервисов, которым нужно валидировать токены пользователей (Bearer или cookie).
"""

from typing import Optional

import jwt
from jwt import PyJWTError

from .exceptions import AuthenticationError


def verify_sso_jwt_and_get_user_id(
    token: str,
    public_key: str,
    issuer: Optional[str] = None,
    algorithms: tuple[str, ...] = ("RS256",),
) -> int:
    """
    Проверяет JWT токен SSO (RS256) и возвращает id пользователя.

    Args:
        token: JWT токен (Bearer или из cookie access_token)
        public_key: Публичный ключ SSO (PEM)
        issuer: Ожидаемый issuer (опционально)
        algorithms: Разрешённые алгоритмы (по умолчанию RS256)

    Returns:
        id_user из payload (id_user или sub)

    Raises:
        AuthenticationError: при невалидном или истёкшем токене
    """
    options = {"verify_signature": True, "verify_exp": True, "verify_iat": True}
    kwargs = {"algorithms": list(algorithms)}
    if issuer:
        kwargs["issuer"] = issuer

    try:
        payload = jwt.decode(token, public_key, options=options, **kwargs)
    except PyJWTError as e:
        raise AuthenticationError(f"Invalid or expired token: {e}") from e

    user_id = payload.get("id_user") or payload.get("sub")
    if user_id is None:
        raise AuthenticationError("Token missing id_user/sub claim")

    try:
        return int(user_id)
    except (ValueError, TypeError) as e:
        raise AuthenticationError(f"Invalid user_id in token: {e}") from e
