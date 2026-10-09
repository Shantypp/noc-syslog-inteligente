/**
 * views/consola.js — Consola tipo PuTTY SIMULADA (RF-07).
 *
 * La decisión (permitido / bloqueado / propuesta / no verificado) la toma el BACKEND.
 * Si estuviera solo en JavaScript, cualquiera podría saltársela con F12.
 */
import { api } from "../api.js";
import { el, operador } from "../ui.js";

export const titulo = "Consola";
export const icono = "›_";

const PERFIL_POR_MARCA = { Cisco: "cisco_ios", Fortinet: "fortigate", Huawei: "huawei_vrp" };
const CLASE = { BLOQUEADO: "t-bloqueado", PROPUESTA: "t-propuesta", NO_VERIFICADO: "t-noverif" };

export async function render(cont) {
  const [perfiles, equipos] = await Promise.all([api("/api/console/perfiles"), api("/api/devices").catch(() => [])]);
  const porId = Object.fromEntries(perfiles.map((p) => [p.id, p]));

  const selEquipo = el("select", {}, el("option", { value: "" }, "(sin equipo)"), equipos.map((d) => el("option", { value: d.id }, `${d.nombre} · ${d.marca}`)));
  const selPerfil = el("select", {}, perfiles.map((p) => el("option", { value: p.id }, p.nombre)));
  const salida = el("div", { class: "salida", role: "log" });
  const prompt = el("span");
  const entrada = el("input", { autocomplete: "off", spellcheck: "false", "aria-label": "Comando" });
  const permitidos = el("div");
  const historial = [];
  let posHistorial = 0;

  const escribir = (texto, clase) => {
    salida.append(el("div", { class: clase }, texto));
    salida.scrollTop = salida.scrollHeight;
  };

  function cambiarPerfil() {
    const p = porId[selPerfil.value];
    prompt.textContent = p.prompt;
    permitidos.replaceChildren(el("h2", {}, `Lista permitida · ${p.nombre}`), el("pre", { class: "codigo" }, p.permitidos.join("\n")));
    escribir(`--- Perfil: ${p.nombre}. Escribe "help" para ver los comandos permitidos ---`, "t-info");
  }

  selEquipo.addEventListener("change", () => {
    const d = equipos.find((x) => String(x.id) === selEquipo.value);
    if (d && PERFIL_POR_MARCA[d.marca] && !(d.marca === "Cisco" && selPerfil.value === "cisco_rommon")) {
      selPerfil.value = PERFIL_POR_MARCA[d.marca];
    }
    cambiarPerfil();
  });
  selPerfil.addEventListener("change", cambiarPerfil);

  entrada.addEventListener("keydown", async (ev) => {
    if (ev.key === "ArrowUp" && historial.length) { posHistorial = Math.max(0, posHistorial - 1); entrada.value = historial[posHistorial]; return; }
    if (ev.key === "ArrowDown" && historial.length) { posHistorial = Math.min(historial.length, posHistorial + 1); entrada.value = historial[posHistorial] || ""; return; }
    if (ev.key !== "Enter") return;
    const comando = entrada.value;
    entrada.value = "";
    if (!comando.trim()) return;
    historial.push(comando); posHistorial = historial.length;
    escribir(`${prompt.textContent} ${comando}`);
    try {
      const r = await api("/api/console/ejecutar", { method: "POST", body: { perfil: selPerfil.value, comando, usuario: operador(), device_id: selEquipo.value ? Number(selEquipo.value) : null } });
      if (r.decision === "PERMITIDO") escribir(r.salida);
      else escribir(`% [${r.decision}] ${r.motivo}${r.decision === "PROPUESTA" ? ` (registro #${r.audit_id}: revísalo en Auditoría)` : ""}`, CLASE[r.decision]);
    } catch (e) {
      escribir(`% Error: ${e.message}`, "t-bloqueado");
    }
  });

  cont.replaceChildren(
    el("h1", {}, "Consola tipo PuTTY · SIMULACIÓN"),
    el("p", { class: "ayuda" }, "Solo lectura. No existe conexión a equipos reales. Todo comando queda en la auditoría con usuario, equipo, fecha y decisión."),
    el("div", { class: "filtros" }, el("label", {}, "Equipo", selEquipo), el("label", {}, "Perfil / modo", selPerfil)),
    el("div", { class: "grid-consola" },
      el("div", { class: "terminal", onclick: () => entrada.focus() },
        el("div", { class: "barra-titulo" }, el("span", {}, "● ● ●"), el("span", {}, "noc-console · SIMULACIÓN · solo lectura")),
        salida,
        el("div", { class: "linea-entrada" }, prompt, entrada)),
      el("section", { class: "panel" }, permitidos,
        el("h2", { style: "margin-top:14px" }, "Prueba también"),
        el("pre", { class: "codigo" }, "configure terminal      → PROPUESTA (requiere aprobación)\nreload                  → BLOQUEADO (destructivo)\nshow version; reload    → BLOQUEADO (encadenamiento)\ndisplay version (Cisco) → NO VERIFICADO (otra marca)\nshow version (ROMMON)   → NO VERIFICADO (otro modo)"))),
  );
  cambiarPerfil();
  entrada.focus();
}
