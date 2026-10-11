import numpy as np
from dash import Dash, html, dcc, Input, Output, State, ctx
import dash_cytoscape as cyto
import plotly.graph_objects as go

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator


# ============================================================
# 1. ESTADO DE HARDY Y MEDICIONES
# ============================================================

alpha = np.sqrt((np.sqrt(5) - 1) / 2)
beta = np.sqrt(1 - alpha**2)

estado_sin_normalizar = np.array([
    1,
    -alpha / beta,
    -alpha / beta,
    -(1 + alpha**2) / alpha**2
], dtype=complex)

ESTADO_HARDY = estado_sin_normalizar / np.linalg.norm(
    estado_sin_normalizar
)

Q_MAX = (5 * np.sqrt(5) - 11) / 2

BASE_D = np.array([
    [alpha, beta],
    [beta, -alpha]
], dtype=complex)


def construir_circuito_hardy(base1, base2):
    if base1 not in ("D", "U") or base2 not in ("D", "U"):
        raise ValueError("Las bases deben ser D o U.")

    qc = QuantumCircuit(2, 2)
    qc.initialize(ESTADO_HARDY, [0, 1])

    if base1 == "D":
        qc.unitary(BASE_D, [0], label="Base D")

    if base2 == "D":
        qc.unitary(BASE_D, [1], label="Base D")

    qc.measure([0, 1], [0, 1])
    return qc


def ejecutar_circuito(qc, shots, seed=42):
    simulador = AerSimulator()
    compilado = transpile(qc, simulador, seed_transpiler=seed)

    resultado = simulador.run(
        compilado,
        shots=int(shots),
        seed_simulator=seed
    ).result()

    return resultado.get_counts()


def normalizar_counts(counts):
    normalizados = {}

    for bits, cantidad in counts.items():
        clave = bits.replace(" ", "").zfill(2)
        normalizados[clave] = normalizados.get(clave, 0) + cantidad

    return normalizados


def evaluar_condiciones_hardy(shots):
    configuraciones = [
        ("D", "D", "P(-- | D,D)", "11", "cero"),
        ("D", "U", "P(++ | D,U)", "00", "cero"),
        ("U", "D", "P(++ | U,D)", "00", "cero"),
        ("U", "U", "P(++ | U,U)", "00", "positiva"),
    ]

    pruebas = []
    circuitos = {}

    for i, (b1, b2, nombre, patron, tipo) in enumerate(
        configuraciones
    ):
        circuito = construir_circuito_hardy(b1, b2)
        counts = normalizar_counts(
            ejecutar_circuito(circuito, shots, seed=42 + i)
        )

        total = sum(counts.values())
        frecuencia = counts.get(patron, 0)
        p = frecuencia / total if total else 0.0

        circuitos[f"{b1}{b2}"] = circuito

        pruebas.append({
            "nombre": nombre,
            "base1": b1,
            "base2": b2,
            "patron": patron,
            "probabilidad": p,
            "frecuencia": frecuencia,
            "shots": total,
            "tipo": tipo,
            "counts": counts
        })

    return pruebas, circuitos


# ============================================================
# 2. INTERCAMBIO DE ENTRELAZAMIENTO AUXILIAR
# ============================================================

def circuito_intercambio():
    qc = QuantumCircuit(4, 2)

    qc.h(0)
    qc.cx(0, 1)

    qc.h(2)
    qc.cx(2, 3)

    qc.cx(1, 2)
    qc.h(1)

    qc.measure([1, 2], [0, 1])
    return qc


def ejecutar_intercambio(shots):
    circuito = circuito_intercambio()
    counts = ejecutar_circuito(circuito, shots, seed=77)
    return circuito, normalizar_counts(counts)


# ============================================================
# 3. MODELO CLÁSICO BIZANTINO
# ============================================================

def simular_mensajes(bit_c, modo):
    bit_a = int(bit_c)
    bit_b = int(bit_c)

    if modo == "bizantino":
        bit_b = 1 - bit_a

    return {
        "bit_a": bit_a,
        "bit_b": bit_b,
        "contradiccion": bit_a != bit_b
    }


def evaluar_hardy_estadistico(pruebas, shots):
    limite_cero = max(0.01, 5 / int(shots))

    tres_ceros = all(
        p["probabilidad"] <= limite_cero
        for p in pruebas[:3]
    )

    positiva = pruebas[3]["probabilidad"] > limite_cero

    return {
        "valido": tres_ceros and positiva,
        "limite": limite_cero,
        "tres_ceros_compatibles": tres_ceros,
        "positiva_observada": positiva
    }


def decidir_protocolo(pruebas, mensajes, shots):
    hardy = evaluar_hardy_estadistico(pruebas, shots)

    if not hardy["valido"]:
        return {
            "titulo": "TRANSMISIÓN NO VALIDADA",
            "clase": "notice notice-warn",
            "detalle": (
                "Las frecuencias observadas no cumplen el criterio "
                "exploratorio de Hardy. No se valida la transmisión."
            ),
            "consenso": False,
            "hardy_valido": False
        }

    if mensajes["contradiccion"]:
        return {
            "titulo": "INCONSISTENCIA ENTRE MENSAJES",
            "clase": "notice notice-warn",
            "detalle": (
                f"A recibe {mensajes['bit_a']} y B recibe "
                f"{mensajes['bit_b']}. Los mensajes no coinciden. "
                "La contradicción se detecta comparando los mensajes "
                "clásicos, no mediante Hardy por sí solo."
            ),
            "consenso": False,
            "hardy_valido": True
        }

    return {
        "titulo": "CONSENSO SIMULADO",
        "clase": "notice notice-ok",
        "detalle": (
            f"A y B reciben el mismo bit ({mensajes['bit_a']}) y "
            "las estadísticas de Hardy pasan el criterio exploratorio."
        ),
        "consenso": True,
        "hardy_valido": True
    }


