/**
 * views/ayuda.js — Ayuda dentro de la aplicación: cómo se usa según el rol,
 * cómo conectar un equipo real, qué significa cada severidad y preguntas frecuentes.
 */
import { api } from "../api.js";
import { el, encabezado, sevBadge, tabla, sesion, montar } from "../ui.js";

export const titulo = "Ayuda";
export const icono = "ayuda";

const SIGNIFICADO = [
  "El equipo no se puede usar (caída total).", "Hay que actuar de inmediato (ej. falla de energía).",
  "Condición crítica (ej. temperatura, fuente de poder).", "Error que afecta un servicio (ej. puerto caído).",
  "Algo puede convertirse en error (ej. intentos de acceso fallidos).", "Normal pero importante (ej. cambio de configuración).",
  "Mensaje informativo.", "Detalle técnico para diagnóstico.",
];

const GUIA_ROL = {
  lector: [
    "Panel general: revise \"Requiere su atención\" y el estado de los equipos.",
    "Eventos: busque por texto, equipo, fecha o severidad. Puede exportar a Excel.",
    "Clic en el nombre de un equipo para ver su ficha completa.",
    "Si detecta algo grave, avise a un operador: su rol solo permite consultar.",
  ],
  operador: [
    "Empiece cada turno en el Panel general › \"Requiere su atención\": está ordenado por prioridad.",
    "Detecciones: decida si cada patrón detectado (fuerza bruta, puerto inestable...) amerita un incidente o se descarta con motivo.",
    "Incidentes › Eventos graves pendientes: abra un incidente o descarte la propuesta con su motivo.",
    "Gestione cada incidente: asigne responsable, márquelo en progreso, agregue notas y ciérrelo con causa y solución.",
    "Si un incidente aparece como \"Recuperado\", el componente volvió a funcionar: verifique y ciérrelo.",
    "Consola: practique comandos. Los que cambian configuración quedan como propuesta para un administrador.",
  ],
  administrador: [
    "Todo lo del operador, más:",
    "Inventario: registre cada equipo con el MISMO nombre (hostname) e IP con que envía sus logs.",
    "Usuarios: cree una cuenta para cada persona con el rol mínimo que necesite.",
    "Auditoría: apruebe o rechace los cambios propuestos por otros (nunca los suyos: separación de funciones).",
    "Configuración: ajuste umbrales y horario laboral, descargue respaldos y cargue la demostración.",
  ],
};

const PREGUNTAS = [
  ["No llegan eventos de mi equipo", "Verifique en este orden: 1) el equipo está en Inventario con su IP exacta; 2) el NOC se inició con \"python iniciar.py --red\"; 3) el firewall de Windows permite UDP en el puerto indicado; 4) el equipo tiene configurado \"logging host\" con la IP de este computador. En Panel general › Control de ingreso verá si los mensajes llegan pero se rechazan (\"equipo no registrado\")."],
  ["¿Por qué un evento grave no creó un incidente solo?", "Por diseño: el sistema PROPONE y una persona DECIDE (flujo seguro del curso). Así se evita que un log manipulado dispare acciones automáticas."],
  ["¿Qué significa \"agrupados como repetidos\"?", "Si un equipo envía el mismo mensaje muchas veces en poco tiempo, se guarda una sola vez con un contador (×N). Así una tormenta no llena la base de datos."],
  ["¿Qué pasa si un equipo envía demasiados mensajes?", "Cada equipo tiene un cupo por minuto (Configuración). Lo que exceda se descarta y aparece una detección de \"Tormenta de eventos\". Los demás equipos no se ven afectados."],
  ["Olvidé mi contraseña", "Un administrador puede asignarle una nueva en Usuarios. Si nadie puede entrar, en la carpeta del proyecto ejecute: python -m app.usuarios clave SU_USUARIO"],
  ["¿Cómo hago una copia de seguridad?", "Configuración › Mantenimiento › Descargar respaldo. Guarde el archivo .db en un lugar seguro."],
  ["¿Los datos son reales?", "No. Los equipos de demostración usan IPs de documentación (192.0.2.x, RFC 5737) y están rotulados como \"Simulado\"."],
];

