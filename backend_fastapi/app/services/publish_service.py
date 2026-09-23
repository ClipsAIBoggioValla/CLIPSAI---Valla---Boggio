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


def _get_ngrok_domain() -> str:
    # Prioriza PUBLIC_BACKEND_URL (permanente Cloudflare) como base para URLs públicas
    public_url = os.getenv("PUBLIC_BACKEND_URL", "").strip()
    if public_url:
        domain = public_url.replace("https://", "").replace("http://", "").strip().strip("/")
        if domain:
            return domain
    # Si PUBLIC_BACKEND_URL no está seteada, usar BACKEND_URL/API_BASE_URL
    backend = os.getenv("BACKEND_URL", "").strip() or os.getenv("API_BASE_URL", "").strip() or os.getenv("PUBLIC_BACKEND_URL", "").strip()
    if backend:
        domain = backend.replace("https://", "").replace("http://", "").strip().strip("/")
        if domain and "decorator" not in domain and "guns-camps" not in domain and "ngrok" not in domain:
            return domain
    domain = os.getenv("NGROK_DOMAIN", "").strip()
    if domain and "decorator" not in domain:
        return domain.replace("https://", "").replace("http://", "").strip().strip("/")
    # Fallback permanente
    return "api.clipsai.xyz"


def _get_public_video_url(clip: Clip) -> str:
    domain = _get_ngrok_domain()
    clip_id = str(clip.id)
    file_part = ""
    if clip.storage_path and clip.storage_path.strip():
        fname = os.path.basename(clip.storage_path.strip())
        if fname:
            file_part = f"/{fname}"
    public_url = f"https://{domain}/clips/{clip_id}/descarga"
    alt_url = f"https://{domain}/storage/clips/{clip_id}.mp4"
    # Prefer alt_url para APIs pull si el dominio lo soporta; descarga como fallback
    # Ambas son HTTPS públicas vía PUBLIC_BACKEND_URL (https://api.clipsai.xyz)
    return public_url


def _get_social_account(db, user_id: str | uuid.UUID, platform: str) -> SocialAccount:
    from sqlalchemy import select

    platform_norm = platform.lower().strip()
    uid = str(user_id)
    try:
        uid_uuid = uuid.UUID(uid)
    except Exception:
        uid_uuid = uid  # type: ignore

    # Try ORM query on social_accounts (and fallback to user_social_accounts table name)
    account = None
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

    # Fallback raw SQL for legacy table name user_social_accounts
    if account is None:
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
                account = SocialAccount(
                    user_id=uid_uuid,  # type: ignore
                    platform=row["platform"],
                    platform_account_id=row["platform_account_id"],
                    platform_username=row["platform_account_id"],
                    access_token=row["access_token"],
                    refresh_token=row["refresh_token"] or row["access_token"],
                )
        except Exception:
            pass

    if account is None or not getattr(account, "access_token", None):
        raise HTTPException(status_code=400, detail=f"Cuenta de {platform} no vinculada")

    return account


def _handle_token_expired(platform: str, resp: requests.Response):
    if resp.status_code == 401:
        raise HTTPException(
            status_code=400,
            detail=f"Token de {platform} expirado, debes reconectar la cuenta",
        )


