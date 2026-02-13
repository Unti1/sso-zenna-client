# SSO Zenna Client

Python клиент для взаимодействия с MS Auth Service API. Предоставляет удобные классы для работы с OAuth 2.0 Authorization Code Flow с PKCE (для пользователей) и Client Credentials Grant (для микросервисов).

## Установка

```bash
pip install -e .
```

Или если пакет опубликован:

```bash
pip install sso_zenna
```

## Быстрый старт

### Для пользователей (UserClient)

```python
import asyncio
from sso_client import UserClient

async def main():
    # Создаем клиент
    client = UserClient(
        base_url="http://localhost:8000",
        client_id="your_client_id",
        redirect_uri="http://localhost:3000/callback"
    )
    
    # Полный цикл авторизации
    token_response = await client.full_auth_flow(
        login="user@example.com",
        password="password123",
        scope="sso.admin.read sso.admin.create"
    )
    
    print(f"Access token: {token_response.access_token}")
    print(f"Refresh token: {token_response.refresh_token}")
    
    # Получаем информацию о пользователе
    user_info = await client.get_current_user()
    print(f"Пользователь: {user_info.name} {user_info.surname}")
    
    # Обновляем токен
    new_token = await client.refresh_access_token()
    print(f"Новый access token: {new_token.access_token}")
    
    await client.close()

asyncio.run(main())
```

### Пошаговая авторизация

```python
import asyncio
from sso_client import UserClient

async def main():
    client = UserClient(
        base_url="http://localhost:8000",
        client_id="your_client_id"
    )
    
    # 1. Получаем PKCE параметры
    pkce_params = await client.get_pkce_params()
    
    # 2. Инициируем авторизацию
    auth_response = await client.authorize(
        scope="sso.admin.read",
        pkce_params=pkce_params
    )
    
    # 3. Выполняем логин
    login_response = await client.login(
        login="user@example.com",
        password="password123",
        session_id=auth_response.session_id
    )
    
    # 4. Обмениваем код на токены
    token_response = await client.exchange_code_for_tokens(
        authorization_code=login_response.authorization_code,
        pkce_params=pkce_params
    )
    
    print(f"Токены получены: {token_response.access_token}")
    
    await client.close()

asyncio.run(main())
```

### Для микросервисов (ServiceClient)

```python
import asyncio
from sso_client import ServiceClient

async def main():
    # Создаем клиент для микросервиса
    client = ServiceClient(
        base_url="http://localhost:8000",
        client_id="service_id",
        client_secret="service_secret"
    )
    
    # Получаем access token
    token_response = await client.get_access_token(
        scope="system.client.read system.client.edit"
    )
    
    print(f"Access token: {token_response.access_token}")
    
    # Выполняем запросы с авторизацией
    user_info = await client.get_current_user()
    
    # Или используем request_with_auth для любых endpoints
    data = await client.request_with_auth(
        method="GET",
        endpoint="admin/users",
        params={"skip": 0, "limit": 10}
    )
    
    await client.close()

asyncio.run(main())
```

## Использование с async context manager

```python
import asyncio
from sso_client import UserClient

async def main():
    async with UserClient(
        base_url="http://localhost:8000",
        client_id="your_client_id"
    ) as client:
        token_response = await client.full_auth_flow(
            login="user@example.com",
            password="password123"
        )
        # Сессия автоматически закроется при выходе

asyncio.run(main())
```

Пример для получения информации по пользвателю для подстановки в Depends
```
from fastapi import FastAPI, Header, HTTPException
from typing import Optional

app = FastAPI()

sso_client = ServiceClient(
    base_url="http://localhost:8000",
    client_id="your_service_id",
    client_secret="your_service_secret"
)

async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Dependency для получения текущего пользователя из токена
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Токен не предоставлен")
    
    # Извлекаем токен из заголовка "Bearer <token>"
    try:
        token = authorization.split(" ")[1]
    except IndexError:
        raise HTTPException(status_code=401, detail="Неверный формат токена")
    
    try:
        user_info = await sso_client.get_current_user(access_token=token)
        return user_info
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Невалидный токен")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при проверке токена: {e}")

@app.get("/protected")
async def protected_endpoint(current_user = Depends(get_current_user)):
    """
    Защищенный endpoint, который требует валидный токен пользователя
    """
    return {
        "message": f"Привет, {current_user.name} {current_user.surname}!",
        "user_id": current_user.id,
        "email": current_user.email,
        "scopes": current_user.scopes
    }

```

## API Reference

### UserClient

Класс для пользовательского взаимодействия с OAuth 2.0 Authorization Code Flow с PKCE.

#### Методы

- `get_pkce_params()` - Получить PKCE параметры от сервера
- `authorize(scope, redirect_uri, pkce_params)` - Инициировать OAuth 2.0 flow
- `login(login, password, session_id)` - Выполнить аутентификацию
- `exchange_code_for_tokens(authorization_code, redirect_uri, pkce_params)` - Обменять код на токены
- `refresh_access_token(refresh_token)` - Обновить access token
- `get_current_user(access_token)` - Получить информацию о пользователе
- `logout(refresh_token)` - Выйти из системы
- `get_available_services()` - Получить список доступных микросервисов
- `full_auth_flow(login, password, scope, redirect_uri)` - Выполнить полный цикл авторизации

### ServiceClient

Класс для микросервисного взаимодействия с Client Credentials Grant.

#### Методы

- `get_access_token(scope)` - Получить access token
- `get_current_user(access_token)` - Получить информацию о текущем пользователе/сервисе
- `request_with_auth(method, endpoint, json_data, params, auto_refresh)` - Выполнить запрос с авторизацией

## Исключения

- `SSOClientError` - Базовое исключение
- `AuthenticationError` - Ошибка аутентификации (401)
- `AuthorizationError` - Ошибка авторизации (403)
- `APIError` - Ошибка API (4xx, 5xx)
- `TokenError` - Ошибка работы с токенами

## Лицензия

MIT

