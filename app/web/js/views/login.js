/**
 * views/login.js — Pantalla de inicio de sesión.
 * La contraseña viaja al servidor, que responde con una cookie HttpOnly (JavaScript no la puede leer).
 */
import { api } from "../api.js";
import { el, icono, montar } from "../ui.js";

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

  montar(cont, el("div", { class: "login-caja" },
    el("div", { class: "marca" }, el("span", { class: "logo" }, icono("actividad", 18)),
      el("div", {}, el("strong", {}, "NOC Syslog"), el("small", {}, "Centro de operaciones de red"))),
    el("h1", {}, "Iniciar sesión"),
    el("p", {}, "Ingrese con su usuario. Lo que puede ver y hacer depende de su rol."),
    el("form", { onsubmit: entrar, novalidate: true },
      el("label", {}, "Usuario", usuario),
      el("label", {}, "Contraseña", clave),
      error, boton),
    el("div", { class: "pie-login" }, "Entorno de laboratorio · datos simulados. Tras 5 intentos fallidos la cuenta se bloquea 15 minutos.",
      el("br"), "¿Olvidó su contraseña? Un administrador puede restablecerla en Usuarios.")));
  usuario.focus();
}

/**
 * Configuración inicial: solo aparece la PRIMERA vez (cuando no existe ningún usuario).
 * Crea el administrador principal sin editar archivos. El servidor solo la acepta desde
 * el mismo computador y una única vez.
 */
export function renderConfiguracionInicial(cont, alEntrar) {
  const nombre = el("input", { autocomplete: "name", maxlength: 80, placeholder: "Ej.: Jhoan Pachón" });
  const usuario = el("input", { autocomplete: "username", maxlength: 40, placeholder: "Ej.: jpachon" });
  const clave = el("input", { type: "password", autocomplete: "new-password", maxlength: 200 });
  const repetir = el("input", { type: "password", autocomplete: "new-password", maxlength: 200 });
  const demo = el("input", { type: "checkbox", checked: true });
  const error = el("div", { class: "error-campo", role: "alert" });
  const boton = el("button", { type: "submit" }, "Crear administrador y entrar");

  async function crear(ev) {
    ev.preventDefault();
    error.textContent = "";
    if (nombre.value.trim().length < 3) return (error.textContent = "Escriba su nombre (mínimo 3 letras).");
    if (!/^[A-Za-z0-9._-]{3,40}$/.test(usuario.value.trim())) return (error.textContent = "El usuario debe tener 3 a 40 caracteres: letras, números, punto, guion o guion bajo (sin espacios).");
    if (clave.value.length < 8) return (error.textContent = "La contraseña debe tener al menos 8 caracteres.");
    if (clave.value !== repetir.value) return (error.textContent = "Las contraseñas no coinciden.");
    boton.disabled = true;
    try {
      const u = await api("/api/auth/configuracion-inicial", { method: "POST",
        body: { nombre: nombre.value.trim(), usuario: usuario.value.trim(), clave: clave.value } });
      if (demo.checked) await api("/api/sistema/demo", { method: "POST" }).catch(() => null);
      alEntrar(u);
    } catch (e) {
      error.textContent = e.message;
    } finally {
      boton.disabled = false;
    }
  }

  montar(cont, el("div", { class: "login-caja" },
    el("div", { class: "marca" }, el("span", { class: "logo" }, icono("actividad", 18)),
      el("div", {}, el("strong", {}, "NOC Syslog"), el("small", {}, "Centro de operaciones de red"))),
    el("h1", {}, "Configuración inicial"),
    el("p", {}, "Es la primera vez que se abre el sistema. Cree el usuario administrador principal: con él podrá crear después a los demás usuarios."),
    el("form", { onsubmit: crear, novalidate: true },
      el("label", {}, "Su nombre completo", nombre),
      el("label", {}, "Usuario para iniciar sesión", usuario),
      el("label", {}, "Contraseña (mínimo 8 caracteres)", clave),
      el("label", {}, "Repita la contraseña", repetir),
      el("label", { class: "check-linea" }, demo, "Cargar equipos y eventos de demostración (simulados)"),
      error, boton),
    el("div", { class: "pie-login" }, "Este paso solo se puede hacer una vez y desde el computador donde está instalado el NOC.")));
  nombre.focus();
}
