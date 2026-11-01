/* Dashboard V8. La lógica cerebral sigue ejecutándose en helice_supabase.py. */
'use strict';

// Los datos de homeostasis son los reales que entrega /estado_cerebral.
let monologueText = '';
let refreshing = false;
let refreshingPersonality = false;

function drawPersonalityRadar(traits) {
  const canvas = $('personality-radar');
  const ctx = canvas.getContext('2d');
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const w = canvas.clientWidth || 250, h = 230;
  canvas.width = Math.round(w * ratio);
  canvas.height = Math.round(h * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, w, h);
  const cx = w / 2, cy = h / 2, radius = Math.min(w * .39, 88);
  const n = traits.length;
  const angle = i => -Math.PI / 2 + (i * 2 * Math.PI / Math.max(3, n));
  const point = (i, fraction) => [cx + Math.cos(angle(i)) * radius * fraction,
                                   cy + Math.sin(angle(i)) * radius * fraction];
  ctx.lineWidth = 1;
  // Con cero, uno o dos rasgos aún no hay polígono: solo la retícula.
  const axes = Math.max(3, n);
  for (const fraction of [.25, .5, .75, 1]) {
    ctx.beginPath();
    for (let i = 0; i < axes; i++) {
      const [x, y] = point(i, fraction);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.strokeStyle = fraction === 1 ? '#37b4ca8c' : '#24627a80';
    ctx.stroke();
  }
  for (let i = 0; i < axes; i++) {
    const [x, y] = point(i, 1);
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(x, y);
    ctx.strokeStyle = '#255d7080'; ctx.stroke();
  }
  if (!n) {
    ctx.font = '12px Segoe UI, sans-serif'; ctx.fillStyle = '#70c4d6';
    ctx.textAlign = 'center'; ctx.fillText('SIN RASGOS', cx, cy - 6);
    ctx.font = '10px Segoe UI, sans-serif';
    ctx.fillText('AÚN DESBLOQUEADOS', cx, cy + 11);
    return;
  }
  ctx.beginPath();
  for (let i = 0; i < n; i++) {
    const [x, y] = point(i, traits[i].puntuacion / 100);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  if (n > 2) ctx.closePath();
  ctx.fillStyle = '#35f0f336';
  if (n > 2) ctx.fill();
  ctx.strokeStyle = '#42f6ff';ctx.lineWidth = 2.2;
  ctx.shadowBlur = 12;ctx.shadowColor = '#0df5fc';ctx.stroke();ctx.shadowBlur = 0;
  for (let i = 0; i < n; i++) {
    const [x, y] = point(i, traits[i].puntuacion / 100);
    ctx.beginPath();ctx.arc(x, y, 3.3, 0, 2 * Math.PI);
    ctx.fillStyle = '#baffff';ctx.fill();
    const [lx, ly] = point(i, 1.13);
    ctx.font = 'bold 10px Segoe UI, sans-serif';ctx.textAlign = 'center';
    ctx.fillText(String(i + 1), lx, ly + 4);
  }
}

function paintPersonality(data) {
  const traits = Array.isArray(data?.rasgos) ? data.rasgos.filter(item =>
    typeof item?.clave === 'string' && Number.isFinite(Number(item.puntuacion))
  ) : [];
  $('personality-count').textContent = traits.length + ' ACTIVOS';
  const notes = {
    desactivado: 'Módulo preparado, pendiente de ejecutar el SQL y activar el interruptor.',
    sin_conexion: 'Sin conexión verificada a las tablas de personalidad.',
    en_incubacion: 'Las elecciones se registran; ningún rasgo reúne aún pruebas suficientes.',
    activo: 'Cada eje representa un rasgo desbloqueado mediante evidencias verificadas.',
  };
  $('personality-note').textContent = notes[data?.estado] ||
    'Pendiente de comprobar las evidencias de personalidad.';
  const list = $('personality-traits'); list.replaceChildren();
  traits.forEach((item, i) => {
    const points = Math.max(0, Math.min(100, Number(item.puntuacion)));
    const row = document.createElement('div');row.className = 'personality-trait';
    const name = document.createElement('span');
    name.textContent = `${i + 1}. ${item.nombre || item.clave}`;
    const score = document.createElement('strong');score.textContent = `${points}/100`;
    const track = document.createElement('div');track.className = 'personality-track';
    const fill = document.createElement('i');fill.style.width = `${points}%`;
    track.append(fill);row.append(name, score, track);
    row.title = `${item.apoyos || 0} evidencias · ${item.dias || 0} días`;
    list.append(row);
  });
  drawPersonalityRadar(traits);
}

async function refreshPersonality() {
  if (refreshingPersonality) return;
  refreshingPersonality = true;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 12000);
  try {
    const response = await fetch('/dashboard/personalidad', {
      credentials: 'same-origin', cache: 'no-store', signal: ctrl.signal
    });
    if (response.status === 401) { requireLogin();return; }
    if (!response.ok) throw Error('HTTP ' + response.status);
    paintPersonality(await response.json());
  } catch (error) {
    $('personality-note').textContent = 'Esperando datos verificados (' + error.message + ').';
  } finally { refreshingPersonality = false; clearTimeout(timer); }
}

function paint(data) {
  const identidad = data?.identidad_lumi;
  if (/^\d{4}-\d{2}-\d{2}$/.test(identidad?.fecha_nacimiento || '') &&
      typeof identidad?.fecha_nacimiento_texto === 'string') {
    $('birth-date').textContent = identidad.fecha_nacimiento_texto.toLocaleUpperCase('es-ES');
    const dias = Number(identidad.dias_desde_nacimiento);
    $('birth-days').textContent = Number.isInteger(dias) && dias >= 0
      ? `${dias} días` : '— días';
  }
  $('metrics').replaceChildren();
  for (const [key, label] of Object.entries(labels)) {
    const raw = data?.[key];
    const value = raw == null ? NaN : Number(raw);
    const valid = Number.isFinite(value);
    const metric = document.createElement('div');
    metric.className = 'metric';
    const name = document.createElement('span'); name.textContent = label;
    const number = document.createElement('b'); number.textContent = valid ? value.toFixed(2) : '—';
    metric.append(name, number);
    const track = document.createElement('div'); track.className = 'bar';
    const bar = document.createElement('i');
    bar.style.width = (valid ? Math.max(0, Math.min(100, value * 100)) : 0) + '%';
    track.append(bar);
    $('metrics').append(metric, track);
  }
  $('state').textContent = data?.estado || 'SIN DATOS';
  monologueText = typeof data?.stream_conciencia === 'string' ? data.stream_conciencia : '';
  $('stream').textContent = monologueText || 'LUMI aún no ha publicado un monólogo interno.';
  $('speak-stream').disabled = !monologueText;
}

function requireLogin() {
  window.location.replace('/panel/login.html');
}

async function refresh() {
  if (refreshing) return;
  refreshing = true;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 15000);
  try {
    const response = await fetch('/estado_cerebral', {
      credentials: 'same-origin', cache: 'no-store', signal: ctrl.signal
    });
    if (response.status === 401) { requireLogin(); return; }
    if (!response.ok) throw Error('HTTP ' + response.status);
    paint(await response.json());
    refreshPersonality();
    $('chat-status').textContent = 'En línea';
    $('chat-status').classList.add('online');
    $('chat-status').style.color = '#69f5dd';
  } catch (error) {
    $('state').textContent = 'SIN CONEXIÓN';
    $('chat-status').textContent = 'Sin conexión: ' + error.message;
    $('chat-status').classList.remove('online');
  } finally {
    refreshing = false;
    clearTimeout(timer);
  }
}