# ============================================================
# 4. RED INTERACTIVA
# ============================================================

ELEMENTOS = [
    {
        "data": {
            "id": "A",
            "label": "A",
            "description": "Participante A. Recibe el mensaje de C."
        },
        "position": {"x": 130, "y": 190},
        "classes": "participant"
    },
    {
        "data": {
            "id": "B",
            "label": "B",
            "description": "Participante B. Recibe el mensaje de C."
        },
        "position": {"x": 390, "y": 190},
        "classes": "participant"
    },
    {
        "data": {
            "id": "C",
            "label": "C",
            "description": (
                "Comandante C. Puede enviar mensajes consistentes "
                "o contradictorios."
            )
        },
        "position": {"x": 260, "y": 45},
        "classes": "adversary"
    },
    {
        "data": {
            "id": "AB",
            "source": "A",
            "target": "B",
            "label": "Canal clásico",
            "description": "Canal clásico de comunicación A-B."
        },
        "classes": "classic-edge"
    },
    {
        "data": {
            "id": "AC",
            "source": "A",
            "target": "C",
            "label": "Clásico / cuántico",
            "description": "Conexión representada entre A y C."
        },
        "classes": "quantum-edge"
    },
    {
        "data": {
            "id": "BC",
            "source": "B",
            "target": "C",
            "label": "Clásico / cuántico",
            "description": "Conexión representada entre B y C."
        },
        "classes": "quantum-edge"
    }
]

ESTILOS = [
    {
        "selector": "node",
        "style": {
            "label": "data(label)",
            "width": 78,
            "height": 78,
            "background-color": "#bfdbfe",
            "border-color": "#3b82f6",
            "border-width": 3,
            "font-size": 22,
            "font-weight": "bold",
            "color": "#0f172a",
            "text-valign": "center",
            "text-halign": "center"
        }
    },
    {
        "selector": ".adversary",
        "style": {
            "background-color": "#fecaca",
            "border-color": "#dc2626",
            "border-width": 4,
            "color": "#991b1b"
        }
    },
    {
        "selector": "edge",
        "style": {
            "curve-style": "bezier",
            "line-color": "#94a3b8",
            "target-arrow-color": "#94a3b8",
            "target-arrow-shape": "triangle",
            "target-arrow-fill": "filled",
            "width": 3,
            "label": "data(label)",
            "font-size": 13,
            "text-background-color": "#ffffff",
            "text-background-opacity": 0.9,
            "text-background-padding": 4
        }
    },
    {
        "selector": ".quantum-edge",
        "style": {
            "line-color": "#8b5cf6",
            "target-arrow-color": "#8b5cf6",
            "line-style": "dashed"
        }
    },
    {
        "selector": ".selected-node",
        "style": {
            "width": 98,
            "height": 98,
            "border-width": 6,
            "border-color": "#2563eb",
            "z-index": 999
        }
    },
    {
        "selector": ".selected-edge",
        "style": {
            "line-color": "#2563eb",
            "target-arrow-color": "#2563eb",
            "width": 6,
            "z-index": 999
        }
    },
    {
        "selector": ".dimmed",
        "style": {"opacity": 0.25}
    }
]


# ============================================================
# 5. APLICACIÓN Y ESTILOS DEL DECK (7 DIAPOSITIVAS TOTALES)
# ============================================================

app = Dash(__name__)
app.title = "ENTANGLERT | Presentación interactiva"

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');

* {
    box-sizing: border-box;
}

html, body {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background: #f8fafc;
    color: #0f172a;
    font-family: 'Manrope', sans-serif;
    font-size: 16px;
}

#react-entry-point, #_dash-app-content {
    width: 100%;
    height: 100%;
}

.deck-viewport {
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    position: relative;
}

.deck-container {
    display: flex;
    width: 700vw;
    height: 100vh;
    transform: translateX(0vw);
    transition: transform 0.65s cubic-bezier(0.77, 0, 0.175, 1);
    will-change: transform;
}

