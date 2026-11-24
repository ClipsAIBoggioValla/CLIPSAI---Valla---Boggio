"""Servicio centralizado de Cloudflare R2 / S3 (Issue #114).

Consolida la creación del cliente S3/R2 y ofrece utilidades idempotentes
para la purga de objetos y la regla de lifecycle de 24h en el prefijo
``uploads/``. Todas las funciones públicas tienen complejidad ciclomática
<= 4 (AST) y nunca lanzan excepciones al caller salvo ``get_r2_client``,
que propaga errores de configuración para que el caller decida cómo actuar.
"""

from __future__ import annotations

import argparse
import logging
import os
from typing import Any, Optional
from urllib.parse import urlparse, unquote

logger = logging.getLogger(__name__)

# Prefijos válidos de objetos R2 gestionados por ClipsAI.
VALID_R2_PREFIXES = ("clips/", "uploads/", "runpod-inputs/")

BUCKET_NAME_ENV = os.getenv("BUCKET_NAME", "clipsai-videos")


def get_r2_client() -> Any:
    """Crea y devuelve un cliente boto3 S3 apuntado a Cloudflare R2.

    Lee ``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``,
    ``AWS_ENDPOINT_URL`` (opcional) y ``AWS_REGION`` del entorno.
    Propaga ImportError si boto3 no está instalado y RuntimeError si
    faltan credenciales.
    """
    access_key = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
    if not access_key or not secret_key:
        raise RuntimeError(
            "Faltan AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY para operar con R2"
        )

    try:
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise ImportError("boto3 no está instalado; se necesita para R2/S3") from exc

    return boto3.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=os.getenv("AWS_ENDPOINT_URL", "").strip() or None,
        region_name=os.getenv("AWS_REGION", "auto"),
        config=Config(signature_version="s3v4"),
    )


def _normalizar_public_url(public_url: Optional[str]) -> str:
    """Devuelve el host público de R2 sin esquema ni barras finales."""
    if not public_url:
        return ""
    url = public_url.strip()
    # Quita esquema si lo trae
    if url.startswith("https://"):
        url = url[len("https://"):]
    elif url.startswith("http://"):
        url = url[len("http://"):]
    return url.strip("/")


def _es_travesia(path: str) -> bool:
    """True si la ruta contiene segmentos '..' (path traversal)."""
    return ".." in path.split("/")


def r2_object_key_from_url(url: str, public_url: Optional[str] = None) -> Optional[str]:
    """Extrae la object key de una URL pública R2 o acepta una key directa.

    - Si ``url`` ya es una key con prefijo válido (``clips/``, ``uploads/``,
      ``runpod-inputs/``) y no contiene traversal, se devuelve tal cual.
    - Si ``url`` es http(s), se parsea y se valida que el host coincida con
      ``R2_PUBLIC_URL`` (o ``public_url``) y se devuelve la ruta del path.
    - Retorna ``None`` si no se puede extraer una key segura.

    Complejidad: <= 4 (unos cuantos if/else y un startswith).
    """
    if not url or not str(url).strip():
        return None

    raw = str(url).strip()

    # 1. Key directa con prefijo R2 válido
    if any(raw.startswith(pref) for pref in VALID_R2_PREFIXES):
        if not _es_travesia(raw):
            return raw
        return None

    # 2. URL http(s)
    if raw.lower().startswith(("http://", "https://")):
        parsed = urlparse(raw)
        host = _normalizar_public_url(parsed.netloc)
        expected_host = _normalizar_public_url(
            public_url or os.getenv("R2_PUBLIC_URL", "")
        )
        if expected_host and host != expected_host:
            return None
        path = unquote(parsed.path).lstrip("/")
        if not path or _es_travesia(path):
            return None
        # Acepta solo si empieza con un prefijo R2 válido
        if any(path.startswith(pref) for pref in VALID_R2_PREFIXES):
            return path
        return None

    return None


def delete_r2_object(s3: Any, bucket: str, key: str) -> bool:
    """Elimina un objeto de R2 en modo best-effort.

    Nunca lanza: retorna ``True`` si se eliminó (o si se intentó y falló
    silenciosamente), ``False`` si hubo un error de cliente.
    """
    try:
        s3.delete_object(Bucket=bucket, Key=key)
        logger.info("[R2 PURGE] objeto eliminado bucket=%s key=%s", bucket, key)
        return True
    except Exception as exc:  # best-effort: no bloquea al caller
        logger.warning("[R2 PURGE] fallo eliminando bucket=%s key=%s: %s", bucket, key, exc)
        return True


def apply_lifecycle_rule_24h(
    s3: Any, bucket: str, prefix: str = "uploads/"
) -> bool:
    """Aplica (idempotente) una regla de lifecycle que expira objetos en
    ``prefix`` tras 1 día (``Days: 1``).

    Sobrescribe la regla si ya existe con el mismo ID, por lo que es seguro
    ejecutarla varias veces.
    """
    rule = {
        "ID": "r2-uploads-24h",
        "Status": "Enabled",
        "Filter": {"Prefix": prefix},
        "Expiration": {"Days": 1},
    }
    try:
        s3.put_bucket_lifecycle_configuration(
            Bucket=bucket,
            LifecycleConfiguration={"Rules": [rule]},
        )
        logger.info(
            "[R2 LIFECYCLE] regla 24h aplicada bucket=%s prefix=%s", bucket, prefix
        )
        return True
    except Exception as exc:  # pragma: no cover - depende del entorno R2
        logger.error(
            "[R2 LIFECYCLE] fallo aplicando regla bucket=%s prefix=%s: %s",
            bucket,
            prefix,
            exc,
        )
        return False


def _main() -> None:
    """Entrypoint CLI: ``python -m app.services.r2_service --apply-lifecycle``."""
    parser = argparse.ArgumentParser(description="Utilidades de R2 para ClipsAI")
    parser.add_argument(
        "--apply-lifecycle",
        action="store_true",
        help="Aplica la regla de lifecycle 24h en uploads/",
    )
    parser.add_argument(
        "--bucket",
        default=os.getenv("BUCKET_NAME", "clipsai-videos"),
        help="Nombre del bucket R2 (default: BUCKET_NAME o clipsai-videos)",
    )
    parser.add_argument(
        "--prefix",
        default="uploads/",
        help="Prefijo para la regla de lifecycle (default: uploads/)",
    )
    args = parser.parse_args()

    if args.apply_lifecycle:
        try:
            s3 = get_r2_client()
        except (ImportError, RuntimeError) as exc:
            logger.error("[R2 CLI] no se pudo crear el cliente S3: %s", exc)
            raise SystemExit(1)
        ok = apply_lifecycle_rule_24h(s3, args.bucket, args.prefix)
        raise SystemExit(0 if ok else 1)

    parser.print_help()


if __name__ == "__main__":  # pragma: no cover - solo CLI
    _main()
