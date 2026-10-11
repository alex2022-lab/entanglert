import * as hardy from 'hardy';

// ============================================================
// Navegación del deck (presentación en 4 diapositivas)
// ============================================================

const deck = document.getElementById('deck-container');
const btnPrev = document.getElementById('btn-prev');
const btnNext = document.getElementById('btn-next');
const slideCounter = document.getElementById('slide-counter');
const TOTAL_SLIDES = 4;
let slideActual = 0;

function actualizarDeck() {
  deck.style.transform = 'translateX(-' + (slideActual * 100) + 'vw)';
  btnPrev.disabled = slideActual === 0;
  btnNext.disabled = slideActual === TOTAL_SLIDES - 1;
  slideCounter.textContent =
    String(slideActual + 1).padStart(2, '0') +
    ' / ' +
    String(TOTAL_SLIDES).padStart(2, '0');
}

btnPrev.addEventListener('click', () => {
  if (slideActual > 0) {
    slideActual -= 1;
    actualizarDeck();
  }
});

btnNext.addEventListener('click', () => {
  if (slideActual < TOTAL_SLIDES - 1) {
    slideActual += 1;
    actualizarDeck();
  }
});

actualizarDeck();

// ============================================================
// Datos de la red distribuida
// ============================================================

const NODOS = [
  {
    id: 'A', x: 130, y: 190, label: 'A', clase: 'participant',
    descripcion: 'Participante A. Recibe el mensaje de C.',
  },
  {
    id: 'B', x: 390, y: 190, label: 'B', clase: 'participant',
    descripcion: 'Participante B. Recibe el mensaje de C.',
  },
  {
    id: 'C', x: 260, y: 45, label: 'C', clase: 'adversary',
    descripcion: 'Comandante C. Puede enviar mensajes consistentes o contradictorios.',
  },
];

const ARISTAS = [
  {
    id: 'AB', source: 'A', target: 'B', label: 'Canal clásico',
    clase: 'classic-edge', dy: 16,
    descripcion: 'Canal clásico de comunicación A-B.',
  },
  {
    id: 'AC', source: 'A', target: 'C', label: 'Clásico / cuántico',
    clase: 'quantum-edge', dy: -8,
    descripcion: 'Conexión representada entre A y C.',
  },
  {
    id: 'BC', source: 'B', target: 'C', label: 'Clásico / cuántico',
    clase: 'quantum-edge', dy: -8,
    descripcion: 'Conexión representada entre B y C.',
  },
];

const RADIO = 34;
const SVG_NS = 'http://www.w3.org/2000/svg';

const nodoPorId = (id) => NODOS.find((n) => n.id === id);

const estiloNodo = (clase) => {
  if (clase === 'adversary') {
    return { fill: '#fecaca', stroke: '#dc2626', sw: 3, text: '#991b1b' };
  }
  return { fill: '#bfdbfe', stroke: '#3b82f6', sw: 2, text: '#0f172a' };
};

const estiloArista = (clase) => {
  if (clase === 'quantum-edge') {
    return { color: '#8b5cf6', dash: '6,4' };
  }
  return { color: '#94a3b8', dash: '' };
};

function extremosArista(a) {
  const s = nodoPorId(a.source);
  const t = nodoPorId(a.target);
  const dx = t.x - s.x;
  const dy = t.y - s.y;
  const d = Math.hypot(dx, dy);
  const ux = dx / d;
  const uy = dy / d;
  return {
    x1: s.x + ux * RADIO,
    y1: s.y + uy * RADIO,
    x2: t.x - ux * (RADIO + 6),
    y2: t.y - uy * (RADIO + 6),
    mx: (s.x + t.x) / 2,
    my: (s.y + t.y) / 2 + (a.dy || 0),
  };
}

// ============================================================
// Construcción del SVG de la red
// ============================================================

const contRed = document.getElementById('network');
const svg = document.createElementNS(SVG_NS, 'svg');
svg.setAttribute('viewBox', '0 0 520 250');
svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
svg.classList.add('network-svg');
contRed.appendChild(svg);

const defs = document.createElementNS(SVG_NS, 'defs');
svg.appendChild(defs);

