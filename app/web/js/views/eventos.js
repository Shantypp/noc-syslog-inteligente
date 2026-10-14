/**
 * views/eventos.js — Consulta de eventos con filtros (RF-04, HU-02) e importación (RF-02).
 * Búsqueda por texto, fecha desde/hasta, marca, equipo y rango de severidad.
 * "Cargar más" trae la siguiente página; "Exportar a Excel" descarga lo filtrado.
 * #eventos/3 abre la consulta filtrada por el equipo 3.
 */
import { api, subirArchivo } from "../api.js";
import { el, fecha, sevBadge, chip, tabla, intentar, aviso, encabezado, formulario, componente, puede, enlaceEquipo, botonDescarga, SEVERIDADES, montar } from "../ui.js";

export const titulo = "Eventos";
export const icono = "eventos";

const POR_PAGINA = 100;
const opcionesSev = (sel) => SEVERIDADES.map((n, i) => el("option", { value: i, selected: i === sel }, `${i} · ${n}`));

/** Fecha local del campo (AAAA-MM-DD) -> ISO UTC del inicio o del final de ese día. */
function limiteDia(valor, finDelDia) {
  if (!valor) return "";
  return new Date(`${valor}T${finDelDia ? "23:59:59" : "00:00:00"}`).toISOString();
}

