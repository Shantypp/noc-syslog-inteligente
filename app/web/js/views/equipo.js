/**
 * views/equipo.js — Ficha de un equipo (#equipo/ID): TODO lo de un router o firewall en una pantalla.
 * Estado, partes con problema, incidentes, detecciones, actividad de 24 h y últimos eventos.
 */
import { api } from "../api.js";
import { el, fecha, sevBadge, chip, tabla, encabezado, componente, montar } from "../ui.js";
import { REGLAS } from "./detecciones.js";

export const titulo = "Ficha del equipo";
export const icono = "equipo";

function actividad(horas) {
  const max = Math.max(1, ...horas.map((h) => h.eventos));
  const local = (h) => String(new Date(h.inicio).getHours()).padStart(2, "0"); // hora del navegador
  return el("div", {},
    el("div", { class: "actividad", role: "img", "aria-label": "Eventos por hora en las últimas 24 horas" },
      horas.map((h) => el("div", { class: `col ${h.eventos ? "" : "cero"}`, style: `height:${Math.max(2, (h.eventos / max) * 100)}%`,
        title: `${local(h)}:00 · ${h.eventos} evento(s)` }))),
    el("div", { class: "actividad-ejes" }, horas.map((h) => el("span", {}, local(h)))));
}

export async function render(cont, param) {
  const id = Number(param);
  const d = id ? await api(`/api/devices/${id}/resumen`).catch(() => null) : null;
  if (!d) {
    montar(cont, encabezado("Administración", "Ficha del equipo", null),
      el("div", { class: "aviso" }, "No se encontró el equipo. ", el("a", { href: "#inventario" }, "Volver al inventario")));
    return;
  }
  const e = d.equipo;
  const malos = d.componentes.filter((c) => c.con_problema);
  montar(cont,
    encabezado(el("span", {}, el("a", { href: "#inventario" }, "Inventario"), " › Ficha del equipo"), e.nombre,
      `${e.marca} ${e.modelo || ""} · ${e.ip} · ${e.ubicacion || "sin ubicación registrada"}`,
      el("a", { href: `#eventos/${e.id}`, class: "boton secundario" }, "Ver todos sus eventos")),

    el("div", { class: "tarjetas" },
      el("div", { class: `tarjeta ${e.estado_operativo === "activo" ? "ok" : "peligro"}` }, el("div", { class: "valor" }, chip(e.estado_operativo)), el("div", { class: "etiqueta" }, "Estado")),
      el("div", { class: `tarjeta ${malos.length ? "peligro" : "ok"}` }, el("div", { class: "valor" }, malos.length), el("div", { class: "etiqueta" }, "Partes con problema")),
      el("div", { class: "tarjeta" }, el("div", { class: "valor" }, d.actividad_24h.reduce((s, h) => s + h.eventos, 0)), el("div", { class: "etiqueta" }, "Eventos en 24 h")),
      el("div", { class: `tarjeta ${d.incidentes.some((i) => i.estado !== "cerrado") ? "alerta" : ""}` },
        el("div", { class: "valor" }, d.incidentes.filter((i) => i.estado !== "cerrado").length), el("div", { class: "etiqueta" }, "Incidentes abiertos")),
      el("div", { class: `tarjeta ${d.detecciones.some((x) => x.estado === "nueva") ? "alerta" : ""}` },
        el("div", { class: "valor" }, d.detecciones.filter((x) => x.estado === "nueva").length), el("div", { class: "etiqueta" }, "Detecciones pendientes"))),

    el("section", { class: "panel" }, el("h2", {}, "Datos del equipo"),
      el("dl", { class: "ficha-datos" },
        [["Nombre (hostname)", e.nombre], ["Dirección IP", e.ip], ["Marca", e.marca], ["Modelo", e.modelo || "—"],
          ["Sistema operativo", e.version_so || "—"], ["Ubicación", e.ubicacion || "—"], ["Último evento", fecha(e.ultimo_evento)],
          ["Conectividad", e.conectividad || (e.origen === "real" ? "Esperando el primer ping" : "Sin ping (equipo simulado)")],
          ["Origen de los datos", e.origen === "simulado" ? "Simulado (laboratorio)" : "Real"]]
          .map(([k, v]) => el("div", {}, el("dt", {}, k), el("dd", {}, v))))),

    el("div", { class: "grid-2" },
      el("section", { class: "panel" }, el("h2", {}, "Puertos y componentes"),
        tabla([
          { titulo: "Componente", valor: (c) => el("strong", {}, c.componente), clase: "nowrap" },
          { titulo: "Estado actual", valor: (c) => chip(c.estado) },
          { titulo: "Desde", valor: (c) => fecha(c.ultimo_evento), clase: "num" },
          { titulo: "Historial", valor: (c) => `${c.eventos} evento(s) · ${c.problemas} problema(s)`, clase: "num" },
          { titulo: "Incidente", valor: (c) => c.incidente_abierto ? el("a", { href: `#incidentes/${c.incidente_abierto}` }, `INC-${c.incidente_abierto}`) : "—" },
        ], d.componentes, "Este equipo no ha reportado eventos de puertos o componentes.")),
      el("section", { class: "panel" }, el("h2", {}, "Actividad últimas 24 horas"), actividad(d.actividad_24h))),

    el("div", { class: "grid-2" },
      el("section", { class: "panel" }, el("h2", {}, "Incidentes"),
        tabla([
          { titulo: "N.º", valor: (i) => el("a", { href: `#incidentes/${i.id}` }, `INC-${i.id}`), clase: "nowrap" },
          { titulo: "Descripción", valor: (i) => i.titulo },
          { titulo: "Severidad", valor: (i) => sevBadge(i.severidad) },
          { titulo: "Estado", valor: (i) => [chip(i.estado), i.recuperado_en && i.estado !== "cerrado" ? [" ", chip("recuperado")] : null] },
        ], d.incidentes, "Sin incidentes registrados.")),
      el("section", { class: "panel" }, el("h2", {}, "Detecciones automáticas"),
        tabla([
          { titulo: "Qué se detectó", valor: (x) => [el("strong", {}, (REGLAS[x.regla] || [x.titulo])[0]), el("br"), el("small", {}, x.detalle)] },
          { titulo: "Estado", valor: (x) => chip(x.estado) },
          { titulo: "Última vez", valor: (x) => fecha(x.actualizada_en), clase: "num" },
        ], d.detecciones, "Sin detecciones."))),

    el("section", { class: "panel" }, el("h2", {}, "Últimos eventos"),
      tabla([
        { titulo: "Fecha", valor: (ev) => fecha(ev.recibido_en), clase: "num" },
        { titulo: "Severidad", valor: (ev) => sevBadge(ev.severidad) },
        { titulo: "Componente", valor: componente },
        { titulo: "Mensaje", clase: "mensaje", valor: (ev) => [ev.sospechoso ? el("span", { class: "marca-sospechoso" }, "SOSPECHOSO") : null,
            ev.mensaje, ev.repeticiones > 1 ? ` (×${ev.repeticiones})` : null] },
      ], d.eventos, "Este equipo todavía no ha enviado eventos.")),
  );
}
