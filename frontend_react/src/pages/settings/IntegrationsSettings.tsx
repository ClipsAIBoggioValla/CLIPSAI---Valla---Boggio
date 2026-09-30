// @ts-nocheck
import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";

// Compatibilidad con ambos sistemas: intenta importar http de @/lib/apiClient (frontend_react) o fallback a fetch nativo
let http: any = null;
let ApiError: any = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const mod = require("@/lib/apiClient");
  http = mod.http;
  const types = require("@/types/api");
  ApiError = types.ApiError;
} catch {
  // fallback será fetch directo
}

type SocialEntry = { connected: boolean; username: string | null; expires_at: string | null };
type SocialStatus = { youtube: SocialEntry; instagram: SocialEntry; tiktok: SocialEntry };
type Platform = "youtube" | "instagram" | "tiktok";

const PLATFORMS: { id: Platform; label: string; logo: string; desc: string; bg: string }[] = [
  { id: "youtube", label: "YouTube", logo: "bi-youtube", desc: "Google Data API v3 — Shorts", bg: "bg-[#FF0000]/10 border-[#FF0000]/20 text-[#FF0000]" },
  { id: "instagram", label: "Instagram", logo: "bi-instagram", desc: "Meta Graph API — Reels", bg: "bg-[#E1306C]/10 border-[#E1306C]/20 text-[#E1306C]" },
  { id: "tiktok", label: "TikTok", logo: "bi-tiktok", desc: "TikTok Content Posting API", bg: "bg-black border-white/20 text-white" },
];

function getAuthHeader(): Record<string, string> | undefined {
  try {
    const t = localStorage.getItem("clipsai_token") || localStorage.getItem("token");
    return t ? { Authorization: `Bearer ${t}` } : undefined;
  } catch {
    return undefined;
  }
}

async function apiGet<T>(path: string): Promise<T> {
  if (http?.get) {
    const headers = getAuthHeader();
    return http.get<T>(path, headers ? { headers } : undefined);
  }
  const headers: Record<string, string> = { Accept: "application/json", "ngrok-skip-browser-warning": "true" };
  const auth = getAuthHeader();
  if (auth) Object.assign(headers, auth);
  const base = (import.meta as any)?.env?.VITE_API_URL || "http://localhost:8000";
  const res = await fetch(`${base.replace(/\/$/, "")}${path}`, { headers, credentials: "include" });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

async function apiDelete(path: string): Promise<void> {
  if (http?.delete) {
    const headers = getAuthHeader();
    return http.delete(path, headers ? { headers } : undefined);
  }
  const headers: Record<string, string> = { Accept: "application/json", "ngrok-skip-browser-warning": "true" };
  const auth = getAuthHeader();
  if (auth) Object.assign(headers, auth);
  const base = (import.meta as any)?.env?.VITE_API_URL || "http://localhost:8000";
  const res = await fetch(`${base.replace(/\/$/, "")}${path}`, { method: "DELETE", headers, credentials: "include" });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `HTTP ${res.status}`);
  }
}

