/**
 * views/consola.js — Consola de equipos tipo PuTTY, SIMULADA y de solo lectura (RF-07).
 *
 * La decisión (permitido / bloqueado / propuesta / no verificado) la toma el BACKEND.
 * Si estuviera solo en JavaScript, cualquiera podría saltársela con F12.
 */
import { api } from "../api.js";
import { el, operador, encabezado, chip } from "../ui.js";

export const titulo = "Consola de equipos";
export const icono = "consola";

const PERFIL_POR_MARCA = { Cisco: "cisco_ios", Fortinet: "fortigate", Huawei: "huawei_vrp" };
const CLASE = { BLOQUEADO: "t-bloqueado", PROPUESTA: "t-propuesta", NO_VERIFICADO: "t-noverif" };

export async function render(cont) {
  const [perfiles, equipos] = await Promise.all([api("/api/console/perfiles"), api("/api/devices").catch(() => [])]);
  const porId = Object.fromEntries(perfiles.map((p) => [p.id, p]));

  const selEquipo = el("select", {}, el("option", { value: "" }, "Sin equipo"), equipos.map((d) => el("option", { value: d.id }, `${d.nombre} · ${d.marca}`)));
  const selPerfil = el("select", {}, perfiles.map((p) => el("option", { value: p.id }, p.nombre)));
  const salida = el("div", { class: "salida", role: "log" });
  const prompt = el("span");
  const entrada = el("input", { autocomplete: "off", spellcheck: "false", "aria-label": "Comando" });
  const permitidos = el("ul", { class: "lista-comandos" });
  const historial = [];
  let posHistorial = 0;

  const escribir = (texto, clase) => {
    salida.append(el("div", { class: clase }, texto));
    salida.scrollTop = salida.scrollHeight;
  };

  function cambiarPerfil() {
    const p = porId[selPerfil.value];
    prompt.textContent = p.prompt;
    // Clic en un comando permitido = se escribe en la consola (más fácil de usar)
    permitidos.replaceChildren(...p.permitidos.map((c) => el("li", {}, el("button", { type: "button", onclick: () => { entrada.value = c; entrada.focus(); } }, c))));
    escribir(`Perfil activo: ${p.nombre}. Escriba "help" para ver los comandos permitidos.`, "t-info");
  }

  selEquipo.addEventListener("change", () => {
    const d = equipos.find((x) => String(x.id) === selEquipo.value);
    if (d && PERFIL_POR_MARCA[d.marca] && !(d.marca === "Cisco" && selPerfil.value === "cisco_rommon")) selPerfil.value = PERFIL_POR_MARCA[d.marca];
    cambiarPerfil();
  });
  selPerfil.addEventListener("change", cambiarPerfil);

  async function enviar(comando) {
    historial.push(comando); posHistorial = historial.length;
    escribir(`${prompt.textContent} ${comando}`);
    try {
      const r = await api("/api/console/ejecutar", { method: "POST", body: { perfil: selPerfil.value, comando, usuario: operador(), device_id: selEquipo.value ? Number(selEquipo.value) : null } });
      if (r.decision === "PERMITIDO") escribir(r.salida);
      else escribir(`% [${r.decision.replace("_", " ")}] ${r.motivo}${r.decision === "PROPUESTA" ? ` Registro #${r.audit_id}: debe aprobarlo otro usuario en Auditoría.` : ""}`, CLASE[r.decision]);
      if (r.decision === "PROPUESTA") window.dispatchEvent(new Event("noc:actualizar-menu"));
    } catch (e) {
      escribir(`% Error: ${e.message}`, "t-bloqueado");
    }
  }

  entrada.addEventListener("keydown", (ev) => {
    if (ev.key === "ArrowUp" && historial.length) { posHistorial = Math.max(0, posHistorial - 1); entrada.value = historial[posHistorial]; return; }
    if (ev.key === "ArrowDown" && historial.length) { posHistorial = Math.min(historial.length, posHistorial + 1); entrada.value = historial[posHistorial] || ""; return; }
    if (ev.key !== "Enter" || !entrada.value.trim()) return;
    const comando = entrada.value;
    entrada.value = "";
    enviar(comando);
  });

  cont.replaceChildren(
    encabezado("Control de cambios", "Consola de equipos",
      "Consola de solo lectura, sin conexión a equipos reales (simulación). Los comandos de consulta se responden; los de cambio quedan como propuesta para aprobación; los peligrosos se bloquean. Todo queda registrado en Auditoría."),
    el("div", { class: "filtros" }, el("label", {}, "Equipo", selEquipo), el("label", {}, "Perfil / modo del equipo", selPerfil)),
    el("div", { class: "grid-consola" },
      el("div", { class: "terminal", onclick: () => entrada.focus() },
        el("div", { class: "barra-titulo" }, "noc-console · simulación · solo lectura"),
        salida,
        el("div", { class: "linea-entrada" }, prompt, entrada)),
      el("section", { class: "panel" },
        el("h2", {}, "Comandos permitidos"),
        el("p", { class: "nota" }, "Haga clic en un comando para escribirlo en la consola."),
        permitidos,
        el("h2", {}, "Qué significa cada respuesta"),
        el("div", { class: "leyenda" },
          el("div", {}, chip("PERMITIDO"), "Consulta autorizada: se muestra la salida simulada."),
          el("div", {}, chip("PROPUESTA"), "Comando de cambio: no se ejecuta; requiere aprobación de otro usuario."),
          el("div", {}, chip("BLOQUEADO"), "Destructivo, encadenado o desconocido: se deniega."),
          el("div", {}, chip("NO_VERIFICADO"), "Comando de otra marca o de otro modo del equipo.")))),
  );
  cambiarPerfil();
  entrada.focus();
}
