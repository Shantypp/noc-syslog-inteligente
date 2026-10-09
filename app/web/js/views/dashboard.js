/**
 * views/dashboard.js — Tablero principal (RF-04, HU-01).
 * Muestra: tarjetas de resumen, estado de equipos, distribución por severidad,
 * eventos críticos, eventos recientes e incidentes activos. Se refresca cada 10 s.
 */
import { api } from "../api.js";
import { el, fecha, sevBadge, chip, tabla, SEVERIDADES } from "../ui.js";

export const titulo = "Dashboard";
export const icono = "▦";

function tarjeta(etiqueta, valor, clase = "") {
  return el("div", { class: `tarjeta ${clase}` }, el("div", { class: "valor" }, valor), el("div", { class: "etiqueta" }, etiqueta));
}

function barras(conteos) {
  const max = Math.max(1, ...conteos);
  return el("div", { class: "barras" }, conteos.map((n, sev) =>
    el("div", { class: "barra" },
      el("span", {}, `${sev} · ${SEVERIDADES[sev]}`),
      el("div", { class: "pista" }, el("div", { class: "relleno", style: `width:${(n / max) * 100}%;background:var(--sev-${sev})` })),
      el("strong", {}, n))));
}

const colEventos = [
  { titulo: "Hora", valor: (e) => fecha(e.recibido_en) },
  { titulo: "Equipo", valor: (e) => e.equipo || e.hostname || "—" },
  { titulo: "Severidad", valor: (e) => sevBadge(e.severidad) },
  { titulo: "Mensaje", clase: "mensaje", valor: (e) => [e.sospechoso ? chip("⚠ sospechoso", "sospechoso") : null, e.sospechoso ? " " : null, e.mensaje, e.repeticiones > 1 ? ` (×${e.repeticiones})` : null] },
];

async function dibujar(cont) {
  const d = await api("/api/dashboard");
  const t = d.tarjetas;
  cont.replaceChildren(
    el("h1", {}, "Estado de la red"),
    el("p", { class: "ayuda" }, `Actualización automática cada 10 s · "Sin comunicación" = sin eventos en ${d.umbral_sin_comunicacion_min} min (HU-01)`),
    el("div", { class: "tarjetas" },
      tarjeta("Equipos", t.equipos_total),
      tarjeta("Activos", t.equipos_activos, "ok"),
      tarjeta("Sin comunicación", t.equipos_sin_comunicacion, t.equipos_sin_comunicacion ? "peligro" : ""),
      tarjeta("Eventos 24 h", t.eventos_24h),
      tarjeta("Críticos 24 h (0–2)", t.criticos_24h, t.criticos_24h ? "peligro" : ""),
      tarjeta("Sospechosos 24 h", t.sospechosos_24h, t.sospechosos_24h ? "alerta" : ""),
      tarjeta("Incidentes abiertos", t.incidentes_abiertos, t.incidentes_abiertos ? "alerta" : ""),
      tarjeta("Propuestas por revisar", t.propuestas_pendientes, t.propuestas_pendientes ? "alerta" : "")),
    el("div", { class: "grid-2" },
      el("section", { class: "panel" }, el("h2", {}, "Estado de dispositivos"),
        tabla([
          { titulo: "Equipo", valor: (e) => [el("strong", {}, e.nombre), el("br"), el("small", {}, e.ip)] },
          { titulo: "Marca", valor: (e) => e.marca },
          { titulo: "Estado", valor: (e) => chip(e.estado_operativo) },
          { titulo: "Último evento", valor: (e) => fecha(e.ultimo_evento) },
        ], d.equipos, "No hay equipos en el inventario")),
      el("section", { class: "panel" }, el("h2", {}, "Eventos por severidad (24 h)"), barras(d.por_severidad))),
    el("section", { class: "panel" }, el("h2", {}, "Eventos críticos recientes (severidad 0–2)"),
      tabla(colEventos, d.eventos_criticos, "Sin eventos críticos 👍")),
    el("div", { class: "grid-2" },
      el("section", { class: "panel" }, el("h2", {}, "Incidentes activos"),
        tabla([
          { titulo: "#", valor: (i) => el("a", { href: "#incidentes" }, `INC-${i.id}`) },
          { titulo: "Sev.", valor: (i) => sevBadge(i.severidad) },
          { titulo: "Título", valor: (i) => i.titulo },
          { titulo: "Estado", valor: (i) => chip(i.estado) },
          { titulo: "Responsable", valor: (i) => i.responsable || "—" },
        ], d.incidentes_activos, "Sin incidentes activos")),
      el("section", { class: "panel" }, el("h2", {}, "Controles de ingreso (desde el arranque)"),
        tabla([
          { titulo: "Resultado", valor: (r) => r[0] },
          { titulo: "Mensajes", valor: (r) => r[1] },
        ], Object.entries(d.ingreso), "Aún no llegan mensajes"))),
    el("section", { class: "panel" }, el("h2", {}, "Últimos 10 eventos"), tabla(colEventos, d.eventos_recientes, "Aún no hay eventos. Envía con scripts/enviar_syslog_prueba.py o importa un .log")),
  );
}

export async function render(cont) {
  await dibujar(cont).catch((e) => cont.replaceChildren(el("div", { class: "aviso" }, `No se pudo cargar: ${e.message}`)));
  const timer = setInterval(() => dibujar(cont).catch(() => {}), 10000);
  return () => clearInterval(timer); // se detiene al cambiar de vista
}
