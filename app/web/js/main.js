/**
 * main.js — Arranque de la interfaz: inicio de sesión y navegación.
 *
 * 1. Pregunta al servidor quién es el usuario (/api/auth/yo).
 * 2. Si no hay sesión, muestra la pantalla de inicio de sesión.
 * 3. Si hay sesión, dibuja el menú según su ROL y la vista pedida (#dashboard, #eventos, ...).
 *
 * Ocultar un botón es solo comodidad: el servidor vuelve a verificar el rol en cada acción.
 */
import { api } from "./api.js";
import { el, icono, sesion, puede, chip, formulario, intentar, aviso } from "./ui.js";
import * as login from "./views/login.js";
import * as dashboard from "./views/dashboard.js";
import * as eventos from "./views/eventos.js";
import * as puertos from "./views/puertos.js";
import * as incidentes from "./views/incidentes.js";
import * as inventario from "./views/inventario.js";
import * as configs from "./views/configs.js";
import * as usuarios from "./views/usuarios.js";
import * as consola from "./views/consola.js";
import * as auditoria from "./views/auditoria.js";
import * as seguridad from "./views/seguridad.js";

const VISTAS = { dashboard, eventos, puertos, incidentes, inventario, configs, usuarios, consola, auditoria, seguridad };
const GRUPOS = [
  ["Operación", ["dashboard", "eventos", "puertos", "incidentes"]],
  ["Administración", ["inventario", "configs", "usuarios"]],
  ["Control de cambios", ["consola", "auditoria"]],
  ["Cumplimiento", ["seguridad"]],
];
const visible = (id) => !VISTAS[id].rolMinimo || puede(VISTAS[id].rolMinimo);

let detenerVista = null; // algunas vistas se refrescan solas; al salir se detienen

async function dibujarMenu(actual) {
  // Contadores de trabajo pendiente (si la API no responde, el menú se dibuja igual)
  const pendientes = await api("/api/dashboard").then((d) => ({
    incidentes: d.tarjetas.propuestas_pendientes, auditoria: d.tarjetas.aprobaciones_pendientes,
    puertos: d.tarjetas.componentes_con_problema,
  })).catch(() => ({}));
  document.getElementById("menu").replaceChildren(
    ...GRUPOS.flatMap(([grupo, ids]) => {
      const accesibles = ids.filter(visible);
      return accesibles.length ? [
        el("div", { class: "grupo" }, grupo),
        ...accesibles.map((id) => el("a", { href: `#${id}`, class: id === actual ? "activo" : null, "aria-current": id === actual ? "page" : null },
          icono(VISTAS[id].icono), VISTAS[id].titulo,
          pendientes[id] ? el("span", { class: "contador", title: "Pendientes" }, pendientes[id]) : null)),
      ] : [];
    }),
    el("div", { class: "pie" }, "NOC Syslog v0.2.0", el("br"), "Proyecto académico · 2026-2"),
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

async function navegar() {
  if (!sesion.usuario) return;
  const pedido = location.hash.slice(1);
  const id = pedido in VISTAS && visible(pedido) ? pedido : "dashboard";
  const vista = VISTAS[id];
  if (detenerVista) detenerVista();
  detenerVista = null;
  dibujarMenu(id);
  const contenedor = document.getElementById("vista");
  contenedor.replaceChildren();
  document.title = `${vista.titulo} · NOC Syslog`;
  detenerVista = (await vista.render(contenedor)) || null;
}

function mostrarLogin() {
  if (detenerVista) detenerVista();
  detenerVista = null;
  document.getElementById("app").hidden = true;
  const caja = document.getElementById("login");
  caja.hidden = false;
  login.render(caja, (usuario) => {
    sesion.usuario = usuario;
    caja.hidden = true;
    caja.replaceChildren();
    document.getElementById("app").hidden = false;
    dibujarUsuario();
    navegar();
  });
}

async function iniciar() {
  document.getElementById("logo").append(icono("actividad", 18));
  try {
    sesion.usuario = await api("/api/auth/yo");
    document.getElementById("app").hidden = false;
    dibujarUsuario();
    navegar();
  } catch {
    mostrarLogin();
  }
}

// Si la sesión vence mientras se usa la aplicación, se pide iniciar sesión de nuevo
window.addEventListener("noc:sesion-vencida", () => {
  if (sesion.usuario) { sesion.usuario = null; aviso("Su sesión terminó. Inicie sesión de nuevo.", "error"); mostrarLogin(); }
});
// Las vistas avisan cuando cambian datos que afectan los contadores del menú
window.addEventListener("noc:actualizar-menu", () => dibujarMenu(location.hash.slice(1) || "dashboard"));
window.addEventListener("hashchange", navegar);
iniciar();
