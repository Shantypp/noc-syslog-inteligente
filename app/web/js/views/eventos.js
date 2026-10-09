/**
 * views/eventos.js — Consulta de eventos con filtros (RF-04, HU-02) e importación (RF-02).
 * Filtros: fecha desde/hasta, marca, equipo y rango de severidad. El total se actualiza.
 */
import { api, subirArchivo } from "../api.js";
import { el, fecha, sevBadge, chip, tabla, intentar, operador, aviso, SEVERIDADES } from "../ui.js";

export const titulo = "Eventos";
export const icono = "≡";

const opcionesSev = (sel) => SEVERIDADES.map((n, i) => el("option", { value: i, selected: i === sel }, `${i} · ${n}`));

/** Fecha local del input (AAAA-MM-DD) -> ISO UTC del inicio o del final de ese día. */
function limiteDia(valor, finDelDia) {
  if (!valor) return "";
  return new Date(`${valor}T${finDelDia ? "23:59:59" : "00:00:00"}`).toISOString();
}

export async function render(cont) {
  const equipos = await api("/api/devices").catch(() => []);

  const f = {
    desde: el("input", { type: "date" }),
    hasta: el("input", { type: "date" }),
    marca: el("select", {}, el("option", { value: "" }, "Todas"), ["Cisco", "Fortinet", "Huawei"].map((m) => el("option", { value: m }, m))),
    equipo: el("select", {}, el("option", { value: "" }, "Todos"), equipos.map((d) => el("option", { value: d.id }, `${d.nombre} (${d.marca})`))),
    sevMin: el("select", {}, opcionesSev(0)),
    sevMax: el("select", {}, opcionesSev(7)),
    sospechosos: el("input", { type: "checkbox" }),
  };
  const total = el("p", { class: "total" });
  const resultado = el("div");
  let ultimaConsulta = 0; // evita que una respuesta vieja pise a una más nueva

  async function buscar() {
    const numero = ++ultimaConsulta;
    const r = await intentar(() => api("/api/events", {
      query: {
        desde: limiteDia(f.desde.value, false), hasta: limiteDia(f.hasta.value, true),
        marca: f.marca.value, device_id: f.equipo.value,
        sev_min: f.sevMin.value, sev_max: f.sevMax.value,
        solo_sospechosos: f.sospechosos.checked || "", limit: 200,
      },
    }));
    if (!r || numero !== ultimaConsulta) return; // llegó tarde: ya hay una consulta más reciente
    total.textContent = `${r.total} evento(s) cumplen el filtro${r.total > r.eventos.length ? ` · mostrando ${r.eventos.length}` : ""}`;
    resultado.replaceChildren(tabla([
      { titulo: "ID", valor: (e) => e.id },
      { titulo: "Recibido", valor: (e) => fecha(e.recibido_en) },
      { titulo: "Equipo", valor: (e) => [e.equipo || "—", el("br"), el("small", {}, e.marca || "")] },
      { titulo: "Severidad", valor: (e) => sevBadge(e.severidad) },
      { titulo: "Facility", valor: (e) => `${e.facility} · ${e.facility_nombre}` },
      { titulo: "Mensaje", clase: "mensaje", valor: (e) => [e.sospechoso ? chip("⚠ sospechoso", "sospechoso") : null, e.sospechoso ? " " : null, e.mensaje, e.repeticiones > 1 ? ` (×${e.repeticiones})` : null] },
      { titulo: "Origen", valor: (e) => e.origen },
      { titulo: "Incidente", valor: (e) => e.incident_id
          ? el("a", { href: "#incidentes" }, `INC-${e.incident_id}`)
          : el("button", { class: "pequeno secundario", onclick: () => crearIncidente(e) }, "Crear") },
    ], r.eventos, "Ningún evento cumple el filtro"));
  }

  async function crearIncidente(e) {
    const responsable = prompt(`Crear incidente para el evento ${e.id}.\nResponsable (opcional):`, "");
    if (responsable === null) return; // canceló
    const inc = await intentar(() => api("/api/incidents", {
      method: "POST", body: { usuario: operador(), event_id: e.id, responsable: responsable.trim() || null },
    }), "Incidente creado");
    if (inc) buscar();
  }

  const archivo = el("input", { type: "file", accept: ".log,.txt" });
  async function importar() {
    if (!archivo.files[0]) return aviso("Elige un archivo .log", "error");
    const r = await intentar(() => subirArchivo("/api/events/importar", archivo.files[0]));
    if (r) {
      aviso(`Importado: ${Object.entries(r.resumen).map(([k, v]) => `${k}=${v}`).join(", ")}`);
      buscar();
    }
  }

  function limpiar() {
    f.desde.value = f.hasta.value = f.marca.value = f.equipo.value = "";
    f.sevMin.value = 0; f.sevMax.value = 7; f.sospechosos.checked = false;
    buscar();
  }

  cont.replaceChildren(
    el("h1", {}, "Eventos Syslog"),
    el("p", { class: "ayuda" }, "Clasificados por equipo, fabricante, fecha, facility y severidad. Los mensajes se muestran como texto: nunca se ejecutan."),
    el("section", { class: "panel" },
      el("div", { class: "filtros" },
        el("label", {}, "Desde", f.desde), el("label", {}, "Hasta", f.hasta),
        el("label", {}, "Marca", f.marca), el("label", {}, "Equipo", f.equipo),
        el("label", {}, "Severidad mín.", f.sevMin), el("label", {}, "Severidad máx.", f.sevMax),
        el("label", {}, "Solo sospechosos", f.sospechosos),
        el("div", { class: "acciones" }, el("button", { onclick: buscar }, "Filtrar"), el("button", { class: "secundario", onclick: limpiar }, "Limpiar"))),
      total, resultado),
    el("section", { class: "panel" }, el("h2", {}, "Importar archivo .log (un mensaje por línea)"),
      el("div", { class: "filtros" }, archivo, el("button", { onclick: importar }, "Importar")),
      el("p", { class: "ayuda" }, "Ejemplo incluido: data/muestras_simuladas.log [SIMULADO]")),
  );
  buscar();
}