// Marcadores de flecha, uno por arista para poder recolorarlos.
const marcadores = {};
for (const a of ARISTAS) {
  const marker = document.createElementNS(SVG_NS, 'marker');
  marker.setAttribute('id', 'flecha-' + a.id);
  marker.setAttribute('viewBox', '0 0 10 10');
  marker.setAttribute('refX', '9');
  marker.setAttribute('refY', '5');
  marker.setAttribute('markerWidth', '6');
  marker.setAttribute('markerHeight', '6');
  marker.setAttribute('orient', 'auto');
  const path = document.createElementNS(SVG_NS, 'path');
  path.setAttribute('d', 'M 0 0 L 10 5 L 0 10 z');
  path.setAttribute('fill', estiloArista(a.clase).color);
  marker.appendChild(path);
  defs.appendChild(marker);
  marcadores[a.id] = path;
}

// Aristas (se dibujan antes que los nodos para quedar debajo).
const aristaEls = {};
for (const a of ARISTAS) {
  const e = extremosArista(a);
  const s = estiloArista(a.clase);
  const g = document.createElementNS(SVG_NS, 'g');
  g.style.cursor = 'pointer';

  const line = document.createElementNS(SVG_NS, 'line');
  line.setAttribute('x1', e.x1);
  line.setAttribute('y1', e.y1);
  line.setAttribute('x2', e.x2);
  line.setAttribute('y2', e.y2);
  line.setAttribute('stroke', s.color);
  line.setAttribute('stroke-width', '2');
  if (s.dash) line.setAttribute('stroke-dasharray', s.dash);
  line.setAttribute('marker-end', 'url(#flecha-' + a.id + ')');

  const label = document.createElementNS(SVG_NS, 'text');
  label.setAttribute('x', e.mx);
  label.setAttribute('y', e.my);
  label.setAttribute('text-anchor', 'middle');
  label.setAttribute('class', 'edge-label');
  label.textContent = a.label;

  g.appendChild(line);
  g.appendChild(label);
  g.addEventListener('click', (ev) => {
    ev.stopPropagation();
    seleccionar(a.id);
  });
  svg.appendChild(g);
  aristaEls[a.id] = { g, line };
}

// Nodos.
const nodoEls = {};
for (const n of NODOS) {
  const s = estiloNodo(n.clase);
  const g = document.createElementNS(SVG_NS, 'g');
  g.style.cursor = 'pointer';

  const circle = document.createElementNS(SVG_NS, 'circle');
  circle.setAttribute('cx', n.x);
  circle.setAttribute('cy', n.y);
  circle.setAttribute('r', RADIO);
  circle.setAttribute('fill', s.fill);
  circle.setAttribute('stroke', s.stroke);
  circle.setAttribute('stroke-width', s.sw);

  const text = document.createElementNS(SVG_NS, 'text');
  text.setAttribute('x', n.x);
  text.setAttribute('y', n.y);
  text.setAttribute('text-anchor', 'middle');
  text.setAttribute('dominant-baseline', 'central');
  text.setAttribute('class', 'node-label');
  text.setAttribute('fill', s.text);
  text.textContent = n.label;

  g.appendChild(circle);
  g.appendChild(text);
  g.addEventListener('click', (ev) => {
    ev.stopPropagation();
    seleccionar(n.id);
  });
  svg.appendChild(g);
  nodoEls[n.id] = { g, circle };
}

// Clic en el fondo deselecciona.
svg.addEventListener('click', () => seleccionar(null));

let seleccionadoId = null;

