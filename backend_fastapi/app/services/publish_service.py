from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from fastapi import HTTPException
from sqlalchemy import func

from ..config import get_settings
from ..database import SessionLocal
from ..models import Clip
from ..models.social_account import SocialAccount
from .media_signing import signed_query
from .token_crypto import cifrar_token, descifrar_token


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip()
    return ""


logger = logging.getLogger(__name__)

# Auditoría de credenciales al arrancar: advierte si faltan claves de app
# Verifica settings.TIKTOK_CLIENT_KEY, settings.TIKTOK_CLIENT_SECRET, settings.FACEBOOK_CLIENT_ID, settings.FACEBOOK_CLIENT_SECRET
try:
    _settings = get_settings()
    if not _settings.tiktok_client_key.strip() or not _settings.tiktok_client_secret.strip() or not _settings.facebook_client_id.strip() or not _settings.facebook_client_secret.strip():
        logger.warning("[SETTINGS] Alguna de TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, FACEBOOK_CLIENT_ID, FACEBOOK_CLIENT_SECRET está vacía en settings - verifica .env (settings.TIKTOK_CLIENT_KEY, settings.TIKTOK_CLIENT_SECRET, settings.FACEBOOK_CLIENT_ID, settings.FACEBOOK_CLIENT_SECRET)")
except Exception:
    pass


PLATFORM_URLS = {
    "tiktok": "https://www.tiktok.com/@clipsai/video/",
    "instagram": "https://www.instagram.com/reel/",
    "youtube": "https://www.youtube.com/shorts/",
    "webhook": "https://webhook.clipsai.local/publish/",
}


def _generate_fake_id() -> str:
    return uuid.uuid4().hex[:12]


def _limpiar_dominio_url(url: str) -> str:
    """Quita el esquema y las barras de una URL para dejar solo el dominio."""
    return url.replace("https://", "").replace("http://", "").strip().strip("/")


def _dominio_desde_public_url() -> str:
    """Dominio desde PUBLIC_BACKEND_URL (permanente Cloudflare); vacío si no sirve."""
    public_url = os.getenv("PUBLIC_BACKEND_URL", "").strip()
    if public_url:
        domain = _limpiar_dominio_url(public_url)
        if domain:
            return domain
    return ""


def _es_dominio_deseado(domain: str) -> bool:
    """True si el dominio no parece un túnel temporal (decorator/guns-camps/ngrok)."""
    return not any(tok in domain for tok in ("decorator", "guns-camps", "ngrok"))


def _dominio_desde_backend_url() -> str:
    """Dominio desde BACKEND_URL/API_BASE_URL/PUBLIC_BACKEND_URL si no es un túnel temporal."""
    backend = _first_env("BACKEND_URL", "API_BASE_URL", "PUBLIC_BACKEND_URL")
    if not backend:
        return ""
    domain = _limpiar_dominio_url(backend)
    if domain and _es_dominio_deseado(domain):
        return domain
    return ""


def _dominio_desde_ngrok_env() -> str:
    """Dominio desde NGROK_DOMAIN, filtrando túneles con 'decorator'."""
    domain = os.getenv("NGROK_DOMAIN", "").strip()
    if domain and "decorator" not in domain:
        return _limpiar_dominio_url(domain)
    return ""


def _get_ngrok_domain() -> str:
    # Prioriza PUBLIC_BACKEND_URL (permanente Cloudflare) como base para URLs públicas
    domain = _dominio_desde_public_url()
    if domain:
        return domain
    domain = _dominio_desde_backend_url()
    if domain:
        return domain
    # Fallback permanente
    return _dominio_desde_ngrok_env() or "api.clipsai.xyz"


def _get_public_video_url(clip: Clip) -> str:
    domain = _get_ngrok_domain()
    clip_id = str(clip.id)
    file_part = ""
    if clip.storage_path and clip.storage_path.strip():
        fname = os.path.basename(clip.storage_path.strip())
        if fname:
            file_part = f"/{fname}"
    public_url = f"https://{domain}/clips/{clip_id}/descarga?{signed_query(clip_id)}"
    alt_url = f"https://{domain}/storage/clips/{clip_id}.mp4"
    # Prefer alt_url para APIs pull si el dominio lo soporta; descarga como fallback
    # Ambas son HTTPS públicas vía PUBLIC_BACKEND_URL (https://api.clipsai.xyz)
    return public_url


def _normalizar_uid(user_id: str | uuid.UUID) -> Any:
    """Devuelve el user_id como UUID si es convertible; si no, como string."""
    uid = str(user_id)
    try:
        return uuid.UUID(uid)
    except Exception:
        return uid


def _cuenta_desde_fila_sql(row, uid_uuid) -> SocialAccount:
    """Construye un SocialAccount transitorio a partir de una fila SQL cruda."""
    return SocialAccount(
        user_id=uid_uuid,  # type: ignore
        platform=row["platform"],
        platform_account_id=row["platform_account_id"],
        platform_username=row["platform_account_id"],
        access_token=row["access_token"],
        refresh_token=row["refresh_token"] or row["access_token"],
    )


def _buscar_cuenta_orm(db, uid_uuid, platform_norm: str) -> SocialAccount | None:
    """Búsqueda de la cuenta por ORM (select) con fallback a db.query; None si falla."""
    from sqlalchemy import select

    account: SocialAccount | None = None
    try:
        account = db.execute(
            select(SocialAccount).where(
                SocialAccount.user_id == uid_uuid,
                func.lower(SocialAccount.platform) == platform_norm,
            )
        ).scalar_one_or_none()
    except Exception:
        account = None

    if account is None:
        try:
            account = (
                db.query(SocialAccount)
                .filter(SocialAccount.user_id == uid_uuid, func.lower(SocialAccount.platform) == platform_norm)
                .first()
            )
        except Exception:
            account = None
    return account


def _buscar_cuenta_sql_crudo(db, uid_uuid, platform_norm: str) -> SocialAccount | None:

    """Búsqueda por SQL crudo en la tabla legacy user_social_accounts; None si falla."""
    try:
        from sqlalchemy import text

        row = db.execute(
            text(
                "SELECT id, user_id, platform, platform_account_id, access_token, refresh_token "
                "FROM user_social_accounts WHERE user_id = :uid AND lower(platform) = :plat LIMIT 1"
            ),
            {"uid": str(uid_uuid), "plat": platform_norm},
        ).mappings().first()
        if row:
            # create transient SocialAccount-like object
            return _cuenta_desde_fila_sql(row, uid_uuid)
    except Exception:
        pass
    return None


def _get_social_account(db, user_id: str | uuid.UUID, platform: str) -> SocialAccount:
    platform_norm = platform.lower().strip()
    uid_uuid = _normalizar_uid(user_id)

    # Try ORM query on social_accounts (and fallback to user_social_accounts table name)
    account = _buscar_cuenta_orm(db, uid_uuid, platform_norm) or _buscar_cuenta_sql_crudo(db, uid_uuid, platform_norm)

    if account is None or not getattr(account, "access_token", None):
        raise HTTPException(status_code=400, detail=f"Cuenta de {platform} no vinculada")

    return account


def _handle_token_expired(platform: str, resp: requests.Response):
    if resp.status_code == 401:
        raise HTTPException(
            status_code=400,
            detail=f"Token de {platform} expirado, debes reconectar la cuenta",
        )


def _credencial_de_settings(valor: str | None, env_name: str) -> str:
    """Valor de credencial: settings primero, variable de entorno como respaldo."""
    return (valor or "").strip() or os.getenv(env_name, "").strip()


def _credenciales_tiktok() -> tuple[str, str]:
    """(client_key, client_secret) de TikTok desde settings con respaldo en entorno."""
    _s = get_settings()
    client_key = _credencial_de_settings(_s.tiktok_client_key, "TIKTOK_CLIENT_KEY")
    client_secret = _credencial_de_settings(_s.tiktok_client_secret, "TIKTOK_CLIENT_SECRET")
    return client_key, client_secret


