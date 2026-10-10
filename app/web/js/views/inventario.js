/**
 * views/inventario.js — Inventario de equipos (RF-01).
 * Solo los equipos registrados aquí pueden enviar Syslog (lista permitida de fuentes).
 */
import { api } from "../api.js";
import { el, fecha, chip, tabla, intentar, encabezado, formulario, confirmar, puede, avisoRol, montar } from "../ui.js";

export const titulo = "Inventario de equipos";
export const icono = "inventario";

const opciones = (lista) => lista.map(([valor, texto]) => ({ valor, texto }));
const CAMPOS = (d = {}) => [
  { id: "nombre", etiqueta: "Nombre del equipo", valor: d.nombre, requerido: true, ayuda: "Debe coincidir con el hostname que envía en sus logs. Ej.: R1-NOC" },
  { id: "ip", etiqueta: "Dirección IP", valor: d.ip, requerido: true, ayuda: "Para datos simulados use el rango de documentación 192.0.2.0/24" },
  { id: "marca", etiqueta: "Marca", tipo: "select", valor: d.marca || "Cisco", opciones: opciones([["Cisco", "Cisco"], ["Fortinet", "Fortinet"], ["Huawei", "Huawei"]]) },
  { id: "modelo", etiqueta: "Modelo", valor: d.modelo },
  { id: "version_so", etiqueta: "Versión del sistema operativo", valor: d.version_so },
  { id: "ubicacion", etiqueta: "Ubicación", valor: d.ubicacion },
  { id: "estado", etiqueta: "Estado administrativo", tipo: "select", valor: d.estado || "activo",
    opciones: opciones([["activo", "Activo"], ["inactivo", "Inactivo (mantenimiento)"], ["sin_comunicacion", "Sin comunicación"]]) },
  { id: "origen", etiqueta: "Origen de los datos", tipo: "select", valor: d.origen || "simulado", opciones: opciones([["simulado", "Simulado"], ["real", "Real"]]) },
];

export async function render(cont) {
  const lista = el("div");

  async function guardar(equipo) {
    const datos = await formulario({
      titulo: equipo ? `Editar equipo · ${equipo.nombre}` : "Registrar equipo",
      descripcion: "Los campos marcados con * son obligatorios.",
      campos: CAMPOS(equipo || {}), aceptar: equipo ? "Guardar cambios" : "Registrar equipo", // null no activa el valor por defecto
    });
    if (!datos) return;
    for (const k of Object.keys(datos)) if (datos[k] === "") datos[k] = null;
    const r = await intentar(() => equipo
      ? api(`/api/devices/${equipo.id}`, { method: "PUT", body: datos })
      : api("/api/devices", { method: "POST", body: datos }), equipo ? "Equipo actualizado" : "Equipo registrado");
    if (r) cargar();
  }

  async function eliminar(d) {
    const ok = await confirmar(`Eliminar ${d.nombre}`, `Se eliminará el equipo ${d.nombre} (${d.ip}). Sus eventos se conservan como evidencia, pero el equipo dejará de estar autorizado para enviar Syslog.`, "Eliminar equipo", true);
    if (ok && await intentar(() => api(`/api/devices/${d.id}`, { method: "DELETE" }), "Equipo eliminado") !== undefined) cargar();
  }

  async function cargar() {
    const equipos = await intentar(() => api("/api/devices")) || [];
    lista.replaceChildren(tabla([
      { titulo: "ID", valor: (d) => d.id, clase: "num" },
      { titulo: "Equipo", valor: (d) => el("strong", {}, d.nombre), clase: "nowrap" },
      { titulo: "IP", valor: (d) => d.ip, clase: "num" },
      { titulo: "Marca", valor: (d) => d.marca },
      { titulo: "Modelo", valor: (d) => d.modelo || "—" },
      { titulo: "Versión", valor: (d) => d.version_so || "—" },
      { titulo: "Ubicación", valor: (d) => d.ubicacion || "—" },
      { titulo: "Estado", valor: (d) => chip(d.estado) },
      { titulo: "Origen", valor: (d) => chip(d.origen) },
      { titulo: "Actualizado", valor: (d) => fecha(d.actualizado_en), clase: "num" },
      { titulo: "", valor: (d) => !puede("administrador") ? "" : el("div", { class: "acciones" },
          el("button", { class: "pequeno secundario", onclick: () => guardar(d) }, "Editar"),
          el("button", { class: "pequeno peligro", onclick: () => eliminar(d) }, "Eliminar")) },
    ], equipos, "No hay equipos registrados. Use el botón Registrar equipo o ejecute: python -m app.seed"));
  }

  montar(cont, 
    encabezado("Administración", "Inventario de equipos",
      "Equipos de red autorizados. Solo los equipos registrados aquí pueden enviar eventos al NOC (lista permitida de fuentes).",
      puede("administrador") ? el("button", { onclick: () => guardar(null) }, "Registrar equipo") : null),
    puede("administrador") ? null : avisoRol("Puede consultar el inventario; registrar, editar o eliminar equipos requiere el rol Administrador."),
    el("section", { class: "panel" }, lista),
  );
  await cargar();
}
