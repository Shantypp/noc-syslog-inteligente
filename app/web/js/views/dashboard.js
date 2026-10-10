/**
 * views/dashboard.js — Panel general (RF-04, HU-01).
 * Arriba: los 4 pasos del trabajo del operador con su estado actual.
 * Debajo: indicadores, estado de equipos, severidades, críticos e incidentes.
 * Se actualiza cada 10 s.
 */
import { api } from "../api.js";
import { el, fecha, sevBadge, chip, tabla, encabezado, componente, SEVERIDADES, montar } from "../ui.js";

export const titulo = "Panel general";
export const icono = "panel";

/** "1 incidente abierto" / "2 incidentes abiertos" */
const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;

function tarjeta(etiqueta, valor, clase = "") {
  return el("div", { class: `tarjeta ${clase}` }, el("div", { class: "valor" }, valor), el("div", { class: "etiqueta" }, etiqueta));
}

/** Paso del flujo de trabajo: número, qué hacer, dónde y cómo va. */
function paso(n, tituloPaso, detalle, estado, destino, pendiente = false) {
  return el("a", { class: `paso ${pendiente ? "pendiente" : ""}`, href: `#${destino}` },
    el("span", { class: "numero" }, n), el("span", { class: "titulo" }, tituloPaso),
    el("span", { class: "detalle" }, detalle), el("span", { class: "situacion" }, estado));
}

function barras(conteos) {
  const max = Math.max(1, ...conteos);
  return el("div", { class: "barras" }, conteos.map((n, sev) =>
    el("div", { class: "barra" },
      el("span", {}, `${sev} · ${SEVERIDADES[sev]}`),
      el("div", { class: "pista" }, el("div", { class: `relleno ${sev <= 2 ? "grave" : ""}`, style: `width:${(n / max) * 100}%` })),
      el("strong", {}, n))));
}

const mensaje = (e) => [e.sospechoso ? el("span", { class: "marca-sospechoso" }, "SOSPECHOSO") : null,
  e.mensaje, e.repeticiones > 1 ? ` (×${e.repeticiones})` : null];

