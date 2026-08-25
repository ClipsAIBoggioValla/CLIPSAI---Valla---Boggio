"""Hash y verificacion de contrasenias usando bcrypt nativo.

Se evita passlib para prevenir el error ValueError: password cannot be longer
than 72 bytes que ocorre con passlib + bcrypt >= 4.0.0 (detect_wrap_bug).

Todas las contrasenas se trunca automaticamente a 72 bytes en UTF-8, que es
el limite maximo que bcrypt acepta de forma nativa.
"""

import bcrypt


def hash_password(plain_password: str) -> str:
    """Devuelve el hash bcrypt de la contrasenia en claro.

    La contrasenia se trunca a 72 bytes en UTF-8 antes de hashear, evitando
    el ValueError de bcrypt 4.x cuando la contrasenia es mas larga.
    """
    pwd_bytes = plain_password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """True si la contrasenia coincide con el hash almacenado.

    Igual que hash_password, trunca la entrada a 72 bytes para mantener
    compatibilidad con hashes generados tanto por esta versi.n como por vers
    previas con passlib.
    """
    pwd_bytes = plain_password.encode("utf-8")[:72]
    hash_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(pwd_bytes, hash_bytes)