function conectar(estado) {
  const ip = estado?.ips_del_equipo?.[0] || "IP_DE_ESTE_COMPUTADOR";
  const puerto = estado?.udp?.puerto || 5514;
  const codigo = (texto) => el("pre", { class: "codigo" }, texto);
  return el("div", {},
    el("p", {}, "Para que un router, switch o firewall envíe sus logs al NOC:"),
    el("ol", { class: "paso-a-paso" },
      el("li", {}, el("strong", {}, "Inicie el NOC en modo red. "), "Cierre la ventana negra del NOC y haga doble clic en ", el("code", {}, "iniciar-red.bat"),
        " (o ejecute ", el("code", {}, "python iniciar.py --red"), "). Windows puede preguntar si permite el acceso a la red: elija ", el("em", {}, "Redes privadas"), "."),
      el("li", {}, el("strong", {}, "Registre el equipo en Inventario "), "con su IP exacta y el mismo nombre (hostname) que tiene configurado."),
      el("li", {}, el("strong", {}, "Configure el equipo "), `para enviar Syslog a ${ip}, puerto UDP ${puerto}. También puede generar la configuración completa en Administración › Plantillas de configuración.`),
      el("li", {}, el("strong", {}, "Verifique "), "en el Panel general que el equipo pase a \"Activo\" y aparezcan sus eventos.")),
    estado?.udp && !estado.udp.solo_local ? null
      : el("div", { class: "aviso info" }, "Ahora mismo el NOC está en modo laboratorio: solo acepta mensajes de este computador."),
    el("h3", {}, "Cisco IOS / IOS XE"), codigo(`configure terminal\n logging host ${ip} transport udp port ${puerto}\n logging trap warnings\n service timestamps log datetime msec\nend`),
    el("h3", {}, "Fortinet FortiGate"), codigo(`config log syslogd setting\n    set status enable\n    set server "${ip}"\n    set port ${puerto}\nend`),
    el("h3", {}, "Huawei VRP"), codigo(`system-view\n info-center enable\n info-center loghost ${ip} port ${puerto}\n quit`),
    el("h3", {}, "Probar sin equipos (simulador incluido)"), codigo(`python scripts/enviar_syslog_prueba.py\npython scripts/enviar_syslog_prueba.py --tormenta`),
  );
}

export async function render(cont) {
  const estado = await api("/api/sistema/estado").catch(() => null);
  const rol = sesion.usuario?.rol || "lector";
  const secciones = {
    inicio: ["Cómo usar el NOC", () => el("div", {},
      el("p", {}, `Su rol es `, el("strong", {}, sesion.usuario?.rol_nombre || rol), ". Esto es lo que puede hacer:"),
      el("ol", { class: "paso-a-paso" }, GUIA_ROL[rol].map((t) => el("li", {}, t))),
      el("h3", {}, "El flujo de trabajo, en una línea"),
      el("p", {}, "Evento recibido → validado → el sistema PROPONE (evento grave o detección) → una PERSONA revisa y decide → incidente → seguimiento → cierre con causa y solución. Todo queda auditado."))],
    conectar: ["Conectar un equipo", () => conectar(estado)],
    severidades: ["Severidades", () => el("div", {},
      el("p", {}, "Cada mensaje Syslog trae una severidad de 0 (más grave) a 7. Por defecto, de 0 a 2 se propone abrir incidente."),
      tabla([{ titulo: "Severidad", valor: (i) => sevBadge(i) }, { titulo: "Qué significa", valor: (i) => SIGNIFICADO[i] }], [0, 1, 2, 3, 4, 5, 6, 7]))],
    preguntas: ["Preguntas frecuentes", () => el("div", {}, PREGUNTAS.map(([p, r]) => el("details", { class: "faq" }, el("summary", {}, p), el("p", {}, r))))],
  };
  const cuerpo = el("div");
  const botones = Object.entries(secciones).map(([id, [nombre]]) => el("button", { type: "button", "data-id": id, onclick: () => mostrar(id) }, nombre));
  function mostrar(id) {
    botones.forEach((b) => b.classList.toggle("activa", b.dataset.id === id));
    montar(cuerpo, secciones[id][1]());
  }
  montar(cont,
    encabezado("Soporte", "Ayuda", "Guía rápida del sistema. Si algo no funciona, revise primero las preguntas frecuentes."),
    el("section", { class: "panel ayuda-pagina" }, el("div", { class: "pestanas" }, botones), cuerpo));
  mostrar("inicio");
}
