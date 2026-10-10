/**
 * views/login.js — Pantalla de inicio de sesión.
 * La contraseña viaja al servidor, que responde con una cookie HttpOnly (JavaScript no la puede leer).
 */
import { api } from "../api.js";
import { el, icono } from "../ui.js";

export function render(cont, alEntrar) {
  const usuario = el("input", { autocomplete: "username", required: true, maxlength: 60 });
  const clave = el("input", { type: "password", autocomplete: "current-password", required: true, maxlength: 200 });
  const error = el("div", { class: "error-campo", role: "alert" });
  const boton = el("button", { type: "submit" }, "Iniciar sesión");

  async function entrar(ev) {
    ev.preventDefault();
    error.textContent = "";
    if (!usuario.value.trim() || !clave.value) { error.textContent = "Escriba su usuario y su contraseña."; return; }
    boton.disabled = true;
    try {
      const u = await api("/api/auth/login", { method: "POST", body: { usuario: usuario.value.trim(), clave: clave.value } });
      alEntrar(u);
    } catch (e) {
      error.textContent = e.message;
      clave.value = "";
      clave.focus();
    } finally {
      boton.disabled = false;
    }
  }

  cont.replaceChildren(el("div", { class: "login-caja" },
    el("div", { class: "marca" }, el("span", { class: "logo" }, icono("actividad", 18)),
      el("div", {}, el("strong", {}, "NOC Syslog"), el("small", {}, "Centro de operaciones de red"))),
    el("h1", {}, "Iniciar sesión"),
    el("p", {}, "Ingrese con su usuario. Lo que puede ver y hacer depende de su rol."),
    el("form", { onsubmit: entrar, novalidate: true },
      el("label", {}, "Usuario", usuario),
      el("label", {}, "Contraseña", clave),
      error, boton),
    el("div", { class: "pie-login" }, "Entorno de laboratorio · datos simulados. Tras 5 intentos fallidos la cuenta se bloquea 15 minutos.")));
  usuario.focus();
}
