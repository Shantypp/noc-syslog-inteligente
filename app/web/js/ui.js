/**
 * ui.js — Utilidades de interfaz.
 *
 * SEGURIDAD: el texto que viene de los logs NO es confiable (puede traer <script>).
 * Por eso TODO se inserta como texto (createTextNode / textContent) y nunca con innerHTML.
 */

export const SEVERIDADES = ["emergency", "alert", "critical", "error", "warning", "notice", "informational", "debug"];

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

/** Fecha ISO (UTC) -> hora local legible. */
export function fecha(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-CO", { dateStyle: "short", timeStyle: "medium" });
}

/** Etiqueta de color para una severidad 0..7. */
export function sevBadge(sev) {
  return el("span", { class: `sev sev-${sev}`, title: `Severidad ${sev}` }, `${sev} · ${SEVERIDADES[sev]}`);
}

export function chip(texto, clase = texto) {
  return el("span", { class: `chip ${clase}` }, String(texto).replace("_", " "));
}

/** Tabla simple: columnas = [{titulo, valor: (fila) => nodo|texto}] */
export function tabla(columnas, filas, textoVacio = "Sin datos") {
  const cuerpo = filas.length
    ? filas.map((f) => el("tr", {}, columnas.map((c) => el("td", { class: c.clase }, c.valor(f)))))
    : [el("tr", {}, el("td", { class: "vacio", colspan: columnas.length }, textoVacio))];
  return el("table", {}, el("thead", {}, el("tr", {}, columnas.map((c) => el("th", {}, c.titulo)))), el("tbody", {}, cuerpo));
}

/** Mensaje emergente de éxito o error. */
export function aviso(texto, tipo = "ok") {
  const t = el("div", { class: `toast ${tipo}` }, texto);
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

/** Nombre del operador actual (se guarda en el navegador). Queda en la auditoría. */
export function operador() {
  return document.getElementById("operador").value.trim() || "operador";
}