// La voz solo se produce cuando el usuario pulsa ▶.
let currentAudio = null;
let currentAudioUrl = null;
let currentAudioButton = null;
function stopAudio() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.onended = null;
    currentAudio.onerror = null;
    currentAudio.src = '';
    currentAudio = null;
  }
  if (currentAudioUrl) {
    URL.revokeObjectURL(currentAudioUrl);
    currentAudioUrl = null;
  }
  if (currentAudioButton) {
    currentAudioButton.textContent = '▶ Escuchar';
    currentAudioButton = null;
  }
}
async function speak(text, button) {
  if (button === currentAudioButton) {
    // En Safari puede requerirse otra pulsación después de crear el audio.
    if (currentAudio?.paused) {
      try { await currentAudio.play(); button.textContent = '■ Detener'; }
      catch { button.textContent = '▶ Reproducir'; }
    } else {
      stopAudio();
    }
    return;
  }
  if (!text?.trim()) return;
  stopAudio();
  button.disabled = true;
  button.textContent = '⏳ Preparando voz…';
  try {
    const response = await fetch('/dashboard/voz', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({texto: text.slice(0, 2500)})
    });
    if (response.status === 401) { requireLogin(); return; }
    if (!response.ok) throw Error('HTTP ' + response.status);
    currentAudioUrl = URL.createObjectURL(await response.blob());
    currentAudioButton = button;
    currentAudio = new Audio(currentAudioUrl);
    currentAudio.onended = stopAudio;
    button.textContent = '■ Detener';
    try {
      await currentAudio.play();
    } catch {
      button.textContent = '▶ Reproducir';
      button.title = 'Pulsa otra vez para reproducir el audio';
    }
  } catch (error) {
    button.textContent = '⚠ Reintentar voz';
    button.title = 'La voz no respondió: ' + error.message;
  } finally {
    button.disabled = false;
  }
}

// Markdown básico para código largo, sin insertar HTML recibido del servidor.
function appendRich(container, value) {
  const parts = String(value).split(/(```[\s\S]*?```)/g);
  for (const part of parts) {
    if (part.startsWith('```') && part.endsWith('```')) {
      const pre = document.createElement('pre');
      pre.textContent = part.slice(3, -3).replace(/^\w+\n/, '');
      const copy = document.createElement('button');
      copy.className = 'copy';
      copy.textContent = 'Copiar código';
      copy.onclick = async () => {
        try { await navigator.clipboard.writeText(pre.textContent); copy.textContent = 'Copiado ✓'; }
        catch { copy.textContent = 'Selecciona el código para copiarlo'; }
      };
      container.append(pre, copy);
    } else if (part) {
      container.append(document.createTextNode(part));
    }
  }
}

