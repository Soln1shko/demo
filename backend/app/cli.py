"""CLI: `python -m app.cli seed` | `python -m app.cli create-operator <id> <name> <password> [--admin]`."""

import asyncio
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import dispose_engine, session_factory
from app.models import User
from app.models.user import ROLE_ADMIN, ROLE_ANALYST
from app.services.seed import seed_all


async def _seed() -> None:
    async with session_factory()() as session:
        await seed_all(session)
    print("Сидинг выполнен: каталог, лента и тестовые аккаунты.")


async def _create_operator(operator_id: str, name: str, password: str, admin: bool) -> None:
    operator_id = operator_id.lower()
    async with session_factory()() as session:
        exists = (
            await session.execute(select(User).where(User.operator_id == operator_id))
        ).scalar_one_or_none()
        if exists:
            print(f"Оператор {operator_id} уже существует.")
            return
        session.add(
            User(
                email=f"{operator_id}@bank.local",
                name=name,
                password_hash=hash_password(password),
                role=ROLE_ADMIN if admin else ROLE_ANALYST,
                operator_id=operator_id,
            )  # fmt: skip
        )
        await session.commit()
    print(f"Оператор {operator_id} создан.")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        raise SystemExit(1)
    if args[0] == "seed":
        asyncio.run(_seed())
    elif args[0] == "create-operator" and len(args) >= 4:
        asyncio.run(_create_operator(args[1], args[2], args[3], "--admin" in args))
    else:
        print(__doc__)
        raise SystemExit(1)
    asyncio.run(dispose_engine())


if __name__ == "__main__":
    main()
