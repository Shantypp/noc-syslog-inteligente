/**
 * views/incidentes.js — Creación, asignación, seguimiento y cierre de incidentes (RF-05, HU-03).
 *
 * Flujo seguro: la política PROPONE incidentes para eventos graves (0–2);
 * un humano los revisa y decide crearlos o no.
 */
import { api } from "../api.js";
import { el, fecha, sevBadge, chip, tabla, intentar, operador } from "../ui.js";

export const titulo = "Incidentes";
export const icono = "⚑";

export async function render(cont) {
  const filtro = el("select", {},
    el("option", { value: "activos" }, "Activos"), el("option", { value: "" }, "Todos"),
    ["abierto", "asignado", "en_progreso", "cerrado"].map((e) => el("option", { value: e }, e.replace("_", " "))));
  const listaPropuestas = el("div");
  const listaIncidentes = el("div");
  const dialogo = el("dialog");

  async function cargar() {
    const [props, incs] = await Promise.all([
      api("/api/incidents/propuestas").catch(() => []),
      api("/api/incidents", { query: { estado: filtro.value } }).catch(() => []),
    ]);
    listaPropuestas.replaceChildren(tabla([
      { titulo: "Evento", valor: (p) => p.id },
      { titulo: "Recibido", valor: (p) => fecha(p.recibido_en) },
      { titulo: "Equipo", valor: (p) => p.equipo || "—" },
      { titulo: "Sev.", valor: (p) => sevBadge(p.severidad) },
      { titulo: "Mensaje", clase: "mensaje", valor: (p) => [p.sospechoso ? chip("⚠ sospechoso: revisar origen", "sospechoso") : null, " ", p.mensaje] },
      { titulo: "Decisión humana", valor: (p) => el("button", { class: "pequeno", onclick: () => crearDesdeEvento(p) }, "Crear incidente") },
    ], props, "No hay eventos graves pendientes de revisión ✔"));

    listaIncidentes.replaceChildren(tabla([
      { titulo: "#", valor: (i) => `INC-${i.id}` },
      { titulo: "Sev.", valor: (i) => sevBadge(i.severidad) },
      { titulo: "Título", valor: (i) => i.titulo },
      { titulo: "Equipo", valor: (i) => i.equipo || "—" },
      { titulo: "Estado", valor: (i) => chip(i.estado) },
      { titulo: "Responsable", valor: (i) => i.responsable || "—" },
      { titulo: "Abierto", valor: (i) => fecha(i.abierto_en) },
      { titulo: "SLA", valor: (i) => i.estado === "cerrado" ? `${i.minutos_abierto} min` : el("span", { style: i.sla_vencido ? "color:var(--peligro)" : "" }, `${i.minutos_abierto}/${i.sla_minutos} min${i.sla_vencido ? " ⚠ vencido" : ""}`) },
      { titulo: "", valor: (i) => el("button", { class: "pequeno secundario", onclick: () => abrirDetalle(i.id) }, "Gestionar") },
    ], incs, "Sin incidentes"));
  }

  async function crearDesdeEvento(p) {
    const responsable = prompt(`Crear incidente para el evento ${p.id} (${p.equipo}).\nResponsable (opcional):`, "");
    if (responsable === null) return;
    if (await intentar(() => api("/api/incidents", { method: "POST", body: { usuario: operador(), event_id: p.id, responsable: responsable.trim() || null } }), "Incidente creado")) cargar();
  }

  async function abrirDetalle(id) {
    const inc = await intentar(() => api(`/api/incidents/${id}`));
    if (!inc) return;
    const cerrado = inc.estado === "cerrado";
    const responsable = el("input", { value: inc.responsable || "", placeholder: "nombre" });
    const estado = el("select", {}, ["abierto", "asignado", "en_progreso"].map((e) => el("option", { value: e, selected: e === inc.estado }, e.replace("_", " "))));
    const nota = el("textarea", { rows: 2, placeholder: "Nota de seguimiento" });
    const causa = el("textarea", { rows: 2, placeholder: "Causa raíz" });
    const solucion = el("textarea", { rows: 2, placeholder: "Solución aplicada" });

    async function guardar() {
      const r = await intentar(() => api(`/api/incidents/${id}`, { method: "PATCH", body: { usuario: operador(), responsable: responsable.value.trim() || null, estado: estado.value, nota: nota.value.trim() || null } }), "Incidente actualizado");
      if (r) { dialogo.close(); cargar(); }
    }
    async function cerrar() {
      const r = await intentar(() => api(`/api/incidents/${id}/cerrar`, { method: "POST", body: { usuario: operador(), causa: causa.value.trim(), solucion: solucion.value.trim() } }), "Incidente cerrado");
      if (r) { dialogo.close(); cargar(); }
    }

    dialogo.replaceChildren(
      el("h1", {}, `INC-${inc.id} · `, inc.titulo),
      el("p", {}, sevBadge(inc.severidad), " ", chip(inc.estado), " · Equipo: ", inc.equipo || "—", " · SLA ", `${inc.sla_minutos} min`),
      inc.evento ? el("pre", { class: "codigo" }, `Evento original #${inc.evento.id} (${inc.evento.origen}):\n${inc.evento.mensaje_crudo}`) : null,
      el("h2", { style: "margin-top:16px" }, "Seguimiento"),
      el("ul", { class: "linea-tiempo" }, inc.seguimiento.map((s) => el("li", {}, el("strong", {}, s.accion), " — ", s.detalle || "", el("br"), el("small", {}, `${s.usuario} · ${fecha(s.fecha)}`)))),
      cerrado
        ? el("p", {}, el("strong", {}, "Causa: "), inc.causa, el("br"), el("strong", {}, "Solución: "), inc.solucion)
        : [
          el("h2", { style: "margin-top:16px" }, "Actualizar"),
          el("div", { class: "form" }, el("label", {}, "Responsable", responsable), el("label", {}, "Estado", estado)),
          el("label", { class: "form", style: "margin-top:10px" }, nota),
          el("div", { class: "acciones", style: "margin-top:10px" }, el("button", { onclick: guardar }, "Guardar cambios")),
          el("h2", { style: "margin-top:16px" }, "Cerrar incidente"),
          el("div", { class: "form" }, el("label", {}, "Causa", causa), el("label", {}, "Solución", solucion)),
          el("div", { class: "acciones", style: "margin-top:10px" }, el("button", { class: "peligro", onclick: cerrar }, "Cerrar incidente")),
        ],
      el("div", { class: "acciones", style: "margin-top:16px;justify-content:flex-end" }, el("button", { class: "secundario", onclick: () => dialogo.close() }, "Volver")),
    );
    dialogo.showModal();
  }

  filtro.addEventListener("change", cargar);
  cont.replaceChildren(
    el("h1", {}, "Incidentes"),
    el("p", { class: "ayuda" }, "Flujo: evento grave → propuesta automática → revisión humana → incidente → seguimiento → cierre con causa y solución."),
    el("section", { class: "panel" }, el("h2", {}, "Propuestas de la política (eventos 0–2 sin incidente)"), listaPropuestas),
    el("section", { class: "panel" }, el("div", { class: "filtros" }, el("label", {}, "Mostrar", filtro)), listaIncidentes),
    dialogo,
  );
  await cargar();
}
