"""
Ручной пример: полный цикл авторизации UserClient.
Переменные берутся из tests/.env.test (скопируйте из .env.test.example и заполните).

Запуск тестов клиентов и ручек /me, /services и т.д.:
  pytest tests/ -v
"""

import asyncio
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env.test")

from sso_zenna import UserClient
import os


def main():
    base_url = os.getenv("sso_url", "https://id.zennafinance.ru/").rstrip("/")
    client_id = os.getenv("client_id", "")
    login = os.getenv("login", "")
    password = os.getenv("password", "")

    if not client_id or not login or not password:
        print("Задайте в tests/.env.test: sso_url, client_id, login, password")
        return

    uc = UserClient(base_url=base_url, client_id=client_id)

    async def run():
        token = await uc.full_auth_flow(login=login, password=password)
        print(f"access_token={token.access_token}")
        print(f"refresh_token={token.refresh_token if token.refresh_token else None}")
        me = await uc.get_current_user()
        print(f"me: id={me.id} email={me.email} name={me.name} {me.surname}")

    asyncio.run(run())


if __name__ == "__main__":
    main()
