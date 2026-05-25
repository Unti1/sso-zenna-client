"""Пример использования ServiceClient"""

import asyncio
from service_client import ServiceClient
 

async def main():
    # Создаем клиент для микросервиса
    client = ServiceClient(
        base_url="http://localhost:8000",
        client_id="service_id",
        client_secret="service_secret",
    )

    try:
        # Получаем access token
        token_response = await client.get_access_token(
            scope="system.client.read system.client.edit",
        )

        print(f"Access token: {token_response.access_token[:50]}...")
        print(f"Expires in: {token_response.expires_in} seconds")
        print(f"Scope: {token_response.scope}")

        # Получаем информацию о текущем пользователе/сервисе
        user_info = await client.get_current_user()
        print(f"\nClient ID: {user_info.id if hasattr(user_info, 'id') else 'N/A'}")

        # Выполняем запросы с авторизацией
        # Пример: получение списка пользователей (требует админских прав)
        try:
            data = await client.request_with_auth(
                method="GET",
                endpoint="admin/users",
                params={"skip": 0, "limit": 10},
            )
            print(f"\nПолучено пользователей: {len(data) if isinstance(data, list) else 'N/A'}")
        except Exception as e:
            print(f"\nОшибка при запросе: {e}")

    except Exception as e:
        print(f"Ошибка: {e}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())

