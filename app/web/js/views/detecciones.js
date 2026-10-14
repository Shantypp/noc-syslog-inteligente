/**
 * views/detecciones.js — Detecciones automáticas: patrones entre VARIOS eventos.
 *
 * Un evento suelto dice "qué pasó"; una detección dice "qué está ocurriendo":
 * fuerza bruta, cambios fuera de horario, puertos inestables, tormentas, manipulación.
 * El sistema detecta; el operador decide: convertir en incidente o descartar con motivo.
 */
import { api } from "../api.js";
import { el, fecha, sevBadge, chip, tabla, intentar, encabezado, formulario, puede, avisoRol, enlaceEquipo, montar } from "../ui.js";

export const titulo = "Detecciones";
export const icono = "detecciones";

export const REGLAS = {
  fuerza_bruta: ["Fuerza bruta", "Muchos inicios de sesión fallidos en poco tiempo contra un equipo (posible ataque para adivinar contraseñas)."],
  fuera_de_horario: ["Cambio fuera de horario", "Alguien cambió la configuración de un equipo fuera del horario laboral."],
  puerto_inestable: ["Puerto inestable", "Un puerto o componente cambia de estado una y otra vez (flapping): cable, transceptor o energía."],
  tormenta: ["Tormenta de eventos", "Un equipo envía más mensajes por minuto de los permitidos: falla en cascada o ataque."],
  manipulacion: ["Manipulación en un log", "Un mensaje intenta dar órdenes (inyección). Se guardó como dato; no se ejecutó nada."],
};

export async function render(cont) {
  const filtro = el("select", {},
    el("option", { value: "nueva" }, "Pendientes de revisión"), el("option", { value: "incidente" }, "Convertidas en incidente"),
    el("option", { value: "descartada" }, "Descartadas"), el("option", { value: "todas" }, "Todas"));
  const lista = el("div");
  const avisarMenu = () => window.dispatchEvent(new Event("noc:actualizar-menu"));

  async function cargar() {
    const datos = await intentar(() => api("/api/detecciones", { query: { estado: filtro.value } })) || [];
    lista.replaceChildren(tabla([
      { titulo: "Severidad", valor: (x) => sevBadge(x.severidad) },
      { titulo: "Qué se detectó", valor: (x) => [el("strong", {}, (REGLAS[x.regla] || [x.titulo])[0]), el("br"), el("small", {}, x.detalle)], clase: "mensaje-normal" },
      { titulo: "Equipo", valor: (x) => enlaceEquipo(x.device_id, x.equipo), clase: "nowrap" },
      { titulo: "Veces", valor: (x) => x.cantidad, clase: "num" },
      { titulo: "Primera / última vez", valor: (x) => [fecha(x.creada_en), el("br"), fecha(x.actualizada_en)], clase: "num" },
      { titulo: "Estado", valor: (x) => [chip(x.estado), x.incident_id ? [el("br"), el("a", { href: `#incidentes/${x.incident_id}` }, `INC-${x.incident_id}`)] : null,
          x.motivo ? [el("br"), el("small", {}, `${x.revisado_por}: ${x.motivo}`)] : null] },
      { titulo: "Decisión", valor: (x) => x.estado !== "nueva" || !puede("operador") ? "—" : el("div", { class: "acciones" },
          el("button", { class: "pequeno", onclick: () => aIncidente(x) }, "Abrir incidente"),
          el("button", { class: "pequeno secundario", onclick: () => descartar(x) }, "Descartar")) },
    ], datos, filtro.value === "nueva" ? "No hay detecciones pendientes. El sistema sigue vigilando." : "No hay detecciones con este filtro."));
  }

  async function aIncidente(x) {
    const r = await intentar(() => api(`/api/detecciones/${x.id}/incidente`, { method: "POST" }), "Incidente abierto");
    if (r) { avisarMenu(); location.hash = `incidentes/${r.incident_id}`; }
  }

  async function descartar(x) {
    const d = await formulario({
      titulo: "Descartar detección",
      descripcion: `${(REGLAS[x.regla] || [x.titulo])[0]} en ${x.equipo || "equipo desconocido"}. Indique por qué no requiere atención: queda registrado con su usuario.`,
      campos: [{ id: "motivo", etiqueta: "Motivo", tipo: "select", valor: "Falso positivo", opciones: [
        { valor: "Falso positivo", texto: "Falso positivo" },
        { valor: "Mantenimiento programado", texto: "Mantenimiento programado" },
        { valor: "Prueba de laboratorio", texto: "Prueba de laboratorio" },
        { valor: "Ya atendido por otro medio", texto: "Ya atendido por otro medio" },
      ] }, { id: "detalle", etiqueta: "Comentario", ayuda: "Opcional." }],
      aceptar: "Descartar",
    });
    if (!d) return;
    const motivo = d.detalle ? `${d.motivo}: ${d.detalle}` : d.motivo;
    if (await intentar(() => api(`/api/detecciones/${x.id}/descartar`, { method: "POST", body: { motivo } }), "Detección descartada")) { cargar(); avisarMenu(); }
  }

  filtro.addEventListener("change", cargar);
  montar(cont,
    encabezado("Operación", "Detecciones automáticas",
      "El sistema analiza los eventos en conjunto y detecta patrones que una persona tardaría en notar. Revise cada detección y decida si abre un incidente o la descarta."),
    puede("operador") ? null : avisoRol("Puede consultar las detecciones; abrir incidentes o descartarlas requiere el rol Operador."),
    el("section", { class: "panel" },
      el("div", { class: "filtros" }, el("label", {}, "Mostrar", filtro)),
      lista),
    el("section", { class: "panel" }, el("h2", {}, "¿Qué detecta el sistema?"),
      el("p", { class: "nota" }, "Los umbrales (cuántos intentos, en cuántos minutos, horario laboral...) los ajusta un administrador en Configuración."),
      tabla([
        { titulo: "Regla", valor: ([, [nombre]]) => el("strong", {}, nombre), clase: "nowrap" },
        { titulo: "Qué significa", valor: ([, [, desc]]) => desc },
      ], Object.entries(REGLAS))),
  );
  await cargar();
}