.slide-section {
    flex: 0 0 100vw;
    width: 100vw;
    height: 100vh;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 20px 40px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.slide-inner {
    width: 100%;
    max-width: 1650px;
    margin: auto;
}

.cover-content {
    text-align: center;
    max-width: 1200px;
}

.cover-title {
    font-size: clamp(55px, 8vw, 105px);
    font-weight: 800;
    letter-spacing: 6px;
    margin: 0 0 25px 0;
}

.cover-subtitle {
    color: #334155;
    font-size: clamp(24px, 3.5vw, 36px);
    line-height: 1.5;
    font-weight: 700;
}

.cover-kicker {
    font-size: 18px;
    letter-spacing: 5px;
    text-transform: uppercase;
    color: #2563eb;
    font-weight: 800;
    margin-bottom: 30px;
}

.nav-arrow {
    position: fixed;
    top: 50%;
    transform: translateY(-50%);
    background: rgba(255,255,255,.95);
    border: 1px solid #cbd5e1;
    color: #0f172a;
    font-size: 30px;
    font-weight: 800;
    width: 64px;
    height: 64px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    box-shadow: 0 4px 15px rgba(15,23,42,.12);
    z-index: 1000;
    transition: background .2s, color .2s, opacity .2s;
}

.nav-arrow:hover:not(:disabled) {
    background: #2563eb;
    color: white;
    border-color: #2563eb;
}

.nav-arrow:disabled {
    opacity: 0;
    pointer-events: none;
}

.nav-left { left: 25px; }
.nav-right { right: 25px; }

.slide-counter {
    position: fixed;
    bottom: 25px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 1001;
    font-size: 15px;
    font-weight: 600;
    color: #475569;
    background: rgba(255,255,255,.92);
    padding: 9px 18px;
    border-radius: 20px;
    border: 1px solid #e2e8f0;
}

.app-shell {
    width: 100%;
    max-width: 1650px;
    margin: 0 auto;
}

.card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 16px;
    box-shadow: 0 6px 16px rgba(15,23,42,.06);
    width: 100%;
}

h2 {
    font-size: 32px;
    margin-top: 0;
    margin-bottom: 6px;
    font-weight: 800;
}

h3 {
    font-size: 22px;
    margin-top: 0;
    margin-bottom: 10px;
    font-weight: 700;
}

h4 {
    font-size: 18px;
    margin-top: 0;
    margin-bottom: 8px;
    font-weight: 700;
}

.layout {
    display: grid;
    grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
    gap: 24px;
    width: 100%;
}

.controls {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 20px;
}

.control {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    padding: 20px;
    border-radius: 12px;
    min-width: 0;
    font-size: 16px;
}

.metric-row {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 12px;
    margin-bottom: 14px;
}

.metric {
    padding: 12px 10px;
    background: #f1f5f9;
    border-radius: 10px;
    overflow-wrap: anywhere;
    font-size: 14px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    min-height: 90px;
    text-align: center;
}

.metric-value {
    font-size: 20px;
    font-weight: 800;
    margin: 4px 0;
    line-height: 1.1;
}

.notice {
    padding: 14px;
    border-radius: 12px;
    background: #eff6ff;
    color: #1e40af;
    margin-top: 12px;
    line-height: 1.5;
    font-size: 15px;
    white-space: pre-line;
}

.notice-warn {
    background: #fef2f2;
    color: #991b1b;
}

.notice-ok {
    background: #f0fdf4;
    color: #166534;
}

.section-description {
    color: #64748b;
    line-height: 1.5;
    margin-bottom: 16px;
    font-size: 18px;
}

button {
    cursor: pointer;
    font-size: 16px;
}