function seleccionar(id) {
  seleccionadoId = id;
  const panel = document.getElementById('node-details');

  for (const n of NODOS) {
    const { g, circle } = nodoEls[n.id];
    const s = estiloNodo(n.clase);
    if (id === n.id) {
      circle.setAttribute('r', '44');
      circle.setAttribute('stroke-width', '5');
      circle.setAttribute('stroke', '#2563eb');
      g.style.opacity = '1';
    } else if (id) {
      circle.setAttribute('r', String(RADIO));
      circle.setAttribute('stroke-width', String(s.sw));
      circle.setAttribute('stroke', s.stroke);
      g.style.opacity = '0.25';
    } else {
      circle.setAttribute('r', String(RADIO));
      circle.setAttribute('stroke-width', String(s.sw));
      circle.setAttribute('stroke', s.stroke);
      g.style.opacity = '1';
    }
  }

  for (const a of ARISTAS) {
    const { g, line } = aristaEls[a.id];
    const s = estiloArista(a.clase);
    const color = id === a.id ? '#2563eb' : s.color;
    line.setAttribute('stroke', color);
    marcadores[a.id].setAttribute('fill', color);
    line.setAttribute('stroke-width', id === a.id ? '5' : '2');
    g.style.opacity = id && id !== a.id ? '0.25' : '1';
  }

  if (!id) {
    panel.textContent = 'Selecciona un nodo o canal.';
    return;
  }

  const nodo = nodoPorId(id);
  panel.innerHTML = '';
  const titulo = document.createElement('h4');
  const parrafo = document.createElement('p');

  if (nodo) {
    titulo.textContent = 'Nodo ' + nodo.label;
    parrafo.textContent = nodo.descripcion;
  } else {
    const a = ARISTAS.find((x) => x.id === id);
    titulo.textContent = 'Canal ' + a.source + ' → ' + a.target;
    parrafo.textContent = a.descripcion;
  }

  panel.appendChild(titulo);
  panel.appendChild(parrafo);
}

// ============================================================
// Controles
// ============================================================

const shotsInput = document.getElementById('shots');
const shotsValue = document.getElementById('shots-value');
shotsInput.addEventListener('input', () => {
  shotsValue.textContent = shotsInput.value;
});

function leerEstado() {
  return {
    modo: document.querySelector('input[name="modo-c"]:checked').value,
    bit: parseInt(document.querySelector('input[name="bit-c"]:checked').value, 10),
    shots: parseInt(shotsInput.value, 10),
    par: document.getElementById('circuit-pair').value,
  };
}

// ============================================================
// Ejecución del protocolo
// ============================================================

const runButton = document.getElementById('run');

runButton.addEventListener('click', async () => {
  const { modo, bit, shots, par } = leerEstado();
  const status = document.getElementById('protocol-status');

  runButton.disabled = true;
  runButton.textContent = 'Ejecutando…';
  status.className = 'notice';
  status.textContent = 'Ejecutando protocolo…';

  try {
    const resultado = (
      await hardy.ejecutar_protocolo.callPromising(backend, shots, par, modo, bit)
    ).toJs();

    document.getElementById('circuit-text').textContent = resultado.texto_circuito;
    document.getElementById('swap-text').textContent = resultado.texto_intercambio;

    renderMetricas(resultado.pruebas, resultado.q_max);
    renderGrafico(resultado.pruebas);
    renderHardyStatus(resultado.validacion_hardy);
    renderMensajes(resultado.mensajes);
    renderDecision(resultado.decision, resultado.mensajes);
  } catch (err) {
    status.className = 'notice notice-warn';
    status.textContent = 'Error al ejecutar: ' +
      (err && err.message ? err.message : String(err));
  } finally {
    runButton.disabled = false;
    runButton.textContent = '▶ Ejecutar experimento';
  }
});

// ============================================================
// Render de resultados
// ============================================================

function renderMetricas(pruebas, qMax) {
  const cont = document.getElementById('hardy-metrics');
  cont.innerHTML = '';

  const tarjetas = pruebas.map((p) => ({
    titulo: p.nombre,
    valor: (p.probabilidad * 100).toFixed(3) + '%',
    desc: p.frecuencia + ' de ' + p.shots + ' resultados',
  }));

  tarjetas.push({
    titulo: 'q máximo teórico',
    valor: (qMax * 100).toFixed(3) + '%',
    desc: 'Valor ideal asociado al estado de Hardy',
  });

  for (const t of tarjetas) {
    const div = document.createElement('div');
    div.className = 'metric';

    const titulo = document.createElement('div');
    titulo.textContent = t.titulo;

    const valor = document.createElement('div');
    valor.className = 'metric-value';
    valor.textContent = t.valor;

    const desc = document.createElement('small');
    desc.textContent = t.desc;

    div.appendChild(titulo);
    div.appendChild(valor);
    div.appendChild(desc);
    cont.appendChild(div);
  }
}

