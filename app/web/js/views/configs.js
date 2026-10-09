/**
 * views/configs.js — Generador de configuraciones Syslog multivendor (RF-06, HU-04).
 * Produce texto comentado para revisión humana. Nunca se aplica a un equipo.
 */
import { api } from "../api.js";
import { el, intentar, aviso } from "../ui.js";

export const titulo = "Configuraciones";
export const icono = "⚙";

/** Pinta la plantilla: las líneas de comentario en otro color (todo como texto, sin HTML). */
function pintarPlantilla(texto) {
  return el("pre", { class: "codigo" }, texto.split("\n").map((l) => {
    const comentario = /^\s*[!#]/.test(l);
    return el("span", { class: comentario ? "comentario" : null }, l + "\n");
  }));
}

export async function render(cont) {
  const op = await api("/api/configgen/opciones");
  const f = {
    fabricante: el("select", {}, op.fabricantes.map((x) => el("option", { value: x.id }, x.nombre))),
    ip: el("input", { value: "192.0.2.10" }),
    umbral: el("select", {}, op.umbrales.map((u) => el("option", { value: u.id, selected: u.id === "warnings" }, `${u.id} (0–${u.severidad_max})`))),
    puerto: el("input", { type: "number", value: "514", min: "1", max: "65535" }),
    facility: el("select", {}, op.facilities.map((x) => el("option", { value: x, selected: x === "local7" }, x))),
    interfaz: el("input", { placeholder: "opcional: GigabitEthernet0/0" }),
  };
  const salida = el("div");
  let ultimoTexto = "";

  async function generar() {
    const r = await intentar(() => api("/api/configgen", {
      query: { fabricante: f.fabricante.value, ip: f.ip.value, umbral: f.umbral.value, puerto: f.puerto.value, facility: f.facility.value, interfaz: f.interfaz.value.trim() },
    }));
    if (!r) return;
    ultimoTexto = r.plantilla;
    salida.replaceChildren(
      el("div", { class: "aviso" }, "⚠ ", r.advertencia),
      el("div", { class: "acciones", style: "margin-bottom:10px" },
        el("button", { onclick: copiar }, "Copiar plantilla"),
        el("span", { class: "chip" }, `Nivel en ${r.nombre}: ${r.parametros.nivel}`)),
      pintarPlantilla(r.plantilla),
      el("div", { class: "grid-2", style: "margin-top:14px" },
        el("section", { class: "panel" }, el("h2", {}, "1 · Identificar versión (antes)"), el("pre", { class: "codigo" }, r.identificar_version),
          el("h2", { style: "margin-top:12px" }, "3 · Verificar (después)"), el("pre", { class: "codigo" }, r.verificacion.join("\n"))),
        el("section", { class: "panel" }, el("h2", {}, "Plan de reversa (rollback)"), el("pre", { class: "codigo" }, r.reversa.join("\n")),
          el("h2", { style: "margin-top:12px" }, "Documentación oficial"), el("p", {}, r.documentacion))),
    );
  }

  async function copiar() {
    try { await navigator.clipboard.writeText(ultimoTexto); aviso("Plantilla copiada"); }
    catch { aviso("No se pudo copiar automáticamente; selecciónala y usa Ctrl+C", "error"); }
  }

  for (const campo of Object.values(f)) campo.addEventListener("change", generar);
  cont.replaceChildren(
    el("h1", {}, "Generador de configuraciones Syslog"),
    el("p", { class: "ayuda" }, "Cisco · Fortinet · Huawei. Cada línea va comentada. Las entradas se validan para impedir inyectar comandos en la plantilla."),
    el("section", { class: "panel" },
      el("div", { class: "form" },
        el("label", {}, "Fabricante", f.fabricante), el("label", {}, "IP del colector", f.ip),
        el("label", {}, "Umbral", f.umbral), el("label", {}, "Puerto UDP", f.puerto),
        el("label", {}, "Facility", f.facility), el("label", {}, "Interfaz de origen", f.interfaz)),
      el("div", { class: "acciones", style: "margin-top:12px" }, el("button", { onclick: generar }, "Generar y explicar"))),
    salida,
  );
  generar();
}
