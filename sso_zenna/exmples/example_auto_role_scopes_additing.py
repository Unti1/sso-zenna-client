"""
Скрипт создания ролей, скоупов (разрешений) и привязки их к клиенту сервиса в SSO zenna.

Работает от имени пользователя-админа (UserClient): логин/пароль → токен с sso.admin.* → вызовы API.
Сервис не создаёт записи сам — все действия идут от профиля админа.

Соответствует RBAC в приложении:
- Роли: UserRole (admin, accountant, lawyer, manager, head_of_fin_econom_depart, head_of_legal_depart)
- Скоупы: RoleScopes (create, edit, read, delete)
- Формат скоупа в токене: {SERVICE_NAME}.{role}.{scope} (например reporting_calendar.accountant.read)

Переменные окружения:
  SSO_BASE_URL, SSO_CLIENT_ID  — для подключения к SSO
  SSO_ADMIN_LOGIN, SSO_ADMIN_PASSWORD — учётные данные пользователя с правами sso.admin (read, create, edit)

Запуск (из каталога src):
  cd src && python -m app.scripts.seed_rbac
"""
import asyncio
import os
import sys
from pathlib import Path

# Добавляем src в PYTHONPATH для импорта app
_src_root = Path(__file__).resolve().parent.parent.parent
if _src_root not in sys.path:
    sys.path.insert(0, str(_src_root))

# Подгружаем .env из корня репозитория
_repo_root = _src_root.parent
_env_file = _repo_root / ".env"
if _env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_file)

from sso_zenna import UserClient

from app.core.settings import config # Ваша конфигурация
from app.schemas.enums import RoleScopes, UserRole # Ваши enum-значения ролей и скоупов


# Человекочитаемые названия ролей для SSO
ROLE_DISPLAY_NAMES = {
    UserRole.ADMIN: "Администратор",
    UserRole.ACCOUNTANT: "Бухгалтер",
    UserRole.LAWYER: "Юрист",
    UserRole.MANAGER: "Менеджер",
    UserRole.HEAD_OF_FIN_ECONOM_DEPART: "Руководитель фин.-экон. отдела",
    UserRole.HEAD_OF_LEGAL_DEPART: "Руководитель юридического отдела",
}

# Scope для админ-операций в SSO (роли/скоупы создаёт только пользователь с этими правами)
ADMIN_SCOPE = "sso.admin.read sso.admin.create sso.admin.edit"


async def get_admin_token(client: UserClient) -> str:
    """Получить access token пользователя-админа (логин + пароль)."""
    login = os.environ.get("SSO_ADMIN_LOGIN", "admin").strip()
    password = os.environ.get("SSO_ADMIN_PASSWORD", "SecretPassword123!").strip()
    if not login or not password:
        raise SystemExit(
            "Задайте SSO_ADMIN_LOGIN и SSO_ADMIN_PASSWORD в .env или в окружении. "
            "Скрипт работает от имени пользователя-админа с правами sso.admin.*"
        )
    token_response = await client.full_auth_flow(
        login=login,
        password=password,
        scope=ADMIN_SCOPE,
    )
    return token_response.access_token


async def ensure_roles(client: UserClient, token: str) -> list[int]:
    """Создать все роли сервиса с привязкой к client_id. Возвращает список role_id для assign_roles_to_client."""
    client_id = config.sso_cfg.CLIENT_ID
    existing = await client.get_roles(client_id=client_id, limit=100, access_token=token)
    items = existing if isinstance(existing, list) else (existing.get("items") or existing.get("data") or [])
    by_name = {r.get("name"): r.get("id") for r in items if isinstance(r, dict) and r.get("name")}

    for role in UserRole:
        name = role.value
        display_name = ROLE_DISPLAY_NAMES.get(role, name)
        if name in by_name:
            print(f"  Роль уже существует: {name} (id={by_name[name]})")
            continue
        try:
            result = await client.create_role(
                name=name,
                display_name=display_name,
                description=f"Роль сервиса отчётности: {display_name}",
                client_id=client_id,
                access_token=token,
            )
            data = result.get("data")
            rid = result.get("id") or (data.get("id") if isinstance(data, dict) else None)
            if rid is not None:
                by_name[name] = int(rid)
            print(f"  Создана роль: {name} ({display_name}), id={rid}")
        except Exception as e:
            print(f"  Ошибка создания роли {name}: {e}")
            raise

    # Собрать актуальный список id ролей (после созданий нужно перечитать, т.к. by_name мог быть неполный)
    existing2 = await client.get_roles(client_id=client_id, limit=100, access_token=token)
    items2 = existing2 if isinstance(existing2, list) else (existing2.get("items") or existing2.get("data") or [])
    role_ids = [r["id"] for r in items2 if isinstance(r, dict) and r.get("id") is not None]
    return role_ids


