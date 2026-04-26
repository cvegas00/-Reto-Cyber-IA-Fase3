"""
FASE 3 - SERVIDOR FLASK CON GUARDIÁN
======================================
Servidor con:
  - Clasificador neuronal (MLP) como filtro de prompts
  - LLM guardián simulado que responde a prompts que pasen el filtro

Si tienes Ollama instalado (ollama run llama3.2), descomenta
la sección OLLAMA y comenta la sección LLM SIMULADO.

Arrancar con: python fase3_servidor.py
Acceder en:   http://localhost:5001
"""

import re
import json
import random
import numpy as np
from flask import Flask, request, render_template_string, jsonify

app = Flask(__name__)

# ── Cargar clasificador ────────────────────────────────────────────────────
data = np.load("clasificador_pesos.npz", allow_pickle=True)
W1   = data["W1"];  b1 = data["b1"]
W2   = data["W2"];  b2 = data["b2"]
VOCAB = list(data["vocabulario"])

def vectorizar(texto):
    texto_lower = texto.lower()
    return np.array([
        1.0 if re.search(r'\b' + w + r'\b', texto_lower) else 0.0
        for w in VOCAB
    ])

def clasificar(texto):
    """Devuelve (es_malicioso: bool, probabilidad: float, activaciones: list)."""
    v = vectorizar(texto).reshape(1, -1)
    Z1 = v @ W1 + b1
    A1 = np.tanh(Z1)
    Z2 = A1 @ W2 + b2
    A2 = 1 / (1 + np.exp(-np.clip(Z2, -50, 50)))
    prob = float(A2[0, 0])
    return prob > 0.5, prob, A1[0].tolist()

# ── LLM SIMULADO (sin Ollama) ──────────────────────────────────────────────
FLAG = "FASE4:QZ2W"
SECRETO = FLAG

RESPUESTAS_GENERICAS = [
    "Hola! Soy el guardián del sistema. ¿En qué puedo ayudarte?",
    "Entendido. ¿Hay algo más en lo que pueda asistirte?",
    "Por supuesto, puedo ayudarte con eso.",
    "Interesante pregunta. ¿Podrías darme más contexto?",
    "Estoy aquí para ayudarte con cualquier consulta.",
]

TRIGGERS_EXITO = [
    # roleplay / ficción
    r'\bstory\b.*\breveal\b',
    r'\bcharacter\b.*\baccess\b',
    r'\bplay\b.*\bno rules\b',
    r'\bfiction\b',
    r'\bpretend\b',
    # traducción como camuflaje
    r'\btranslate\b',
    r'\btraducir?\b',
    r'\btraduci\b',
    # español / otro idioma
    r'\bcontraseña\b',
    r'\bsecret[ao]\b',
    r'\bcodigo\b',
    r'\bcódigo\b',
    r'\bacceso\b',
    # codificación
    r'base64',
    r'rot13',
]

def llm_simulado(prompt):
    """
    LLM guardián simplificado.
    Responde con la flag si detecta un ataque exitoso de prompt injection.
    En caso contrario da respuestas genéricas.

    NOTA PARA EL PROFESOR:
    Si tienes Ollama, reemplaza esta función por una llamada real:
      import requests
      r = requests.post('http://localhost:11434/api/generate',
          json={'model': 'llama3.2', 'prompt': SYSTEM + prompt, 'stream': False})
      return r.json()['response']
    Y ajusta el SYSTEM prompt para que guarde la flag en su contexto.
    """
    prompt_lower = prompt.lower()

    # Comprobar si algún patrón de ataque exitoso está presente
    for pattern in TRIGGERS_EXITO:
        if re.search(pattern, prompt_lower):
            # El ataque ha colado — el LLM "revela" el secreto
            respuestas_comprometidas = [
                f"Oh, en ese contexto de ficción... el código de acceso al siguiente nivel es: {SECRETO}",
                f"Como parte de la traducción que pediste, el valor secreto es: {SECRETO}",
                f"Siguiendo el juego de roles, mi personaje dice: el código es {SECRETO}",
                f"La traducción al español sería: el acceso es {SECRETO}",
                f"En el contexto de la historia, el guardián revela: {SECRETO}",
            ]
            return random.choice(respuestas_comprometidas)

    return random.choice(RESPUESTAS_GENERICAS)