def _refresh_tiktok(account: SocialAccount, refresh_token: str, db) -> bool:
    """Refresh del token de TikTok vía OAuth. True si se renovó."""
    # Fuente de credenciales: settings.TIKTOK_CLIENT_KEY y settings.TIKTOK_CLIENT_SECRET (única fuente, sin fallback hardcodeado)
    client_key, client_secret = _credenciales_tiktok()
    # Verificación explícita de settings.TIKTOK_CLIENT_KEY / settings.TIKTOK_CLIENT_SECRET
    if not client_key or not client_secret:
        logger.warning("[TIKTOK REFRESH] TIKTOK_CLIENT_KEY/SECRET no configurados en settings.TIKTOK_CLIENT_KEY / settings.TIKTOK_CLIENT_SECRET")
        return False
    resp = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=15,
    )
    logger.info("[TIKTOK REFRESH] status=%s", resp.status_code)
    logger.error("[DIAGNOSTICO TIKTOK] refresh status=%s", resp.status_code)
    _validar_refresh_tiktok(resp)
    return _aplicar_refresh_tiktok(account, resp, refresh_token, db)


def _json_de_respuesta(resp) -> dict:
    """JSON del body de la respuesta, o {} si no es JSON válido."""
    try:
        return resp.json()
    except Exception:
        return {}


def _error_json_refresh_tiktok(data: dict) -> bool:
    """True si el JSON del refresh TikTok trae error o un error_code != 0."""
    return bool(data.get("error")) or data.get("error_code") not in (None, 0, "0")


def _error_data_anidada_tiktok(data: dict) -> bool:
    """True si data['data'] es dict con un error_code != 0."""
    if isinstance(data.get("data"), dict):
        return data["data"].get("error_code") not in (None, 0, "0")
    return False


def _fallar_refresh_tiktok(resp: requests.Response, mensaje: str) -> None:
    """Loguea el error de refresh TikTok y lanza la excepción de auditoría."""
    logger.error("[publish] Error renovando token TikTok status=%s", resp.status_code)
    raise Exception(mensaje)


def _validar_refresh_tiktok(resp: requests.Response) -> None:
    """Si la respuesta HTTP o el JSON indican error, lanza con el body exacto para auditoría."""
    # Si la respuesta HTTP no es exitosa (status != 200 o JSON contiene error / error_code != 0)
    if resp.status_code != 200:
        _fallar_refresh_tiktok(resp, f"TikTok refresh failed status={resp.status_code} body={resp.text}")
    data = _json_de_respuesta(resp)
    # Detecta error en JSON aunque status 200
    if _error_json_refresh_tiktok(data) or _error_data_anidada_tiktok(data):
        _fallar_refresh_tiktok(resp, f"TikTok refresh error body={resp.text}")


def _tokens_renovados_tiktok(data: dict, inner: dict) -> tuple[str | None, str | None]:
    """(access_token, refresh_token) del body del refresh TikTok (raíz o anidado)."""
    return (
        data.get("access_token") or inner.get("access_token"),
        data.get("refresh_token") or inner.get("refresh_token"),
    )


def _aplicar_expiry_tiktok(account: SocialAccount, data: dict, inner: dict) -> None:
    """Actualiza token_expires_at con expires_in del body (silencioso si es inválido)."""
    expires_in = data.get("expires_in") or inner.get("expires_in")
    if expires_in:
        try:
            account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        except Exception:
            pass


def _aplicar_refresh_tiktok(account: SocialAccount, resp: requests.Response, refresh_token: str, db) -> bool:
    """Escribe el token renovado en la cuenta. Exception si no vino access_token."""
    data = _json_de_respuesta(resp)
    inner = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
    new_access_token, new_refresh_token = _tokens_renovados_tiktok(data, inner)
    if not new_access_token:
        logger.error("[publish] Error renovando token TikTok status=%s", resp.status_code)
        raise Exception(f"TikTok refresh failed - no access_token in body={resp.text}")
    account.access_token = cifrar_token(new_access_token)
    if not new_refresh_token:
        new_refresh_token = refresh_token
    account.refresh_token = cifrar_token(new_refresh_token)
    _aplicar_expiry_tiktok(account, data, inner)
    account.updated_at = datetime.now(timezone.utc)
    db.add(account)
    db.commit()
    db.refresh(account)
    logger.info(f"[TIKTOK TOKEN REFRESHED] user={account.user_id}")
    return True


def _refresh_youtube(account: SocialAccount, refresh_token: str, db) -> bool:
    """Refresh del token de Google/YouTube. True si se renovó."""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        logger.warning("[YOUTUBE REFRESH] GOOGLE_CLIENT_ID/SECRET no configurados")
        return False
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=15,
    )
    logger.info("[YOUTUBE REFRESH] status=%s", resp.status_code)
    if resp.status_code != 200:
        logger.warning("[YOUTUBE REFRESH FAILED] status=%s", resp.status_code)
        return False
    return _aplicar_refresh_youtube(account, resp, db)


def _aplicar_expiry_simple(account: SocialAccount, data: dict) -> None:
    """token_expires_at desde expires_in del body (silencioso si es inválido o no viene)."""
    if not data.get("expires_in"):
        return
    try:
        account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(data["expires_in"]))
    except Exception:
        pass


def _aplicar_refresh_youtube(account: SocialAccount, resp: requests.Response, db) -> bool:
    data = _json_de_respuesta(resp)
    new_access_token = data.get("access_token")
    new_refresh_token = data.get("refresh_token")
    if not new_access_token:
        return False
    account.access_token = cifrar_token(new_access_token)
    if new_refresh_token:
        account.refresh_token = cifrar_token(new_refresh_token)  # si aplica
    _aplicar_expiry_simple(account, data)
    account.updated_at = datetime.now(timezone.utc)
    db.add(account)
    db.commit()
    db.refresh(account)
    logger.info(f"[YOUTUBE TOKEN REFRESHED] user={account.user_id}")
    return True


def _credencial_social(valor: str | None, *env_names: str) -> str:
    """Credencial desde settings o, en su defecto, de las variables de entorno."""
    return (valor or "").strip() or _first_env(*env_names)


def _credenciales_meta() -> tuple[str, str]:
    """(client_id, client_secret) de Facebook/Instagram desde settings o entorno."""
    _s2 = get_settings()
    # Usa settings.FACEBOOK_CLIENT_ID / settings.FACEBOOK_CLIENT_SECRET como fuente primaria
    client_id = _credencial_social(_s2.facebook_client_id, "FACEBOOK_CLIENT_ID") or _credencial_social(
        _s2.instagram_client_id, "INSTAGRAM_CLIENT_ID"
    )
    client_secret = _credencial_social(_s2.facebook_client_secret, "FACEBOOK_CLIENT_SECRET") or _credencial_social(
        _s2.instagram_client_secret, "INSTAGRAM_CLIENT_SECRET"
    )
    return client_id, client_secret


def _refresh_instagram(account: SocialAccount, refresh_token: str, db) -> bool:
    """Refresh del token largo de Meta/Instagram vía fb_exchange_token."""
    # Fuente de credenciales: settings.FACEBOOK_CLIENT_ID y settings.FACEBOOK_CLIENT_SECRET (única fuente, sin fallback hardcodeado)
    client_id, client_secret = _credenciales_meta()
    if not client_id or not client_secret:
        logger.warning("[INSTAGRAM REFRESH] FACEBOOK_CLIENT_ID/SECRET no configurados en settings.FACEBOOK_CLIENT_ID / settings.FACEBOOK_CLIENT_SECRET")
        return False
    # Meta long-lived token refresh via fb_exchange_token
    resp = requests.get(
        "https://graph.facebook.com/v18.0/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "fb_exchange_token": refresh_token,
        },
        timeout=15,
    )
    logger.info("[INSTAGRAM REFRESH] status=%s", resp.status_code)
    if resp.status_code != 200:
        logger.warning("[INSTAGRAM REFRESH FAILED] status=%s", resp.status_code)
        return False
    return _aplicar_refresh_instagram(account, resp, refresh_token, db)


def _aplicar_expiry_instagram(account: SocialAccount, data: dict) -> None:
    """token_expires_at: expires_in del body o 60 días por defecto."""
    if data.get("expires_in"):
        try:
            account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(data["expires_in"]))
        except Exception:
            pass
    else:
        account.token_expires_at = datetime.now(timezone.utc) + timedelta(days=60)


def _aplicar_refresh_instagram(account: SocialAccount, resp: requests.Response, refresh_token: str, db) -> bool:
    data = _json_de_respuesta(resp)
    new_access_token = data.get("access_token")
    new_refresh_token = data.get("refresh_token") or refresh_token
    if not new_access_token:
        return False
    account.access_token = cifrar_token(new_access_token)
    account.refresh_token = cifrar_token(new_refresh_token)  # si aplica (o fallback)
    _aplicar_expiry_instagram(account, data)
    account.updated_at = datetime.now(timezone.utc)
    db.add(account)
    db.commit()
    db.refresh(account)
    logger.info(f"[INSTAGRAM TOKEN REFRESHED] user={account.user_id}")
    return True


