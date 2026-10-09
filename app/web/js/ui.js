/**
 * ui.js — Utilidades de interfaz compartidas por todas las vistas.
 *
 * SEGURIDAD: el texto que viene de los logs NO es confiable (puede traer <script>).
 * Por eso los datos se insertan siempre como texto (createTextNode / textContent),
 * nunca con innerHTML.
 */

export const SEVERIDADES = ["Emergencia", "Alerta", "Crítico", "Error", "Advertencia", "Aviso", "Informativo", "Depuración"];

/**
 * Crea un elemento HTML de forma segura.
 *   el("button", { class: "pequeno", onclick: fn }, "Guardar")
 * Los hijos de tipo texto se agregan como texto plano (nunca como HTML).
 */
export function el(tag, attrs = {}, ...hijos) {
  const nodo = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") nodo.className = v;
    else if (k.startsWith("on")) nodo.addEventListener(k.slice(2), v);
    else if (k === "value") nodo.value = v;
    else nodo.setAttribute(k, v === true ? "" : v);
  }
  for (const h of hijos.flat(Infinity)) { // acepta listas anidadas de hijos
    if (h === null || h === undefined || h === false) continue;
    nodo.append(h instanceof Node ? h : document.createTextNode(String(h)));
  }
  return nodo;
}

/* Íconos de línea (trazos tipo Lucide, licencia ISC). Son trazos fijos del código,
   no datos externos, por eso es seguro construirlos a partir de esta tabla. */
