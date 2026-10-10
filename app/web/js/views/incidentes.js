/**
 * views/incidentes.js — Creación, asignación, seguimiento y cierre de incidentes (RF-05, HU-03).
 *
 * Flujo seguro: la política PROPONE incidentes para eventos graves (0–2);
 * una persona los revisa y decide abrirlos o no.
 */
import { api } from "../api.js";
import { el, fecha, sevBadge, chip, tabla, intentar, encabezado, formulario, componente, puede, avisoRol, SEVERIDADES, montar } from "../ui.js";

export const titulo = "Incidentes";
export const icono = "incidentes";

const ETAPAS = [["abierto", "Abierto"], ["asignado", "Asignado"], ["en_progreso", "En progreso"], ["cerrado", "Cerrado"]];
const ACCIONES = { creado: "Incidente creado", asignado: "Responsable asignado", estado: "Cambio de estado", nota: "Nota de seguimiento", cerrado: "Incidente cerrado" };

/** Línea de etapas: muestra en qué punto del ciclo va el incidente. */
function etapas(estado) {
  const actual = ETAPAS.findIndex(([e]) => e === estado);
  return el("div", { class: "etapas" }, ETAPAS.map(([, nombre], i) => el("div", { class: `etapa ${i <= actual ? "hecha" : ""}` }, nombre)));
}