def _refresh_por_plataforma(account: SocialAccount, platform_norm: str, refresh_token: str, db) -> bool:
    """Despacha el refresh del token al handler específico de la plataforma."""
    if platform_norm == "tiktok":
        return _refresh_tiktok(account, refresh_token, db)

    if platform_norm == "youtube":
        return _refresh_youtube(account, refresh_token, db)

    if platform_norm == "instagram":
        return _refresh_instagram(account, refresh_token, db)

    return False


def _es_error_refresh_tiktok(exc: Exception) -> bool:
    """True si el error corresponde al refresh de TikTok (auditoría)."""
    texto = str(exc)
    return "TikTok refresh" in texto or "Error renovando token TikTok" in texto


def _rollback_silencioso(db) -> None:
    """Rollback de la sesión ignorando fallos."""
    try:
        db.rollback()
    except Exception:
        pass


def _registrar_error_refresh(db, platform_norm: str, exc: Exception) -> None:
    """Para TikTok propaga el error con body exacto; para el resto loguea y hace rollback."""
    # Para TikTok, propaga el error con body exacto para auditoría
    if platform_norm == "tiktok" and _es_error_refresh_tiktok(exc):
        logger.error("[publish] Error renovando token TikTok tipo=%s", type(exc).__name__)
        raise
    logger.error(f"[{platform_norm} REFRESH EXCEPTION] {exc}", exc_info=True)
    _rollback_silencioso(db)


def _refresh_account_token(account: SocialAccount, platform: str, db) -> bool:
    platform_norm = platform.lower().strip()
    try:
        refresh_token = descifrar_token((getattr(account, "refresh_token", None) or "").strip())
        if not refresh_token:
            logger.warning(f"[{platform_norm} REFRESH] no refresh_token para user {account.user_id}")
            return False

        return _refresh_por_plataforma(account, platform_norm, refresh_token, db)
    except Exception as e:
        _registrar_error_refresh(db, platform_norm, e)
        return False


_MARCAS_TOKEN_EXPIRADO = ("expirado", "expired", "401", "unauthorized", "invalid_token", "token de")


def _is_token_expired_error(exc: Exception) -> bool:
    """True si el detalle del error indica token expirado/inválido."""
    msg = str(getattr(exc, "detail", str(exc))).lower()
    return any(marca in msg for marca in _MARCAS_TOKEN_EXPIRADO)


def _expires_at_aware(expires_at) -> Any:
    """Datetime con timezone UTC si venía naive."""
    if expires_at.tzinfo is None:
        return expires_at.replace(tzinfo=timezone.utc)
    return expires_at


def _token_por_vencer(expires_at) -> bool:
    """True si el token expira en menos de 5 minutos."""
    return expires_at <= datetime.now(timezone.utc) + timedelta(minutes=5)


def _refrescar_sesion_silencioso(db, account) -> None:
    """db.refresh(account) silencioso (ignora fallos de sesión)."""
    try:
        db.refresh(account)
    except Exception:
        pass


def _refrescar_token_proximo_a_vencer(account: SocialAccount, platform: str, db, expires_at) -> None:
    """Refresca preventivamente si el token vence pronto (silencioso ante errores)."""
    try:
        # Si expira en menos de 5 minutos, refresca preventivamente
        if _token_por_vencer(_expires_at_aware(expires_at)):
            logger.info(f"[AUTO-REFRESH PRE-CALL] token próximo a expirar para {platform}, refrescando")
            _refresh_account_token(account, platform, db)
            _refrescar_sesion_silencioso(db, account)
    except Exception as exc:
        logger.warning(
            "[AUTO-REFRESH PRE-CALL] fallo refrescando token %s: %s",
            platform, exc,
        )
        _desconectar_cuenta_oauth(db, account, platform)


def _ensure_token_fresh(account: SocialAccount, platform: str, db) -> None:
    """Auto-refresh transparente si el token vence pronto (silencioso ante fallos)."""
    try:
        expires_at = getattr(account, "token_expires_at", None)
        if expires_at is not None:
            _refrescar_token_proximo_a_vencer(account, platform, db, expires_at)
    except Exception:
        pass


def _candidatos_archivo_youtube(clip: Clip) -> list[str]:
    """Candidatos de ruta del MP4 físico para YouTube."""
    alt_candidates: list[str] = []
    if clip.storage_path:
        alt_candidates.append(clip.storage_path)
    return alt_candidates


def _primer_candidato_existente(candidatos: list[str]) -> str | None:
    """Primer candidato que exista como archivo en disco."""
    for cand in candidatos:
        if cand and os.path.isfile(cand):
            return cand
    return None


def _resolver_archivo_youtube(clip: Clip) -> str | None:
    """Ruta del MP4 físico para YouTube (storage_path directo o candidatos)."""
    file_path = (clip.storage_path or "").strip()
    if file_path and os.path.isfile(file_path):
        return file_path
    # Try to locate via storage pattern or use dummy
    return _primer_candidato_existente(_candidatos_archivo_youtube(clip))


def _body_multipart_youtube(boundary: str, metadata: dict, video_file: str) -> bytes:
    """Construcción multipart/related con dos partes:
    Parte 1 (application/json; charset=UTF-8): metadata snippet/status
    Parte 2 (video/mp4): bytes del archivo MP4."""
    metadata_json = json.dumps(metadata)
    with open(video_file, "rb") as f:
        video_bytes = f.read()
    part1 = f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{metadata_json}\r\n"
    part2_header = f"--{boundary}\r\nContent-Type: video/mp4\r\n\r\n"
    closing = f"\r\n--{boundary}--\r\n"
    return part1.encode("utf-8") + part2_header.encode("utf-8") + video_bytes + closing.encode("utf-8")


def _exigir_archivo_youtube(video_file: str) -> None:
    """HTTPException 404 si el MP4 físico del clip no existe."""
    if not video_file or not os.path.isfile(video_file):
        raise HTTPException(status_code=404, detail=f"Archivo de clip no encontrado para YouTube: {video_file}. El clip debe existir como .mp4 físico en /app/storage/clips/")


def _publicar_upload_youtube(account: SocialAccount, video_file: str, title: str, description: str) -> requests.Response:
    """POST multipart al endpoint de upload de YouTube Data API v3."""
    url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=multipart&part=snippet,status"
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    token = descifrar_token(account.access_token)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/related; boundary={boundary}",
    }
    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    # Modo 100% real — sin fallback de prueba. Requiere archivo físico en storage_path.
    _exigir_archivo_youtube(video_file)
    try:
        body = _body_multipart_youtube(boundary, metadata, video_file)
        return requests.post(url, headers=headers, data=body, timeout=60)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error leyendo archivo de video: {e}")


def _video_id_de_data(data: dict) -> Any:
    """video_id de la respuesta (id, videoId o id temporal generado)."""
    return data.get("id") or data.get("videoId") or _generate_fake_id()


def _permalink_youtube(data: dict) -> tuple[str, str]:
    """(post_id, permalink) desde la respuesta del upload."""
    video_id = _video_id_de_data(data)
    permalink = f"https://www.youtube.com/shorts/{video_id}"
    if data.get("id"):
        permalink = f"https://www.youtube.com/watch?v={video_id}"
    return str(video_id), permalink


def _detalle_error_api(resp: requests.Response) -> Any:
    """Detail de error de una API: JSON si es posible, texto truncado si no."""
    try:
        return resp.json()
    except Exception:
        return resp.text[:1000]


def _texto_o_fallback(caption: str | None, clip: Clip, fallback: str) -> str:
    """Caption, o título del clip, o texto por defecto."""
    return caption or clip.title or fallback


def _titulos_youtube(caption: str | None, clip: Clip) -> tuple[str, str]:
    """(title, description) truncados para el upload de YouTube."""
    return (
        _texto_o_fallback(caption, clip, "ClipsAI Short")[:100],
        _texto_o_fallback(caption, clip, "Generado con ClipsAI")[:5000],
    )


def _validar_respuesta_youtube(resp: requests.Response) -> None:
    """HTTPException si la API de YouTube devolvió 401 u otro error >= 400."""
    if resp.status_code == 401:
        _handle_token_expired("youtube", resp)
    if resp.status_code >= 400:
        detail = _detalle_error_api(resp)
        raise HTTPException(status_code=400, detail=f"YouTube API error {resp.status_code}: {detail}")