const messages = $('messages');
function bubble(role, value, pending = false) {
  const root = document.createElement('div');
  root.className = 'message' + (role === 'Tú' ? ' mine' : '');
  const title = document.createElement('div');
  title.className = 'who';
  title.textContent = role;
  const box = document.createElement('div');
  box.className = 'bubble';
  root.append(title, box);
  if (pending) {
    box.classList.add('placeholder');
    box.textContent = 'LUMI está pensando…';
    const dots = document.createElement('span');
    dots.className = 'thinking';
    for (let i = 0; i < 3; i++) dots.append(document.createElement('span'));
    box.append(dots);
  } else appendRich(box, value);
  messages.append(root);
  messages.scrollTop = messages.scrollHeight;
  return {root, box};
}

function setAnswer(message, value) {
  message.box.classList.remove('placeholder');
  message.box.replaceChildren();
  appendRich(message.box, value);
  const tools = document.createElement('div');
  tools.className = 'message-tools';
  const play = document.createElement('button');
  play.className = 'talk-btn';
  play.textContent = '▶ Escuchar respuesta';
  play.onclick = () => speak(value, play);
  tools.append(play);
  message.root.append(tools);
  messages.scrollTop = messages.scrollHeight;
}

function updateCount() {
  $('count').textContent = $('input').value.length.toLocaleString('es-ES') + ' / 4.000';
}

async function send() {
  const field = $('input');
  const value = field.value.trim();
  if (!value || $('send').disabled) return;
  if (value.length > 4000) {
    bubble('Sistema', 'Máximo 4.000 caracteres. Divide el texto en dos mensajes.');
    return;
  }
  // El envío aparece instantáneamente. Solo la respuesta espera al backend.
  bubble('Tú', value);
  const pending = bubble('LUMI', '', true);
  field.value = '';
  updateCount();
  $('send').disabled = true;
  $('chat-status').textContent = 'LUMI está pensando…';
  try {
    const response = await fetch('/preguntar', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      credentials: 'same-origin',
      body: JSON.stringify({q: value})
    });
    if (response.status === 401) {
      field.value = value; updateCount(); requireLogin(); return;
    }
    if (!response.ok) throw Error('HTTP ' + response.status);
    const result = await response.json();
    setAnswer(pending, result.respuesta || '[Sin respuesta]');
    $('chat-status').textContent = 'Respuesta recibida';
    refresh();
  } catch (error) {
    pending.box.replaceChildren();
    pending.box.textContent = 'No se recibió respuesta (' + error.message +
      '). Conservamos el mensaje en el editor para reintentar.';
    field.value = value;
    updateCount();
    $('chat-status').textContent = 'Reintentar envío';
  } finally {
    $('send').disabled = false;
  }
}

function navSelected(id) {
  document.querySelectorAll('.nav button').forEach(button =>
    button.classList.toggle('selected', button.id === id));
}
$('nav-core').onclick = () => {
  navSelected('nav-core');
  document.querySelector('.center').scrollIntoView({behavior: 'smooth', block: 'start'});
};
$('nav-chat').onclick = () => {
  navSelected('nav-chat');
  $('input').focus();
  document.querySelector('.chat').scrollIntoView({behavior: 'smooth', block: 'start'});
};
$('nav-stream').onclick = () => {
  navSelected('nav-stream');
  $('monologue-card').scrollIntoView({behavior: 'smooth', block: 'center'});
};
$('speak-stream').onclick = () => speak(monologueText, $('speak-stream'));
$('send').onclick = send;
$('input').addEventListener('input', updateCount);
$('input').addEventListener('keydown', event => {
  if (event.key === 'Enter' && event.ctrlKey) { event.preventDefault(); send(); }
});
$('tab-msg').onclick = () => {
  document.querySelectorAll('.tabs button').forEach(btn => btn.classList.remove('active'));
  $('tab-msg').classList.add('active');
  $('input').placeholder = 'Escribe a LUMI…';
};
$('tab-code').onclick = () => {
  document.querySelectorAll('.tabs button').forEach(btn => btn.classList.remove('active'));
  $('tab-code').classList.add('active');
  $('input').placeholder = 'Pega tu código extenso. Puedes enviarlo en bloques.';
  $('input').focus();
};
$('logout').onclick = async () => {
  stopAudio();
  try { await fetch('/dashboard/logout', {method: 'POST', credentials: 'same-origin'}); }
  finally { requireLogin(); }
};
paint({});
paintPersonality({estado: 'desactivado', rasgos: []});
updateCount();
refresh();
setInterval(() => { if (!document.hidden) refresh(); }, 16000);
