/**
 * views/puertos.js — Puertos y componentes: QUÉ PARTE de cada equipo genera el problema.
 * Ej.: R1-NOC · GigabitEthernet0/2 Caído · SW-CORE · Fuente de poder 2 en Falla.
 * El estado actual de cada componente es el de su último evento.
 */
import { api } from "../api.js";
import { el, fecha, sevBadge, chip, tabla, encabezado } from "../ui.js";

export const titulo = "Puertos y componentes";
export const icono = "puertos";

export async function render(cont) {
  const soloProblemas = el("input", { type: "checkbox" });
  const resultado = el("div");
  const resumen = el("p", { class: "total" });

  async function cargar() {
    const d = await api("/api/puertos");
    const lista = soloProblemas.checked ? d.componentes.filter((c) => c.con_problema) : d.componentes;
    resumen.textContent = `${d.total} componentes con eventos registrados · ${d.con_problema} con problema actualmente`;
    const porEquipo = Map.groupBy ? Map.groupBy(lista, (c) => c.equipo) : lista.reduce((m, c) => m.set(c.equipo, [...(m.get(c.equipo) || []), c]), new Map());
    resultado.replaceChildren(...(porEquipo.size ? [...porEquipo].map(([equipo, comps]) => {
      const malos = comps.filter((c) => c.con_problema);
      return el("section", { class: "panel equipo-puertos" },
        el("h2", {}, equipo, el("small", {}, comps[0].marca),
          malos.length ? el("span", { class: "problemas" }, `${malos.length} con problema`) : el("span", { class: "ok-texto" }, "Sin problemas")),
        tabla([
          { titulo: "Componente", valor: (c) => el("strong", {}, c.componente), clase: "nowrap" },
          { titulo: "Estado actual", valor: (c) => chip(c.estado) },
          { titulo: "Último evento", valor: (c) => fecha(c.ultimo_evento), clase: "num" },
          { titulo: "Severidad", valor: (c) => sevBadge(c.severidad) },
          { titulo: "Mensaje", valor: (c) => c.ultimo_mensaje, clase: "mensaje" },
          { titulo: "Historial", valor: (c) => `${c.eventos} evento(s) · ${c.problemas} problema(s)`, clase: "num" },
          { titulo: "Incidente", valor: (c) => c.incidente_abierto ? el("a", { href: "#incidentes" }, `INC-${c.incidente_abierto}`) : "—" },
        ], comps));
    }) : [el("section", { class: "panel" }, el("p", { class: "total" },
      soloProblemas.checked ? "No hay componentes con problema." : "Aún no hay eventos que identifiquen puertos o componentes."))]));
  }

  soloProblemas.addEventListener("change", cargar);
  cont.replaceChildren(
    encabezado("Operación", "Puertos y componentes",
      "Indica qué parte de cada equipo está generando el problema: puertos e interfaces, fuentes de poder, sensores, túneles VPN y clúster de alta disponibilidad. Se identifica automáticamente a partir del texto de cada evento."),
    el("div", { class: "filtros" }, el("label", { class: "check" }, soloProblemas, "Mostrar solo componentes con problema")),
    resumen, resultado,
  );
  await cargar();
}
