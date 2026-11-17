/**
 * views/sistema.js — Configuración del sistema (solo administrador).
 *
 *  - Estado del colector: si el receptor Syslog está escuchando y a qué IP/puerto apuntar los equipos.
 *  - Parámetros: umbrales y reglas, editables sin tocar archivos ni reiniciar.
 *  - Mantenimiento: datos de demostración, respaldo descargable y retención.
 */
import { api } from "../api.js";
import { el, fecha, intentar, encabezado, confirmar, aviso, botonDescarga, montar } from "../ui.js";

export const titulo = "Configuración";
export const icono = "sistema";
export const rolMinimo = "administrador";

const GRUPOS = [
  ["Incidentes y estado de los equipos", ["umbral_incidente", "minutos_sin_comunicacion", "intervalo_ping_s"]],
  ["Control de tormentas", ["ventana_dedup_s", "limite_por_minuto"]],
  ["Detecciones automáticas", ["fuerza_bruta_intentos", "fuerza_bruta_ventana_min", "inestable_cambios", "inestable_ventana_min",
    "horario_inicio", "horario_fin", "desfase_utc"]],
  ["Defensa frente a agentes automatizados o de IA", ["aprobacion_ventana_min", "consola_max_por_minuto"]],
  ["Alertas por Telegram", ["telegram_severidad", "telegram_espera_min"]],
  ["Datos", ["dias_retencion"]],
];

function panelTelegram(t) {
  if (!t) return null;
  async function probar() {
    const r = await intentar(() => api("/api/sistema/telegram/prueba", { method: "POST" }));
    if (r) aviso("Mensaje de prueba enviado. Revise el chat de Telegram.");
  }
  return el("section", { class: "panel" }, el("h2", {}, "Alertas por Telegram"),
    el("dl", { class: "lista-datos" },
      el("dt", {}, "Estado"),
      el("dd", {}, el("span", { class: `semaforo ${t.configurado ? "verde" : "rojo"}` }),
        t.configurado ? `Configurado (bot ${t.token} · chat ${t.chat_id})` : "Sin configurar: escriba TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en el archivo .env y reinicie el NOC"),
      el("dt", {}, "Qué se avisa"),
      el("dd", {}, "Equipos que caen o vuelven (ping), pérdida de la red de gestión, detecciones nuevas y eventos graves."),
      el("dt", {}, "Enviadas / descartadas"),
      el("dd", {}, `${t.enviadas} enviadas · ${t.descartadas_por_inundacion} descartadas por anti-inundación (máx. ${t.max_por_minuto}/min) · ${t.errores} errores`),
      t.ultimo_error ? [el("dt", {}, "Último error"), el("dd", {}, t.ultimo_error)] : null),
    el("p", { class: "nota", style: "margin:12px 0" }, "El token nunca se muestra completo ni se guarda en la base de datos: vive solo en el archivo .env del servidor."),
    el("button", { class: "secundario", disabled: !t.configurado, onclick: probar }, "Enviar mensaje de prueba"));
}

function estadoColector(s) {
  const udp = s.udp;
  return el("section", { class: "panel" }, el("h2", {}, "Estado del colector"),
    el("dl", { class: "lista-datos" },
      el("dt", {}, "Receptor Syslog (UDP)"),
      el("dd", {}, el("span", { class: `semaforo ${udp.activo ? "verde" : "rojo"}` }),
        udp.activo ? `Escuchando en ${udp.host}:${udp.puerto}` : (udp.error || "Apagado (SYSLOG_UDP_ENABLED=0)")),
      el("dt", {}, "Quién puede enviar"),
      el("dd", {}, udp.solo_local ? "Solo este computador (modo laboratorio seguro)"
        : `Equipos de la red, hacia ${s.ips_del_equipo.join(" o ") || "la IP de este computador"} puerto ${udp.puerto}`),
      el("dt", {}, "Eventos recibidos"), el("dd", {}, `${s.eventos_ultimo_minuto} en el último minuto · ${s.eventos_ultima_hora} en la última hora`),
      el("dt", {}, "Último evento"), el("dd", {}, fecha(s.ultimo_evento)),
      el("dt", {}, "Base de datos"), el("dd", {}, `${s.eventos_guardados} eventos · ${s.equipos} equipos · ${s.base_de_datos_mb ?? "—"} MB`),
      el("dt", {}, "Versión"), el("dd", {}, `NOC Syslog ${s.version}`)),
    udp.solo_local ? el("p", { class: "nota", style: "margin:12px 0 0" },
      "Para recibir logs de routers reales, inicie el sistema con iniciar-red.bat (o python iniciar.py --red). Vea Ayuda › Conectar un equipo.") : null);
}