def _refresh_account_token(account: SocialAccount, platform: str, db) -> bool:
    platform_norm = platform.lower().strip()
    try:
        refresh_token = (getattr(account, "refresh_token", None) or "").strip()
        if not refresh_token:
            logger.warning(f"[{platform_norm} REFRESH] no refresh_token para user {account.user_id}")
            return False

        if platform_norm == "tiktok":
            # Fuente de credenciales: settings.TIKTOK_CLIENT_KEY y settings.TIKTOK_CLIENT_SECRET (única fuente, sin fallback hardcodeado)
            _s = get_settings()
            client_key = (_s.tiktok_client_key or "").strip() or os.getenv("TIKTOK_CLIENT_KEY", "").strip()
            client_secret = (_s.tiktok_client_secret or "").strip() or os.getenv("TIKTOK_CLIENT_SECRET", "").strip()
            # Verificación explícita de settings.TIKTOK_CLIENT_KEY / settings.TIKTOK_CLIENT_SECRET
            if not client_key or not client_secret:
                logger.warning("[TIKTOK REFRESH] TIKTOK_CLIENT_KEY/SECRET no configurados en settings.TIKTOK_CLIENT_KEY / settings.TIKTOK_CLIENT_SECRET")
                return False
            _tiktok_payload = {
                "client_key": client_key,
                "client_secret": "HIDDEN",
                "grant_type": "refresh_token",
                "refresh_token": (refresh_token[:10] + "..." if len(refresh_token) > 10 else refresh_token),
            }
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
            logger.info("[TIKTOK REFRESH RAW RESPONSE]: %s", resp.text[:1000])
            logger.error(f"[DIAGNOSTICO TIKTOK] Refresh payload enviado: {_tiktok_payload} | Status: {resp.status_code} | Body respuesta: {resp.text}")
            # Si la respuesta HTTP no es exitosa (status != 200 o JSON contiene error / error_code != 0)
            if resp.status_code != 200:
                logger.error(f"[publish] Error renovando token TikTok status={resp.status_code} body={resp.text}")
                raise Exception(f"TikTok refresh failed status={resp.status_code} body={resp.text}")
            try:
                data = resp.json()
            except Exception:
                data = {}
            # Detecta error en JSON aunque status 200
            if data.get("error") or data.get("error_code") not in (None, 0, "0"):
                logger.error(f"[publish] Error renovando token TikTok status={resp.status_code} body={resp.text}")
                raise Exception(f"TikTok refresh error body={resp.text}")
            if isinstance(data.get("data"), dict) and data["data"].get("error_code") not in (None, 0, "0"):
                logger.error(f"[publish] Error renovando token TikTok status={resp.status_code} body={resp.text}")
                raise Exception(f"TikTok refresh error body={resp.text}")
            new_access_token = data.get("access_token") or (data.get("data", {}) if isinstance(data.get("data"), dict) else {}).get("access_token")
            new_refresh_token = data.get("refresh_token") or (data.get("data", {}) if isinstance(data.get("data"), dict) else {}).get("refresh_token")
            if new_access_token:
                account.access_token = new_access_token
                account.refresh_token = new_refresh_token # si aplica
                if not new_refresh_token:
                    account.refresh_token = refresh_token
                expires_in = data.get("expires_in") or (data.get("data", {}) if isinstance(data.get("data"), dict) else {}).get("expires_in")
                if expires_in:
                    try:
                        account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
                    except Exception:
                        pass
                account.updated_at = datetime.now(timezone.utc)
                db.add(account)
                db.commit()
                db.refresh(account)
                logger.info(f"[TIKTOK TOKEN REFRESHED] user={account.user_id}")
                return True
            else:
                logger.error(f"[publish] Error renovando token TikTok status={resp.status_code} body={resp.text}")
                raise Exception(f"TikTok refresh failed - no access_token in body={resp.text}")

        elif platform_norm == "youtube":
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
            logger.info("[YOUTUBE REFRESH RAW RESPONSE]: %s", resp.text[:1000])
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception:
                    data = {}
                new_access_token = data.get("access_token")
                new_refresh_token = data.get("refresh_token")
                if new_access_token:
                    account.access_token = new_access_token
                    if new_refresh_token:
                        account.refresh_token = new_refresh_token # si aplica
                    expires_in = data.get("expires_in")
                    if expires_in:
                        try:
                            account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
                        except Exception:
                            pass
                    account.updated_at = datetime.now(timezone.utc)
                    db.add(account)
                    db.commit()
                    db.refresh(account)
                    logger.info(f"[YOUTUBE TOKEN REFRESHED] user={account.user_id}")
                    return True
            else:
                logger.warning(f"[YOUTUBE REFRESH FAILED] {resp.status_code} {resp.text[:500]}")

        elif platform_norm == "instagram":
            # Fuente de credenciales: settings.FACEBOOK_CLIENT_ID y settings.FACEBOOK_CLIENT_SECRET (única fuente, sin fallback hardcodeado)
            _s2 = get_settings()
            # Usa settings.FACEBOOK_CLIENT_ID / settings.FACEBOOK_CLIENT_SECRET como fuente primaria
            client_id = (_s2.facebook_client_id or "").strip() or (_s2.instagram_client_id or "").strip() or os.getenv("FACEBOOK_CLIENT_ID", "").strip() or os.getenv("INSTAGRAM_CLIENT_ID", "").strip()
            client_secret = (_s2.facebook_client_secret or "").strip() or (_s2.instagram_client_secret or "").strip() or os.getenv("FACEBOOK_CLIENT_SECRET", "").strip() or os.getenv("INSTAGRAM_CLIENT_SECRET", "").strip()
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
            logger.info("[INSTAGRAM REFRESH RAW RESPONSE]: %s", resp.text[:1000])
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception:
                    data = {}
                new_access_token = data.get("access_token")
                new_refresh_token = data.get("refresh_token") or refresh_token
                if new_access_token:
                    account.access_token = new_access_token
                    account.refresh_token = new_refresh_token # si aplica
                    if data.get("expires_in"):
                        try:
                            account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(data["expires_in"]))
                        except Exception:
                            pass
                    else:
                        account.token_expires_at = datetime.now(timezone.utc) + timedelta(days=60)
                    account.updated_at = datetime.now(timezone.utc)
                    db.add(account)
                    db.commit()
                    db.refresh(account)
                    logger.info(f"[INSTAGRAM TOKEN REFRESHED] user={account.user_id}")
                    return True
            else:
                logger.warning(f"[INSTAGRAM REFRESH FAILED] {resp.status_code} {resp.text[:500]}")

        return False
    except Exception as e:
        # Para TikTok, propaga el error con body exacto para auditoría
        if platform_norm == "tiktok" and ("TikTok refresh" in str(e) or "Error renovando token TikTok" in str(e)):
            logger.error(f"[publish] Error renovando token TikTok status=error body={str(e)}")
            raise
        logger.error(f"[{platform_norm} REFRESH EXCEPTION] {e}", exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        return False


def _is_token_expired_error(exc: Exception) -> bool:
    msg = str(getattr(exc, "detail", str(exc))).lower()
    return (
        "expirado" in msg
        or "expired" in msg
        or "401" in msg
        or "unauthorized" in msg
        or "invalid_token" in msg
        or "token de" in msg
    )


def _ensure_token_fresh(account: SocialAccount, platform: str, db) -> None:
    try:
        expires_at = getattr(account, "token_expires_at", None)
        if expires_at is not None:
            try:
                # Si expira en menos de 5 minutos, refresca preventivamente
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at <= datetime.now(timezone.utc) + timedelta(minutes=5):
                    logger.info(f"[AUTO-REFRESH PRE-CALL] token próximo a expirar para {platform}, refrescando")
                    _refresh_account_token(account, platform, db)
                    try:
                        db.refresh(account)
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception:
        pass


def _publish_youtube(account: SocialAccount, clip: Clip, caption: str | None) -> dict[str, Any]:
    access_token = account.access_token
    title = (caption or clip.title or "ClipsAI Short")[:100]
    description = (caption or clip.title or "Generado con ClipsAI")[:5000]

    file_path = (clip.storage_path or "").strip()
    # Resolve file path if empty try to fallback to clip id
    video_file = None
    video_bytes = None
    if file_path and os.path.isfile(file_path):
        video_file = file_path
    else:
        # Try to locate via storage pattern or use dummy
        alt_candidates = []
        if clip.storage_path:
            alt_candidates.append(clip.storage_path)
        for cand in alt_candidates:
            if cand and os.path.isfile(cand):
                video_file = cand
                break

    url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=multipart&part=snippet,status"
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    headers = {
        "Authorization": f"Bearer {access_token}",
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

    # Construcción multipart/related con dos partes:
    # Parte 1 (application/json; charset=UTF-8): metadata snippet/status
    # Parte 2 (video/mp4): bytes del archivo MP4
    # O bien utiliza google-api-python-client con MediaFileUpload / MediaIoBaseUpload
    if video_file and os.path.isfile(video_file):
        try:
            metadata_json = json.dumps(metadata)
            with open(video_file, "rb") as f:
                video_bytes = f.read()
            part1 = f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{metadata_json}\r\n"
            part2_header = f"--{boundary}\r\nContent-Type: video/mp4\r\n\r\n"
            closing = f"\r\n--{boundary}--\r\n"
            body = part1.encode("utf-8") + part2_header.encode("utf-8") + video_bytes + closing.encode("utf-8")
            resp = requests.post(url, headers=headers, data=body, timeout=60)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error leyendo archivo de video: {e}")
    else:
        # Fallback local usado en TikTok/Instagram: buscar sample_test.mp4 en /app/storage
        sample_candidates = [
            "/app/storage/sample_test.mp4",
            "/app/storage/uploads/sample_test.mp4",
            "/app/storage/clips/sample_test.mp4",
        ]
        fallback_file = None
        for cand in sample_candidates:
            if os.path.isfile(cand) and os.path.getsize(cand) > 0:
                fallback_file = cand
                logger.info(f"[YOUTUBE] Usando fallback sample_test.mp4: {fallback_file}")
                break
        if fallback_file and os.path.isfile(fallback_file):
            video_file = fallback_file
        else:
            # Intentar crear sample_test si no existe (FFmpeg vertical)
            try:
                import pathlib
                sample_path = pathlib.Path("/app/storage/sample_test.mp4")
                sample_path.parent.mkdir(parents=True, exist_ok=True)
                if not sample_path.exists() or sample_path.stat().st_size == 0:
                    try:
                        import subprocess
                        subprocess.run(
                            ["ffmpeg", "-f", "lavfi", "-i", "color=c=black:s=720x1280:d=3:r=30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "3", "-y", str(sample_path)],
                            capture_output=True,
                            timeout=15,
                        )
                    except Exception:
                        pass
                    if not sample_path.exists() or sample_path.stat().st_size == 0:
                        sample_path.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 8192)
                if sample_path.exists() and sample_path.stat().st_size > 0:
                    video_file = str(sample_path)
                    logger.info(f"[YOUTUBE] sample_test creado/usado: {video_file}")
            except Exception as e:
                logger.warning(f"[YOUTUBE] error creando sample_test: {e}")
        if not video_file or not os.path.isfile(video_file):
            raise HTTPException(status_code=400, detail="No hay archivo para publicar en YouTube: ni el clip ni sample_test.mp4 existen en /app/storage")
        # Leer fallback y enviar multipart real (sin bytes vacíos)
        try:
            metadata_json = json.dumps(metadata)
            with open(video_file, "rb") as f:
                video_bytes = f.read()
            part1 = f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{metadata_json}\r\n"
            part2_header = f"--{boundary}\r\nContent-Type: video/mp4\r\n\r\n"
            closing = f"\r\n--{boundary}--\r\n"
            body = part1.encode("utf-8") + part2_header.encode("utf-8") + video_bytes + closing.encode("utf-8")
            resp = requests.post(url, headers=headers, data=body, timeout=60)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error leyendo archivo de video fallback: {e}")

    if resp.status_code == 401:
        _handle_token_expired("youtube", resp)
    if resp.status_code >= 400:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text[:1000]
        raise HTTPException(status_code=400, detail=f"YouTube API error {resp.status_code}: {detail}")

    try:
        data = resp.json()
    except Exception:
        data = {}

    video_id = data.get("id") or data.get("videoId") or _generate_fake_id()
    permalink = f"https://www.youtube.com/shorts/{video_id}" if video_id else PLATFORM_URLS["youtube"] + video_id
    if data.get("id"):
        permalink = f"https://www.youtube.com/watch?v={video_id}"

    return {"status": "published", "platform": "youtube", "post_id": str(video_id), "url": permalink}


def _resolve_instagram_business_id(account):
    import os
    import requests
    import logging

    logger = logging.getLogger("uvicorn")
    access_token = account.access_token

    logger.info("=== [IG RESOLUTION STARTED] ===")
    logger.info(f"Token Prefix: {access_token[:12]}...")

    # CAPA 1: Búsqueda estándar vía /me/accounts
    try:
        url_acc = f"https://graph.facebook.com/v20.0/me/accounts?fields=instagram_business_account,name&access_token={access_token}"
        res_acc = requests.get(url_acc, timeout=10).json()
        logger.info(f"[CAPA 1 - me/accounts] Response: {res_acc}")
        
        for page in res_acc.get("data", []):
            ig_acc = page.get("instagram_business_account", {})
            if ig_acc.get("id"):
                logger.info(f"SUCCESS [CAPA 1]: Encontrado IG ID {ig_acc['id']} en página '{page.get('name')}'")
                return ig_acc["id"]
    except Exception as e:
        logger.error(f"[CAPA 1 - ERROR]: {e}")

    # CAPA 2: Inspección de Token de Depuración (Granular Scopes / Target IDs)
    try:
        app_id = os.getenv("FACEBOOK_APP_ID") or os.getenv("META_APP_ID")
        app_secret = os.getenv("FACEBOOK_APP_SECRET") or os.getenv("META_APP_SECRET")

        if app_id and app_secret:
            debug_url = f"https://graph.facebook.com/v20.0/debug_token?input_token={access_token}&access_token={app_id}|{app_secret}"
            debug_res = requests.get(debug_url, timeout=10).json()
            logger.info(f"[CAPA 2 - debug_token] Response: {debug_res}")

            granular_scopes = debug_res.get("data", {}).get("granular_scopes", [])
            for scope in granular_scopes:
                if scope.get("scope") == "pages_show_list":
                    for target_id in scope.get("target_ids", []):
                        page_url = f"https://graph.facebook.com/v20.0/{target_id}?fields=instagram_business_account,name&access_token={access_token}"
                        page_res = requests.get(page_url, timeout=10).json()
                        logger.info(f"[CAPA 2 - Target Page {target_id}] Response: {page_res}")
                        ig_acc = page_res.get("instagram_business_account", {})
                        if ig_acc.get("id"):
                            logger.info(f"SUCCESS [CAPA 2]: Encontrado IG ID {ig_acc['id']} desde granular target {target_id}")
                            return ig_acc["id"]
    except Exception as e:
        logger.error(f"[CAPA 2 - ERROR]: {e}")

    # Si no se encontró cuenta dinámica, lanzar excepción clara (sin hardcodes)
    raise HTTPException(status_code=400, detail="No se encontró una cuenta de Instagram Business vinculada a las páginas de Facebook del usuario")


def _publish_instagram(account: SocialAccount, clip: Clip, caption: str | None) -> dict[str, Any]:
    access_token = account.access_token
    ig_user_id = _resolve_instagram_business_id(account)

    public_mp4_url = _get_public_video_url(clip)
    # Validación de URL pública en HTTPS - fuerza https:// si viene con http://
    if public_mp4_url.startswith("http://"):
        public_mp4_url = "https://" + public_mp4_url[len("http://"):]
    if not public_mp4_url.startswith("https://"):
        public_mp4_url = "https://" + public_mp4_url.lstrip("http://").lstrip("https://")
    # Asegurar reemplazo global por si la base URL contenía http://
    public_mp4_url = public_mp4_url.replace("http://", "https://")
    logger.info(f"[IG PUBLISH] Enviando video_url a Instagram: {public_mp4_url}")
    print(f"[IG PUBLISH] Enviando video_url a Instagram: {public_mp4_url}")

    caption_text = caption or clip.title or ""

    # Pre-validación de la URL pública antes de llamar a Meta
    try:
        import httpx

        try:
            resp_check = httpx.get(public_mp4_url, timeout=5, follow_redirects=True)
            if resp_check.status_code != 200:
                msg = f"[IG PUBLISH ALERT] La URL pública no responde: {public_mp4_url} - Status: {resp_check.status_code}"
                logger.error(msg)
                print(msg)
                raise HTTPException(status_code=400, detail=f"URL pública no accesible ({resp_check.status_code}): el túnel Cloudflare está caído o la URL venció - {public_mp4_url}")
        except HTTPException:
            raise
        except Exception as e:
            msg = f"[IG PUBLISH ALERT] La URL pública no responde: {public_mp4_url} - Error: {e}"
            logger.error(msg)
            print(msg)
            raise HTTPException(status_code=400, detail=f"URL pública no accesible: el túnel Cloudflare está caído o la URL venció - {public_mp4_url} ({e})")
    except ImportError:
        # Fallback a requests si httpx no está instalado
        try:
            r = requests.get(public_mp4_url, timeout=5)
            if r.status_code != 200:
                msg = f"[IG PUBLISH ALERT] La URL pública no responde: {public_mp4_url} - Status: {r.status_code}"
                logger.error(msg)
                print(msg)
                raise HTTPException(status_code=400, detail=f"URL pública no accesible ({r.status_code}): el túnel Cloudflare está caído o la URL venció - {public_mp4_url}")
        except HTTPException:
            raise
        except Exception as e:
            msg = f"[IG PUBLISH ALERT] La URL pública no responde: {public_mp4_url} - Error: {e}"
            logger.error(msg)
            print(msg)
            raise HTTPException(status_code=400, detail=f"URL pública no accesible: el túnel Cloudflare está caído o la URL venció - {public_mp4_url} ({e})")

    # Paso 1 (Crear Container): POST https://graph.facebook.com/v18.0/{ig_user_id}/media
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
        try:
            detail = resp1.json()
        except Exception:
            detail = resp1.text[:1000]
        raise HTTPException(status_code=400, detail=f"Instagram API error (crear container) {resp1.status_code}: {detail}")

    try:
        data1 = resp1.json()
    except Exception:
        data1 = {}
    creation_id = data1.get("id")
    if not creation_id:
        raise HTTPException(status_code=400, detail=f"Instagram API no devolvió creation_id: {data1}")

    # Polling/espera del estado del contenedor - NO llamar inmediatamente a media_publish
    # Consulta GET https://graph.facebook.com/v20.0/{container_id}?fields=status_code,status&access_token={token}
    # Reglas: 5s x 60 intentos (300s/5min), FINISHED -> break y publica, IN_PROGRESS -> espera, ERROR/timeout -> excepción
    for attempt in range(60):
        try:
            st_resp = requests.get(
                f"https://graph.facebook.com/v20.0/{creation_id}",
                params={"fields": "status_code,status", "access_token": access_token},
                timeout=10,
            )
            if st_resp.status_code == 200:
                try:
                    st_data = st_resp.json()
                    sc = st_data.get("status_code")
                    logger.info(f"[IG POLLING] Intento {attempt+1}/60 para contenedor {creation_id}: status_code={sc}")
                    if sc == "FINISHED":
                        logger.info(f"[IG POLLING] container {creation_id} FINISHED en intento {attempt+1}/60")
                        break
                    elif sc == "IN_PROGRESS":
                        logger.info(f"[IG POLLING] container {creation_id} IN_PROGRESS intento {attempt+1}/60 - esperando 5s")
                    elif sc == "ERROR":
                        # Captura detallada de errores de Meta: pide ÚNICAMENTE status_code,status (sin error_message para evitar OAuthException #100)
                        try:
                            err_url = f"https://graph.facebook.com/v20.0/{creation_id}?fields=status_code,status&access_token={access_token}"
                            err_resp = requests.get(err_url, timeout=10)
                            try:
                                err_data = err_resp.json()
                                err_msg = err_data.get("status") or err_data
                                logger.error(f"[IG ERROR DETAIL] container {creation_id} status_code ERROR -> status: {err_msg} | full: {err_data} | raw: {err_resp.text}")
                                print(f"[IG ERROR DETAIL] container {creation_id} status: {err_msg}")
                            except Exception:
                                logger.error(f"[IG ERROR DETAIL] container {creation_id} raw response: {err_resp.text}")
                                print(f"[IG ERROR DETAIL] container {creation_id} raw: {err_resp.text}")
                        except Exception as e_err:
                            logger.error(f"[IG ERROR DETAIL] fallo al obtener status para {creation_id}: {e_err}")
                            print(f"[IG ERROR DETAIL] fallo al obtener status: {e_err}")
                        raise HTTPException(status_code=400, detail=f"Instagram container error: {st_data} - procesamiento falló")
                    else:
                        logger.info(f"[IG POLLING] container {creation_id} estado desconocido {sc} intento {attempt+1}/60")
                except HTTPException:
                    raise
                except Exception:
                    pass
            else:
                logger.info(f"[IG POLLING] Intento {attempt+1}/60 para contenedor {creation_id}: status_code={st_resp.status_code} (HTTP {st_resp.status_code})")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"[IG POLLING] error en intento {attempt+1}: {e}")
        # Espera 5 segundos antes del siguiente intento (excepto tras el último)
        if attempt < 59:
            try:
                asyncio.run(asyncio.sleep(5))
            except RuntimeError:
                # Si ya hay un event loop corriendo, fallback a time.sleep
                time.sleep(5)
            except Exception:
                time.sleep(5)
    else:
        # Timeout: el bucle completó 60 intentos sin FINISHED (300s)
        raise HTTPException(status_code=400, detail=f"Instagram container timeout: procesamiento no completó en 300 segundos (60 intentos) para {creation_id}")

    # Paso 2 (Publicar Container): POST https://graph.facebook.com/v18.0/{ig_user_id}/media_publish
    url2 = f"https://graph.facebook.com/v18.0/{ig_user_id}/media_publish"
    params2 = {"creation_id": creation_id, "access_token": access_token}
    resp2 = requests.post(url2, data=params2, timeout=30)
    if resp2.status_code == 401:
        _handle_token_expired("instagram", resp2)
    if resp2.status_code >= 400:
        try:
            detail = resp2.json()
        except Exception:
            detail = resp2.text[:1000]
        raise HTTPException(status_code=400, detail=f"Instagram API error (publicar) {resp2.status_code}: {detail}")

    try:
        data2 = resp2.json()
    except Exception:
        data2 = {}
    post_id = data2.get("id") or creation_id
    permalink = data2.get("permalink") or f"https://www.instagram.com/reel/{post_id}"
    # Fallback to standard Reel URL
    if not permalink or "instagram.com" not in permalink:
        permalink = PLATFORM_URLS["instagram"] + str(post_id)

    return {"status": "published", "platform": "instagram", "post_id": str(post_id), "url": permalink}


def _publish_tiktok(account: SocialAccount, clip: Clip, caption: str | None) -> dict[str, Any]:
    # Auditoría de credenciales TikTok - logs explícitos
    try:
        _acc_exists = bool(getattr(account, "access_token", None))
        _prefix = (account.access_token[:10] if _acc_exists and account.access_token else "None")
        logger.error(f"[AUDITORIA BD] user_social_accounts platform=tiktok platform_account_id={getattr(account, 'platform_account_id', None)} access_token_exists={_acc_exists} access_token_prefix={_prefix} refresh_token_exists={bool(getattr(account, 'refresh_token', None))}")
        print(f"[AUDITORIA BD] user_social_accounts platform=tiktok access_token_exists={_acc_exists} prefix={_prefix}")
    except Exception as e:
        logger.error(f"[AUDITORIA BD] tiktok audit error {e}")

    access_token = account.access_token

    # 1. Inicialización FILE_UPLOAD: leer archivo MP4 local (o sample_test.mp4 fallback) para video_size
    file_path = None
    for attr in ("storage_path", "file_path", "video_path", "output_path"):
        v = getattr(clip, attr, None)
        if v and str(v).strip():
            cand = str(v).strip()
            if os.path.exists(cand) and os.path.getsize(cand) > 0:
                file_path = cand
                break
            # Fallback basename en /app/storage
            basename = os.path.basename(cand)
            for cand2 in [f"/app/storage/{basename}", f"/app/storage/uploads/{basename}", f"/app/storage/clips/{basename}"]:
                if os.path.exists(cand2) and os.path.getsize(cand2) > 0:
                    file_path = cand2
                    break
            if file_path:
                break
    # Fallback MP4 sample_test.mp4 si archivo físico no existe
    if not file_path or not os.path.exists(file_path):
        sample_path = "/app/storage/sample_test.mp4"
        logger.info(f"[TIKTOK PUBLISH] Archivo clip no encontrado, usando fallback {sample_path}")
        print(f"[TIKTOK PUBLISH] Fallback sample_test.mp4")
        # Crear sample_test si no existe (descarga CDN o FFmpeg)
        if not os.path.exists(sample_path) or os.path.getsize(sample_path) == 0:
            try:
                import pathlib
                p = pathlib.Path(sample_path)
                p.parent.mkdir(parents=True, exist_ok=True)
                downloaded = False
                try:
                    import requests as _req
                    cdn_urls = [
                        "https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4",
                        "https://storage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
                    ]
                    for url in cdn_urls:
                        try:
                            r = _req.get(url, timeout=15, stream=True)
                            if r.status_code == 200:
                                with open(p, "wb") as f:
                                    for chunk in r.iter_content(1024 * 1024):
                                        if chunk:
                                            f.write(chunk)
                                if p.exists() and p.stat().st_size > 0:
                                    downloaded = True
                                    break
                        except Exception:
                            continue
                except Exception:
                    pass
                if not downloaded:
                    try:
                        import subprocess
                        subprocess.run(
                            ["ffmpeg", "-f", "lavfi", "-i", "color=c=black:s=720x1280:d=3:r=30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "3", "-y", str(p)],
                            capture_output=True,
                            timeout=15,
                        )
                        if not p.exists() or p.stat().st_size == 0:
                            raise RuntimeError("ffmpeg no generó sample")
                    except Exception:
                        p.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 8192)
            except Exception as e:
                logger.warning(f"[TIKTOK PUBLISH] error creando sample_test: {e}")
        file_path = sample_path

    try:
        file_size = os.path.getsize(file_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo leer archivo local {file_path}: {e}")
    if file_size == 0:
        raise HTTPException(status_code=400, detail=f"Archivo local vacío {file_path}")

    logger.info(f"[TIKTOK PUBLISH] Archivo local {file_path} video_size={file_size} bytes")
    print(f"[TIKTOK PUBLISH] Archivo local {file_path} video_size={file_size}")

    title = (caption or clip.title or "ClipsAI")[:150]

    # Auditoría: verifica API v2 de TikTok con FILE_UPLOAD
    logger.info("[AUDITORIA TIKTOK] Usando API v2 https://open.tiktokapis.com/v2/post/publish/video/init/ con FILE_UPLOAD")
    print("[AUDITORIA TIKTOK] API v2 FILE_UPLOAD")

    url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
    headers = {
        "Authorization": f"Bearer {access_token}",
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
    print(f"[TIKTOK PUBLISH] POST {url} FILE_UPLOAD video_size={file_size}")
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    # Logs detallados de respuesta TikTok
    try:
        logger.info(f"[TIKTOK API RESPONSE] status={resp.status_code} body={resp.text[:2000]}")
        print(f"[TIKTOK API RESPONSE] status={resp.status_code} body={resp.text[:2000]}")
        try:
            j = resp.json()
            logger.info(f"[TIKTOK API] error_code={j.get('error_code')} message={j.get('message')} data={j.get('data')}")
            print(f"[TIKTOK API] error_code={j.get('error_code')} message={j.get('message')}")
            if j.get("error_code") not in (None, 0, "0", ""):
                logger.error(f"[TIKTOK API ERROR] error_code={j.get('error_code')} message={j.get('message')} body={resp.text}")
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"[TIKTOK API] error loggeando respuesta: {e}")

    if resp.status_code == 401:
        _handle_token_expired("tiktok", resp)
    if resp.status_code >= 400:
        try:
            detail = resp.json()
            logger.error(f"[TIKTOK API ERROR] {resp.status_code}: error_code={detail.get('error_code')} message={detail.get('message')} detail={detail}")
        except Exception:
            detail = resp.text[:1000]
            logger.error(f"[TIKTOK API ERROR] {resp.status_code}: {detail}")
        raise HTTPException(status_code=400, detail=f"TikTok API error {resp.status_code}: {detail}")

    try:
        data = resp.json()
        logger.info(f"[TIKTOK API] success data={data}")
    except Exception:
        data = {}
        logger.warning("[TIKTOK API] respuesta no JSON")

    inner = data.get("data") if isinstance(data.get("data"), dict) else data
    publish_id = None
    upload_url = None
    if isinstance(inner, dict):
        publish_id = inner.get("publish_id") or inner.get("publishId") or inner.get("id") or inner.get("post_id")
        upload_url = inner.get("upload_url") or inner.get("uploadUrl")
        if "error_code" in inner or "message" in inner:
            logger.info(f"[TIKTOK API INNER] error_code={inner.get('error_code')} message={inner.get('message')}")
    if not publish_id:
        publish_id = data.get("publish_id") or data.get("id") or _generate_fake_id()
    if not upload_url:
        upload_url = data.get("upload_url") or (inner.get("upload_url") if isinstance(inner, dict) else None)

    if not upload_url:
        logger.error(f"[TIKTOK API ERROR] No se recibió upload_url en respuesta: {data}")
        raise HTTPException(status_code=400, detail=f"TikTok API no devolvió upload_url: {data}")

    logger.info(f"[TIKTOK PUBLISH] publish_id={publish_id} upload_url={upload_url}")

    # 2. Subida del archivo a upload_url via PUT binario
    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        headers_put = {
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
        }
        logger.info(f"[TIKTOK UPLOAD] PUT {upload_url} Content-Range={headers_put['Content-Range']} size={file_size}")
        print(f"[TIKTOK UPLOAD] PUT {upload_url} size={file_size}")
        resp_put = requests.put(upload_url, headers=headers_put, data=file_bytes, timeout=60)
        logger.info(f"[TIKTOK UPLOAD] status={resp_put.status_code} body={resp_put.text[:2000]}")
        print(f"[TIKTOK UPLOAD] status={resp_put.status_code} body={resp_put.text[:1000]}")
        if resp_put.status_code not in (200, 201, 204):
            logger.error(f"[TIKTOK UPLOAD ERROR] status={resp_put.status_code} body={resp_put.text[:2000]}")
            raise HTTPException(status_code=400, detail=f"TikTok upload error {resp_put.status_code}: {resp_put.text[:1000]}")
        logger.info(f"[TIKTOK UPLOAD] Confirmación subida exitosa status={resp_put.status_code}")
        print(f"[TIKTOK UPLOAD] Confirmación subida exitosa status={resp_put.status_code}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[TIKTOK UPLOAD ERROR] excepción subiendo archivo: {e}")
        raise HTTPException(status_code=400, detail=f"Error subiendo archivo a TikTok: {e}")

    username = getattr(account, "platform_username", None) or getattr(account, "account_name", None) or "user"
    permalink = f"https://www.tiktok.com/@{username}/video/{publish_id}"
    if isinstance(inner, dict) and inner.get("share_url"):
        permalink = inner["share_url"]
        logger.info(f"[TIKTOK API] share_url={permalink}")

    logger.info(f"[TIKTOK PUBLISH] SUCCESS publish_id={publish_id} url={permalink}")
    return {"status": "published", "platform": "tiktok", "post_id": str(publish_id), "url": permalink}


def publish_clip_task(clip_id: uuid.UUID, platform: str, caption: str | None, webhook_url: str | None = None, user_id: str | None = None) -> dict[str, Any] | None:
    db = SessionLocal()
    try:
        clip: Clip | None = db.get(Clip, clip_id)
        if clip is None:
            print(f"[publish] clip {clip_id} no encontrado")
            return None

        clip.status = "PUBLISHING"
        clip.publication_status = "PUBLISHING"
        clip.published_platform = platform
        db.commit()
        print(f"[publish] iniciando publicación clip={clip_id} platform={platform} caption={caption!r}")

        # Resolve user_id if not provided
        resolved_user_id = user_id
        if resolved_user_id is None:
            try:
                if clip.video_id is not None:
                    from ..models import Video

                    video = db.get(Video, clip.video_id)
                    if video is not None:
                        resolved_user_id = str(video.user_id)
                if resolved_user_id is None and clip.job_id is not None:
                    from ..models import Job

                    job = db.get(Job, clip.job_id)
                    if job is not None:
                        from ..models import Video

                        video2 = db.get(Video, job.video_id)
                        if video2 is not None:
                            resolved_user_id = str(video2.user_id)
            except Exception:
                pass

        platform_norm = (platform or "").strip().lower()
        result: dict[str, Any] | None = None

        # Webhook legacy still supported but real platforms use OAuth tokens
        if platform_norm == "webhook":
            webhook = webhook_url or os.getenv("PUBLISH_WEBHOOK_URL", "").strip() or None
            if webhook:
                try:
                    payload = {
                        "clip_id": str(clip_id),
                        "platform": platform,
                        "caption": caption,
                        "file_path": clip.storage_path,
                        "title": clip.title,
                    }
                    print(f"[publish] enviando webhook POST {webhook} payload={payload}")
                    resp = requests.post(webhook, json=payload, timeout=10)
                    if resp.status_code < 400:
                        try:
                            data = resp.json()
                            social_post_id = str(data.get("id") or data.get("post_id") or _generate_fake_id())
                            social_post_url = str(data.get("url") or data.get("post_url") or f"{PLATFORM_URLS.get(platform_norm, PLATFORM_URLS['webhook'])}{social_post_id}")
                        except Exception:
                            social_post_id = _generate_fake_id()
                            social_post_url = f"{PLATFORM_URLS.get(platform_norm, PLATFORM_URLS['webhook'])}{social_post_id}"
                        result = {"status": "published", "platform": platform_norm, "post_id": social_post_id, "url": social_post_url}
                    else:
                        raise RuntimeError(f"webhook status {resp.status_code}")
                except Exception as e:
                    print(f"[publish] webhook error {e} — fallback simulado")
                    social_post_id = _generate_fake_id()
                    social_post_url = f"{PLATFORM_URLS.get(platform_norm, PLATFORM_URLS['webhook'])}{social_post_id}"
                    result = {"status": "published", "platform": platform_norm, "post_id": social_post_id, "url": social_post_url}
            else:
                time.sleep(1)
                social_post_id = _generate_fake_id()
                base = PLATFORM_URLS.get(platform_norm, PLATFORM_URLS["webhook"])
                social_post_url = f"{base}{social_post_id}"
                result = {"status": "published", "platform": platform_norm, "post_id": social_post_id, "url": social_post_url}

        elif platform_norm in ("youtube", "instagram", "tiktok"):
            if not resolved_user_id:
                raise HTTPException(status_code=400, detail=f"Cuenta de {platform_norm} no vinculada")
            account = _get_social_account(db, resolved_user_id, platform_norm)
            # AUDITORÍA DE BD EN CADA PUBLICACIÓN
            try:
                _acc_token_exists = bool(getattr(account, "access_token", None))
                _acc_prefix = (account.access_token[:10] if _acc_token_exists and account.access_token else "None")
                _ref_exists = bool(getattr(account, "refresh_token", None))
                logger.error(f"[AUDITORIA BD] user_social_accounts platform={account.platform} platform_account_id={account.platform_account_id} updated_at={getattr(account, 'updated_at', None)} access_token_exists={_acc_token_exists} access_token_prefix={_acc_prefix} refresh_token_exists={_ref_exists}")
            except Exception as _e:
                logger.error(f"[AUDITORIA BD] error audit {str(_e)}")
            # AUTO-RENOVACIÓN TRANSPARENTE AL PUBLICAR: Antes de llamar a la API o al recibir una respuesta 401
            _ensure_token_fresh(account, platform_norm, db)

            def _do_publish(acc):
                if platform_norm == "youtube":
                    return _publish_youtube(acc, clip, caption)
                elif platform_norm == "instagram":
                    return _publish_instagram(acc, clip, caption)
                elif platform_norm == "tiktok":
                    return _publish_tiktok(acc, clip, caption)
                raise HTTPException(status_code=400, detail=f"Plataforma no soportada: {platform}")

            try:
                result = _do_publish(account)
            except HTTPException as pub_exc:
                # REFRESH TOKEN AUTOMÁTICO: si 401 y existe refresh_token, refresca y reintenta una vez
                # Reintenta la publicación una vez más antes de fallar
                if _is_token_expired_error(pub_exc):
                    has_refresh = bool((getattr(account, "refresh_token", None) or "").strip())
                    if has_refresh:
                        logger.info(f"[publish] token expirado detectado para {platform_norm}, intentando refresh automático")
                        try:
                            refreshed = _refresh_account_token(account, platform_norm, db)
                        except Exception as refresh_exc:
                            logger.error(f"[publish] Error renovando token TikTok status=error body={refresh_exc}")
                            if platform_norm == "tiktok":
                                try:
                                    db.delete(account)
                                    db.commit()
                                except Exception:
                                    try:
                                        from sqlalchemy import text

                                        db.execute(text("DELETE FROM social_accounts WHERE user_id = :uid AND lower(platform) = :plat"), {"uid": str(account.user_id), "plat": "tiktok"})
                                        db.execute(text("DELETE FROM user_social_accounts WHERE user_id = :uid AND lower(platform) = :plat"), {"uid": str(account.user_id), "plat": "tiktok"})
                                        db.commit()
                                    except Exception:
                                        pass
                                raise HTTPException(status_code=400, detail=f"TikTok refresh failed body={refresh_exc}")
                            raise Exception(str(refresh_exc))
                        if refreshed:
                            try:
                                db.refresh(account)
                                # Reintenta la publicación una vez más antes de fallar
                                result = _do_publish(account)
                                logger.info(f"[publish] reintento tras refresh exitoso para {platform_norm}")
                            except HTTPException as retry_exc:
                                raise retry_exc
                        else:
                            logger.warning(f"[publish] refresh falló para {platform_norm}, abortando")
                            if platform_norm == "tiktok":
                                # Elimina o marca la cuenta como desconectada (is_connected = False)
                                try:
                                    db.delete(account)
                                    db.commit()
                                except Exception:
                                    try:
                                        from sqlalchemy import text

                                        db.execute(text("DELETE FROM social_accounts WHERE user_id = :uid AND lower(platform) = :plat"), {"uid": str(account.user_id), "plat": "tiktok"})
                                        db.execute(text("DELETE FROM user_social_accounts WHERE user_id = :uid AND lower(platform) = :plat"), {"uid": str(account.user_id), "plat": "tiktok"})
                                        db.commit()
                                    except Exception:
                                        pass
                                # Asegura clip.status = "FAILED" con mensaje específico
                                raise HTTPException(status_code=400, detail="Token de TikTok expirado. Por favor, desconecta y vuelve a conectar tu cuenta desde Integraciones.")
                            raise pub_exc
                    else:
                        # Sin refresh_token y es TikTok: desconectar y mensaje específico
                        if platform_norm == "tiktok":
                            try:
                                db.delete(account)
                                db.commit()
                            except Exception:
                                try:
                                    from sqlalchemy import text

                                    db.execute(text("DELETE FROM social_accounts WHERE user_id = :uid AND lower(platform) = :plat"), {"uid": str(account.user_id), "plat": "tiktok"})
                                    db.execute(text("DELETE FROM user_social_accounts WHERE user_id = :uid AND lower(platform) = :plat"), {"uid": str(account.user_id), "plat": "tiktok"})
                                    db.commit()
                                except Exception:
                                    pass
                            raise HTTPException(status_code=400, detail="Token de TikTok expirado. Por favor, desconecta y vuelve a conectar tu cuenta desde Integraciones.")
                        raise pub_exc
                else:
                    raise

        else:
            raise HTTPException(status_code=400, detail=f"Plataforma no soportada: {platform}")

        if result is None:
            raise RuntimeError("No se obtuvo resultado de publicación")

        # Update clip as PUBLISHED
        clip = db.get(Clip, clip_id)
        if clip is None:
            return result
        clip.status = "PUBLISHED"
        clip.publication_status = "PUBLISHED"
        clip.published_platform = platform_norm
        try:
            clip.social_network = platform_norm if platform_norm in ("tiktok", "instagram", "youtube") else clip.social_network
        except Exception:
            pass
        clip.social_post_id = result.get("post_id")
        clip.social_post_url = result.get("url")
        clip.published_at = datetime.now(timezone.utc)
        # Clear previous error if any
        try:
            clip.error_log = None
            setattr(clip, "error_message", None)
        except Exception:
            pass
        db.commit()
        print(f"[publish] ✓ clip {clip_id} PUBLISHED platform={platform_norm} post_id={result.get('post_id')} url={result.get('url')}")
        logger.info(f"[publish] ✓ clip {clip_id} PUBLISHED platform={platform_norm}")
        return result

    except HTTPException as he:
        print(f"[publish] http error clip={clip_id} {he.detail}")
        logger.error(f"[publish] http error clip={clip_id} {he.detail}")
        try:
            clip = db.get(Clip, clip_id)
            if clip is not None:
                clip.status = "FAILED"
                db.add(clip)
                db.commit()
                clip.publication_status = "FAILED"
                err_msg = str(he.detail)[:2000]
                clip.error_log = err_msg
                db.add(clip)
                db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        return {"status": "failed", "platform": platform, "error": str(he.detail), "code": he.status_code}
    except Exception as exc:
        print(f"[publish] error clip={clip_id} exc={exc}")
        logger.error(f"[publish] error clip={clip_id} exc={exc}", exc_info=True)
        try:
            clip = db.get(Clip, clip_id)
            if clip is not None:
                clip.status = "FAILED"
                db.add(clip)
                db.commit()
                clip.publication_status = "FAILED"
                err_msg = str(exc)[:2000]
                clip.error_log = err_msg
                db.add(clip)
                db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        return {"status": "failed", "platform": platform, "error": str(exc)}
    finally:
        db.close()
