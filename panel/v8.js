/* Dashboard V8. La lógica cerebral sigue ejecutándose en helice_supabase.py. */
'use strict';

// Los datos de homeostasis son los reales que entrega /estado_cerebral.
let monologueText = '';
let refreshing = false;

function paint(data) {
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
    $('conn-note').textContent = 'Neurodatos recibidos directamente de LUMI.';
    $('chat-status').textContent = 'En línea';
    $('chat-status').classList.add('online');
    $('chat-status').style.color = '#69f5dd';
  } catch (error) {
    $('state').textContent = 'SIN CONEXIÓN';
    $('conn-note').textContent = 'Consulta pendiente: ' + error.message +
      '. Render podría estar despertándose.';
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
$('refresh').onclick = refresh;
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
updateCount();
refresh();
setInterval(() => { if (!document.hidden) refresh(); }, 16000);
