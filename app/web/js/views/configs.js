/**
 * views/configs.js — Plantillas de configuración Syslog multivendor (RF-06, HU-04).
 * Produce texto comentado para revisión humana. Nunca se aplica a un equipo.
 */
import { api } from "../api.js";
import { el, intentar, aviso, encabezado, montar } from "../ui.js";

export const titulo = "Plantillas de configuración";
export const icono = "configs";

/** Pinta la plantilla: los comentarios en gris (todo como texto, sin HTML). */
function pintarPlantilla(texto) {
  return el("pre", { class: "codigo" }, texto.split("\n").map((l) =>
    el("span", { class: /^\s*[!#]/.test(l) ? "comentario" : null }, l + "\n")));
}

export async function render(cont) {
  const op = await api("/api/configgen/opciones");
  const f = {
    fabricante: el("select", {}, op.fabricantes.map((x) => el("option", { value: x.id }, x.nombre))),
    ip: el("input", { value: "192.0.2.10" }),
    umbral: el("select", {}, op.umbrales.map((u) => el("option", { value: u.id, selected: u.id === "warnings" }, `${u.id} (severidad 0–${u.severidad_max})`))),
    puerto: el("input", { type: "number", value: "514", min: "1", max: "65535" }),
    facility: el("select", {}, op.facilities.map((x) => el("option", { value: x, selected: x === "local7" }, x))),
    interfaz: el("input", { placeholder: "Opcional. Ej.: GigabitEthernet0/0" }),
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
      el("div", { class: "aviso" }, el("strong", {}, "Antes de aplicar: "), r.advertencia),
      el("section", { class: "panel" },
        el("h2", {}, "Paso 1 · Identificar la versión del equipo"),
        el("p", { class: "nota" }, `Ejecute este comando y confirme la versión en la documentación oficial: ${r.documentacion}.`),
        el("pre", { class: "codigo" }, r.identificar_version)),
      el("section", { class: "panel" },
        el("h2", {}, `Paso 2 · Configuración para ${r.nombre}`, el("span", { style: "margin-left:auto" }, el("button", { class: "pequeno secundario", onclick: copiar }, "Copiar"))),
        el("p", { class: "nota" }, `Nivel en la sintaxis de ${r.nombre}: ${r.parametros.nivel}. Las líneas en gris son comentarios explicativos.`),
        pintarPlantilla(r.plantilla)),
      el("div", { class: "grid-2" },
        el("section", { class: "panel" }, el("h2", {}, "Paso 3 · Verificar después de aplicar"), el("pre", { class: "codigo" }, r.verificacion.join("\n"))),
        el("section", { class: "panel" }, el("h2", {}, "Plan de reversa (rollback)"), el("pre", { class: "codigo" }, r.reversa.join("\n")))),
    );
  }

  async function copiar() {
    try { await navigator.clipboard.writeText(ultimoTexto); aviso("Plantilla copiada al portapapeles"); }
    catch { aviso("No se pudo copiar automáticamente; seleccione el texto y use Ctrl+C", "error"); }
  }

  for (const campo of Object.values(f)) campo.addEventListener("change", generar);
  montar(cont, 
    encabezado("Administración", "Plantillas de configuración",
      "Genera la configuración Syslog comentada para Cisco, Fortinet o Huawei. Es un texto para revisión: la aplicación nunca lo aplica a los equipos. Los datos de entrada se validan para impedir que se inyecten comandos."),
    el("section", { class: "panel" },
      el("h2", {}, "Parámetros"),
      el("div", { class: "form" },
        el("label", {}, "Fabricante", f.fabricante), el("label", {}, "IP del colector (NOC)", f.ip),
        el("label", {}, "Severidad mínima a enviar", f.umbral), el("label", {}, "Puerto UDP", f.puerto),
        el("label", {}, "Facility", f.facility), el("label", {}, "Interfaz de origen", f.interfaz)),
      el("div", { class: "acciones", style: "margin-top:12px" }, el("button", { onclick: generar }, "Generar plantilla"))),
    salida,
  );
  generar();
}
