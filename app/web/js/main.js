/**
 * main.js — Arranque de la interfaz: inicio de sesión, navegación y avisos en vivo.
 *
 * 1. Pregunta al servidor si ya está configurado (/api/auth/estado). Si no hay usuarios,
 *    muestra la configuración inicial (crear el primer administrador).
 * 2. Pregunta quién es el usuario (/api/auth/yo). Si no hay sesión, muestra el inicio de sesión.
 * 3. Dibuja el menú según su ROL y la vista pedida: #dashboard, #eventos, #equipo/3, #incidentes/7 ...
 * 4. Cada 15 s consulta /api/novedades: actualiza los contadores del menú y avisa de eventos
 *    graves y detecciones nuevas, esté en la pantalla que esté.
 *
 * Ocultar un botón es solo comodidad: el servidor vuelve a verificar el rol en cada acción.
 */
import { api } from "./api.js";
import { el, icono, sesion, puede, chip, formulario, intentar, aviso } from "./ui.js";
import * as login from "./views/login.js";
import * as dashboard from "./views/dashboard.js";
import * as detecciones from "./views/detecciones.js";
import * as eventos from "./views/eventos.js";
import * as puertos from "./views/puertos.js";
import * as incidentes from "./views/incidentes.js";
import * as equipo from "./views/equipo.js";
import * as inventario from "./views/inventario.js";
import * as configs from "./views/configs.js";
import * as usuarios from "./views/usuarios.js";
import * as sistema from "./views/sistema.js";
import * as consola from "./views/consola.js";
import * as auditoria from "./views/auditoria.js";
import * as seguridad from "./views/seguridad.js";
import * as ayuda from "./views/ayuda.js";

const VISTAS = { dashboard, detecciones, eventos, puertos, incidentes, equipo, inventario, configs, usuarios, sistema, consola, auditoria, seguridad, ayuda };
const GRUPOS = [
  ["Operación", ["dashboard", "detecciones", "incidentes", "eventos", "puertos"]],
  ["Administración", ["inventario", "configs", "usuarios", "sistema"]],
  ["Control de cambios", ["consola", "auditoria"]],
  ["Cumplimiento", ["seguridad"]],
  ["Soporte", ["ayuda"]],
];
const visible = (id) => !VISTAS[id].rolMinimo || puede(VISTAS[id].rolMinimo);

let detenerVista = null; // algunas vistas se refrescan solas; al salir se detienen
let contadores = {};     // pendientes por sección (los actualiza la consulta de novedades)
let version = "";

/** "#equipo/3" -> { id: "equipo", param: "3" } */
function rutaActual() {
  const [id, ...resto] = location.hash.slice(1).split("/");
  return { id: id || "dashboard", param: resto.join("/") || null };
}

function dibujarMenu() {
  const actual = rutaActual().id === "equipo" ? "inventario" : rutaActual().id;
  document.getElementById("menu").replaceChildren(
    ...GRUPOS.flatMap(([grupo, ids]) => {
      const accesibles = ids.filter(visible);
      return accesibles.length ? [
        el("div", { class: "grupo" }, grupo),
        ...accesibles.map((id) => el("a", { href: `#${id}`, class: id === actual ? "activo" : null, "aria-current": id === actual ? "page" : null },
          icono(VISTAS[id].icono), VISTAS[id].titulo,
          contadores[id] ? el("span", { class: "contador", title: "Pendientes" }, contadores[id]) : null)),
      ] : [];
    }),
    el("div", { class: "pie" }, `NOC Syslog v${version}`, el("br"), "Proyecto académico · 2026-2"),
  );
}

function dibujarUsuario() {
  const u = sesion.usuario;
  document.getElementById("usuario-sesion").replaceChildren(
    el("div", { class: "quien" }, el("strong", {}, u.nombre), `${u.usuario} · `, chip(u.rol)),
    el("button", { class: "pequeno secundario", onclick: cambiarClave }, "Cambiar contraseña"),
    el("button", { class: "pequeno secundario", onclick: cerrarSesion, title: "Cerrar sesión" }, icono("salir", 15), "Salir"),
  );
}

async function cambiarClave() {
  const d = await formulario({
    titulo: "Cambiar mi contraseña",
    campos: [
      { id: "actual", etiqueta: "Contraseña actual", tipo: "password", requerido: true },
      { id: "nueva", etiqueta: "Nueva contraseña", tipo: "password", requerido: true, ayuda: "Mínimo 8 caracteres." },
    ],
    aceptar: "Cambiar contraseña",
  });
  if (d) await intentar(() => api("/api/auth/cambiar-clave", { method: "POST", body: d }), "Contraseña actualizada");
}