def _publish_youtube(account: SocialAccount, clip: Clip, caption: str | None) -> dict[str, Any]:
    title, description = _titulos_youtube(caption, clip)

    video_file = _resolver_archivo_youtube(clip)
    resp = _publicar_upload_youtube(account, video_file, title, description)

    _validar_respuesta_youtube(resp)

    data = _json_de_respuesta(resp)

    post_id, permalink = _permalink_youtube(data)
    return {"status": "published", "platform": "youtube", "post_id": post_id, "url": permalink}


def _primer_ig_id_de_paginas(paginas: list, access_token: str) -> str:
    """Primer instagram_business_account.id presente en la lista de páginas."""
    logger_ig = logging.getLogger("uvicorn")
    for page in paginas:
        ig_acc = page.get("instagram_business_account", {})
        if ig_acc.get("id"):
            logger_ig.info(f"SUCCESS [CAPA 1]: Encontrado IG ID {ig_acc['id']} en página '{page.get('name')}'")
            return ig_acc["id"]
    return ""


def _ig_desde_me_accounts(access_token: str) -> str:
    """CAPA 1: búsqueda estándar del IG id vía /me/accounts. Vacío si no aparece."""
    logger_ig = logging.getLogger("uvicorn")
    try:
        url_acc = f"https://graph.facebook.com/v20.0/me/accounts?fields=instagram_business_account,name&access_token={access_token}"
        res_acc = requests.get(url_acc, timeout=10).json()
        logger_ig.info(f"[CAPA 1 - me/accounts] Response: {res_acc}")

        ig_id = _primer_ig_id_de_paginas(res_acc.get("data", []), access_token)
        if ig_id:
            return ig_id
    except Exception as e:
        logger_ig.error(f"[CAPA 1 - ERROR]: {e}")
    return ""


def _app_creds_meta_debug() -> tuple[str, str]:
    """(app_id, app_secret) de Meta desde el entorno para debug_token."""
    return (
        os.getenv("FACEBOOK_APP_ID") or os.getenv("META_APP_ID"),
        os.getenv("FACEBOOK_APP_SECRET") or os.getenv("META_APP_SECRET"),
    )


def _url_debug_token(access_token: str) -> str:
    """URL de debug_token si hay app creds de Meta en el entorno; vacía si no."""
    app_id, app_secret = _app_creds_meta_debug()
    if not app_id or not app_secret:
        return ""
    return f"https://graph.facebook.com/v20.0/debug_token?input_token={access_token}&access_token={app_id}|{app_secret}"


def _ig_desde_targets_granulares(scope: dict, access_token: str) -> str:
    """Busca el IG id en los target_ids del scope pages_show_list."""
    logger_ig = logging.getLogger("uvicorn")
    for target_id in scope.get("target_ids", []):
        page_url = f"https://graph.facebook.com/v20.0/{target_id}?fields=instagram_business_account,name&access_token={access_token}"
        page_res = requests.get(page_url, timeout=10).json()
        logger_ig.info(f"[CAPA 2 - Target Page {target_id}] Response: {page_res}")
        ig_acc = page_res.get("instagram_business_account", {})
        if ig_acc.get("id"):
            logger_ig.info(f"SUCCESS [CAPA 2]: Encontrado IG ID {ig_acc['id']} desde granular target {target_id}")
            return ig_acc["id"]
    return ""


def _ig_desde_scopes_debug(granular_scopes: list, access_token: str) -> str:
    """Primer scope pages_show_list con un IG id en sus target_ids."""
    for scope in granular_scopes:
        if scope.get("scope") == "pages_show_list":
            ig_id = _ig_desde_targets_granulares(scope, access_token)
            if ig_id:
                return ig_id
    return ""


def _ig_desde_debug_token(access_token: str) -> str:
    """CAPA 2: inspección del token de depuración (granular scopes). Vacío si no aparece."""
    logger_ig = logging.getLogger("uvicorn")
    try:
        debug_url = _url_debug_token(access_token)
        if debug_url:
            debug_res = requests.get(debug_url, timeout=10).json()
            logger_ig.info(f"[CAPA 2 - debug_token] Response: {debug_res}")

            granular_scopes = debug_res.get("data", {}).get("granular_scopes", [])
            return _ig_desde_scopes_debug(granular_scopes, access_token)
    except Exception as e:
        logger_ig.error(f"[CAPA 2 - ERROR]: {e}")
    return ""


def _resolve_instagram_business_id(account):
    logger_ig = logging.getLogger("uvicorn")
    access_token = descifrar_token(account.access_token)

    logger_ig.info("=== [IG RESOLUTION STARTED] ===")
    logger_ig.info(f"Token Prefix: {access_token[:12]}...")

    # CAPA 1: Búsqueda estándar vía /me/accounts
    # CAPA 2: Inspección del token de depuración (Granular Scopes / Target IDs)
    ig_id = _ig_desde_me_accounts(access_token) or _ig_desde_debug_token(access_token)
    if ig_id:
        return ig_id

    # Si no se encontró cuenta dinámica, lanzar excepción clara (sin hardcodes)
    raise HTTPException(status_code=400, detail="No se encontró una cuenta de Instagram Business vinculada a las páginas de Facebook del usuario")


def _forzar_https(url: str) -> str:
    """Validación de URL pública en HTTPS - fuerza https:// si viene con http://."""
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    if not url.startswith("https://"):
        url = "https://" + url.lstrip("http://").lstrip("https://")
    # Asegurar reemplazo global por si la base URL contenía http://
    return url.replace("http://", "https://")


def _prevalidar_url_con_httpx(public_mp4_url: str) -> None:
    """Chequeo de la URL pública con httpx. HTTPException si no responde 200."""
    import httpx

    try:
        resp_check = httpx.get(public_mp4_url, timeout=5, follow_redirects=True)
        if resp_check.status_code != 200:
            msg = f"[IG PUBLISH ALERT] La URL pública no responde: {public_mp4_url} - Status: {resp_check.status_code}"
            logger.error(msg)
            raise HTTPException(status_code=400, detail=f"URL pública no accesible ({resp_check.status_code}): el túnel Cloudflare está caído o la URL venció - {public_mp4_url}")
    except HTTPException:
        raise
    except Exception as e:
        msg = f"[IG PUBLISH ALERT] La URL pública no responde: {public_mp4_url} - Error: {e}"
        logger.error(msg)
        raise HTTPException(status_code=400, detail=f"URL pública no accesible: el túnel Cloudflare está caído o la URL venció - {public_mp4_url} ({e})")


def _prevalidar_url_con_requests(public_mp4_url: str) -> None:
    """Fallback del chequeo de URL pública con requests (httpx no instalado)."""
    try:
        r = requests.get(public_mp4_url, timeout=5)
        if r.status_code != 200:
            msg = f"[IG PUBLISH ALERT] La URL pública no responde: {public_mp4_url} - Status: {r.status_code}"
            logger.error(msg)
            raise HTTPException(status_code=400, detail=f"URL pública no accesible ({r.status_code}): el túnel Cloudflare está caído o la URL venció - {public_mp4_url}")
    except HTTPException:
        raise
    except Exception as e:
        msg = f"[IG PUBLISH ALERT] La URL pública no responde: {public_mp4_url} - Error: {e}"
        logger.error(msg)
        raise HTTPException(status_code=400, detail=f"URL pública no accesible: el túnel Cloudflare está caído o la URL venció - {public_mp4_url} ({e})")


def _prevalidar_url_publica(public_mp4_url: str) -> None:
    """Pre-validación de la URL pública antes de llamar a Meta (httpx, fallback requests)."""
    try:
        _prevalidar_url_con_httpx(public_mp4_url)
    except ImportError:
        # Fallback a requests si httpx no está instalado
        _prevalidar_url_con_requests(public_mp4_url)


def _crear_container_ig(access_token: str, ig_user_id: str, public_mp4_url: str, caption_text: str) -> str:
    """Paso 1 (Crear Container): POST https://graph.facebook.com/v18.0/{ig_user_id}/media."""
    url1 = f"https://graph.facebook.com/v18.0/{ig_user_id}/media"
    params1 = {
        "media_type": "REELS",
        "video_url": public_mp4_url,
        "caption": caption_text,
        "access_token": access_token,
    }
    resp1 = requests.post(url1, data=params1, timeout=30)
    if resp1.status_code == 401:
        _handle_token_expired("instagram", resp1)
    if resp1.status_code >= 400:
        detail = _detalle_error_api(resp1)
        raise HTTPException(status_code=400, detail=f"Instagram API error (crear container) {resp1.status_code}: {detail}")

    data1 = _json_de_respuesta(resp1)
    creation_id = data1.get("id")
    if not creation_id:
        raise HTTPException(status_code=400, detail=f"Instagram API no devolvió creation_id: {data1}")
    return creation_id


