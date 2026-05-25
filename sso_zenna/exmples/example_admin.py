"""Пример использования UserClient"""

import asyncio

from user_client import UserClient


async def main():
    # Создаем клиент
    client = UserClient(
        base_url="http://localhost:8000",
        client_id="your_client_id"
    )

    try:
        # Полный цикл авторизации
        token_response = await client.full_auth_flow(
            login="admin",
            password="SecretPassword123!",
            scope="sso.admin.read sso.admin.create",
        )

        print(f"Access token: {token_response.access_token[:50]}...")
        print(
            f"Refresh token: {token_response.refresh_token[:50] if token_response.refresh_token else None}...")
        print(f"Expires in: {token_response.expires_in} seconds")

        # Получаем информацию о пользователе
        user_info = await client.get_current_user()
        print(f"\nПользователь: {user_info.name} {user_info.surname}")
        print(f"Email: {user_info.email}")
        print(f"Scopes: {user_info.scopes}")

        # Обновляем токен
        new_token = await client.refresh_access_token()
        print(
            f"\nНовый access token получен: {new_token.access_token[:50]}...")

        # Получаем список доступных сервисов
        services = await client.get_available_services()
        print(f"\nДоступно сервисов: {len(services.services)}")
        for service in services.services:
            print(f"  - {service.name} ({service.client_id})")

    except Exception as e:
        print(f"Ошибка: {e}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