export async function render(cont) {
  const [estado, parametros, tg] = await Promise.all([api("/api/sistema/estado").catch(() => null),
    api("/api/sistema/configuracion").catch(() => []), api("/api/sistema/telegram").catch(() => null)]);
  const porClave = Object.fromEntries(parametros.map((p) => [p.clave, p]));
  const entradas = {};
  const guardar = el("button", { disabled: true }, "Guardar cambios");

  const filas = GRUPOS.map(([grupo, claves]) => [
    el("div", { class: "grupo-parametros" }, grupo),
    claves.filter((c) => porClave[c]).map((c) => {
      const p = porClave[c];
      const input = el("input", { type: "number", min: p.minimo, max: p.maximo, value: p.valor, "aria-label": p.nombre });
      input.addEventListener("input", () => {
        input.classList.toggle("cambiado", Number(input.value) !== p.valor);
        guardar.disabled = !Object.values(entradas).some((i) => i.classList.contains("cambiado"));
      });
      entradas[c] = input;
      return el("div", { class: "parametro" },
        el("div", {}, el("strong", {}, p.nombre), el("small", {}, p.descripcion),
          el("small", { class: "suave" }, `Rango ${p.minimo} a ${p.maximo} · por defecto ${p.defecto}`
            + (p.modificado_por ? ` · cambiado por ${p.modificado_por} el ${fecha(p.modificado_en)}` : ""))),
        el("div", { class: "control" }, input, el("span", { class: "suave" }, p.unidad)));
    }),
  ]);

  guardar.addEventListener("click", async () => {
    const valores = {};
    for (const [c, i] of Object.entries(entradas)) if (i.classList.contains("cambiado")) valores[c] = Number(i.value);
    if (await intentar(() => api("/api/sistema/configuracion", { method: "PUT", body: { valores } }), "Configuración guardada. Se aplica de inmediato.")) render(cont);
  });

  async function demo() {
    const ok = await confirmar("Cargar datos de demostración",
      "Se registrarán 3 equipos SIMULADOS (IPs de documentación 192.0.2.x) y se importarán eventos de ejemplo. Si ya existen, no se duplican.", "Cargar demostración");
    if (!ok) return;
    const r = await intentar(() => api("/api/sistema/demo", { method: "POST" }));
    if (r) { aviso(`Demostración cargada: ${r.equipos_creados} equipo(s) nuevo(s), ${r.eventos.guardado || 0} evento(s) guardados.`); window.dispatchEvent(new Event("noc:actualizar-menu")); render(cont); }
  }

  async function retencion() {
    const dias = porClave.dias_retencion?.valor;
    const ok = await confirmar("Aplicar retención ahora",
      `Se eliminarán los eventos de más de ${dias} días, excepto los vinculados a incidentes (son evidencia). Esto también ocurre automáticamente cada vez que se inicia el servidor.`, "Aplicar retención", true);
    if (!ok) return;
    const r = await intentar(() => api("/api/sistema/retencion", { method: "POST" }));
    if (r) { aviso(`Retención aplicada: ${r.eventos_eliminados} evento(s) eliminados.`); render(cont); }
  }

  montar(cont,
    encabezado("Administración", "Configuración del sistema",
      "Ajuste cómo trabaja el NOC sin editar archivos ni reiniciar. Cada cambio queda registrado con su usuario y la fecha."),
    estado ? estadoColector(estado) : el("div", { class: "aviso" }, "No se pudo consultar el estado del colector."),
    panelTelegram(tg),
    el("section", { class: "panel" },
      el("h2", {}, "Parámetros", el("span", { style: "margin-left:auto" }, guardar)),
      el("div", { class: "parametros" }, filas)),
    el("section", { class: "panel" }, el("h2", {}, "Mantenimiento"),
      el("div", { class: "parametros" },
        el("div", { class: "parametro" }, el("div", {}, el("strong", {}, "Datos de demostración"),
          el("small", {}, "Registra equipos simulados y carga eventos de ejemplo para practicar o presentar el sistema.")),
          el("div", { class: "control" }, el("button", { class: "secundario", onclick: demo }, "Cargar demostración"))),
        el("div", { class: "parametro" }, el("div", {}, el("strong", {}, "Respaldo de la base de datos"),
          el("small", {}, "Descarga una copia completa (archivo .db). Guárdela en un lugar seguro: contiene la auditoría y los usuarios (sin contraseñas, solo sus huellas).")),
          el("div", { class: "control" }, botonDescarga("/api/sistema/respaldo", "Descargar respaldo"))),
        el("div", { class: "parametro" }, el("div", {}, el("strong", {}, "Retención de eventos"),
          el("small", {}, `Elimina eventos de más de ${porClave.dias_retencion?.valor ?? "—"} días que no estén vinculados a incidentes.`)),
          el("div", { class: "control" }, el("button", { class: "peligro", onclick: retencion }, "Aplicar ahora"))))),
  );
}
