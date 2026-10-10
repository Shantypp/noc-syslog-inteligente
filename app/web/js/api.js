/**
 * api.js — Comunicación con el backend (FastAPI).
 * Todas las vistas usan estas funciones en lugar de llamar fetch() directamente.
 */

/** Convierte el error de FastAPI en un texto legible. */
function textoError(data, status) {
  if (!data) return `Error ${status}`;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    // Errores de validación (422): [{loc: [...], msg: "..."}]
    return data.detail.map((d) => `${d.loc.slice(1).join(".")}: ${d.msg}`).join(" · ");
  }
  return `Error ${status}`;
}

/**
 * Llama a la API.
 *   api("/api/devices")
 *   api("/api/devices", { method: "POST", body: {...} })
 *   api("/api/events", { query: { sev_max: 3 } })
 */
export async function api(ruta, { method = "GET", body, query } = {}) {
  const url = new URL(ruta, location.origin);
  for (const [k, v] of Object.entries(query || {})) {
    if (v !== "" && v !== null && v !== undefined) url.searchParams.set(k, v);
  }
  const resp = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (resp.status === 204) return null;
  const data = await resp.json().catch(() => null);
  if (resp.status === 401 && !ruta.startsWith("/api/auth/")) window.dispatchEvent(new Event("noc:sesion-vencida"));
  if (!resp.ok) throw new Error(textoError(data, resp.status));
  return data;
}

/** Sube un archivo (multipart/form-data). */
export async function subirArchivo(ruta, archivo) {
  const form = new FormData();
  form.append("archivo", archivo);
  const resp = await fetch(ruta, { method: "POST", body: form });
  const data = await resp.json().catch(() => null);
  if (!resp.ok) throw new Error(textoError(data, resp.status));
  return data;
}