async function cerrarSesion() {
  await api("/api/auth/logout", { method: "POST" }).catch(() => {});
  sesion.usuario = null;
  mostrarLogin();
}

// ------------------------------------------------------------------ avisos en vivo

const referencia = { evento: 0, deteccion: 0 }; // últimos ids vistos
let temporizadorNovedades = null;

function avisoEnVivo(titulo, detalle, destino) {
  const t = el("div", { class: "toast vivo", role: "alert", title: "Clic para ver" },
    el("strong", {}, titulo), detalle);
  t.addEventListener("click", () => { location.hash = destino; t.remove(); });
  document.getElementById("toasts").append(t);
  setTimeout(() => t.remove(), 12000);
}

async function consultarNovedades() {
  if (!sesion.usuario) return;
  const n = await api("/api/novedades", { query: referencia }).catch(() => null);
  if (!n) return;
  for (const e of n.eventos_graves.slice(0, 3)) {
    avisoEnVivo(`Evento grave en ${e.equipo || "equipo desconocido"}`,
      `${e.componente ? `${e.componente} · ` : ""}${e.mensaje.slice(0, 120)}`, "incidentes");
  }
  for (const x of n.detecciones.slice(0, 3)) {
    avisoEnVivo(`Detección: ${x.titulo}`, x.equipo || "", "detecciones");
  }
  referencia.evento = n.ultimo_evento;
  referencia.deteccion = n.ultima_deteccion;
  if (JSON.stringify(n.contadores) !== JSON.stringify(contadores)) { contadores = n.contadores; dibujarMenu(); }
}

function iniciarNovedades() {
  clearInterval(temporizadorNovedades);
  referencia.evento = referencia.deteccion = 0; // la primera consulta solo toma la referencia
  consultarNovedades();
  temporizadorNovedades = setInterval(consultarNovedades, 15000);
}

// ------------------------------------------------------------------ navegación

let turno = 0; // cada navegación tiene un número; solo la última se muestra

async function navegar() {
  if (!sesion.usuario) return;
  const { id: pedido, param } = rutaActual();
  const id = pedido in VISTAS && visible(pedido) ? pedido : "dashboard";
  const vista = VISTAS[id];
  const miTurno = ++turno;
  if (detenerVista) detenerVista();
  detenerVista = null;
  dibujarMenu();
  document.title = `${vista.titulo} · NOC Syslog`;
  // La vista se dibuja en un contenedor propio. Si mientras tanto el usuario pidió otra
  // pantalla, esta se descarta: así una vista lenta no "pisa" a la más reciente.
  const contenedor = el("div");
  const detener = (await vista.render(contenedor, param)) || null;
  if (miTurno !== turno) { if (detener) detener(); return; }
  detenerVista = detener;
  document.getElementById("vista").replaceChildren(contenedor);
  window.scrollTo(0, 0);
}

function entrar(usuario) {
  sesion.usuario = usuario;
  const caja = document.getElementById("login");
  caja.hidden = true;
  caja.replaceChildren();
  document.getElementById("app").hidden = false;
  dibujarUsuario();
  iniciarNovedades();
  navegar();
}

function mostrarLogin(configuracionInicial = false) {
  if (detenerVista) detenerVista();
  detenerVista = null;
  clearInterval(temporizadorNovedades);
  contadores = {};
  document.getElementById("app").hidden = true;
  const caja = document.getElementById("login");
  caja.hidden = false;
  (configuracionInicial ? login.renderConfiguracionInicial : login.render)(caja, entrar);
}

async function iniciar() {
  document.getElementById("logo").append(icono("actividad", 18));
  version = (await api("/api/health").catch(() => ({}))).version || "";
  const estado = await api("/api/auth/estado").catch(() => ({}));
  if (estado.requiere_configuracion) return mostrarLogin(true);
  try {
    entrar(await api("/api/auth/yo"));
  } catch {
    mostrarLogin();
  }
}

// Si la sesión vence mientras se usa la aplicación, se pide iniciar sesión de nuevo
window.addEventListener("noc:sesion-vencida", () => {
  if (sesion.usuario) { sesion.usuario = null; aviso("Su sesión terminó. Inicie sesión de nuevo.", "error"); mostrarLogin(); }
});
// Las vistas avisan cuando cambian datos que afectan los contadores del menú
window.addEventListener("noc:actualizar-menu", consultarNovedades);
window.addEventListener("hashchange", navegar);
iniciar();
