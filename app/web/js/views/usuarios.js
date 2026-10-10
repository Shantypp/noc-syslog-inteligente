/**
 * views/usuarios.js — Gestión de usuarios y roles (solo administrador).
 * Roles: Lector (consulta) · Operador (atiende y propone) · Administrador (aprueba y administra).
 */
import { api } from "../api.js";
import { el, fecha, chip, tabla, intentar, encabezado, formulario, sesion } from "../ui.js";

export const titulo = "Usuarios";
export const icono = "usuarios";
export const rolMinimo = "administrador";

const ROLES = [
  { valor: "lector", texto: "Lector · solo consulta" },
  { valor: "operador", texto: "Operador · atiende incidentes y propone cambios" },
  { valor: "administrador", texto: "Administrador · aprueba cambios y administra" },
];

export async function render(cont) {
  const lista = el("div");
  const accesos = el("div");

  async function cargar() {
    const [usuarios, log] = await Promise.all([api("/api/usuarios"), api("/api/usuarios/accesos")]);
    lista.replaceChildren(tabla([
      { titulo: "Usuario", valor: (u) => el("strong", {}, u.usuario), clase: "nowrap" },
      { titulo: "Nombre", valor: (u) => u.nombre },
      { titulo: "Rol", valor: (u) => chip(u.rol) },
      { titulo: "Estado", valor: (u) => el("span", { class: `estado ${u.activo ? "verde" : ""}` }, u.activo ? "Activo" : "Inactivo") },
      { titulo: "Creado", valor: (u) => fecha(u.creado_en), clase: "num" },
      { titulo: "", valor: (u) => el("div", { class: "acciones" },
          el("button", { class: "pequeno secundario", onclick: () => editar(u) }, "Editar"),
          el("button", { class: "pequeno secundario", onclick: () => restablecer(u) }, "Restablecer contraseña"),
          u.id !== sesion.usuario.id ? el("button", { class: "pequeno peligro", onclick: () => activar(u, !u.activo) }, u.activo ? "Desactivar" : "Activar") : null) },
    ], usuarios));
    accesos.replaceChildren(tabla([
      { titulo: "Fecha", valor: (a) => fecha(a.fecha), clase: "num" },
      { titulo: "Usuario", valor: (a) => a.usuario },
      { titulo: "Resultado", valor: (a) => el("span", { class: `estado ${a.exito ? "verde" : "rojo"}` }, a.exito ? "Exitoso" : "Fallido") },
      { titulo: "Detalle", valor: (a) => a.detalle },
      { titulo: "IP", valor: (a) => a.ip || "—", clase: "num" },
    ], log, "Sin intentos registrados."));
  }

  async function crear() {
    const d = await formulario({
      titulo: "Crear usuario",
      campos: [
        { id: "usuario", etiqueta: "Usuario", requerido: true, ayuda: "Letras, números, punto, guion. Ej.: maria.gomez" },
        { id: "nombre", etiqueta: "Nombre completo", requerido: true },
        { id: "rol", etiqueta: "Rol", tipo: "select", valor: "operador", opciones: ROLES },
        { id: "clave", etiqueta: "Contraseña inicial", tipo: "password", requerido: true, ayuda: "Mínimo 8 caracteres. El usuario puede cambiarla después." },
      ],
      aceptar: "Crear usuario",
    });
    if (d && await intentar(() => api("/api/usuarios", { method: "POST", body: d }), "Usuario creado")) cargar();
  }

  async function editar(u) {
    const d = await formulario({
      titulo: `Editar usuario · ${u.usuario}`,
      descripcion: "Si cambia el rol, la sesión abierta de ese usuario se cierra para aplicar los nuevos permisos.",
      campos: [
        { id: "nombre", etiqueta: "Nombre completo", valor: u.nombre, requerido: true },
        { id: "rol", etiqueta: "Rol", tipo: "select", valor: u.rol, opciones: ROLES },
      ],
      aceptar: "Guardar cambios",
    });
    if (d && await intentar(() => api(`/api/usuarios/${u.id}`, { method: "PATCH", body: d }), "Usuario actualizado")) cargar();
  }

  async function restablecer(u) {
    const d = await formulario({
      titulo: `Restablecer contraseña · ${u.usuario}`,
      campos: [{ id: "clave", etiqueta: "Nueva contraseña", tipo: "password", requerido: true, ayuda: "Mínimo 8 caracteres." }],
      aceptar: "Restablecer",
    });
    if (d && await intentar(() => api(`/api/usuarios/${u.id}/clave`, { method: "POST", body: d }), "Contraseña restablecida")) cargar();
  }

  async function activar(u, activo) {
    if (await intentar(() => api(`/api/usuarios/${u.id}`, { method: "PATCH", body: { activo } }), activo ? "Usuario activado" : "Usuario desactivado")) cargar();
  }

  cont.replaceChildren(
    encabezado("Administración", "Usuarios",
      "Cada persona entra con su propio usuario. El rol define qué puede hacer: el Lector solo consulta; el Operador atiende incidentes y propone cambios; el Administrador aprueba cambios de otros y administra el sistema.",
      el("button", { onclick: crear }, "Crear usuario")),
    el("section", { class: "panel" }, el("h2", {}, "Usuarios registrados"), lista),
    el("section", { class: "panel" }, el("h2", {}, "Permisos por rol"),
      tabla([
        { titulo: "Acción", valor: (f) => f[0] },
        { titulo: "Lector", valor: (f) => f[1] }, { titulo: "Operador", valor: (f) => f[2] }, { titulo: "Administrador", valor: (f) => f[3] },
      ], [
        ["Ver panel, eventos, puertos, incidentes, auditoría", "Sí", "Sí", "Sí"],
        ["Consola: consultas básicas (versión, interfaces)", "Sí", "Sí", "Sí"],
        ["Consola: consultas de configuración de logs", "No", "Sí", "Sí"],
        ["Consola: proponer cambios", "No", "Sí", "Sí"],
        ["Abrir, gestionar y cerrar incidentes; importar eventos", "No", "Sí", "Sí"],
        ["Aprobar o rechazar cambios de otro usuario", "No", "No", "Sí"],
        ["Inventario de equipos y gestión de usuarios", "No", "No", "Sí"],
      ])),
    el("section", { class: "panel" }, el("h2", {}, "Últimos inicios de sesión"),
      el("p", { class: "nota" }, "Tras 5 intentos fallidos en 15 minutos la cuenta se bloquea temporalmente."), accesos),
  );
  await cargar();
}
