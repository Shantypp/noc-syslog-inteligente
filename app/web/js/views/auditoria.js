/**
 * views/auditoria.js — Bitácora de comandos y revisión humana de propuestas (RF-08, HU-05).
 * Responde: ¿quién propuso, quién aprobó y qué pasó con cada comando?
 */
import { api } from "../api.js";
import { el, fecha, chip, tabla, intentar, operador } from "../ui.js";

export const titulo = "Auditoría";
export const icono = "✎";

export async function render(cont) {
  const filtro = el("select", {}, el("option", { value: "" }, "Todas"),
    ["PERMITIDO", "BLOQUEADO", "PROPUESTA", "NO_VERIFICADO"].map((d) => el("option", { value: d }, d)));
  const pendientes = el("div");
  const bitacora = el("div");
  const integridad = el("p");

  async function decidir(fila, aprobar) {
    let motivo = null;
    if (!aprobar) {
      motivo = prompt("Motivo del rechazo:", "");
      if (motivo === null) return;
    }
    const r = await intentar(() => api(`/api/auditoria/${fila.id}/${aprobar ? "aprobar" : "rechazar"}`, { method: "POST", body: { usuario: operador(), motivo } }),
      aprobar ? "Propuesta aprobada (ejecución simulada)" : "Propuesta rechazada");
    if (r) cargar();
  }

  async function cargar() {
    const [pend, todos, integ] = await Promise.all([
      api("/api/auditoria", { query: { pendientes: true } }),
      api("/api/auditoria", { query: { decision: filtro.value } }),
      api("/api/auditoria/integridad"),
    ]);
    integridad.replaceChildren(integ.alterados.length
      ? el("span", { style: "color:var(--peligro)" }, `⚠ ${integ.alterados.length} registro(s) ALTERADO(S): ${integ.alterados.join(", ")}`)
      : el("span", { style: "color:var(--ok)" }, `✔ Integridad verificada: ${integ.integros}/${integ.total} registros coinciden con su hash SHA-256`));

    pendientes.replaceChildren(tabla([
      { titulo: "#", valor: (a) => a.id },
      { titulo: "Fecha", valor: (a) => fecha(a.fecha) },
      { titulo: "Propuso", valor: (a) => a.usuario },
      { titulo: "Equipo", valor: (a) => a.equipo || "—" },
      { titulo: "Comando", clase: "mensaje", valor: (a) => a.comando },
      { titulo: `Revisión (como "${operador()}")`, valor: (a) => el("div", { class: "acciones" },
          el("button", { class: "pequeno", onclick: () => decidir(a, true) }, "Aprobar"),
          el("button", { class: "pequeno peligro", onclick: () => decidir(a, false) }, "Rechazar")) },
    ], pend, "No hay propuestas pendientes"));

    bitacora.replaceChildren(tabla([
      { titulo: "#", valor: (a) => a.id },
      { titulo: "Fecha", valor: (a) => fecha(a.fecha) },
      { titulo: "Usuario", valor: (a) => a.usuario },
      { titulo: "Equipo", valor: (a) => a.equipo || "—" },
      { titulo: "Comando", clase: "mensaje", valor: (a) => a.comando },
      { titulo: "Decisión", valor: (a) => chip(a.decision) },
      { titulo: "Aprobado por", valor: (a) => a.aprobado_por || "—" },
      { titulo: "Resultado", valor: (a) => a.resultado },
      { titulo: "Hash", clase: "mensaje", valor: (a) => el("span", { title: a.hash_evidencia }, a.hash_evidencia.slice(0, 12) + "…") },
    ], todos, "Sin registros. Usa la Consola para generar actividad."));
  }

  filtro.addEventListener("change", cargar);
  cont.replaceChildren(
    el("h1", {}, "Auditoría de comandos"),
    el("p", { class: "ayuda" }, "Flujo seguro: propuesta → revisión humana → aprobación → ejecución autorizada (simulada en el MVP) → verificación → auditoría. Quien propone no puede aprobar su propia propuesta."),
    el("section", { class: "panel" }, el("h2", {}, "Propuestas pendientes de revisión humana"), pendientes),
    el("section", { class: "panel" },
      el("div", { class: "filtros" }, el("label", {}, "Decisión", filtro),
        el("a", { href: "/api/auditoria/exportar", download: "auditoria_noc.csv" }, el("button", { class: "secundario" }, "Exportar CSV"))),
      integridad, bitacora),
  );
  await cargar();
}