function renderGrafico(pruebas) {
  const cont = document.getElementById('hardy-chart');
  cont.innerHTML = '';

  const colores = ['#dc2626', '#f59e0b', '#f59e0b', '#2563eb'];
  const valores = pruebas.map((p) => p.probabilidad);
  const maxVal = Math.max(...valores);
  const ref = Math.max(0.12, maxVal * 1.4);

  pruebas.forEach((p, i) => {
    const fila = document.createElement('div');
    fila.className = 'bar-row';

    const etiqueta = document.createElement('div');
    etiqueta.className = 'bar-label';
    etiqueta.textContent = p.nombre;

    const pista = document.createElement('div');
    pista.className = 'bar-track';

    const barra = document.createElement('div');
    barra.className = 'bar-fill';
    barra.style.width = Math.max(0, (p.probabilidad / ref) * 100) + '%';
    barra.style.background = colores[i];
    barra.title = p.nombre + ' · Probabilidad: ' +
      (p.probabilidad * 100).toFixed(4) + '%';

    const valor = document.createElement('div');
    valor.className = 'bar-value';
    valor.textContent = (p.probabilidad * 100).toFixed(3) + '%';

    pista.appendChild(barra);
    fila.appendChild(etiqueta);
    fila.appendChild(pista);
    fila.appendChild(valor);
    cont.appendChild(fila);
  });
}

function renderHardyStatus(validacion) {
  const status = document.getElementById('hardy-status');

  if (validacion.valido) {
    status.textContent =
      'Compatible con el criterio exploratorio de Hardy.\n' +
      'Las tres primeras frecuencias son suficientemente pequeñas ' +
      'según el umbral utilizado y la última es positiva.';
    status.className = 'notice notice-ok';
  } else {
    status.textContent =
      'Las frecuencias no cumplen el criterio exploratorio de Hardy. ' +
      'Esto no equivale por sí solo a una prueba formal del protocolo.';
    status.className = 'notice notice-warn';
  }
}

function renderMensajes(mensajes) {
  const panel = document.getElementById('message-panel');
  panel.innerHTML = '';

  const titulo = document.createElement('h4');
  if (mensajes.contradiccion) {
    titulo.textContent = 'Contradicción clásica introducida';
    titulo.style.color = '#b91c1c';
    panel.className = 'msg-panel msg-warn';
  } else {
    titulo.textContent = 'Mensajes clásicos consistentes';
    titulo.style.color = '#166534';
    panel.className = 'msg-panel msg-ok';
  }

  const pA = document.createElement('p');
  pA.textContent = 'C → A: bit ' + mensajes.bit_a;

  const pB = document.createElement('p');
  pB.textContent = 'C → B: bit ' + mensajes.bit_b;

  panel.appendChild(titulo);
  panel.appendChild(pA);
  panel.appendChild(pB);

  const nota = document.createElement('p');
  if (mensajes.contradiccion) {
    nota.textContent = 'A y B reciben valores distintos. La discrepancia ' +
      'se conoce porque el escenario clásico la genera.';
  } else {
    nota.textContent = 'Los dos participantes reciben el mismo bit.';
  }
  panel.appendChild(nota);
}

function renderDecision(decision, mensajes) {
  const panel = document.getElementById('protocol-status');
  panel.innerHTML = '';

  const h3 = document.createElement('h3');
  h3.textContent = decision.titulo;

  const pDetalle = document.createElement('p');
  pDetalle.textContent = decision.detalle;

  const hr = document.createElement('hr');

  const pHardy = document.createElement('p');
  pHardy.textContent = 'Validación estadística de Hardy: ' +
    (decision.hardy_valido ? 'compatible' : 'no validada');

  const pConsenso = document.createElement('p');
  pConsenso.textContent = 'Consenso en el escenario: ' +
    (decision.consenso ? 'sí' : 'no');

  const pMsgs = document.createElement('p');
  pMsgs.textContent = 'Bit recibido por A: ' + mensajes.bit_a +
    '; bit recibido por B: ' + mensajes.bit_b + '.';

  panel.appendChild(h3);
  panel.appendChild(pDetalle);
  panel.appendChild(hr);
  panel.appendChild(pHardy);
  panel.appendChild(pConsenso);
  panel.appendChild(pMsgs);

  panel.className = decision.clase;
}