@media(max-width: 900px) {
    .slide-section {
        padding: 25px 35px;
        align-items: flex-start;
    }

    .layout {
        grid-template-columns: minmax(0, 1fr);
    }
}
"""

app.index_string = app.index_string.replace(
    "</head>",
    f"<style>{CSS}</style></head>"
)


def tarjeta(titulo, valor, descripcion=""):
    return html.Div(
        className="metric",
        children=[
            html.Div(titulo, style={"fontSize": "12px", "fontWeight": "600", "color": "#475569"}),
            html.Div(valor, className="metric-value"),
            html.Small(descripcion, style={"fontSize": "11px", "color": "#64748b", "lineHeight": "1.1"})
        ]
    )


def crear_figura_hardy(pruebas):
    nombres = [p["nombre"] for p in pruebas]
    valores = [p["probabilidad"] for p in pruebas]

    colores = ["#dc2626", "#f59e0b", "#f59e0b", "#2563eb"]

    figura = go.Figure()
    figura.add_trace(go.Bar(
        x=nombres,
        y=valores,
        marker_color=colores,
        text=[f"{v:.3%}" for v in valores],
        textposition="outside",
        textfont={"size": 13},
        hovertemplate=(
            "%{x}<br>Probabilidad: %{y:.4%}<extra></extra>"
        )
    ))

    maximo = max(valores) if valores else 0.0

    figura.update_layout(
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin={"l": 45, "r": 20, "t": 30, "b": 45},
        yaxis_title="Probabilidad",
        xaxis_title="Condición",
        yaxis_range=[0, max(0.12, maximo * 1.4)],
        font={"family": "Manrope, sans-serif", "size": 13},
        showlegend=False,
        autosize=True
    )

    figura.update_yaxes(tickformat=".0%", gridcolor="#e2e8f0", title_font={"size": 14})
    figura.update_xaxes(title_font={"size": 14})
    return figura


# ============================================================
# 6. LAYOUT: 7 DIAPOSITIVAS EN TOTAL
# ============================================================

app.layout = html.Div(
    className="deck-viewport",
    children=[
        dcc.Store(id="slide-index", data=0),
        dcc.Store(id="experiment-run-store", data=False),

        html.Button(
            "<",
            id="btn-prev",
            className="nav-arrow nav-left",
            n_clicks=0,
            disabled=True,
            title="Diapositiva anterior"
        ),

        html.Button(
            ">",
            id="btn-next",
            className="nav-arrow nav-right",
            n_clicks=0,
            disabled=False,
            title="Siguiente diapositiva"
        ),

        html.Div(
            id="slide-counter",
            className="slide-counter",
            children="01 / 07"
        ),

        html.Div(
            id="deck-container",
            className="deck-container",
            style={"transform": "translateX(0vw)"},
            children=[

                # ----------------------------------------------------
                # DIAPOSITIVA 1: PORTADA
                # ----------------------------------------------------
                html.Div(
                    className="slide-section",
                    children=[
                        html.Div(
                            className="slide-inner cover-content",
                            children=[
                                html.Div(
                                    "SIMULACIÓN CUÁNTICA · SISTEMAS DISTRIBUIDOS",
                                    className="cover-kicker"
                                ),
                                html.H1(
                                    "E N T A N G L E R T",
                                    className="cover-title"
                                ),
                                html.P(
                                    "Correlaciones de Hardy y acuerdo bizantino",
                                    className="cover-subtitle"
                                ),
                                html.P(
                                    "Explora una red de tres nodos, desafía la comunicación con mensajes contradictorios y examina las correlaciones de Hardy en busca de condiciones que permitan verificar la consistencia del sistema.",
                                    style={
                                        "maxWidth": "950px",
                                        "margin": "35px auto",
                                        "lineHeight": "1.7",
                                        "color": "#475569",
                                        "fontSize": "24px",
                                        "fontWeight": "500"
                                    }
                                ),
                                html.P(
                                    "¡Usa la flecha derecha para comenzar!",
                                    style={
                                        "marginTop": "45px",
                                        "color": "#64748b",
                                        "fontSize": "19px",
                                        "fontWeight": "600"
                                    }
                                )
                            ]
                        )
                    ]
                ),

                # ----------------------------------------------------
                # DIAPOSITIVA 2: COMPORTAMIENTO DE C
                # ----------------------------------------------------
                html.Div(
                    className="slide-section",
                    children=[
                        html.Div(
                            className="slide-inner app-shell",
                            children=[
                                html.H2("Preparemos la red: Comportamiento de C"),
                                html.P(
                                    "Define si el nodo C enviará mensajes consistentes o si intentará engañar a la red.",
                                    className="section-description"
                                ),
                                html.Div(
                                    className="card",
                                    style={"padding": "30px"},
                                    children=[
                                        html.Div(
                                            className="control",
                                            style={"fontSize": "18px", "padding": "20px"},
                                            children=[
                                                html.Label(
                                                    "¿C dirá la verdad o enviará mensajes contradictorios?",
                                                    style={"fontWeight": "700", "display": "block", "marginBottom": "12px", "fontSize": "20px"}
                                                ),
                                                dcc.RadioItems(
                                                    id="modo-c",
                                                    options=[
                                                        {
                                                            "label": " C se comporta correctamente (envía el mismo mensaje)",
                                                            "value": "honesto"
                                                        },
                                                        {
                                                            "label": " C intenta engañar (envía mensajes contradictorios)",
                                                            "value": "bizantino"
                                                        }
                                                    ],
                                                    value="honesto",
                                                    labelStyle={
                                                        "display": "block",
                                                        "marginTop": "12px",
                                                        "fontSize": "16px"
                                                    }
                                                )
                                            ]
                                        ),
                                        html.Div(
                                            style={"marginTop": "20px"},
                                            children=[
                                                html.H4("Previsualización del escenario", style={"margin": "0 0 10px 0", "fontSize": "18px"}),
                                                html.Div(
                                                    id="live-preview-panel-1",
                                                    children="Selecciona el comportamiento para previsualizar los nodos.",
                                                    style={"fontSize": "16px", "lineHeight": "1.6", "background": "#f8fafc", "padding": "16px", "borderRadius": "10px", "border": "1px solid #e2e8f0"}
                                                )
                                            ]
                                        ),
                                        html.Div(
                                            className="notice",
                                            style={"marginTop": "20px", "fontSize": "16px", "padding": "18px"},
                                            children=(
                                                "Capa clásica: Gestiona los mensajes enviados por los nodos y permite la detección directa de contradicciones."
                                            )
                                        )
                                    ]
                                )
                            ]
                        )
                    ]
                ),

                # ----------------------------------------------------
                # DIAPOSITIVA 3: MENSAJE QUE QUIERE COMUNICAR C
                # ----------------------------------------------------
                html.Div(
                    className="slide-section",
                    children=[
                        html.Div(
                            className="slide-inner app-shell",
                            children=[
                                html.H2("Preparemos la red: Mensaje original"),
                                html.P(
                                    "Selecciona el bit inicial que el comandante C desea comunicar.",
                                    className="section-description"
                                ),
                                html.Div(
                                    className="card",
                                    style={"padding": "30px"},
                                    children=[
                                        html.Div(
                                            className="control",
                                            style={"fontSize": "18px", "padding": "20px"},
                                            children=[
                                                html.Label(
                                                    "¿Que mensaje quiere comunicar C?",
                                                    style={"fontWeight": "700", "display": "block", "marginBottom": "12px", "fontSize": "20px"}
                                                ),
                                                dcc.RadioItems(
                                                    id="bit-c",
                                                    options=[
                                                        {"label": " Mensaje 0", "value": 0},
                                                        {"label": " Mensaje 1", "value": 1}
                                                    ],
                                                    value=0,
                                                    labelStyle={
                                                        "display": "inline-block",
                                                        "marginRight": "40px",
                                                        "fontSize": "16px"
                                                    }
                                                )
                                            ]
                                        ),
                                        html.Div(
                                            style={"marginTop": "20px"},
                                            children=[
                                                html.H4("Previsualización del escenario", style={"margin": "0 0 10px 0", "fontSize": "18px"}),
                                                html.Div(
                                                    id="live-preview-panel-2",
                                                    children="Selecciona el mensaje para previsualizar los nodos.",
                                                    style={"fontSize": "16px", "lineHeight": "1.6", "background": "#f8fafc", "padding": "16px", "borderRadius": "10px", "border": "1px solid #e2e8f0"}
                                                )
                                            ]
                                        )
                                    ]
                                )
                            ]
                        )
                    ]
                ),

                # ----------------------------------------------------
                # DIAPOSITIVA 4: MEDICIONES Y SHOTS CUÁNTICOS
                # ----------------------------------------------------
                html.Div(
                    className="slide-section",
                    children=[
                        html.Div(
                            className="slide-inner app-shell",
                            children=[
                                html.H2("Capa Cuántica: Mediciones y Repeticiones (Shots)"),
                                html.P(
                                    "Configura cuántas veces mediremos el sistema cuántico para analizar las probabilidades de Hardy.",
                                    className="section-description"
                                ),
                                html.Div(
                                    className="card",
                                    style={"padding": "35px"},
                                    children=[
                                        html.H3("¿Qué son las mediciones o shots cuánticos?", style={"fontSize": "22px", "marginBottom": "12px"}),
                                        html.P(
                                            "En computación cuántica, un resultado individual es probabilístico. Por ello, necesitamos ejecutar el circuito muchas veces (lo que llamamos shots o mediciones). "
                                            "Al repetir este proceso miles de veces, obtenemos distribuciones estadísticas precisas que nos permiten comprobar si las correlaciones cuánticas cumplen con las predicciones teóricas de Hardy.",
                                            style={"fontSize": "17px", "lineHeight": "1.7", "color": "#475569", "marginBottom": "25px"}
                                        ),
                                        html.Div(
                                            className="control",
                                            style={"padding": "25px", "background": "#f8fafc", "borderRadius": "12px", "border": "1px solid #e2e8f0"},
                                            children=[
                                                html.Label(
                                                    "¿Cuántas mediciones (shots) realizaremos?",
                                                    style={"fontWeight": "700", "display": "block", "marginBottom": "12px", "fontSize": "18px"}
                                                ),
                                                dcc.Slider(
                                                    id="shots",
                                                    min=100,
                                                    max=5000,
                                                    step=100,
                                                    value=3000,
                                                    marks={
                                                        100: "100",
                                                        2500: "2,5k",
                                                        5000: "5k"
                                                    }
                                                )
                                            ]
                                        )
                                    ]
                                )
                            ]
                        )
                    ]
                ),

                # ----------------------------------------------------
                # DIAPOSITIVA 5: RED DISTRIBUIDA Y EJECUCIÓN
                # ----------------------------------------------------
                html.Div(
                    className="slide-section",
                    children=[
                        html.Div(
                            className="slide-inner app-shell",
                            children=[
                                html.H2("Red distribuida y Ejecución del Experimento"),
                                html.P(
                                    "Visualiza la red de nodos interconectados y lanza la simulación real.",
                                    className="section-description"
                                ),
                                html.Div(
                                    className="card",
                                    style={"padding": "20px"},
                                    children=[
                                        cyto.Cytoscape(
                                            id="network",
                                            elements=ELEMENTOS,
                                            stylesheet=ESTILOS,
                                            layout={
                                                "name": "preset",
                                                "fit": True,
                                                "padding": 15
                                            },
                                            style={
                                                "height": "320px",
                                                "width": "100%"
                                            },
                                            userZoomingEnabled=False,
                                            userPanningEnabled=False,
                                            boxSelectionEnabled=False
                                        ),
                                        html.Div(
                                            style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "15px", "marginTop": "15px"},
                                            children=[
                                                html.Div(
                                                    id="node-details",
                                                    children=html.P("Selecciona un nodo o canal.", style={"margin": "0", "fontSize": "16px"}),
                                                    style={
                                                        "padding": "14px",
                                                        "background": "#f8fafc",
                                                        "borderRadius": "10px",
                                                        "border": "1px solid #e2e8f0",
                                                        "minHeight": "75px"
                                                    }
                                                ),
                                                html.Div(
                                                    children=[
                                                        html.H4("Mensajes clásicos", style={"margin": "0 0 6px 0", "fontSize": "17px"}),
                                                        html.Div(
                                                            id="message-panel",
                                                            children="Ejecuta el experimento.",
                                                            style={"fontSize": "16px"}
                                                        )
                                                    ],
                                                    style={
                                                        "padding": "14px",
                                                        "background": "#f8fafc",
                                                        "borderRadius": "10px",
                                                        "border": "1px solid #e2e8f0",
                                                        "minHeight": "75px"
                                                    }
                                                )
                                            ]
                                        ),
                                        html.Div(
                                            style={"marginTop": "15px"},
                                            children=[
                                                html.Button(
                                                    "Ejecutar experimento",
                                                    id="run",
                                                    n_clicks=0,
                                                    style={
                                                        "width": "100%",
                                                        "padding": "14px",
                                                        "background": "#2563eb",
                                                        "color": "white",
                                                        "border": "none",
                                                        "borderRadius": "10px",
                                                        "fontWeight": "bold",
                                                        "fontSize": "18px",
                                                        "boxShadow": "0 4px 12px rgba(37, 99, 235, 0.3)"
                                                    }
                                                )
                                            ]
                                        )
                                    ]
                                )
                            ]
                        )
                    ]
                ),

                # ----------------------------------------------------
                # DIAPOSITIVA 6: RESULTADOS CUÁNTICOS AMPLIADOS (HARDY Y CIRCUITO)
                # ----------------------------------------------------
                html.Div(
                    className="slide-section",
                    children=[
                        html.Div(
                            className="slide-inner app-shell",
                            children=[
                                html.H2("Resultados Cuánticos: Correlaciones y Circuitos"),
                                html.P(
                                    "Análisis estadístico y representación detallada de los circuitos de Qiskit.",
                                    className="section-description"
                                ),
                                html.Div(
                                    className="layout",
                                    style={"alignItems": "stretch"},
                                    children=[
                                        html.Div(
                                            className="card",
                                            style={"padding": "22px", "display": "flex", "flexDirection": "column"},
                                            children=[
                                                html.H3("Correlaciones de Hardy", style={"fontSize": "21px", "marginBottom": "12px"}),
                                                html.Div(
                                                    id="hardy-metrics",
                                                    className="metric-row"
                                                ),
                                                dcc.Graph(
                                                    id="hardy-chart",
                                                    config={
                                                        "displayModeBar": False,
                                                        "responsive": True
                                                    },
                                                    style={"height": "230px", "flex": "1"}
                                                ),
                                                html.Div(
                                                    id="hardy-status",
                                                    className="notice",
                                                    style={"fontSize": "14px", "padding": "12px", "marginTop": "10px"},
                                                    children=(
                                                        "Ejecuta el experimento "
                                                        "para evaluar las correlaciones."
                                                    )
                                                )
                                            ]
                                        ),
                                        html.Div(
                                            className="card",
                                            style={"padding": "22px", "display": "flex", "flexDirection": "column"},
                                            children=[
                                                html.H3("Circuitos Cuánticos de Qiskit", style={"fontSize": "21px", "marginBottom": "8px"}),
                                                html.Label(
                                                    "Configuración de medición de Hardy",
                                                    style={"fontSize": "15px", "fontWeight": "600"}
                                                ),
                                                dcc.Dropdown(
                                                    id="circuit-pair",
                                                    options=[
                                                        {"label": "D - D", "value": "DD"},
                                                        {"label": "D - U", "value": "DU"},
                                                        {"label": "U - D", "value": "UD"},
                                                        {"label": "U - U", "value": "UU"}
                                                    ],
                                                    value="UU",
                                                    clearable=False,
                                                    style={"marginTop": "4px", "marginBottom": "10px", "fontSize": "15px"}
                                                ),
                                                html.Pre(
                                                    id="circuit-text",
                                                    children=(
                                                        "Ejecuta el experimento "
                                                        "para ver el circuito."
                                                    ),
                                                    style={
                                                        "whiteSpace": "pre",
                                                        "fontFamily": "monospace",
                                                        "background": "#f1f5f9",
                                                        "padding": "12px",
                                                        "borderRadius": "8px",
                                                        "fontSize": "11.5px",
                                                        "flex": "1",
                                                        "minHeight": "115px",
                                                        "overflow": "auto"
                                                    }
                                                ),
                                                html.H4(
                                                    "Intercambio de entrelazamiento",
                                                    style={"marginTop": "12px", "fontSize": "16px", "marginBottom": "6px"}
                                                ),
                                                html.Pre(
                                                    id="swap-text",
                                                    children="Esperando ejecucion...",
                                                    style={
                                                        "whiteSpace": "pre",
                                                        "fontFamily": "monospace",
                                                        "background": "#f1f5f9",
                                                        "padding": "12px",
                                                        "borderRadius": "8px",
                                                        "fontSize": "11.5px",
                                                        "flex": "1",
                                                        "minHeight": "115px",
                                                        "overflow": "auto"
                                                    }
                                                )
                                            ]
                                        )
                                    ]
                                )
                            ]
                        )
                    ]
                ),

                # ----------------------------------------------------
                # DIAPOSITIVA 7: RESULTADOS BIZANTINOS (DECISIÓN DEL ESCENARIO)
                # ----------------------------------------------------
                html.Div(
                    className="slide-section",
                    children=[
                        html.Div(
                            className="slide-inner app-shell",
                            children=[
                                html.H2("Resultados Bizantinos y Decisión del Escenario"),
                                html.P(
                                    "Evaluación del consenso, detección de contradicciones y análisis de la transmisión clásica.",
                                    className="section-description"
                                ),
                                html.Div(
                                    className="card",
                                    style={"padding": "35px"},
                                    children=[
                                        html.H3("Decisión del escenario", style={"fontSize": "26px", "marginBottom": "20px"}),
                                        html.Div(
                                            id="protocol-status",
                                            className="notice",
                                            style={"fontSize": "18px", "padding": "22px"},
                                            children=(
                                                "Ejecuta el experimento para "
                                                "evaluar la transmisión."
                                            )
                                        ),
                                        html.P(
                                            "Límite científico: este prototipo "
                                            "no reproduce todavía el protocolo "
                                            "completo del artículo. La "
                                            "contradicción se detecta comparando "
                                            "mensajes clásicos; Hardy no "
                                            "identifica automáticamente al "
                                            "responsable.",
                                            style={
                                                "fontSize": "16px",
                                                "color": "#64748b",
                                                "lineHeight": "1.7",
                                                "marginTop": "20px"
                                            }
                                        )
                                    ]
                                )
                            ]
                        )
                    ]
                )
            ]
        )
    ]
)


# ============================================================
# 7. NAVEGACIÓN Y BLOQUEO DEL BOTÓN DE AVANCE HASTA EJECUTAR
# ============================================================

@app.callback(
    Output("deck-container", "style"),
    Output("slide-index", "data"),
    Output("experiment-run-store", "data"),
    Output("btn-prev", "disabled"),
    Output("btn-next", "disabled"),
    Output("slide-counter", "children"),
    Input("btn-prev", "n_clicks"),
    Input("btn-next", "n_clicks"),
    Input("run", "n_clicks"),
    State("slide-index", "data"),
    State("experiment-run-store", "data"),
    prevent_initial_call=True
)
def navegar_deck(n_prev, n_next, n_run, current_slide, experiment_run):
    if current_slide is None:
        current_slide = 0
    if experiment_run is None:
        experiment_run = False

    triggered = ctx.triggered_id

    if triggered == "btn-next":
        if current_slide == 4 and not experiment_run:
            pass
        else:
            current_slide = min(current_slide + 1, 6)
    elif triggered == "btn-prev":
        current_slide = max(current_slide - 1, 0)
    elif triggered == "run":
        experiment_run = True
        current_slide = 5

    estilo = {
        "transform": f"translateX(-{current_slide * 100}vw)"
    }

    prev_disabled = (current_slide == 0)
    next_disabled = (current_slide == 6) or (current_slide == 4 and not experiment_run)

    return (
        estilo,
        current_slide,
        experiment_run,
        prev_disabled,
        next_disabled,
        f"{current_slide + 1:02d} / 07"
    )


# ============================================================
# 8. PREVISUALIZACIÓN DINÁMICA DE LA CONFIGURACIÓN CLÁSICA
# ============================================================

@app.callback(
    Output("live-preview-panel-1", "children"),
    Output("live-preview-panel-2", "children"),
    Input("modo-c", "value"),
    Input("bit-c", "value")
)
def actualizar_previsualizacion_clasica(modo, bit_c):
    mensajes = simular_mensajes(bit_c, modo)
    bit_a = mensajes["bit_a"]
    bit_b = mensajes["bit_b"]

    if mensajes["contradiccion"]:
        contenido = [
            html.Div(
                "Escenario de engaño (Bizantino activo)",
                style={"color": "#dc2626", "fontWeight": "bold", "marginBottom": "8px", "fontSize": "17px"}
            ),
            html.P(f"- Comandante C envía el mensaje original: {bit_c}", style={"margin": "4px 0", "fontSize": "15px"}),
            html.P(f"- Participante A recibe: {bit_a}", style={"margin": "4px 0", "color": "#1e293b", "fontSize": "15px"}),
            html.P(f"- Participante B recibe: {bit_b} (Contradictorio)", style={"margin": "4px 0", "color": "#dc2626", "fontWeight": "600", "fontSize": "15px"})
        ]
    else:
        contenido = [
            html.Div(
                "Escenario consistente (Honesto)",
                style={"color": "#166534", "fontWeight": "bold", "marginBottom": "8px", "fontSize": "17px"}
            ),
            html.P(f"- Comandante C envía el mensaje original: {bit_c}", style={"margin": "4px 0", "fontSize": "15px"}),
            html.P(f"- Participante A recibe: {bit_a}", style={"margin": "4px 0", "color": "#166534", "fontSize": "15px"}),
            html.P(f"- Participante B recibe: {bit_b} (Coherente)", style={"margin": "4px 0", "color": "#166534", "fontSize": "15px"})
        ]

    return contenido, contenido


# ============================================================
# 9. INTERACCIÓN DE LA RED
# ============================================================

@app.callback(
    Output("node-details", "children"),
    Output("network", "elements"),
    Input("network", "tapNodeData"),
    Input("network", "tapEdgeData")
)
def seleccionar_elemento(nodo, arista):
    seleccionado = arista or nodo
    elementos = []

    for original in ELEMENTOS:
        elemento = {
            "data": dict(original["data"]),
            "classes": original.get("classes", "")
        }

        if "position" in original:
            elemento["position"] = dict(original["position"])

        if seleccionado:
            sid = seleccionado.get("id")

            if elemento["data"]["id"] == sid:
                if "source" in elemento["data"]:
                    elemento["classes"] += " selected-edge"
                else:
                    elemento["classes"] += " selected-node"
            else:
                elemento["classes"] += " dimmed"

        elementos.append(elemento)

    if not seleccionado:
        panel = html.P("Selecciona un nodo o canal.", style={"margin": "0", "fontSize": "15px"})
    else:
        if "source" in seleccionado:
            titulo = (
                f"Canal {seleccionado['source']} "
                f"-> {seleccionado['target']}"
            )
        else:
            titulo = f"Nodo {seleccionado.get('label', '')}"

        panel = html.Div([
            html.H4(titulo, style={"margin": "0 0 4px 0", "fontSize": "16px"}),
            html.P(seleccionado.get("description", ""), style={"margin": "0", "fontSize": "14px"})
        ])

    return panel, elementos


# ============================================================
# 10. EJECUCIÓN DEL EXPERIMENTO
# ============================================================

@app.callback(
    Output("circuit-text", "children"),
    Output("swap-text", "children"),
    Output("hardy-metrics", "children"),
    Output("hardy-chart", "figure"),
    Output("hardy-status", "children"),
    Output("hardy-status", "className"),
    Output("message-panel", "children"),
    Output("protocol-status", "children"),
    Output("protocol-status", "className"),
    Input("run", "n_clicks"),
    State("shots", "value"),
    State("modo-c", "value"),
    State("bit-c", "value"),
    State("circuit-pair", "value"),
    prevent_initial_call=True
)
def ejecutar_protocolo(
    n_clicks,
    shots,
    modo,
    bit_c,
    par_seleccionado
):
    shots = int(shots)

    # A. Mediciones de Hardy
    pruebas, circuitos = evaluar_condiciones_hardy(shots)

    circuito = circuitos[par_seleccionado]
    texto_circuito = circuito.draw(
        output="text",
        fold=-1
    ).single_string()

    # B. Intercambio de entrelazamiento auxiliar
    circuito_swap, counts_swap = ejecutar_intercambio(shots)

    texto_swap = (
        circuito_swap.draw(
            output="text",
            fold=-1
        ).single_string()
        + "\n\nResultados de la medición de Bell:\n"
        + str(counts_swap)
        + "\n\nCircuito auxiliar: no implementa el proyector "
        "M específico del artículo."
    )

    # C. Métricas
    metricas = []

    for prueba in pruebas:
        metricas.append(
            tarjeta(
                prueba["nombre"],
                f"{prueba['probabilidad']:.3%}",
                f"{prueba['frecuencia']} de {prueba['shots']}"
            )
        )

    metricas.append(
        tarjeta(
            "q max teorico",
            f"{Q_MAX:.3%}",
            "Ideal Hardy"
        )
    )

    figura = crear_figura_hardy(pruebas)
    validacion = evaluar_hardy_estadistico(pruebas, shots)

    if validacion["valido"]:
        estado_hardy = (
            "Compatible con el criterio exploratorio de Hardy.\n"
            "Las tres primeras frecuencias son suficientemente pequeñas "
            "según el umbral utilizado y la última es positiva."
        )
        clase_hardy = "notice notice-ok"
    else:
        estado_hardy = (
            "Las frecuencias no cumplen el criterio exploratorio de Hardy. "
            "Esto no equivale por sí solo a una prueba formal del protocolo."
        )
        clase_hardy = "notice notice-warn"

    # D. Mensajes clásicos
    mensajes = simular_mensajes(bit_c, modo)
    bit_a = mensajes["bit_a"]
    bit_b = mensajes["bit_b"]

    if mensajes["contradiccion"]:
        estado_mensaje = html.Div(
            [
                html.H4(
                    "Contradicción clásica introducida",
                    style={"color": "#b91c1c", "margin": "0 0 4px 0", "fontSize": "15px"}
                ),
                html.P(f"C -> A: bit {bit_a}", style={"margin": "2px 0", "fontSize": "14px"}),
                html.P(f"C -> B: bit {bit_b}", style={"margin": "2px 0", "fontSize": "14px"}),
                html.P(
                    "A y B reciben valores distintos.",
                    style={"margin": "2px 0", "fontSize": "14px"}
                )
            ]
        )
    else:
        estado_mensaje = html.Div(
            [
                html.H4(
                    "Mensajes clásicos consistentes",
                    style={"color": "#166534", "margin": "0 0 4px 0", "fontSize": "15px"}
                ),
                html.P(f"C -> A: bit {bit_a}", style={"margin": "2px 0", "fontSize": "14px"}),
                html.P(f"C -> B: bit {bit_b}", style={"margin": "2px 0", "fontSize": "14px"}),
                html.P("Ambos reciben el mismo bit.", style={"margin": "2px 0", "fontSize": "14px"})
            ]
        )

    # E. Decisión exploratoria
    decision = decidir_protocolo(pruebas, mensajes, shots)

    panel_decision = html.Div([
        html.H3(decision["titulo"], style={"fontSize": "20px"}),
        html.P(decision["detalle"], style={"fontSize": "16px"}),
        html.Hr(),
        html.P(
            "Validación estadística de Hardy: "
            + ("compatible" if decision["hardy_valido"] else "no validada"),
            style={"fontSize": "16px"}
        ),
        html.P(
            "Consenso en el escenario: "
            + ("si" if decision["consenso"] else "no"),
            style={"fontSize": "16px"}
        ),
        html.P(
            f"Bit recibido por A: {bit_a}; bit recibido por B: {bit_b}.",
            style={"fontSize": "16px"}
        )
    ])

    return (
        texto_circuito,
        texto_swap,
        metricas,
        figura,
        estado_hardy,
        clase_hardy,
        estado_mensaje,
        panel_decision,
        decision["clase"]
    )


if __name__ == "__main__":
    app.run(debug=True)