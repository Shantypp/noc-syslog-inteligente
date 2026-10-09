/**
 * main.js — Arranque de la interfaz y navegación entre vistas.
 *
 * Cada vista es un módulo con: { titulo, icono, render(contenedor) }.
 * La URL cambia a #nombre-vista y main.js dibuja la vista correspondiente.
 */
import { el } from "./ui.js";
import * as dashboard from "./views/dashboard.js";
import * as eventos from "./views/eventos.js";
import * as incidentes from "./views/incidentes.js";
import * as inventario from "./views/inventario.js";
import * as configs from "./views/configs.js";
import * as consola from "./views/consola.js";
import * as auditoria from "./views/auditoria.js";

const VISTAS = { dashboard, eventos, incidentes, inventario, configs, consola, auditoria };

let detenerVista = null; // algunas vistas se refrescan solas; al salir se detienen

function dibujarMenu(actual) {
  const menu = document.getElementById("menu");
  menu.replaceChildren(
    ...Object.entries(VISTAS).map(([id, v]) =>
      el("a", { href: `#${id}`, class: id === actual ? "activo" : null }, el("span", {}, v.icono), v.titulo)
    )
  );
}

async function navegar() {
  const id = location.hash.slice(1) || "dashboard";
  const vista = VISTAS[id] || dashboard;
  if (detenerVista) detenerVista();
  detenerVista = null;
  dibujarMenu(id in VISTAS ? id : "dashboard");
  const contenedor = document.getElementById("vista");
  contenedor.replaceChildren();
  document.title = `${vista.titulo} · NOC Syslog Inteligente`;
  detenerVista = (await vista.render(contenedor)) || null;
}

// Operador: se recuerda en este navegador
const inputOperador = document.getElementById("operador");
try { inputOperador.value = localStorage.getItem("noc.operador") || ""; } catch { /* modo privado */ }
inputOperador.placeholder = "tu nombre";
inputOperador.addEventListener("change", () => {
  try { localStorage.setItem("noc.operador", inputOperador.value.trim()); } catch { /* sin almacenamiento */ }
});

window.addEventListener("hashchange", navegar);
navegar();
