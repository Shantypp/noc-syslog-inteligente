/**
 * views/auditoria.js — Bitácora de comandos y aprobación de cambios (RF-08, HU-05).
 * Responde: ¿quién propuso, quién aprobó y qué pasó con cada comando?
 */
import { api } from "../api.js";
import { el, fecha, chip, tabla, intentar, encabezado, formulario, puede, sesion } from "../ui.js";

export const titulo = "Auditoría";
export const icono = "auditoria";

export async function render(cont) {
  const filtro = el("select", {}, el("option", { value: "" }, "Todas"),
    ["PERMITIDO", "BLOQUEADO", "PROPUESTA", "NO_VERIFICADO"].map((d) => el("option", { value: d }, { PERMITIDO: "Permitido", BLOQUEADO: "Bloqueado", PROPUESTA: "Propuesta", NO_VERIFICADO: "No verificado" }[d])));
  const pendientes = el("div");
  const bitacora = el("div");
  const integridad = el("div");
  const usuarioActual = el("strong");

  async function decidir(fila, aprobar) {
    let motivo = null;
    if (aprobar) {
      const ok = await formulario({ titulo: `Aprobar cambio #${fila.id}`, aceptar: "Aprobar",
        descripcion: `Comando "${fila.comando}" propuesto por ${fila.usuario} en ${fila.equipo || "sin equipo"}. En esta versión la ejecución es simulada: no se envía nada a ningún equipo.` });
      if (!ok) return;
    } else {
      const d = await formulario({ titulo: `Rechazar cambio #${fila.id}`, aceptar: "Rechazar", peligro: true,
        campos: [{ id: "motivo", etiqueta: "Motivo del rechazo", tipo: "textarea", requerido: true }] });
      if (!d) return;
      motivo = d.motivo;
    }
    const r = await intentar(() => api(`/api/auditoria/${fila.id}/${aprobar ? "aprobar" : "rechazar"}`, { method: "POST", body: { motivo } }),
      aprobar ? "Cambio aprobado (ejecución simulada)" : "Cambio rechazado");
    if (r) { cargar(); window.dispatchEvent(new Event("noc:actualizar-menu")); }
  }

  async function cargar() {
    usuarioActual.textContent = `${sesion.usuario.nombre} (${sesion.usuario.rol_nombre})`;
    const [pend, todos, integ] = await Promise.all([
      api("/api/auditoria", { query: { pendientes: true } }),
      api("/api/auditoria", { query: { decision: filtro.value } }),
      api("/api/auditoria/integridad"),
    ]);
    integridad.replaceChildren(integ.alterados.length
      ? el("div", { class: "aviso" }, el("strong", {}, "Alerta de integridad: "), `${integ.alterados.length} registro(s) fueron modificados fuera de la aplicación (N.º ${integ.alterados.join(", ")}).`)
      : el("div", { class: "aviso info" }, el("strong", {}, "Integridad verificada: "),
          integ.total === 1 ? "el registro coincide con su huella SHA-256; no fue alterado."
            : `los ${integ.total} registros coinciden con su huella SHA-256. Ningún registro fue alterado.`));

    pendientes.replaceChildren(tabla([
      { titulo: "N.º", valor: (a) => a.id, clase: "num" },
      { titulo: "Fecha", valor: (a) => fecha(a.fecha), clase: "num" },
      { titulo: "Propuesto por", valor: (a) => a.usuario },
      { titulo: "Equipo", valor: (a) => a.equipo || "—" },
      { titulo: "Comando", clase: "mensaje", valor: (a) => a.comando },
      { titulo: "Decisión", valor: (a) => !puede("administrador") ? el("span", { class: "suave" }, "Requiere Administrador")
          : a.usuario.toLowerCase() === sesion.usuario.usuario.toLowerCase() ? el("span", { class: "suave" }, "Propuesto por usted: debe aprobarlo otro administrador")
          : el("div", { class: "acciones" },
          el("button", { class: "pequeno", onclick: () => decidir(a, true) }, "Aprobar"),
          el("button", { class: "pequeno peligro", onclick: () => decidir(a, false) }, "Rechazar")) },
    ], pend, "No hay cambios pendientes de aprobación."));

    bitacora.replaceChildren(tabla([
      { titulo: "N.º", valor: (a) => a.id, clase: "num" },
      { titulo: "Fecha", valor: (a) => fecha(a.fecha), clase: "num" },
      { titulo: "Usuario", valor: (a) => a.usuario },
      { titulo: "Equipo", valor: (a) => a.equipo || "—" },
      { titulo: "Comando", clase: "mensaje", valor: (a) => a.comando },
      { titulo: "Decisión", valor: (a) => chip(a.decision) },
      { titulo: "Aprobado por", valor: (a) => a.aprobado_por || "—" },
      { titulo: "Resultado", valor: (a) => a.resultado === "PENDIENTE_APROBACION" ? "Pendiente de aprobación" : a.resultado },
      { titulo: "Huella", clase: "mensaje", valor: (a) => el("span", { title: a.hash_evidencia }, a.hash_evidencia.slice(0, 10)) },
    ], todos, "Sin registros. La actividad de la Consola de equipos aparece aquí."));
  }

  filtro.addEventListener("change", cargar);
  cont.replaceChildren(
    encabezado("Control de cambios", "Auditoría",
      "Registro de cada comando: quién lo escribió, cuándo, en qué equipo y qué decidió el sistema. Los cambios propuestos se aprueban aquí.",
      el("a", { href: "/api/auditoria/exportar", download: "auditoria_noc.csv" }, el("button", { class: "secundario" }, "Exportar CSV"))),
    el("section", { class: "panel" },
      el("h2", {}, "Cambios pendientes de aprobación"),
      el("p", { class: "nota" }, "Solo un administrador aplica cambios, y nunca los que él mismo propuso (separación de funciones). Usuario de la sesión: ", usuarioActual, "."),
      pendientes),
    el("section", { class: "panel" },
      el("h2", {}, "Bitácora de comandos"),
      integridad,
      el("div", { class: "filtros" }, el("label", {}, "Decisión", filtro)),
      bitacora),
  );
  await cargar();
}