const TRAZOS = {
  panel: [["rect", { x: 3, y: 3, width: 7, height: 9, rx: 1 }], ["rect", { x: 14, y: 3, width: 7, height: 5, rx: 1 }], ["rect", { x: 14, y: 12, width: 7, height: 9, rx: 1 }], ["rect", { x: 3, y: 16, width: 7, height: 5, rx: 1 }]],
  eventos: [["path", { d: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" }]],
  incidentes: [["path", { d: "m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" }], ["path", { d: "M12 9v4M12 17h.01" }]],
  inventario: [["rect", { x: 2, y: 2, width: 20, height: 8, rx: 2 }], ["rect", { x: 2, y: 14, width: 20, height: 8, rx: 2 }], ["path", { d: "M6 6h.01M6 18h.01" }]],
  configs: [["path", { d: "M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5Z" }], ["path", { d: "M14 2v6h6M10 13l-2 2 2 2M14 17l2-2-2-2" }]],
  consola: [["path", { d: "m4 17 6-6-6-6M12 19h8" }]],
  auditoria: [["rect", { x: 8, y: 2, width: 8, height: 4, rx: 1 }], ["path", { d: "M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2M9 14l2 2 4-4" }]],
  seguridad: [["path", { d: "M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" }], ["path", { d: "m9 12 2 2 4-4" }]],
  actividad: [["path", { d: "M22 12h-4l-3 9L9 3l-3 9H2" }]],
};

export function icono(nombre, tam = 18) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  for (const [k, v] of Object.entries({ viewBox: "0 0 24 24", width: tam, height: tam, fill: "none", stroke: "currentColor",
    "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round", class: "icono", "aria-hidden": "true" })) svg.setAttribute(k, v);
  for (const [tag, attrs] of TRAZOS[nombre] || []) {
    const t = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) t.setAttribute(k, v);
    svg.append(t);
  }
  return svg;
}

/** Fecha ISO (UTC) -> hora local legible. */
export function fecha(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-CO", { dateStyle: "short", timeStyle: "short" });
}

/** Etiqueta de severidad 0..7 (rojo solo para 0-2). */
export function sevBadge(sev) {
  return el("span", { class: `sev sev-${sev}`, title: `Severidad Syslog ${sev}` }, `${sev} · ${SEVERIDADES[sev]}`);
}

/** Texto y color de cada estado que muestra la aplicación. */
const ESTADOS = {
  activo: ["Activo", "verde"], inactivo: ["Inactivo", ""], sin_comunicacion: ["Sin comunicación", "rojo"],
  abierto: ["Abierto", "rojo"], asignado: ["Asignado", "ambar"], en_progreso: ["En progreso", "azul"], cerrado: ["Cerrado", "verde"],
  PERMITIDO: ["Permitido", "verde"], BLOQUEADO: ["Bloqueado", "rojo"], PROPUESTA: ["Propuesta", "ambar"], NO_VERIFICADO: ["No verificado", "violeta"],
  simulado: ["Simulado", ""], real: ["Real", "azul"],
};
export function chip(valor) {
  const [texto, color] = ESTADOS[valor] || [String(valor), ""];
  return el("span", { class: `estado ${color}` }, texto);
}

/** Encabezado estándar de cada pantalla: sección, título, explicación y acciones. */
export function encabezado(ruta, titulo, descripcion, ...acciones) {
  return el("div", { class: "encabezado" },
    el("div", {}, el("div", { class: "ruta" }, ruta), el("h1", {}, titulo), descripcion ? el("p", {}, descripcion) : null),
    acciones.length ? el("div", { class: "acciones" }, acciones) : null);
}

/** Tabla simple: columnas = [{titulo, valor: (fila) => nodo|texto, clase}] */
export function tabla(columnas, filas, textoVacio = "Sin datos") {
  const cuerpo = filas.length
    ? filas.map((f) => el("tr", {}, columnas.map((c) => el("td", { class: c.clase }, c.valor(f)))))
    : [el("tr", {}, el("td", { class: "vacio", colspan: columnas.length }, textoVacio))];
  return el("div", { class: "tabla-contenedor" },
    el("table", {}, el("thead", {}, el("tr", {}, columnas.map((c) => el("th", {}, c.titulo)))), el("tbody", {}, cuerpo)));
}

/** Mensaje emergente de éxito o error. */
export function aviso(texto, tipo = "ok") {
  const t = el("div", { class: `toast ${tipo}`, role: tipo === "error" ? "alert" : "status" }, texto);
  document.getElementById("toasts").append(t);
  setTimeout(() => t.remove(), tipo === "error" ? 7000 : 3500);
}

/** Ejecuta una acción y muestra el error si falla. */
export async function intentar(fn, exito) {
  try {
    const r = await fn();
    if (exito) aviso(exito);
    return r;
  } catch (e) {
    aviso(e.message, "error");
    return undefined;
  }
}

/** Nombre del usuario de la sesión. Queda en incidentes y auditoría. */
export function operador() {
  return document.getElementById("operador").value.trim() || "operador";
}

/**
 * Ventana con formulario (reemplaza a prompt() del navegador).
 * campos: [{ id, etiqueta, tipo: "text"|"textarea"|"select", opciones, valor, requerido, ayuda }]
 * Devuelve una promesa con {id: valor} o null si se cancela.
 */
export function formulario({ titulo, descripcion, campos = [], aceptar = "Guardar", cancelar = "Cancelar", peligro = false, contenido = null }) {
  return new Promise((resolver) => {
    const entradas = {};
    const error = el("div", { class: "error-campo", role: "alert" });
    const filas = campos.map((c) => {
      const control = c.tipo === "textarea" ? el("textarea", { rows: 3, value: c.valor ?? "" })
        : c.tipo === "select" ? el("select", {}, c.opciones.map((o) => el("option", { value: o.valor, selected: o.valor === c.valor }, o.texto)))
        : el("input", { value: c.valor ?? "", autocomplete: "off" });
      control.addEventListener("input", () => { error.textContent = ""; });
      entradas[c.id] = control;
      return el("label", {}, c.etiqueta + (c.requerido ? " *" : ""), control, c.ayuda ? el("span", { class: "ayuda" }, c.ayuda) : null);
    });
    const ventana = el("dialog", {},
      el("form", { method: "dialog" },
        el("div", { class: "cabecera" }, el("h1", {}, titulo), descripcion ? el("p", {}, descripcion) : null),
        el("div", { class: "cuerpo" }, contenido, filas, error),
        el("div", { class: "pie" },
          cancelar ? el("button", { type: "button", class: "secundario", onclick: () => cerrar(null) }, cancelar) : null,
          el("button", { type: "submit", class: peligro ? "peligro" : null }, aceptar))));
    const cerrar = (valor) => { ventana.close(); ventana.remove(); resolver(valor); };
    ventana.querySelector("form").addEventListener("submit", (ev) => {
      ev.preventDefault();
      const faltante = campos.find((c) => c.requerido && !entradas[c.id].value.trim());
      if (faltante) { error.textContent = `Completa el campo "${faltante.etiqueta}".`; entradas[faltante.id].focus(); return; }
      cerrar(Object.fromEntries(campos.map((c) => [c.id, entradas[c.id].value.trim()])));
    });
    ventana.addEventListener("cancel", (ev) => { ev.preventDefault(); cerrar(null); });
    document.body.append(ventana);
    ventana.showModal();
    (Object.values(entradas)[0] || ventana.querySelector("button[type=submit]")).focus();
  });
}

/** Confirmación (reemplaza a confirm() del navegador). */
export async function confirmar(titulo, mensaje, aceptar = "Confirmar", peligro = false) {
  return (await formulario({ titulo, descripcion: mensaje, aceptar, peligro })) !== null;
}