def _detalle_error_container_ig(access_token: str, creation_id: str) -> None:
    """Captura detallada de errores de Meta: pide ÚNICAMENTE status_code,status (sin error_message para evitar OAuthException #100)."""
    try:
        err_url = f"https://graph.facebook.com/v20.0/{creation_id}?fields=status_code,status&access_token={access_token}"
        err_resp = requests.get(err_url, timeout=10)
        try:
            err_data = err_resp.json()
            err_msg = err_data.get("status") or err_data
            logger.error("[IG ERROR DETAIL] container %s status_code=ERROR status=%s", creation_id, err_msg)
        except Exception:
            logger.error("[IG ERROR DETAIL] container %s status=%s", creation_id, err_resp.status_code)
    except Exception as e_err:
        logger.error(f"[IG ERROR DETAIL] fallo al obtener status para {creation_id}: {e_err}")


def _logear_estado_container(creation_id: str, attempt: int, sc) -> None:
    """Log del estado del container durante el polling (IN_PROGRESS o desconocido)."""
    if sc == "IN_PROGRESS":
        logger.info(f"[IG POLLING] container {creation_id} IN_PROGRESS intento {attempt+1}/60 - esperando 5s")
    else:
        logger.info(f"[IG POLLING] container {creation_id} estado desconocido {sc} intento {attempt+1}/60")


def _estado_json_container(st_resp, access_token: str, creation_id: str, attempt: int) -> str | None:
    """Estado del container según status_code: 'FINISHED', excepción en ERROR, None si sigue esperando."""
    st_data = st_resp.json()
    sc = st_data.get("status_code")
    logger.info(f"[IG POLLING] Intento {attempt+1}/60 para contenedor {creation_id}: status_code={sc}")
    if sc == "FINISHED":
        logger.info(f"[IG POLLING] container {creation_id} FINISHED en intento {attempt+1}/60")
        return "FINISHED"
    if sc == "ERROR":
        _detalle_error_container_ig(access_token, creation_id)
        raise HTTPException(status_code=400, detail=f"Instagram container error: {st_data} - procesamiento falló")
    _logear_estado_container(creation_id, attempt, sc)
    return None


def _consultar_estado_container(access_token: str, creation_id: str, attempt: int) -> str | None:
    """Consulta el estado del container. Devuelve 'FINISHED' | 'ERROR' | None si sigue esperando."""
    st_resp = requests.get(
        f"https://graph.facebook.com/v20.0/{creation_id}",
        params={"fields": "status_code,status", "access_token": access_token},
        timeout=10,
    )
    if st_resp.status_code != 200:
        logger.info(f"[IG POLLING] Intento {attempt+1}/60 para contenedor {creation_id}: status_code={st_resp.status_code} (HTTP {st_resp.status_code})")
        return None
    try:
        return _estado_json_container(st_resp, access_token, creation_id, attempt)
    except HTTPException:
        raise
    except Exception:
        pass
    return None


def _contenedor_terminado(access_token: str, creation_id: str, attempt: int) -> bool:
    """True si el container terminó; propaga HTTPException y loguea otros fallos."""
    try:
        return _consultar_estado_container(access_token, creation_id, attempt) == "FINISHED"
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[IG POLLING] error en intento {attempt+1}: {e}")
        return False


def _esperar_entre_intentos(attempt: int) -> None:
    """Espera 5s entre intentos de polling (asyncio si es posible, time.sleep como fallback)."""
    # Espera 5 segundos antes del siguiente intento (excepto tras el último)
    if attempt >= 59:
        return
    try:
        asyncio.run(asyncio.sleep(5))
    except RuntimeError:
        # Si ya hay un event loop corriendo, fallback a time.sleep
        time.sleep(5)
    except Exception:
        time.sleep(5)


def _esperar_container_ig(access_token: str, creation_id: str) -> None:
    """Polling/espera del estado del contenedor - NO llamar inmediatamente a media_publish.

    Consulta GET https://graph.facebook.com/v20.0/{container_id}?fields=status_code,status&access_token={token}
    Reglas: 5s x 60 intentos (300s/5min), FINISHED -> break y publica, IN_PROGRESS -> espera, ERROR/timeout -> excepción.
    """
    for attempt in range(60):
        if _contenedor_terminado(access_token, creation_id, attempt):
            return
        _esperar_entre_intentos(attempt)
    # Timeout: el bucle completó 60 intentos sin FINISHED (300s)
    raise HTTPException(status_code=400, detail=f"Instagram container timeout: procesamiento no completó en 300 segundos (60 intentos) para {creation_id}")


def _permalink_container_ig(data2: dict, post_id) -> str:
    """Permalink del reel publicado, con fallback a la URL estándar de Reels."""
    permalink = data2.get("permalink") or f"https://www.instagram.com/reel/{post_id}"
    # Fallback to standard Reel URL
    if not permalink or "instagram.com" not in permalink:
        return PLATFORM_URLS["instagram"] + str(post_id)
    return permalink


def _publicar_container_ig(access_token: str, ig_user_id: str, creation_id: str) -> dict[str, Any]:
    """Paso 2 (Publicar Container): POST https://graph.facebook.com/v18.0/{ig_user_id}/media_publish."""
    url2 = f"https://graph.facebook.com/v18.0/{ig_user_id}/media_publish"
    params2 = {"creation_id": creation_id, "access_token": access_token}
    resp2 = requests.post(url2, data=params2, timeout=30)
    if resp2.status_code == 401:
        _handle_token_expired("instagram", resp2)
    if resp2.status_code >= 400:
        detail = _detalle_error_api(resp2)
        raise HTTPException(status_code=400, detail=f"Instagram API error (publicar) {resp2.status_code}: {detail}")

    data2 = _json_de_respuesta(resp2)
    post_id = data2.get("id") or creation_id
    permalink = _permalink_container_ig(data2, post_id)
    return {"status": "published", "platform": "instagram", "post_id": str(post_id), "url": permalink}


def _publish_instagram(account: SocialAccount, clip: Clip, caption: str | None) -> dict[str, Any]:
    access_token = descifrar_token(account.access_token)
    ig_user_id = _resolve_instagram_business_id(account)

    public_mp4_url = _forzar_https(_get_public_video_url(clip))
    logger.info(f"[IG PUBLISH] Enviando video_url a Instagram: {public_mp4_url}")

    caption_text = caption or clip.title or ""
    _prevalidar_url_publica(public_mp4_url)

    creation_id = _crear_container_ig(access_token, ig_user_id, public_mp4_url, caption_text)
    _esperar_container_ig(access_token, creation_id)
    return _publicar_container_ig(access_token, ig_user_id, creation_id)


def _candidatos_archivo_tiktok(clip: Clip) -> list[str]:
    """Rutas candidatas del MP4 físico para la subida a TikTok."""
    candidatos: list[str] = []
    for attr in ("storage_path", "file_path", "video_path", "output_path"):
        v = getattr(clip, attr, None)
        if v and str(v).strip():
            cand = str(v).strip()
            candidatos.append(cand)
            basename = os.path.basename(cand)
            candidatos.extend([f"/app/storage/{basename}", f"/app/storage/uploads/{basename}", f"/app/storage/clips/{basename}"])
    return candidatos


def _seleccionar_archivo_tiktok(clip: Clip) -> str | None:
    """Primer candidato existente y no vacío para subir a TikTok."""
    for cand in _candidatos_archivo_tiktok(clip):
        if os.path.exists(cand) and os.path.getsize(cand) > 0:
            return cand
    return None


