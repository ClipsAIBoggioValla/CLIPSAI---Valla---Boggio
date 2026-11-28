"""CLI de operador para conceder admin a cuentas ya registradas."""

from __future__ import annotations

import argparse

from .database import SessionLocal
from .services.admin_service import grant_admins


def main() -> None:
    parser = argparse.ArgumentParser(description="Concede privilegios admin a cuentas existentes.")
    parser.add_argument("emails", nargs="+", help="Email de una o más cuentas previamente registradas")
    args = parser.parse_args()
    if SessionLocal is None:
        parser.error("No hay base de datos configurada en este entorno.")
    db = SessionLocal()
    try:
        count = grant_admins(db, args.emails)
        print(f"Privilegios admin concedidos a {count} cuenta(s).")
    except ValueError as exc:
        db.rollback()
        parser.error(str(exc))
    finally:
        db.close()


if __name__ == "__main__":
    main()