export async function render(cont, param) {
  const equipos = await api("/api/devices").catch(() => []);

  const f = {
    q: el("input", { type: "search", placeholder: "Ej.: Gi0/1, login, FW-EDGE…", maxlength: 100, style: "min-width:240px" }),
    desde: el("input", { type: "date" }),
    hasta: el("input", { type: "date" }),
    marca: el("select", {}, el("option", { value: "" }, "Todas"), ["Cisco", "Fortinet", "Huawei"].map((m) => el("option", { value: m }, m))),
    equipo: el("select", {}, el("option", { value: "" }, "Todos"), equipos.map((d) => el("option", { value: d.id, selected: String(d.id) === param }, `${d.nombre} (${d.marca})`))),
    sevMin: el("select", {}, opcionesSev(0)),
    sevMax: el("select", {}, opcionesSev(7)),
    sospechosos: el("input", { type: "checkbox" }),
  };
  const total = el("p", { class: "total" });
  const resultado = el("div");
  const masBoton = el("button", { class: "secundario", hidden: true }, "Cargar más");
  const exportar = botonDescarga("/api/events/exportar.csv", "Exportar a Excel");
  let ultimaConsulta = 0; // evita que una respuesta vieja pise a una más nueva
  let cargados = [];

  const filtros = () => ({
    q: f.q.value.trim(), desde: limiteDia(f.desde.value, false), hasta: limiteDia(f.hasta.value, true),
    marca: f.marca.value, device_id: f.equipo.value, sev_min: f.sevMin.value, sev_max: f.sevMax.value,
    solo_sospechosos: f.sospechosos.checked || "",
  });

  function dibujarTabla(totalFiltrado) {
    total.textContent = `${totalFiltrado} evento(s) cumplen el filtro${totalFiltrado > cargados.length ? ` · se muestran ${cargados.length}` : ""}`;
    masBoton.hidden = cargados.length >= totalFiltrado;
    resultado.replaceChildren(tabla([
      { titulo: "ID", valor: (e) => e.id, clase: "num" },
      { titulo: "Recibido", valor: (e) => fecha(e.recibido_en), clase: "num" },
      { titulo: "Equipo", valor: (e) => [enlaceEquipo(e.device_id, e.equipo || e.hostname), el("br"), el("small", {}, e.marca || "")], clase: "nowrap" },
      { titulo: "Severidad", valor: (e) => sevBadge(e.severidad) },
      { titulo: "Componente", valor: componente },
      { titulo: "Mensaje", clase: "mensaje", valor: (e) => [e.sospechoso ? el("span", { class: "marca-sospechoso" }, "SOSPECHOSO") : null, e.mensaje, e.repeticiones > 1 ? ` (×${e.repeticiones})` : null] },
      { titulo: "Origen", valor: (e) => chip(e.origen) },
      { titulo: "Incidente", valor: (e) => e.incident_id
          ? el("a", { href: `#incidentes/${e.incident_id}` }, `INC-${e.incident_id}`)
          : puede("operador") ? el("button", { class: "pequeno secundario", onclick: () => abrirIncidente(e) }, "Abrir incidente") : "—" },
    ], cargados, "Ningún evento cumple el filtro."));
  }

  async function buscar(siguientePagina = false) {
    const numero = ++ultimaConsulta;
    const query = filtros();
    const r = await intentar(() => api("/api/events", { query: { ...query, limit: POR_PAGINA, offset: siguientePagina ? cargados.length : 0 } }));
    if (!r || numero !== ultimaConsulta) return; // llegó tarde: ya hay una consulta más reciente
    cargados = siguientePagina ? cargados.concat(r.eventos) : r.eventos;
    const url = new URL("/api/events/exportar.csv", location.origin);
    for (const [k, v] of Object.entries(query)) if (v !== "" && v !== null) url.searchParams.set(k, v);
    exportar.href = url.pathname + url.search;
    dibujarTabla(r.total);
  }

  async function abrirIncidente(e) {
    const datos = await formulario({
      titulo: `Abrir incidente para el evento ${e.id}`,
      descripcion: `${e.equipo || "Equipo"} · severidad ${e.severidad} (${SEVERIDADES[e.severidad]})${e.componente ? ` · componente: ${e.componente} (${e.estado_componente})` : ""}`,
      campos: [{ id: "responsable", etiqueta: "Responsable", ayuda: "Opcional. Si lo indica, el incidente queda asignado." }],
      aceptar: "Abrir incidente",
    });
    if (!datos) return;
    const inc = await intentar(() => api("/api/incidents", {
      method: "POST", body: { event_id: e.id, responsable: datos.responsable || null },
    }), "Incidente abierto");
    if (inc) { buscar(); window.dispatchEvent(new Event("noc:actualizar-menu")); }
  }

  const archivo = el("input", { type: "file", accept: ".log,.txt" });
  async function importar() {
    if (!archivo.files[0]) return aviso("Seleccione un archivo .log", "error");
    const r = await intentar(() => subirArchivo("/api/events/importar", archivo.files[0]));
    if (r) {
      const nombres = { guardado: "guardados", duplicado: "repetidos", fuente_no_autorizada: "de equipos no registrados", invalido: "inválidos", limitado: "descartados" };
      aviso(`Archivo importado: ${Object.entries(r.resumen).map(([k, v]) => `${v} ${nombres[k] || k}`).join(", ")}`);
      buscar();
      window.dispatchEvent(new Event("noc:actualizar-menu"));
    }
  }

  function limpiar() {
    f.q.value = f.desde.value = f.hasta.value = f.marca.value = f.equipo.value = "";
    f.sevMin.value = 0; f.sevMax.value = 7; f.sospechosos.checked = false;
    buscar();
  }

  // Buscar mientras se escribe (con una pequeña espera) y al cambiar cualquier filtro
  let espera;
  f.q.addEventListener("input", () => { clearTimeout(espera); espera = setTimeout(() => buscar(), 350); });
  for (const k of ["desde", "hasta", "marca", "equipo", "sevMin", "sevMax", "sospechosos"]) f[k].addEventListener("change", () => buscar());
  masBoton.addEventListener("click", () => buscar(true));

  montar(cont,
    encabezado("Operación", "Eventos",
      "Mensajes Syslog recibidos. Escriba en el buscador o use los filtros: la lista se actualiza sola. Los mensajes se muestran siempre como texto: nunca se ejecutan.",
      exportar),
    el("section", { class: "panel" },
      el("div", { class: "filtros" },
        el("label", {}, "Buscar texto", f.q),
        el("label", {}, "Desde", f.desde), el("label", {}, "Hasta", f.hasta),
        el("label", {}, "Marca", f.marca), el("label", {}, "Equipo", f.equipo),
        el("label", {}, "Severidad mínima", f.sevMin), el("label", {}, "Severidad máxima", f.sevMax),
        el("label", { class: "check" }, f.sospechosos, "Solo sospechosos"),
        el("div", { class: "acciones" }, el("button", { class: "secundario", onclick: limpiar }, "Limpiar filtros"))),
      total, resultado, el("div", { style: "text-align:center;margin-top:12px" }, masBoton)),
    !puede("operador") ? null : el("section", { class: "panel" }, el("h2", {}, "Importar eventos desde archivo"),
      el("p", { class: "nota" }, "Archivo de texto con un mensaje Syslog por línea. Ejemplo incluido: data/muestras_simuladas.log (datos simulados)."),
      el("div", { class: "filtros" }, archivo, el("button", { class: "secundario", onclick: importar }, "Importar archivo"))),
  );
  await buscar();
}