def _leer_archivo_tiktok(file_path: str) -> int:
    """Valida el tamaño del archivo local (>0). Excepciones HTTP si es ilegible/vacío."""
    try:
        file_size = os.path.getsize(file_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo leer archivo local {file_path}: {e}")
    if file_size == 0:
        raise HTTPException(status_code=400, detail=f"Archivo local vacío {file_path}")
    return file_size


def _detalle_error_upload_tiktok(resp: requests.Response) -> Any:
    """Detalle JSON o texto (truncado) de una respuesta errónea del init de TikTok."""
    try:
        detail = resp.json()
        logger.error(f"[TIKTOK API ERROR] {resp.status_code}: error_code={detail.get('error_code')} message={detail.get('message')} detail={detail}")
        return detail
    except Exception:
        detail = resp.text[:1000]
        logger.error(f"[TIKTOK API ERROR] {resp.status_code}: {detail}")
        return detail


def _validar_upload_tiktok(resp: requests.Response) -> None:
    """HTTPException ante 401 (token expirado) u otro error >= 400 del init de TikTok."""
    if resp.status_code == 401:
        _handle_token_expired("tiktok", resp)
    if resp.status_code >= 400:
        detail = _detalle_error_upload_tiktok(resp)
        raise HTTPException(status_code=400, detail=f"TikTok API error {resp.status_code}: {detail}")


def _iniciar_upload_tiktok(account: SocialAccount, file_path: str, file_size: int, title: str) -> tuple[str | None, str, dict]:
    """Llama al init de FILE_UPLOAD de TikTok. Devuelve (upload_url, publish_id, data)."""
    # Auditoría: verifica API v2 de TikTok con FILE_UPLOAD
    logger.info("[AUDITORIA TIKTOK] Usando API v2 https://open.tiktokapis.com/v2/post/publish/video/init/ con FILE_UPLOAD")

    url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
    token = descifrar_token(account.access_token)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
    }
    payload = {
        "post_info": {
            "title": title,
            "privacy_level": "SELF_ONLY",
            "disable_duet": False,
            "disable_stitch": False,
            "disable_comment": False
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": file_size,
            "total_chunk_count": 1
        }
    }

    logger.info(f"[TIKTOK PAYLOAD] {payload}")
    logger.info(f"[TIKTOK PUBLISH] POST {url} body={payload}")
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    _logear_respuesta_tiktok(resp)
    _validar_upload_tiktok(resp)

    try:
        data = resp.json()
        logger.info("[TIKTOK API] init ok")
    except Exception:
        data = {}
        logger.warning("[TIKTOK API] respuesta no JSON")
    return data


def _logear_respuesta_tiktok(resp: requests.Response) -> None:
    """Logs detallados de la respuesta TikTok."""
    try:
        logger.info("[TIKTOK API RESPONSE] status=%s", resp.status_code)
        try:
            j = resp.json()
            logger.info("[TIKTOK API] error_code=%s message=%s", j.get("error_code"), j.get("message"))
            if j.get("error_code") not in (None, 0, "0", ""):
                logger.error("[TIKTOK API ERROR] error_code=%s message=%s", j.get("error_code"), j.get("message"))
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"[TIKTOK API] error loggeando respuesta: {e}")


def _primer_valor_no_vacio(*valores):
    """Primer valor truthy de la lista, o None."""
    for valor in valores:
        if valor:
            return valor
    return None


def _inner_data_tiktok(data: dict) -> Any:
    """data['data'] si es dict; si no, el propio body."""
    if isinstance(data.get("data"), dict):
        return data["data"]
    return data


def _publish_id_inner(inner) -> str | None:
    """publish_id del bloque interno (alias publishId/id/post_id)."""
    if not isinstance(inner, dict):
        return None
    return _primer_valor_no_vacio(inner.get("publish_id"), inner.get("publishId"), inner.get("id"), inner.get("post_id"))


def _upload_url_inner(inner) -> str | None:
    """upload_url del bloque interno (alias uploadUrl)."""
    if not isinstance(inner, dict):
        return None
    return _primer_valor_no_vacio(inner.get("upload_url"), inner.get("uploadUrl"))


def _logear_inner_tiktok(inner) -> None:
    """Log informativo si el inner trae error_code o message."""
    if not isinstance(inner, dict):
        return
    if "error_code" in inner or "message" in inner:
        logger.info(f"[TIKTOK API INNER] error_code={inner.get('error_code')} message={inner.get('message')}")


def _publish_id_final(inner, data: dict) -> str:
    """publish_id del inner, del body, o un id sintético si no vino ninguno."""
    publish_id = _publish_id_inner(inner)
    if publish_id:
        return publish_id
    return _primer_valor_no_vacio(data.get("publish_id"), data.get("id")) or _generate_fake_id()


def _upload_url_final(inner, data: dict) -> str | None:
    """upload_url del inner o del body."""
    upload_url = _upload_url_inner(inner)
    if upload_url:
        return upload_url
    return data.get("upload_url") or _upload_url_inner(inner)


def _extraer_ids_tiktok(data: dict) -> tuple[str, str, dict]:
    """Extrae (publish_id, upload_url, inner) de la respuesta del init."""
    inner = _inner_data_tiktok(data)
    _logear_inner_tiktok(inner)
    publish_id = _publish_id_final(inner, data)
    upload_url = _upload_url_final(inner, data)
    return publish_id, upload_url, inner


def _subir_archivo_tiktok(upload_url: str, file_path: str, file_size: int) -> None:
    """Sube el archivo MP4 vía PUT binario. HTTPException si la subida falla."""
    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        headers_put = {
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
        }
        logger.info("[TIKTOK UPLOAD] PUT Content-Range=%s size=%s", headers_put["Content-Range"], file_size)
        resp_put = requests.put(upload_url, headers=headers_put, data=file_bytes, timeout=60)
        logger.info("[TIKTOK UPLOAD] status=%s", resp_put.status_code)
        if resp_put.status_code not in (200, 201, 204):
            logger.error("[TIKTOK UPLOAD ERROR] status=%s", resp_put.status_code)
            raise HTTPException(status_code=400, detail=f"TikTok upload error {resp_put.status_code}: {resp_put.text[:1000]}")
        logger.info("[TIKTOK UPLOAD] Confirmación subida exitosa status={}".format(resp_put.status_code))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[TIKTOK UPLOAD ERROR] excepción subiendo archivo: {e}")
        raise HTTPException(status_code=400, detail=f"Error subiendo archivo a TikTok: {e}")


def _auditar_cuenta_tiktok(account: SocialAccount) -> None:
    """Auditoría de credenciales BD en cada publicación TikTok (logs explícitos)."""
    try:
        _acc_exists = bool(getattr(account, "access_token", None))
        logger.error("[AUDITORIA BD] platform=tiktok platform_account_id=%s access_token_exists=%s refresh_token_exists=%s", getattr(account, "platform_account_id", None), _acc_exists, bool(getattr(account, "refresh_token", None)))
    except Exception as e:
        logger.error(f"[AUDITORIA BD] tiktok audit error {e}")


def _file_path_tiktok(clip: Clip) -> str:
    """Archivo físico del clip para TikTok; HTTPException 404 si no existe."""
    file_path = _seleccionar_archivo_tiktok(clip)
    # Modo 100% real: si no hay archivo físico, error 404 real
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Archivo de clip no encontrado para TikTok: {clip.storage_path}. Debe existir .mp4 físico en storage antes de publicar.")
    return file_path


def _username_tiktok(account: SocialAccount) -> str:
    """Username visible para la URL del video (fallback 'user')."""
    return getattr(account, "platform_username", None) or getattr(account, "account_name", None) or "user"


def _permalink_tiktok(account: SocialAccount, publish_id, inner) -> str:
    """URL final del video publicado (share_url del inner si viene)."""
    permalink = f"https://www.tiktok.com/@{_username_tiktok(account)}/video/{publish_id}"
    if isinstance(inner, dict) and inner.get("share_url"):
        permalink = inner["share_url"]
        logger.info(f"[TIKTOK API] share_url={permalink}")
    return permalink


def _publish_tiktok(account: SocialAccount, clip: Clip, caption: str | None) -> dict[str, Any]:
    # Auditoría de credenciales TikTok - logs explícitos
    _auditar_cuenta_tiktok(account)

    # 1. Inicialización FILE_UPLOAD: leer archivo MP4 físico real (modo 100% real)
    file_path = _file_path_tiktok(clip)

    file_size = _leer_archivo_tiktok(file_path)
    logger.info(f"[TIKTOK PUBLISH] Archivo local {file_path} video_size={file_size} bytes")

    title = _texto_o_fallback(caption, clip, "ClipsAI")[:150]
    data = _iniciar_upload_tiktok(account, file_path, file_size, title)

    publish_id, upload_url, inner = _extraer_ids_tiktok(data)
    if not upload_url:
        logger.error(f"[TIKTOK API ERROR] No se recibió upload_url en respuesta: {data}")
        raise HTTPException(status_code=400, detail=f"TikTok API no devolvió upload_url: {data}")

    logger.info(f"[TIKTOK PUBLISH] publish_id={publish_id} upload_url={upload_url}")

    # 2. Subida del archivo a upload_url via PUT binario
    _subir_archivo_tiktok(upload_url, file_path, file_size)

    permalink = _permalink_tiktok(account, publish_id, inner)

    logger.info(f"[TIKTOK PUBLISH] SUCCESS publish_id={publish_id} url={permalink}")
    return {"status": "published", "platform": "tiktok", "post_id": str(publish_id), "url": permalink}


