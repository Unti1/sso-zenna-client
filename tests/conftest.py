"""Конфигурация pytest и загрузка переменных из tests/.env.test"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Загружаем env из tests/.env.test (рядом с conftest)
_env_path = Path(__file__).resolve().parent / ".env.test"
load_dotenv(_env_path)



@pytest.fixture(scope="session")
def sso_url() -> str:
    """Базовый URL SSO (из .env.test)."""
    url = os.getenv("sso_url", "http://localhost:8001/")
    return url.rstrip("/")


@pytest.fixture(scope="session")
def user_login() -> str:
    """Логин пользователя для тестов (из .env.test)."""
    return os.getenv("login", "")


@pytest.fixture(scope="session")
def user_password() -> str:
    """Пароль пользователя для тестов (из .env.test)."""
    return os.getenv("password", "")


@pytest.fixture(scope="session")
def user_client_id() -> str:
    """client_id OAuth-клиента для пользовательских тестов (из .env.test)."""
    return os.getenv("client_id", "")


@pytest.fixture(scope="session")
def service_client_id() -> str:
    """client_id микросервиса для ServiceClient (из .env.test)."""
    return os.getenv("service_client_id", "") or os.getenv("client_id", "")


@pytest.fixture(scope="session")
def service_client_secret() -> str:
    """client_secret микросервиса для ServiceClient (из .env.test)."""
    return os.getenv("service_client_secret", "")


@pytest.fixture
def user_client(sso_url: str, user_client_id: str):
    """UserClient с параметрами из .env.test."""
    if not user_client_id:
        pytest.skip("В .env.test задайте client_id для тестов UserClient")
    from sso_zenna import UserClient
    return UserClient(base_url=sso_url, client_id=user_client_id)


@pytest.fixture
def sso_service_client(sso_url: str, service_client_id: str, service_client_secret: str):
    """Экземпляр ServiceClient. Пропуск теста, если в .env.test нет service_client_secret."""
    from sso_zenna import ServiceClient
    if not service_client_id or not service_client_secret:
        pytest.skip("В .env.test задайте service_client_id и service_client_secret для тестов ServiceClient")
    return ServiceClient(
        base_url=sso_url,
        client_id=service_client_id,
        client_secret=service_client_secret,
    )