async def ensure_scopes(client: UserClient, token: str) -> None:
    """
    Создать все скоупы для сервиса (client + role + action).
    Вызывается после ensure_roles. К клиенту привязываются роли (assign_roles_to_client), не скоупы.
    """
    client_id = config.sso_cfg.CLIENT_ID
    service_name = config.app_cfg.SERVICE_NAME
    existing = await client.get_scopes(limit=500, access_token=token)
    items = existing if isinstance(existing, list) else (existing.get("items") or existing.get("data") or [])
    # Ключ для проверки существования: (client, role, action) или name, в зависимости от ответа API
    seen = set()
    for s in items:
        if not isinstance(s, dict):
            continue
        name = s.get("name")
        if name:
            seen.add(name)
        else:
            key = (s.get("client"), s.get("role"), s.get("action"))
            if all(key):
                seen.add(key)

    for role in UserRole:
        for scope_enum in RoleScopes:
            name = f"{service_name}.{role.value}.{scope_enum.value}"
            if name in seen:
                print(f"  Scope уже существует: {name}")
                continue
            key = (client_id, role.value, scope_enum.value)
            if key in seen:
                print(f"  Scope уже существует: {key}")
                continue
            try:
                result = await client.create_scope(
                    name=name,
                    client=client_id,
                    role=role.value,
                    action=scope_enum.value,
                    description=f"Reporting: роль {role.value}, действие {scope_enum.value}",
                    access_token=token,
                )
                data = result.get("data")
                sid = result.get("id") or (data.get("id") if isinstance(data, dict) else None)
                print(f"  Создан scope: {name}" + (f" (id={sid})" if sid is not None else ""))
                seen.add(name)
                seen.add(key)
            except Exception as e:
                print(f"  Ошибка создания scope {name}: {e}")
                raise


async def assign_roles_to_service_client(client: UserClient, token: str, role_ids: list[int]) -> None:
    """Привязать роли к клиенту сервиса (assign_roles_to_client)."""
    client_id = config.sso_cfg.CLIENT_ID
    if not role_ids:
        print("  Нет ролей для привязки к клиенту.")
        return
    await client.assign_roles_to_client(
        client_id=client_id,
        role_ids=role_ids,
        access_token=token,
    )
    print(f"  К клиенту {client_id} привязано ролей: {len(role_ids)}")


async def main() -> None:
    print("Конфигурация:")
    print(f"  SSO BASE_URL: {config.sso_cfg.BASE_URL}")
    print(f"  CLIENT_ID: {config.sso_cfg.CLIENT_ID}")
    print(f"  SERVICE_NAME: {config.app_cfg.SERVICE_NAME}")
    print(f"  Логин админа: {os.environ.get('SSO_ADMIN_LOGIN', '(не задан)')}")
    print()

    client = UserClient(
        base_url=config.sso_cfg.BASE_URL,
        client_id=config.sso_cfg.CLIENT_ID,
    )

    try:
        print("1. Авторизация под пользователем-админом (sso.admin.*)...")
        token = await get_admin_token(client)
        print("   Токен получен.\n")

        print("2. Создание ролей...")
        role_ids = await ensure_roles(client, token)
        print(f"   Всего ролей у клиента: {len(role_ids)}\n")

        print("3. Создание скоупов (scope)...")
        await ensure_scopes(client, token)
        print()

        print("4. Привязка ролей к клиенту сервиса (assign_roles_to_client)...")
        await assign_roles_to_service_client(client, token, role_ids)
        print()

        print("Готово. Роли и скоупы созданы/обновлены в SSO.")
    except Exception as e:
        print(f"Ошибка: {e}")
        raise
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
