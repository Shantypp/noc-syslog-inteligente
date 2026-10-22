/**
 * views/dashboard.js — Panel general (RF-04, HU-01).
 *
 * Arriba: "Requiere su atención", la lista de lo que hay que hacer AHORA, ordenada por prioridad
 *         (SLA vencidos, detecciones, propuestas, aprobaciones, equipos caídos, recuperados).
 * Debajo: indicadores, estado de equipos, severidades, críticos e incidentes.
 * Se actualiza cada 10 s.
 */
import { api } from "../api.js";
import { el, fecha, sevBadge, chip, tabla, encabezado, componente, enlaceEquipo, icono as figura, plural, SEVERIDADES, montar } from "../ui.js";

export const titulo = "Panel general";
export const icono = "panel";

function tarjeta(etiqueta, valor, clase = "", destino = null) {
  const contenido = [el("div", { class: "valor" }, valor), el("div", { class: "etiqueta" }, etiqueta)];
  return destino ? el("a", { class: `tarjeta enlace ${clase}`, href: `#${destino}` }, contenido) : el("div", { class: `tarjeta ${clase}` }, contenido);
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

const IR_A = { sla: "Gestionar incidente", recuperado: "Revisar y cerrar", deteccion: "Revisar detección",
  propuestas: "Decidir", aprobaciones: "Aprobar o rechazar", sin_comunicacion: "Ver equipos" };

/** "Requiere su atención": cada fila dice qué pasa, dónde y lleva a la pantalla que lo resuelve. */
function bandeja(items) {
  return el("section", { class: "bandeja" },
    el("h2", {}, "Requiere su atención", items.length ? chip(items.length > 1 ? `${items.length} asuntos` : "1 asunto") : null),
    items.length
      ? items.map((it) => el("a", { class: `item-atencion p${it.prioridad}`, href: `#${it.enlace}` },
          el("span", { class: "franja" }),
          el("div", {}, el("strong", {}, it.titulo), el("small", {}, it.detalle)),
          el("span", { class: "ir" }, `${IR_A[it.tipo] || "Ver"} →`)))
      : el("div", { class: "bandeja-vacia" }, figura("seguridad", 18), "Todo en orden: no hay asuntos pendientes."));
}

async function dibujar(cont) {
  const d = await api("/api/dashboard");
  const t = d.tarjetas;
  const ingreso = Object.entries(d.ingreso);
  montar(cont,
    encabezado("Operación", "Panel general",
      `Estado de la red en tiempo real (se actualiza cada 10 segundos). Empiece por "Requiere su atención": está ordenado por prioridad.`),

    bandeja(d.atencion),

    el("div", { class: "tarjetas" },
      tarjeta("Equipos activos", `${t.equipos_activos} de ${t.equipos_total}`, "ok", "inventario"),
      tarjeta("Sin comunicación", t.equipos_sin_comunicacion, t.equipos_sin_comunicacion ? "peligro" : "", "inventario"),
      tarjeta("Eventos últimas 24 h", t.eventos_24h, "", "eventos"),
      tarjeta(`Eventos graves (0–${d.umbral_incidente})`, t.criticos_24h, t.criticos_24h ? "peligro" : "", "eventos"),
      tarjeta("Detecciones nuevas", t.detecciones_nuevas, t.detecciones_nuevas ? "alerta" : "", "detecciones"),
      tarjeta("Incidentes abiertos", t.incidentes_abiertos, t.incidentes_abiertos ? "alerta" : "", "incidentes"),
      tarjeta("Componentes con problema", t.componentes_con_problema, t.componentes_con_problema ? "peligro" : "", "puertos")),

    el("div", { class: "grid-2" },
      el("section", { class: "panel" }, el("h2", {}, "Estado de los equipos"),
        el("p", { class: "nota" }, `Clic en un equipo para ver su ficha completa. A los equipos reales el NOC les hace ping para saber si están vivos; a los demás se les mira si enviaron eventos en los últimos ${d.umbral_sin_comunicacion_min} min.`),
        tabla([
          { titulo: "Equipo", valor: (e) => [enlaceEquipo(e.id, e.nombre), el("br"), el("small", {}, `${e.ip} · ${e.marca}`)], clase: "nowrap" },
          { titulo: "Estado", valor: (e) => [chip(e.estado_operativo), e.conectividad ? [el("br"), el("small", {}, e.conectividad)] : null] },
          { titulo: "Dónde está el problema", valor: (e) => e.componentes_con_problema.length
              ? el("a", { href: `#equipo/${e.id}`, class: "problemas" }, e.componentes_con_problema.join(", ")) : el("span", { class: "suave" }, "Sin problemas") },
          { titulo: "Último evento", valor: (e) => fecha(e.ultimo_evento), clase: "num" },
        ], d.equipos, "No hay equipos registrados. Comience en Inventario o cargue la demostración en Configuración.")),
      el("section", { class: "panel" }, el("h2", {}, "Eventos por severidad (24 h)"), barras(d.por_severidad))),

    el("section", { class: "panel" }, el("h2", {}, "Eventos graves recientes"),
      tabla([
        { titulo: "Fecha", valor: (e) => fecha(e.recibido_en), clase: "num" },
        { titulo: "Equipo", valor: (e) => enlaceEquipo(e.device_id, e.equipo || e.hostname), clase: "nowrap" },
        { titulo: "Severidad", valor: (e) => sevBadge(e.severidad) },
        { titulo: "Componente", valor: componente },
        { titulo: "Mensaje", clase: "mensaje", valor: mensaje },
      ], d.eventos_criticos, "No hay eventos graves.")),

    el("div", { class: "grid-2" },
      el("section", { class: "panel" }, el("h2", {}, "Incidentes abiertos"),
        tabla([
          { titulo: "N.º", valor: (i) => el("a", { href: `#incidentes/${i.id}` }, `INC-${i.id}`), clase: "nowrap" },
          { titulo: "Equipo", valor: (i) => enlaceEquipo(i.device_id, i.equipo), clase: "nowrap" },
          { titulo: "Severidad", valor: (i) => sevBadge(i.severidad) },
          { titulo: "Estado", valor: (i) => [chip(i.estado), i.recuperado_en ? [" ", chip("recuperado")] : null] },
          { titulo: "Responsable", valor: (i) => i.responsable || "Sin asignar" },
        ], d.incidentes_activos, "No hay incidentes abiertos.")),
      el("section", { class: "panel" }, el("h2", {}, "Control de ingreso de mensajes (hoy)"),
        el("p", { class: "nota" }, "Qué pasó con cada mensaje recibido hoy. Los contadores se conservan aunque se reinicie el servidor."),
        tabla([
          { titulo: "Resultado", valor: (r) => ({ guardado: "Guardados", duplicado: "Agrupados como repetidos", limitado: "Descartados por límite de frecuencia",
              fuente_no_autorizada: "Rechazados: equipo no registrado", invalido: "Rechazados: formato inválido" })[r[0]] || r[0] },
          { titulo: "Mensajes", valor: (r) => r[1], clase: "num" },
        ], ingreso, "Aún no se han recibido mensajes hoy."))),

    el("section", { class: "panel" }, el("h2", {}, "Últimos eventos recibidos"),
      tabla([
        { titulo: "Fecha", valor: (e) => fecha(e.recibido_en), clase: "num" },
        { titulo: "Equipo", valor: (e) => enlaceEquipo(e.device_id, e.equipo || e.hostname), clase: "nowrap" },
        { titulo: "Severidad", valor: (e) => sevBadge(e.severidad) },
        { titulo: "Componente", valor: componente },
        { titulo: "Mensaje", clase: "mensaje", valor: mensaje },
      ], d.eventos_recientes, `Aún no hay eventos. ${plural(t.equipos_total, "equipo registrado", "equipos registrados")}: vea Ayuda › Conectar un equipo.`)),
  );
}

export async function render(cont) {
  await dibujar(cont).catch((e) => montar(cont, el("div", { class: "aviso" }, `No se pudo cargar el panel: ${e.message}`)));
  // Al refrescar el panel también se actualizan los contadores del menú (mismos datos, mismo momento)
  const timer = setInterval(() => dibujar(cont).then(() => window.dispatchEvent(new Event("noc:actualizar-menu"))).catch(() => {}), 10000);
  return () => clearInterval(timer); // se detiene al cambiar de vista
}
