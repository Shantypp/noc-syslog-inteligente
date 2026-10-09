/**
 * views/inventario.js — Inventario editable de equipos (RF-01).
 * Crear, editar y eliminar. Solo los equipos del inventario pueden enviar Syslog (allowlist).
 */
import { api } from "../api.js";
import { el, fecha, chip, tabla, intentar } from "../ui.js";

export const titulo = "Inventario";
export const icono = "▤";

const CAMPOS = [
  { id: "nombre", etiqueta: "Nombre *", placeholder: "R1-NOC" },
  { id: "ip", etiqueta: "IP *", placeholder: "192.0.2.10" },
  { id: "marca", etiqueta: "Marca *", opciones: ["Cisco", "Fortinet", "Huawei"] },
  { id: "modelo", etiqueta: "Modelo" },
  { id: "version_so", etiqueta: "Versión SO" },
  { id: "ubicacion", etiqueta: "Ubicación" },
  { id: "estado", etiqueta: "Estado", opciones: ["activo", "inactivo", "sin_comunicacion"] },
  { id: "origen", etiqueta: "Origen", opciones: ["simulado", "real"] },
];

export async function render(cont) {
  let editando = null; // id del equipo en edición (null = nuevo)
  const entradas = Object.fromEntries(CAMPOS.map((c) => [c.id, c.opciones
    ? el("select", {}, c.opciones.map((o) => el("option", { value: o }, o)))
    : el("input", { placeholder: c.placeholder || "" })]));
  const tituloForm = el("h2", {}, "Nuevo equipo");
  const btnGuardar = el("button", { onclick: guardar }, "Guardar");
  const lista = el("div");

  function limpiar() {
    editando = null;
    for (const c of CAMPOS) entradas[c.id].value = c.opciones ? c.opciones[0] : "";
    tituloForm.textContent = "Nuevo equipo";
  }

  function editar(d) {
    editando = d.id;
    for (const c of CAMPOS) entradas[c.id].value = d[c.id] ?? "";
    tituloForm.textContent = `Editando ${d.nombre} (id ${d.id})`;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function guardar() {
    const datos = Object.fromEntries(CAMPOS.map((c) => [c.id, entradas[c.id].value.trim() || null]));
    const r = await intentar(() => editando
      ? api(`/api/devices/${editando}`, { method: "PUT", body: datos })
      : api("/api/devices", { method: "POST", body: datos }), editando ? "Equipo actualizado" : "Equipo creado");
    if (r) { limpiar(); cargar(); }
  }

  async function eliminar(d) {
    if (!confirm(`¿Eliminar ${d.nombre} (${d.ip})? Sus eventos se conservan como evidencia.`)) return;
    if (await intentar(() => api(`/api/devices/${d.id}`, { method: "DELETE" }), "Equipo eliminado") !== undefined) cargar();
  }

  async function cargar() {
    const equipos = await intentar(() => api("/api/devices")) || [];
    lista.replaceChildren(tabla([
      { titulo: "ID", valor: (d) => d.id },
      { titulo: "Nombre", valor: (d) => el("strong", {}, d.nombre) },
      { titulo: "IP", valor: (d) => d.ip },
      { titulo: "Marca", valor: (d) => d.marca },
      { titulo: "Modelo", valor: (d) => d.modelo || "—" },
      { titulo: "Versión", valor: (d) => d.version_so || "—" },
      { titulo: "Ubicación", valor: (d) => d.ubicacion || "—" },
      { titulo: "Estado", valor: (d) => chip(d.estado) },
      { titulo: "Origen", valor: (d) => d.origen },
      { titulo: "Actualizado", valor: (d) => fecha(d.actualizado_en) },
      { titulo: "", valor: (d) => el("div", { class: "acciones" },
          el("button", { class: "pequeno secundario", onclick: () => editar(d) }, "Editar"),
          el("button", { class: "pequeno peligro", onclick: () => eliminar(d) }, "Eliminar")) },
    ], equipos, "Inventario vacío. Ejecuta: python -m app.seed"));
  }

  cont.replaceChildren(
    el("h1", {}, "Inventario de dispositivos"),
    el("p", { class: "ayuda" }, "Solo los equipos registrados aquí pueden enviar eventos (lista permitida de fuentes). Usa IPs de documentación (192.0.2.0/24) para datos simulados."),
    el("section", { class: "panel" }, tituloForm,
      el("div", { class: "form" }, CAMPOS.map((c) => el("label", {}, c.etiqueta, entradas[c.id]))),
      el("div", { class: "acciones", style: "margin-top:12px" }, btnGuardar, el("button", { class: "secundario", onclick: limpiar }, "Cancelar"))),
    el("section", { class: "panel" }, lista),
  );
  limpiar();
  await cargar();
}