async function dibujar(cont) {
  const d = await api("/api/dashboard");
  const t = d.tarjetas;
  montar(cont, 
    encabezado("Operación", "Panel general",
      `Estado de la red en tiempo real. Se actualiza cada 10 segundos. Un equipo pasa a "Sin comunicación" si no envía eventos en ${d.umbral_sin_comunicacion_min} minutos.`),

    el("h2", {}, "Flujo de trabajo del operador"),
    el("div", { class: "flujo" },
      paso(1, "Registrar equipos", "Solo los equipos del inventario pueden enviar eventos.",
        plural(t.equipos_total, "equipo registrado", "equipos registrados"), "inventario", t.equipos_total === 0),
      paso(2, "Recibir eventos", "Llegan por Syslog o se importan desde un archivo.",
        plural(t.eventos_24h, "evento en 24 h", "eventos en 24 h"), "eventos"),
      paso(3, "Revisar eventos graves", "El sistema propone; usted decide si abre incidente.",
        t.propuestas_pendientes ? plural(t.propuestas_pendientes, "evento pendiente de revisión", "eventos pendientes de revisión") : "Sin pendientes", "incidentes", t.propuestas_pendientes > 0),
      paso(4, "Gestionar incidentes", "Asignar responsable, dar seguimiento y cerrar.",
        t.incidentes_abiertos ? plural(t.incidentes_abiertos, "incidente abierto", "incidentes abiertos") : "Sin incidentes abiertos", "incidentes", t.incidentes_abiertos > 0)),

    el("div", { class: "tarjetas" },
      tarjeta("Equipos activos", `${t.equipos_activos} de ${t.equipos_total}`, "ok"),
      tarjeta("Equipos sin comunicación", t.equipos_sin_comunicacion, t.equipos_sin_comunicacion ? "peligro" : ""),
      tarjeta("Eventos últimas 24 h", t.eventos_24h),
      tarjeta("Eventos críticos (0–2)", t.criticos_24h, t.criticos_24h ? "peligro" : ""),
      tarjeta("Componentes con problema", t.componentes_con_problema, t.componentes_con_problema ? "peligro" : ""),
      tarjeta("Eventos sospechosos", t.sospechosos_24h, t.sospechosos_24h ? "alerta" : ""),
      tarjeta("Aprobaciones pendientes", t.aprobaciones_pendientes, t.aprobaciones_pendientes ? "alerta" : "")),

    el("div", { class: "grid-2" },
      el("section", { class: "panel" }, el("h2", {}, "Estado de los equipos"),
        tabla([
          { titulo: "Equipo", valor: (e) => [el("strong", {}, e.nombre), el("br"), el("small", {}, e.ip)], clase: "nowrap" },
          { titulo: "Marca", valor: (e) => e.marca },
          { titulo: "Estado", valor: (e) => chip(e.estado_operativo) },
          { titulo: "Dónde está el problema", valor: (e) => e.componentes_con_problema.length
              ? el("a", { href: "#puertos", class: "problemas" }, e.componentes_con_problema.join(", ")) : el("span", { class: "suave" }, "Sin problemas") },
          { titulo: "Último evento", valor: (e) => fecha(e.ultimo_evento), clase: "num" },
        ], d.equipos, "No hay equipos registrados. Comience en Inventario.")),
      el("section", { class: "panel" }, el("h2", {}, "Eventos por severidad (24 h)"), barras(d.por_severidad))),

    el("section", { class: "panel" }, el("h2", {}, "Eventos críticos recientes"),
      tabla([
        { titulo: "Fecha", valor: (e) => fecha(e.recibido_en), clase: "num" },
        { titulo: "Equipo", valor: (e) => e.equipo || e.hostname || "—", clase: "nowrap" },
        { titulo: "Severidad", valor: (e) => sevBadge(e.severidad) },
        { titulo: "Componente", valor: componente },
        { titulo: "Mensaje", clase: "mensaje", valor: mensaje },
        { titulo: "Incidente", valor: (e) => el("a", { href: "#incidentes" }, "Revisar") },
      ], d.eventos_criticos, "No hay eventos críticos.")),

    el("div", { class: "grid-2" },
      el("section", { class: "panel" }, el("h2", {}, "Incidentes abiertos"),
        tabla([
          { titulo: "N.º", valor: (i) => el("a", { href: "#incidentes" }, `INC-${i.id}`), clase: "nowrap" },
          { titulo: "Severidad", valor: (i) => sevBadge(i.severidad) },
          { titulo: "Estado", valor: (i) => chip(i.estado) },
          { titulo: "Responsable", valor: (i) => i.responsable || "Sin asignar" },
        ], d.incidentes_activos, "No hay incidentes abiertos.")),
      el("section", { class: "panel" }, el("h2", {}, "Control de ingreso de mensajes"),
        el("p", { class: "nota" }, "Resultado de cada mensaje recibido desde que se inició el servidor."),
        tabla([
          { titulo: "Resultado", valor: (r) => ({ guardado: "Guardados", duplicado: "Agrupados como repetidos", limitado: "Descartados por límite de frecuencia",
              fuente_no_autorizada: "Rechazados: equipo no registrado", invalido: "Rechazados: formato inválido" })[r[0]] || r[0] },
          { titulo: "Mensajes", valor: (r) => r[1], clase: "num" },
        ], Object.entries(d.ingreso), "Aún no se han recibido mensajes."))),

    el("section", { class: "panel" }, el("h2", {}, "Últimos eventos recibidos"),
      tabla([
        { titulo: "Fecha", valor: (e) => fecha(e.recibido_en), clase: "num" },
        { titulo: "Equipo", valor: (e) => e.equipo || e.hostname || "—", clase: "nowrap" },
        { titulo: "Severidad", valor: (e) => sevBadge(e.severidad) },
        { titulo: "Componente", valor: componente },
        { titulo: "Mensaje", clase: "mensaje", valor: mensaje },
      ], d.eventos_recientes, "Aún no hay eventos. Ejecute scripts/enviar_syslog_prueba.py o importe un archivo en Eventos.")),
  );
}

export async function render(cont) {
  await dibujar(cont).catch((e) => montar(cont, el("div", { class: "aviso" }, `No se pudo cargar el panel: ${e.message}`)));
  const timer = setInterval(() => dibujar(cont).catch(() => {}), 10000);
  return () => clearInterval(timer); // se detiene al cambiar de vista
}