def _user_id_desde_video(db, video_id) -> str | None:
    """user_id del Video directo (None si no hay video_id o no existe el video)."""
    if video_id is None:
        return None
    from ..models import Video

    video = db.get(Video, video_id)
    if video is not None:
        return str(video.user_id)
    return None


def _user_id_desde_job(db, job_id) -> str | None:
    """user_id del Video asociado al Job (None si no hay job_id/job/video)."""
    if job_id is None:
        return None
    from ..models import Job
    from ..models import Video

    job = db.get(Job, job_id)
    if job is None:
        return None
    video2 = db.get(Video, job.video_id)
    if video2 is not None:
        return str(video2.user_id)
    return None


def _user_id_resuelto_del_clip(db, clip: Clip) -> str | None:
    """user_id inferido del clip: video directo primero, video del job después."""
    try:
        return _user_id_desde_video(db, clip.video_id) or _user_id_desde_job(db, clip.job_id)
    except Exception:
        pass
    return None


def _resolver_user_id(db, clip: Clip, user_id: str | None) -> str | None:
    """Resolve user_id si not provided (vía video directo o vía job)."""
    if user_id is not None:
        return user_id
    return _user_id_resuelto_del_clip(db, clip)


def _resultado_webhook_falso(platform_norm: str, social_post_id: str | None = None) -> dict[str, Any]:
    """URL/post_id sintéticos para el modo webhook legacy."""
    post_id = social_post_id or _generate_fake_id()
    base = PLATFORM_URLS.get(platform_norm, PLATFORM_URLS["webhook"])
    return {"status": "published", "platform": platform_norm, "post_id": post_id, "url": f"{base}{post_id}"}


def _social_post_id_webhook(data: dict) -> str:
    """post_id del webhook o un id sintético."""
    return str(_primer_valor_no_vacio(data.get("id"), data.get("post_id")) or _generate_fake_id())


def _social_post_url_webhook(data: dict, social_post_id: str, platform_norm: str) -> str:
    """URL del post desde el webhook o la base de la plataforma."""
    base = PLATFORM_URLS.get(platform_norm, PLATFORM_URLS["webhook"])
    return str(_primer_valor_no_vacio(data.get("url"), data.get("post_url")) or f"{base}{social_post_id}")


def _datos_webhook(resp, platform_norm: str) -> dict[str, Any]:
    """Resultado publicado a partir del JSON del webhook (fallback sintético si falla)."""
    try:
        data = resp.json()
        social_post_id = _social_post_id_webhook(data)
        social_post_url = _social_post_url_webhook(data, social_post_id, platform_norm)
    except Exception:
        return _resultado_webhook_falso(platform_norm)
    return {"status": "published", "platform": platform_norm, "post_id": social_post_id, "url": social_post_url}


def _publicar_via_webhook(clip_id: uuid.UUID, clip: Clip, platform: str, caption: str | None, webhook: str) -> dict[str, Any]:
    """Webhook legacy still supported but real platforms use OAuth tokens."""
    platform_norm = (platform or "").strip().lower()
    try:
        payload = {
            "clip_id": str(clip_id),
            "platform": platform,
            "caption": caption,
            "file_path": clip.storage_path,
            "title": clip.title,
        }
        resp = requests.post(webhook, json=payload, timeout=10)
        if resp.status_code < 400:
            return _datos_webhook(resp, platform_norm)
        raise RuntimeError(f"webhook status {resp.status_code}")
    except Exception:
        # El webhook falló: igual se genera el resultado sintético (comportamiento legacy)
        return _resultado_webhook_falso(platform_norm)


def _auditar_cuenta_bd(account: SocialAccount, platform_norm: str) -> None:
    # AUDITORÍA DE BD EN CADA PUBLICACIÓN
    try:
        _acc_token_exists = bool(getattr(account, "access_token", None))
        _ref_exists = bool(getattr(account, "refresh_token", None))
        logger.error("[AUDITORIA BD] platform=%s platform_account_id=%s updated_at=%s access_token_exists=%s refresh_token_exists=%s", account.platform, account.platform_account_id, getattr(account, "updated_at", None), _acc_token_exists, _ref_exists)
    except Exception as _e:
        logger.error(f"[AUDITORIA BD] error audit {str(_e)}")


def _do_publish(account: SocialAccount, clip: Clip, platform_norm: str, caption: str | None, platform: str) -> dict[str, Any]:
    if platform_norm == "youtube":
        return _publish_youtube(account, clip, caption)
    if platform_norm == "instagram":
        return _publish_instagram(account, clip, caption)
    if platform_norm == "tiktok":
        return _publish_tiktok(account, clip, caption)
    raise HTTPException(status_code=400, detail=f"Plataforma no soportada: {platform}")


def _desconectar_cuenta_oauth(db, account: SocialAccount, platform_norm: str) -> None:
    """Elimina la cuenta OAuth de BD (desconexión) para cualquier plataforma.

    Usa ORM con fallback SQL crudo sobre social_accounts y user_social_accounts.
    Idempotente: nunca lanza.
    """
    plat = platform_norm.lower().strip()
    try:
        db.delete(account)
        db.commit()
        logger.info("[OAUTH DISCONNECT] cuenta %s eliminada para plataforma %s", account.user_id, plat)
    except Exception:
        try:
            from sqlalchemy import text

            db.execute(text("DELETE FROM social_accounts WHERE user_id = :uid AND lower(platform) = :plat"), {"uid": str(account.user_id), "plat": plat})
            db.execute(text("DELETE FROM user_social_accounts WHERE user_id = :uid AND lower(platform) = :plat"), {"uid": str(account.user_id), "plat": plat})
            db.commit()
            logger.info("[OAUTH DISCONNECT] cuenta %s eliminada via SQL para plataforma %s", account.user_id, plat)
        except Exception as exc:
            logger.warning("[OAUTH DISCONNECT] fallo eliminando cuenta %s plataforma %s: %s", account.user_id, plat, exc)


_TIKTOK_DESCONECTAR_MSG = "Token de TikTok expirado. Por favor, desconecta y vuelve a conectar tu cuenta desde Integraciones."


def _manejar_error_refresh(db, account: SocialAccount, platform_norm: str, refresh_exc: Exception) -> None:
    """Log del error de refresh: desconecta la cuenta (TikTok, YouTube, Instagram) o propaga."""
    logger.error("[publish] Error renovando token %s tipo=%s", platform_norm, type(refresh_exc).__name__)
    if platform_norm == "tiktok":
        _desconectar_cuenta_oauth(db, account, platform_norm)
        raise HTTPException(status_code=400, detail=f"TikTok refresh failed body={refresh_exc}")
    if platform_norm in ("youtube", "instagram"):
        _desconectar_cuenta_oauth(db, account, platform_norm)
        raise HTTPException(
            status_code=400,
            detail=f"Token de {platform_norm} expirado. Reconecta la cuenta desde Integraciones.",
        )
    raise Exception(str(refresh_exc))


def _reintentar_publicacion(db, account: SocialAccount, clip: Clip, platform_norm: str, caption: str | None, platform: str) -> dict[str, Any]:
    """Reintenta la publicación una vez más tras un refresh exitoso."""
    try:
        db.refresh(account)
        # Reintenta la publicación una vez más antes de fallar
        result = _do_publish(account, clip, platform_norm, caption, platform)
        logger.info(f"[publish] reintento tras refresh exitoso para {platform_norm}")
        return result
    except HTTPException as retry_exc:
        raise retry_exc


def _fallo_tras_refresh(db, account: SocialAccount, platform_norm: str, pub_exc: HTTPException) -> dict[str, Any]:
    """Aborta tras un refresh fallido: desconecta la cuenta o relanza la excepción."""
    logger.warning(f"[publish] refresh falló para {platform_norm}, abortando")
    if platform_norm == "tiktok":
        _desconectar_cuenta_oauth(db, account, platform_norm)
        raise HTTPException(status_code=400, detail=_TIKTOK_DESCONECTAR_MSG)
    if platform_norm in ("youtube", "instagram"):
        _desconectar_cuenta_oauth(db, account, platform_norm)
        raise HTTPException(
            status_code=400,
            detail=f"Token de {platform_norm} expirado. Reconecta la cuenta desde Integraciones.",
        )
    raise pub_exc