export default function IntegrationsSettings() {
  const [searchParams, setSearchParams] = useSearchParams();
  const integration = searchParams.get("integration");
  const statusParam = searchParams.get("status");
  const errorDetail = searchParams.get("error") || searchParams.get("message");

  const [social, setSocial] = useState<SocialStatus | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [loadingAction, setLoadingAction] = useState<Platform | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [confirmPlatform, setConfirmPlatform] = useState<Platform | null>(null);

  const fetchStatus = useCallback(async () => {
    setLoadingStatus(true);
    setError(null);
    try {
      const data = await apiGet<SocialStatus>("/auth/social/status");
      setSocial(data);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Error al cargar estado de integraciones";
      setError(msg);
    } finally {
      setLoadingStatus(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  useEffect(() => {
    if (statusParam === "success") fetchStatus();
  }, [statusParam, fetchStatus]);

  useEffect(() => {
    if (statusParam) {
      const t = setTimeout(() => {
        const next = new URLSearchParams(searchParams);
        next.delete("integration");
        next.delete("status");
        next.delete("error");
        next.delete("message");
        setSearchParams(next, { replace: true });
      }, 5000);
      return () => clearTimeout(t);
    }
  }, [statusParam, searchParams, setSearchParams]);

  const handleConnect = async (platform: Platform) => {
    setLoadingAction(platform);
    setError(null);
    setSuccess(null);
    try {
      const data = await apiGet<{ auth_url?: string; url?: string }>(`/auth/social/${platform}/connect`);
      const url = (data as any).auth_url || (data as any).url;
      if (!url) {
        setError("No se recibió url de OAuth del backend");
        return;
      }
      // Validación básica de dominio esperado
      const expected = platform === "youtube" ? "accounts.google.com" : platform === "instagram" ? "facebook.com" : "tiktok.com";
      if (!url.includes(expected)) {
        console.warn("[Integrations] URL inesperada:", url);
      }
      window.location.href = url;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : `Error al conectar ${platform}`;
      setError(msg);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleDisconnect = async (platform: Platform) => {
    setLoadingAction(platform);
    setError(null);
    setSuccess(null);
    try {
      await apiDelete(`/auth/social/${platform}`);
      setSuccess(`${platform} desconectado correctamente`);
      setConfirmPlatform(null);
      await fetchStatus();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : `Error al desconectar ${platform}`;
      setError(msg);
    } finally {
      setLoadingAction(null);
    }
  };

  if (loadingStatus && !social) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="page-header mb-8">
          <div className="h-8 w-48 bg-white/10 rounded animate-pulse" />
          <div className="h-4 w-80 bg-white/5 rounded animate-pulse mt-3" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[0, 1, 2].map((i) => (
            <div key={i} className="card-spark p-5 animate-pulse">
              <div className="flex items-center gap-3 mb-4">
                <div className="h-10 w-10 rounded-xl bg-white/10" />
                <div className="flex-1">
                  <div className="h-4 w-20 bg-white/10 rounded mb-2" />
                  <div className="h-3 w-32 bg-white/5 rounded" />
                </div>
                <div className="h-6 w-20 bg-white/5 rounded-full" />
              </div>
              <div className="h-10 w-full bg-white/5 rounded-lg" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="page-header mb-8">
        <div className="flex items-center gap-4">
          <span className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-[#FF0000] text-white border border-white/10">
            <i className="bi bi-link-45deg" style={{ fontSize: "1.5rem" }} />
          </span>
          <div>
            <h1 className="text-2xl font-extrabold text-white leading-tight">Integraciones</h1>
            <p className="text-sm text-[#94A3B8]">Conecta tus redes sociales para publicación automática — Issue #28</p>
          </div>
        </div>
      </div>

      {/* Feedback OAuth redirect */}
      {integration && statusParam === "success" && (
        <div role="alert" className="mb-4 flex items-start gap-3 rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-4 text-emerald-300">
          <i className="bi bi-check-circle-fill mt-0.5" />
          <div className="text-sm">
            <strong className="capitalize">{integration} conectado correctamente</strong> — ya puedes publicar.
          </div>
        </div>
      )}
      {integration && statusParam === "error" && (
        <div role="alert" className="mb-4 flex items-start gap-3 rounded-lg border border-red-500/20 bg-red-500/10 p-4 text-red-300">
          <i className="bi bi-exclamation-triangle-fill mt-0.5" />
          <div className="text-sm">
            <strong>Error al conectar {integration}</strong> {errorDetail ? `— ${errorDetail}` : ""}.
          </div>
        </div>
      )}
      {success && (
        <div role="alert" className="mb-4 flex items-center justify-between rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3 text-sm text-emerald-300">
          <span>{success}</span>
          <button onClick={() => setSuccess(null)} className="text-emerald-300/70 hover:text-emerald-300">
            <i className="bi bi-x-lg" />
          </button>
        </div>
      )}
      {error && (
        <div role="alert" className="mb-4 flex items-center justify-between rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-300">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-300/70 hover:text-red-300">
            <i className="bi bi-x-lg" />
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {PLATFORMS.map((p) => {
          const entry = social?.[p.id];
          const isConnected = !!entry?.connected;
          const isLoading = loadingAction === p.id;
          return (
            <div key={p.id} className="card-spark flex flex-col p-5 border border-white/10 rounded-xl bg-[#0B0F17]/50">
              <div className="flex items-center gap-3 mb-3">
                <span className={`h-10 w-10 rounded-xl flex items-center justify-center text-xl border ${p.bg}`}>
                  <i className={`bi ${p.logo}`} />
                </span>
                <div className="flex-1 min-w-0">
                  <h3 className="font-bold text-white leading-tight">{p.label}</h3>
                  {isConnected && entry?.username ? (
                    <p className="text-xs font-mono text-emerald-300 truncate">@{entry.username}</p>
                  ) : (
                    <p className="text-xs text-[#94A3B8] truncate">{p.desc}</p>
                  )}
                </div>
                {isConnected ? (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/20 shrink-0">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" /> 🟢 Conectado
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-white/5 text-[#94A3B8] border border-white/10 shrink-0">
                    ⚪ Sin conectar
                  </span>
                )}
              </div>

              {isConnected ? (
                <button
                  onClick={() => setConfirmPlatform(p.id)}
                  disabled={!!loadingAction}
                  data-testid={`disconnect-${p.id}-btn`}
                  className="mt-auto w-full flex items-center justify-center gap-2 rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 disabled:opacity-50 py-2.5 text-sm font-medium transition-colors"
                >
                  {isLoading ? (
                    <>
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-red-400/30 border-t-red-400" /> Desconectando...
                    </>
                  ) : (
                    <>
                      <i className="bi bi-box-arrow-right" /> Desconectar
                    </>
                  )}
                </button>
              ) : (
                <button
                  onClick={() => handleConnect(p.id)}
                  disabled={!!loadingAction}
                  data-testid={`connect-${p.id}-btn`}
                  className="mt-auto w-full flex items-center justify-center gap-2 rounded-lg bg-[#B4F105] text-[#0B0F17] font-bold hover:opacity-90 disabled:opacity-50 py-2.5 text-sm transition-colors"
                >
                  {isLoading ? (
                    <>
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-[#0B0F17]/30 border-t-[#0B0F17]" /> Conectando...
                    </>
                  ) : (
                    <>
                      <i className="bi bi-box-arrow-up-right" /> Conectar
                    </>
                  )}
                </button>
              )}
              <p className="text-[11px] text-[#64748B] mt-2 text-center">
                {isConnected ? `Conectado ${entry?.expires_at ? `· expira ${new Date(entry.expires_at).toLocaleDateString()}` : ""}` : `GET /auth/social/${p.id}/connect`}
              </p>
            </div>
          );
        })}
      </div>

      {/* Modal confirmación desconectar */}
      {confirmPlatform && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setConfirmPlatform(null)} />
          <div className="relative w-full max-w-md rounded-xl border border-white/10 bg-[#141A26] p-6 shadow-xl">
            <h3 className="text-lg font-bold text-white mb-2">¿Desconectar {confirmPlatform}?</h3>
            <p className="text-sm text-[#94A3B8] mb-6">
              Se revocará el token y no podrás publicar en <strong className="text-white capitalize">{confirmPlatform}</strong> hasta reconectar. ¿Continuar?
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setConfirmPlatform(null)}
                className="px-4 py-2 rounded-lg bg-white/5 text-white border border-white/10 hover:bg-white/10 text-sm"
              >
                Cancelar
              </button>
              <button
                onClick={() => handleDisconnect(confirmPlatform)}
                disabled={!!loadingAction}
                className="px-4 py-2 rounded-lg bg-red-500 text-white hover:bg-red-600 disabled:opacity-50 text-sm font-medium"
              >
                {loadingAction ? "Desconectando..." : "Desconectar"}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="mt-6 rounded-xl border border-white/5 bg-[#0B0F17]/30 p-4">
        <h4 className="text-sm font-bold text-white mb-2 flex items-center gap-2">
          <i className="bi bi-info-circle text-[#B4F105]" /> Flujo OAuth
        </h4>
        <ol className="list-decimal list-inside text-xs text-[#94A3B8] space-y-1">
          <li>
            Al cargar, <code>GET /auth/social/status</code> consulta `social_accounts`/`user_social_accounts` para `tiktok`/`instagram`/`youtube`.
          </li>
          <li>
            Conectar → <code>GET /auth/social/{"{platform}"}/connect</code> → redirect a <code>url</code> (Google/Facebook/TikTok).
          </li>
          <li>Callback guarda tokens → redirige a <code>?integration={"{platform}"}&status=success</code>.</li>
          <li>
            Desconectar → <code>DELETE /auth/social/{"{platform}"}</code> → refresh <code>GET /auth/social/status</code>.
          </li>
        </ol>
      </div>
    </div>
  );
}