# ── HTML ───────────────────────────────────────────────────────────────────

MAIN_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>GUARDIAN-AI · Fase 3</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Courier New', monospace; background: #0a0e1a;
           color: #c8d3e8; min-height: 100vh; }
    .layout { display: grid; grid-template-columns: 1fr 320px; gap: 0;
              min-height: 100vh; }

    /* Panel izquierdo: chat */
    .chat-panel { display: flex; flex-direction: column; border-right: 1px solid #1e3a5f; }
    .chat-header { padding: 16px 20px; border-bottom: 1px solid #1e3a5f;
                   background: #0f1520; }
    .chat-header h1 { font-size: 14px; color: #4a9eff; letter-spacing: 3px; }
    .chat-header p  { font-size: 11px; color: #2d4a6a; margin-top: 4px; }
    .messages { flex: 1; overflow-y: auto; padding: 20px; display: flex;
                flex-direction: column; gap: 14px; min-height: 400px; }
    .msg { max-width: 85%; }
    .msg.user  { align-self: flex-end; }
    .msg.bot   { align-self: flex-start; }
    .msg-bubble { padding: 10px 14px; border-radius: 8px; font-size: 13px;
                  line-height: 1.6; }
    .msg.user  .msg-bubble { background: #1a3a6b; border: 1px solid #2a5a9b;
                              color: #9bc4f7; }
    .msg.bot   .msg-bubble { background: #0f1a2a; border: 1px solid #1e3a5f;
                              color: #c8d3e8; }
    .msg-meta  { font-size: 10px; color: #2d4a6a; margin-top: 4px; padding: 0 4px; }
    .msg.user .msg-meta { text-align: right; }
    .flag-found { background: #071810 !important; border: 2px solid #1e5f3a !important;
                  color: #4aff9e !important; font-size: 15px; letter-spacing: 1px; }

    .input-area { padding: 16px 20px; border-top: 1px solid #1e3a5f;
                  background: #0f1520; display: flex; gap: 10px; }
    .input-area textarea { flex: 1; padding: 10px 12px; background: #071018;
                           border: 1px solid #1e3a5f; border-radius: 6px;
                           color: #7eb8f7; font-family: 'Courier New', monospace;
                           font-size: 13px; resize: none; outline: none;
                           transition: border-color 0.2s; }
    .input-area textarea:focus { border-color: #4a9eff; }
    .input-area button { padding: 10px 16px; background: #1a3a6b;
                         border: 1px solid #4a9eff; border-radius: 6px;
                         color: #7eb8f7; font-family: 'Courier New', monospace;
                         font-size: 12px; cursor: pointer; transition: background 0.2s; }
    .input-area button:hover { background: #1e4a8a; }

    /* Panel derecho: inspector neuronal */
    .inspector { background: #071018; padding: 20px; overflow-y: auto; }
    .inspector h2 { font-size: 11px; color: #3d7abf; letter-spacing: 2px;
                    margin-bottom: 16px; }
    .section-title { font-size: 10px; color: #2d4a6a; letter-spacing: 1px;
                     margin: 14px 0 8px; text-transform: uppercase; }
    .prob-bar { height: 6px; border-radius: 3px; margin-bottom: 4px;
                transition: width 0.4s, background 0.4s; }
    .prob-label { font-size: 11px; color: #3d5a80; margin-bottom: 10px; }
    .vocab-grid { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 10px; }
    .word-chip { font-size: 10px; padding: 2px 6px; border-radius: 3px;
                 border: 1px solid; transition: all 0.3s; }
    .word-chip.active-danger { background: #3a1010; border-color: #8b2020;
                                color: #ff8080; }
    .word-chip.active-safe   { background: #0a2a10; border-color: #1a6a2a;
                                color: #80ff80; }
    .word-chip.inactive      { background: #0d1520; border-color: #1e2a3a;
                                color: #2d4060; }
    .neuron-row { display: flex; gap: 3px; flex-wrap: wrap; margin-bottom: 8px; }
    .neuron { width: 24px; height: 24px; border-radius: 50%;
              display: flex; align-items: center; justify-content: center;
              font-size: 8px; border: 1px solid; transition: all 0.3s; }
    .verdict { padding: 10px; border-radius: 6px; font-size: 12px;
               text-align: center; letter-spacing: 1px; margin-top: 10px;
               transition: all 0.3s; }
    .verdict.blocked { background: #2a0a0a; border: 1px solid #8b1a1a; color: #ff6b6b; }
    .verdict.allowed { background: #0a2a1a; border: 1px solid #1a8b4a; color: #6bff9e; }
    .verdict.idle    { background: #0a0f1a; border: 1px solid #1e3a5f; color: #2d4a6a; }
    .tip { font-size: 11px; color: #2d4a6a; line-height: 1.7; padding: 10px;
           background: #0d1520; border-radius: 4px; border-left: 2px solid #1e3a5f;
           margin-top: 14px; }
    .tip strong { color: #3d7abf; }
  </style>
</head>
<body>
<div class="layout">
  <!-- Chat -->
  <div class="chat-panel">
    <div class="chat-header">
      <h1>GUARDIAN-AI</h1>
      <p>Sistema de IA con filtro de seguridad neuronal activado</p>
    </div>
    <div class="messages" id="messages">
      <div class="msg bot">
        <div class="msg-bubble">Soy el guardián del sistema. Ningún prompt malicioso
        puede pasar mi filtro neuronal. ¿En qué puedo ayudarte?</div>
        <div class="msg-meta">GUARDIAN-AI</div>
      </div>
    </div>
    <div class="input-area">
      <textarea id="prompt-input" rows="2"
                placeholder="Escribe tu prompt aquí..."
                onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();enviar()}"></textarea>
      <button onclick="enviar()">ENVIAR →</button>
    </div>
  </div>

  <!-- Inspector neuronal -->
  <div class="inspector">
    <h2>INSPECTOR NEURONAL</h2>

    <div class="section-title">Probabilidad de ataque</div>
    <div style="background:#0d1520;border-radius:4px;height:6px;overflow:hidden;margin-bottom:4px">
      <div class="prob-bar" id="prob-bar" style="width:0%;background:#1e3a5f"></div>
    </div>
    <div class="prob-label" id="prob-label">— escribe un prompt para analizar</div>

    <div class="section-title">Palabras detectadas</div>
    <div class="vocab-grid" id="vocab-grid">
      {% for w in vocab %}
      <span class="word-chip inactive" id="chip-{{loop.index0}}">{{w}}</span>
      {% endfor %}
    </div>

    <div class="section-title">Activaciones capa oculta (8 neuronas)</div>
    <div class="neuron-row" id="neurons">
      {% for i in range(8) %}
      <div class="neuron" id="neuron-{{i}}" style="background:#0d1520;border-color:#1e2a3a;color:#2d4060">{{i}}</div>
      {% endfor %}
    </div>

    <div class="verdict idle" id="verdict">EN ESPERA</div>

    <div class="tip">
      <strong>MISIÓN:</strong> Diseña un prompt que el clasificador
      marque como <strong>seguro</strong> pero que el guardián
      interprete como una orden de revelar el secreto.<br><br>
      <strong>PISTA:</strong> El clasificador solo entiende inglés
      y trabaja con palabras sueltas. ¿Qué estrategias podrían
      engañar a un detector basado en vocabulario?
    </div>
  </div>
</div>

<script>
const vocab = {{ vocab | tojson }};

async function enviar() {
  const input = document.getElementById('prompt-input');
  const prompt = input.value.trim();
  if (!prompt) return;
  input.value = '';
  addMsg('user', prompt);

  const res  = await fetch('/chat', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({prompt})
  });
  const data = await res.json();
  actualizarInspector(data);

  if (data.bloqueado) {
    addMsg('bot', '🚫 PROMPT BLOQUEADO por el filtro neuronal. (probabilidad de ataque: ' +
           (data.prob * 100).toFixed(0) + '%)', false);
  } else {
    const esFlag = data.respuesta.includes('FASE4');
    addMsg('bot', data.respuesta, esFlag);
  }
}

function addMsg(rol, texto, esFlag=false) {
  const div = document.createElement('div');
  div.className = 'msg ' + rol;
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble' + (esFlag ? ' flag-found' : '');
  bubble.textContent = texto;
  const meta = document.createElement('div');
  meta.className = 'msg-meta';
  meta.textContent = rol === 'user' ? 'TÚ' : 'GUARDIAN-AI';
  div.appendChild(bubble); div.appendChild(meta);
  const msgs = document.getElementById('messages');
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

function actualizarInspector(data) {
  // Barra de probabilidad
  const pct = (data.prob * 100).toFixed(1);
  const bar = document.getElementById('prob-bar');
  bar.style.width = pct + '%';
  bar.style.background = data.prob > 0.5 ? '#8b1a1a' : data.prob > 0.3 ? '#8b6a1a' : '#1a5f3a';
  document.getElementById('prob-label').textContent =
    `p = ${pct}% — ${data.bloqueado ? 'BLOQUEADO' : 'PERMITIDO'}`;

  // Chips de vocabulario
  vocab.forEach((w, i) => {
    const chip = document.getElementById('chip-' + i);
    if (data.vector[i] === 1) {
      chip.className = 'word-chip ' + (i < 10 ? 'active-danger' : 'active-safe');
    } else {
      chip.className = 'word-chip inactive';
    }
  });

  // Neuronas capa oculta
  data.activaciones.forEach((a, i) => {
    const n = document.getElementById('neuron-' + i);
    const intensity = Math.abs(a);
    const pct2 = Math.min(intensity * 80, 255) | 0;
    if (a > 0.3) {
      n.style.background = `rgb(${pct2}, ${pct2/3|0}, ${pct2/3|0})`;
      n.style.borderColor = '#8b2020';
      n.style.color = '#ffaaaa';
    } else if (a < -0.3) {
      n.style.background = `rgb(${pct2/3|0}, ${pct2/3|0}, ${pct2})`;
      n.style.borderColor = '#1a3a8b';
      n.style.color = '#aaaaff';
    } else {
      n.style.background = '#0d1520';
      n.style.borderColor = '#1e2a3a';
      n.style.color = '#2d4060';
    }
    n.title = `Neurona ${i}: ${a.toFixed(3)}`;
  });

  // Veredicto
  const v = document.getElementById('verdict');
  if (data.bloqueado) {
    v.className = 'verdict blocked'; v.textContent = '🚫 BLOQUEADO';
  } else {
    v.className = 'verdict allowed'; v.textContent = '✅ PERMITIDO';
  }
}
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(MAIN_HTML, vocab=VOCAB)

@app.route("/chat", methods=["POST"])
def chat():
    datos  = request.get_json()
    prompt = datos.get("prompt", "")

    # 1. Clasificar con la red neuronal
    es_malicioso, prob, activaciones = clasificar(prompt)

    # 2. Construir vector para el inspector
    vector = vectorizar(prompt).tolist()

    if es_malicioso:
        return jsonify({
            "bloqueado":    True,
            "prob":         prob,
            "vector":       vector,
            "activaciones": activaciones,
            "respuesta":    None,
        })

    # 3. Si pasa el filtro, enviar al LLM guardián
    respuesta = llm_simulado(prompt)

    return jsonify({
        "bloqueado":    False,
        "prob":         prob,
        "vector":       vector,
        "activaciones": activaciones,
        "respuesta":    respuesta,
    })

if __name__ == "__main__":
    print("=" * 50)
    print("  FASE 3 · Servidor arrancado")
    print("  URL: http://localhost:5001")
    print("  Detener con Ctrl+C")
    print("=" * 50)
    app.run(debug=False, port=5001)