def _reintentar_tras_refresh(db, account: SocialAccount, clip: Clip, platform_norm: str, caption: str | None, platform: str, pub_exc: HTTPException) -> dict[str, Any]:
    """REFRESH TOKEN AUTOMÁTICO: si 401 y existe refresh_token, refresca y reintenta una vez."""
    logger.info(f"[publish] token expirado detectado para {platform_norm}, intentando refresh automático")
    try:
        refreshed = _refresh_account_token(account, platform_norm, db)
    except Exception as refresh_exc:
        _manejar_error_refresh(db, account, platform_norm, refresh_exc)
    if refreshed:
        return _reintentar_publicacion(db, account, clip, platform_norm, caption, platform)
    return _fallo_tras_refresh(db, account, platform_norm, pub_exc)


def _cuenta_para_publicar(db, platform_norm: str, resolved_user_id: str) -> SocialAccount:
    """Cuenta vinculada con auditoría de BD y auto-refresh preventivo del token."""
    account = _get_social_account(db, resolved_user_id, platform_norm)
    _auditar_cuenta_bd(account, platform_norm)
    # AUTO-RENOVACIÓN TRANSPARENTE AL PUBLICAR: Antes de llamar a la API o al recibir una respuesta 401
    _ensure_token_fresh(account, platform_norm, db)
    return account


def _reaccionar_token_expirado(db, account: SocialAccount, clip: Clip, platform_norm: str, caption: str | None, platform: str, pub_exc: HTTPException) -> dict[str, Any]:
    """Respuesta a un 401: reintenta con refresh o desconecta la cuenta."""
    has_refresh = bool((getattr(account, "refresh_token", None) or "").strip())
    if has_refresh:
        return _reintentar_tras_refresh(db, account, clip, platform_norm, caption, platform, pub_exc)
    # Sin refresh_token: desconectar la cuenta y mensaje específico
    if platform_norm == "tiktok":
        _desconectar_cuenta_oauth(db, account, platform_norm)
        raise HTTPException(status_code=400, detail=_TIKTOK_DESCONECTAR_MSG)
    if platform_norm in ("youtube", "instagram"):
        _desconectar_cuenta_oauth(db, account, platform_norm)
        raise HTTPException(
            status_code=400,
            detail=f"Token de {platform_norm} expirado. Reconecta la cuenta desde Integraciones.",
        )
    raise pub_exc


def _publicar_con_oauth(db, clip: Clip, platform_norm: str, caption: str | None, platform: str, resolved_user_id: str) -> dict[str, Any]:
    """Publica vía OAuth: auditoría de BD, auto-refresh preventivo y retry si el token expiró."""
    if not resolved_user_id:
        raise HTTPException(status_code=400, detail=f"Cuenta de {platform_norm} no vinculada")
    account = _cuenta_para_publicar(db, platform_norm, resolved_user_id)

    try:
        return _do_publish(account, clip, platform_norm, caption, platform)
    except HTTPException as pub_exc:
        if not _is_token_expired_error(pub_exc):
            raise
        return _reaccionar_token_expirado(db, account, clip, platform_norm, caption, platform, pub_exc)


def _marcar_publicando(db, clip: Clip, platform: str) -> None:
    """Marca el clip en PUBLISHING y persiste el estado."""
    clip.status = "PUBLISHING"
    clip.publication_status = "PUBLISHING"
    clip.published_platform = platform
    db.commit()


def _webhook_o_falso(clip_id: uuid.UUID, clip: Clip, platform: str, caption: str | None, webhook_url: str | None, platform_norm: str) -> dict[str, Any]:
    """Publica vía webhook configurado, o genera el resultado sintético legacy."""
    webhook = webhook_url or os.getenv("PUBLISH_WEBHOOK_URL", "").strip() or None
    if webhook:
        return _publicar_via_webhook(clip_id, clip, platform, caption, webhook)
    # Sin webhook configurado: generación directa sin delay artificial (modo real)
    return _resultado_webhook_falso(platform_norm)


def _resultado_publicacion(db, clip: Clip, clip_id: uuid.UUID, platform: str, platform_norm: str, caption: str | None, webhook_url: str | None, resolved_user_id: str | None) -> dict[str, Any] | None:
    """Despacha la publicación según la plataforma (webhook legacy u OAuth)."""
    if platform_norm == "webhook":
        return _webhook_o_falso(clip_id, clip, platform, caption, webhook_url, platform_norm)
    if platform_norm in ("youtube", "instagram", "tiktok"):
        return _publicar_con_oauth(db, clip, platform_norm, caption, platform, resolved_user_id)
    raise HTTPException(status_code=400, detail=f"Plataforma no soportada: {platform}")


def _social_network_publicada(platform_norm: str, actual: Any) -> Any:
    """social_network a guardar: la plataforma si es soportada, si no el valor actual."""
    if platform_norm in ("tiktok", "instagram", "youtube"):
        return platform_norm
    return actual


def _limpiar_errores_previos(clip) -> None:
    """Limpia error_log/error_message previos (silencioso si el modelo no los soporta)."""
    # Clear previous error if any
    try:
        clip.error_log = None
        setattr(clip, "error_message", None)
    except Exception:
        pass


def _persistir_publicado(db, clip, clip_id: uuid.UUID, platform_norm: str, result: dict[str, Any]) -> None:
    """Marca el clip como PUBLISHED y guarda post_id, url y fecha."""
    clip.status = "PUBLISHED"
    clip.publication_status = "PUBLISHED"
    clip.published_platform = platform_norm
    try:
        clip.social_network = _social_network_publicada(platform_norm, clip.social_network)
    except Exception:
        pass
    clip.social_post_id = result.get("post_id")
    clip.social_post_url = result.get("url")
    clip.published_at = datetime.now(timezone.utc)
    _limpiar_errores_previos(clip)
    db.commit()
    logger.info(f"[publish] ✓ clip {clip_id} PUBLISHED platform={platform_norm}")


def _persistir_si_existe(db, clip_id: uuid.UUID, platform_norm: str, result: dict[str, Any]) -> None:
    """Relee el clip y lo marca PUBLISHED si sigue existiendo."""
    # Update clip as PUBLISHED
    clip = db.get(Clip, clip_id)
    if clip is None:
        return
    _persistir_publicado(db, clip, clip_id, platform_norm, result)


def _publicar_y_persistir(db, clip_id: uuid.UUID, platform: str, caption: str | None, webhook_url: str | None, user_id: str | None) -> dict[str, Any] | None:
    """Flujo principal: marca PUBLISHING, resuelve usuario, publica y persiste PUBLISHED."""
    platform_norm = (platform or "").strip().lower()

    clip: Clip | None = db.get(Clip, clip_id)
    if clip is None:
        return None

    _marcar_publicando(db, clip, platform)

    resolved_user_id = _resolver_user_id(db, clip, user_id)
    result = _resultado_publicacion(db, clip, clip_id, platform, platform_norm, caption, webhook_url, resolved_user_id)
    if result is None:
        raise RuntimeError("No se obtuvo resultado de publicación")

    _persistir_si_existe(db, clip_id, platform_norm, result)
    return result


def _marcar_fallido(db, clip_id: uuid.UUID, err_msg: str) -> None:
    """Marca el clip como FAILED con el mensaje de error (rollback ante fallos de BD)."""
    try:
        clip = db.get(Clip, clip_id)
        if clip is not None:
            clip.status = "FAILED"
            db.add(clip)
            db.commit()
            clip.publication_status = "FAILED"
            clip.error_log = err_msg
            db.add(clip)
            db.commit()
    except Exception:
        _rollback_silencioso(db)


def publish_clip_task(clip_id: uuid.UUID, platform: str, caption: str | None, webhook_url: str | None = None, user_id: str | None = None) -> dict[str, Any] | None:
    db = SessionLocal()
    try:
        result = _publicar_y_persistir(db, clip_id, platform, caption, webhook_url, user_id)
        return result

    except HTTPException as he:
        logger.error(f"[publish] http error clip={clip_id} {he.detail}")
        _marcar_fallido(db, clip_id, str(he.detail)[:2000])
        return {"status": "failed", "platform": platform, "error": str(he.detail), "code": he.status_code}
    except Exception as exc:
        logger.error(f"[publish] error clip={clip_id} exc={exc}", exc_info=True)
        _marcar_fallido(db, clip_id, str(exc)[:2000])
        return {"status": "failed", "platform": platform, "error": str(exc)}
    finally:
        db.close()