export async function render(cont) {
  const filtro = el("select", {},
    el("option", { value: "activos" }, "Abiertos (sin cerrar)"), el("option", { value: "" }, "Todos"),
    ETAPAS.map(([v, t]) => el("option", { value: v }, t)));
  const listaPropuestas = el("div");
  const listaIncidentes = el("div");
  const avisarMenu = () => window.dispatchEvent(new Event("noc:actualizar-menu"));

  async function cargar() {
    const [props, incs] = await Promise.all([
      api("/api/incidents/propuestas").catch(() => []),
      api("/api/incidents", { query: { estado: filtro.value } }).catch(() => []),
    ]);
    listaPropuestas.replaceChildren(tabla([
      { titulo: "Evento", valor: (p) => p.id, clase: "num" },
      { titulo: "Recibido", valor: (p) => fecha(p.recibido_en), clase: "num" },
      { titulo: "Equipo", valor: (p) => p.equipo || "—", clase: "nowrap" },
      { titulo: "Severidad", valor: (p) => sevBadge(p.severidad) },
      { titulo: "Componente", valor: componente },
      { titulo: "Mensaje", clase: "mensaje", valor: (p) => [p.sospechoso ? el("span", { class: "marca-sospechoso" }, "SOSPECHOSO · verificar origen") : null, p.mensaje] },
      { titulo: "Decisión", valor: (p) => puede("operador") ? el("button", { class: "pequeno", onclick: () => abrirDesdeEvento(p) }, "Abrir incidente") : "—" },
    ], props, "No hay eventos graves pendientes de revisión."));

    listaIncidentes.replaceChildren(tabla([
      { titulo: "N.º", valor: (i) => el("strong", {}, `INC-${i.id}`), clase: "nowrap" },
      { titulo: "Severidad", valor: (i) => sevBadge(i.severidad) },
      { titulo: "Descripción", valor: (i) => i.titulo },
      { titulo: "Equipo", valor: (i) => i.equipo || "—", clase: "nowrap" },
      { titulo: "Componente", valor: componente },
      { titulo: "Estado", valor: (i) => chip(i.estado) },
      { titulo: "Responsable", valor: (i) => i.responsable || "Sin asignar" },
      { titulo: "Abierto", valor: (i) => fecha(i.abierto_en), clase: "num" },
      { titulo: "Tiempo / SLA", clase: "num", valor: (i) => i.estado === "cerrado" ? `${i.minutos_abierto} min`
          : el("span", { class: i.sla_vencido ? "texto-peligro" : null }, `${i.minutos_abierto} de ${i.sla_minutos} min${i.sla_vencido ? " · vencido" : ""}`) },
      { titulo: "", valor: (i) => el("button", { class: "pequeno secundario", onclick: () => gestionar(i.id) }, i.estado === "cerrado" || !puede("operador") ? "Ver detalle" : "Gestionar") },
    ], incs, "No hay incidentes con este filtro."));
  }

  async function abrirDesdeEvento(p) {
    const datos = await formulario({
      titulo: "Abrir incidente",
      descripcion: `Evento ${p.id} de ${p.equipo || "equipo desconocido"} · severidad ${p.severidad} (${SEVERIDADES[p.severidad]})${p.componente ? ` · componente afectado: ${p.componente} (${p.estado_componente})` : ""}`,
      campos: [{ id: "responsable", etiqueta: "Responsable", ayuda: "Opcional. Si lo indica, el incidente queda asignado de inmediato." }],
      aceptar: "Abrir incidente",
    });
    if (!datos) return;
    const ok = await intentar(() => api("/api/incidents", { method: "POST", body: { event_id: p.id, responsable: datos.responsable || null } }), "Incidente abierto");
    if (ok) { cargar(); avisarMenu(); }
  }

  /** Ventana de gestión: información, evento de origen, historial y acciones. */
  async function gestionar(id) {
    const inc = await intentar(() => api(`/api/incidents/${id}`));
    if (!inc) return;
    const cerrado = inc.estado === "cerrado";
    const resumen = el("div", {},
      etapas(inc.estado),
      el("p", {}, sevBadge(inc.severidad), "  ", chip(inc.estado), `  ·  Equipo: ${inc.equipo || "—"}  ·  Responsable: ${inc.responsable || "Sin asignar"}  ·  SLA: ${inc.sla_minutos} min`),
      inc.componente ? el("div", { class: "aviso" }, el("strong", {}, "Componente afectado: "), `${inc.componente} (${inc.estado_componente}) en ${inc.equipo}`) : null,
      inc.evento ? el("div", {}, el("h2", {}, "Evento de origen"), el("pre", { class: "codigo" }, `#${inc.evento.id} (${inc.evento.origen})  ${inc.evento.mensaje_crudo}`)) : null,
      el("h2", { style: "margin-top:12px" }, "Historial"),
      el("ul", { class: "historial" }, inc.seguimiento.map((s) => el("li", {},
        el("strong", {}, ACCIONES[s.accion] || s.accion), s.detalle ? ` — ${s.detalle}` : "", el("br"),
        el("small", {}, `${s.usuario} · ${fecha(s.fecha)}`)))),
      cerrado ? el("div", { class: "aviso info" }, el("strong", {}, "Causa: "), inc.causa, el("br"), el("strong", {}, "Solución: "), inc.solucion) : null,
    );

    if (cerrado || !puede("operador")) {
      await formulario({ titulo: `INC-${inc.id} · ${inc.titulo}`, contenido: resumen, aceptar: "Cerrar ventana", cancelar: null });
      return;
    }
    const accion = await formulario({
      titulo: `INC-${inc.id} · ${inc.titulo}`, contenido: resumen,
      campos: [
        { id: "accion", etiqueta: "¿Qué desea hacer?", tipo: "select", valor: inc.responsable ? "progreso" : "asignar", opciones: [
          { valor: "asignar", texto: "Asignar o cambiar responsable" },
          { valor: "progreso", texto: "Marcar en progreso" },
          { valor: "nota", texto: "Agregar nota de seguimiento" },
          { valor: "cerrar", texto: "Cerrar incidente" },
        ] },
      ],
      aceptar: "Continuar",
    });
    if (!accion) return;
    await ejecutar(inc, accion.accion);
  }

  async function ejecutar(inc, accion) {
    const url = `/api/incidents/${inc.id}`;
    let r;
    if (accion === "asignar") {
      const d = await formulario({ titulo: `Asignar responsable · INC-${inc.id}`, campos: [{ id: "responsable", etiqueta: "Responsable", valor: inc.responsable || "", requerido: true }], aceptar: "Asignar" });
      if (d) r = await intentar(() => api(url, { method: "PATCH", body: { responsable: d.responsable } }), "Responsable asignado");
    } else if (accion === "progreso") {
      const d = await formulario({ titulo: `Marcar en progreso · INC-${inc.id}`,
        campos: [{ id: "responsable", etiqueta: "Responsable", valor: inc.responsable || "", requerido: true }, { id: "nota", etiqueta: "Nota", tipo: "textarea", ayuda: "Opcional: qué se está haciendo." }],
        aceptar: "Guardar" });
      if (d) r = await intentar(() => api(url, { method: "PATCH", body: { responsable: d.responsable, estado: "en_progreso", nota: d.nota || null } }), "Incidente en progreso");
    } else if (accion === "nota") {
      const d = await formulario({ titulo: `Nota de seguimiento · INC-${inc.id}`, campos: [{ id: "nota", etiqueta: "Nota", tipo: "textarea", requerido: true }], aceptar: "Agregar nota" });
      if (d) r = await intentar(() => api(url, { method: "PATCH", body: { nota: d.nota } }), "Nota agregada");
    } else if (accion === "cerrar") {
      const d = await formulario({ titulo: `Cerrar incidente · INC-${inc.id}`, descripcion: "Para cerrar se debe documentar la causa y la solución.",
        campos: [{ id: "causa", etiqueta: "Causa raíz", tipo: "textarea", requerido: true }, { id: "solucion", etiqueta: "Solución aplicada", tipo: "textarea", requerido: true }],
        aceptar: "Cerrar incidente" });
      if (d) r = await intentar(() => api(`${url}/cerrar`, { method: "POST", body: { causa: d.causa, solucion: d.solucion } }), "Incidente cerrado");
    }
    if (r) { cargar(); avisarMenu(); }
  }

  filtro.addEventListener("change", cargar);
  montar(cont, 
    encabezado("Operación", "Incidentes",
      "Paso 1: revise los eventos graves que propone el sistema y decida si abre un incidente. Paso 2: asigne un responsable, registre el seguimiento y cierre documentando causa y solución."),
    puede("operador") ? null : avisoRol("Puede consultar los incidentes, pero abrirlos y gestionarlos requiere el rol Operador."),
    el("section", { class: "panel" },
      el("h2", {}, "Eventos graves pendientes de revisión"),
      el("p", { class: "nota" }, "La política del sistema marca los eventos de severidad 0 a 2. Ningún incidente se crea sin una decisión humana."),
      listaPropuestas),
    el("section", { class: "panel" },
      el("h2", {}, "Incidentes"),
      el("div", { class: "filtros" }, el("label", {}, "Mostrar", filtro)),
      listaIncidentes),
  );
  await cargar();
}
