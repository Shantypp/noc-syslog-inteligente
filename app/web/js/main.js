/**
 * main.js — Arranque de la interfaz y navegación.
 *
 * El menú se agrupa en el orden en que se trabaja:
 *   Operación -> Administración -> Control de cambios -> Cumplimiento
 * Cada vista es un módulo con: { titulo, icono, render(contenedor) }.
 */
import { api } from "./api.js";
import { el, icono } from "./ui.js";
import * as dashboard from "./views/dashboard.js";
import * as eventos from "./views/eventos.js";
import * as incidentes from "./views/incidentes.js";
import * as inventario from "./views/inventario.js";
import * as configs from "./views/configs.js";
import * as consola from "./views/consola.js";
import * as auditoria from "./views/auditoria.js";
import * as seguridad from "./views/seguridad.js";

const VISTAS = { dashboard, eventos, incidentes, inventario, configs, consola, auditoria, seguridad };
const GRUPOS = [
  ["Operación", ["dashboard", "eventos", "incidentes"]],
  ["Administración", ["inventario", "configs"]],
  ["Control de cambios", ["consola", "auditoria"]],
  ["Cumplimiento", ["seguridad"]],
];

let detenerVista = null; // algunas vistas se refrescan solas; al salir se detienen

async function dibujarMenu(actual) {
  // Contadores de trabajo pendiente (si la API no responde, el menú se dibuja igual)
  const pendientes = await api("/api/dashboard").then((d) => ({
    incidentes: d.tarjetas.propuestas_pendientes, auditoria: d.tarjetas.aprobaciones_pendientes,
  })).catch(() => ({}));
  document.getElementById("menu").replaceChildren(
    ...GRUPOS.flatMap(([grupo, ids]) => [
      el("div", { class: "grupo" }, grupo),
      ...ids.map((id) => el("a", { href: `#${id}`, class: id === actual ? "activo" : null, "aria-current": id === actual ? "page" : null },
        icono(VISTAS[id].icono), VISTAS[id].titulo,
        pendientes[id] ? el("span", { class: "contador", title: "Pendientes" }, pendientes[id]) : null)),
    ]),
    el("div", { class: "pie" }, "NOC Syslog v0.2.0", el("br"), "Proyecto académico · 2026-2"),
  );
}

async function navegar() {
  const id = location.hash.slice(1) in VISTAS ? location.hash.slice(1) : "dashboard";
  const vista = VISTAS[id];
  if (detenerVista) detenerVista();
  detenerVista = null;
  dibujarMenu(id);
  const contenedor = document.getElementById("vista");
  contenedor.replaceChildren();
  document.title = `${vista.titulo} · NOC Syslog`;
  detenerVista = (await vista.render(contenedor)) || null;
}

// Logo
document.getElementById("logo").append(icono("actividad", 18));

// Usuario de la sesión: se recuerda en este navegador
const inputOperador = document.getElementById("operador");
try { inputOperador.value = localStorage.getItem("noc.operador") || ""; } catch { /* modo privado */ }
inputOperador.placeholder = "Escriba su nombre";
inputOperador.addEventListener("change", () => {
  try { localStorage.setItem("noc.operador", inputOperador.value.trim()); } catch { /* sin almacenamiento */ }
});

// Las vistas avisan cuando cambian datos que afectan los contadores del menú
window.addEventListener("noc:actualizar-menu", () => dibujarMenu(location.hash.slice(1) || "dashboard"));
window.addEventListener("hashchange", navegar);
navegar();
