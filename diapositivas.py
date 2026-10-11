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
# 5. APLICACIÓN Y ESTILOS DEL DECK (6 DIAPOSITIVAS TOTALES)
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
    font-size: 18px;
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
    width: 600vw;
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
    padding: 40px 60px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.slide-inner {
    width: 100%;
    max-width: 1400px;
    margin: auto;
}

.cover-content {
    text-align: center;
    max-width: 1100px;
}

.cover-title {
    font-size: clamp(40px, 6vw, 84px);
    font-weight: 800;
    letter-spacing: 4px;
    margin: 0 0 20px 0;
}

.cover-subtitle {
    color: #64748b;
    font-size: clamp(20px, 2.5vw, 28px);
    line-height: 1.7;
}

.cover-kicker {
    font-size: 15px;
    letter-spacing: 4px;
    text-transform: uppercase;
    color: #64748b;
    margin-bottom: 25px;
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
    max-width: 1400px;
    margin: 0 auto;
}

.card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 28px;
    margin-bottom: 20px;
    box-shadow: 0 6px 16px rgba(15,23,42,.06);
    width: 100%;
}

h2 {
    font-size: 36px;
    margin-top: 0;
    margin-bottom: 10px;
    font-weight: 800;
}

h3 {
    font-size: 26px;
    margin-top: 0;
    margin-bottom: 12px;
    font-weight: 700;
}

h4 {
    font-size: 22px;
    margin-top: 0;
    margin-bottom: 10px;
    font-weight: 700;
}

.layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
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
    padding: 22px;
    border-radius: 12px;
    min-width: 0;
    font-size: 18px;
}

.metric-row {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
}

.metric {
    padding: 18px;
    background: #f1f5f9;
    border-radius: 12px;
    overflow-wrap: anywhere;
    font-size: 17px;
}

.metric-value {
    font-size: 30px;
    font-weight: 800;
    margin: 6px 0;
}

.notice {
    padding: 18px;
    border-radius: 12px;
    background: #eff6ff;
    color: #1e40af;
    margin-top: 16px;
    line-height: 1.65;
    font-size: 17px;
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
    line-height: 1.6;
    margin-bottom: 24px;
    font-size: 20px;
}

button {
    cursor: pointer;
    font-size: 18px;
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
            html.Div(titulo, style={"fontSize": "16px"}),
            html.Div(valor, className="metric-value"),
            html.Small(descripcion, style={"fontSize": "14px"})
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
        textfont={"size": 15},
        hovertemplate=(
            "%{x}<br>Probabilidad: %{y:.4%}<extra></extra>"
        )
    ))

    maximo = max(valores) if valores else 0.0

    figura.update_layout(
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin={"l": 55, "r": 25, "t": 40, "b": 65},
        yaxis_title="Probabilidad observada",
        xaxis_title="Condición de Hardy",
        yaxis_range=[0, max(0.12, maximo * 1.4)],
        font={"family": "Manrope, sans-serif", "size": 15},
        showlegend=False,
        autosize=True
    )

    figura.update_yaxes(tickformat=".0%", gridcolor="#e2e8f0", title_font={"size": 16})
    figura.update_xaxes(title_font={"size": 16})
    return figura


# ============================================================
# 6. LAYOUT: 6 DIAPOSITIVAS EN TOTAL
# ============================================================

app.layout = html.Div(
    className="deck-viewport",
    children=[
        dcc.Store(id="slide-index", data=0),

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
            children="01 / 06"
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
                                    "SIMULACION CUANTICA · SISTEMAS DISTRIBUIDOS",
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
                                    "Explora una red de tres nodos, "
                                    "desafia la comunicacion con mensajes contradictorios "
                                    "y examina las correlaciones de Hardy en busca de condiciones que permitan verificar la consistencia del sistema.",
                                    style={
                                        "maxWidth": "800px",
                                        "margin": "30px auto",
                                        "lineHeight": "1.8",
                                        "color": "#475569",
                                        "fontSize": "21px"
                                    }
                                ),
                                html.P(
                                    "Usa la flecha derecha para comenzar.",
                                    style={
                                        "marginTop": "50px",
                                        "color": "#64748b",
                                        "fontSize": "17px"
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
                                    "Define si el nodo C enviara mensajes consistentes o si intentara enganar a la red.",
                                    className="section-description"
                                ),
                                html.Div(
                                    className="card",
                                    style={"padding": "35px"},
                                    children=[
                                        html.Div(
                                            className="control",
                                            style={"fontSize": "20px", "padding": "25px"},
                                            children=[
                                                html.Label(
                                                    "¿C dira la verdad o enviara mensajes contradictorios?",
                                                    style={"fontWeight": "700", "display": "block", "marginBottom": "16px", "fontSize": "22px"}
                                                ),
                                                dcc.RadioItems(
                                                    id="modo-c",
                                                    options=[
                                                        {
                                                            "label": " C se comporta correctamente (envia el mismo mensaje)",
                                                            "value": "honesto"
                                                        },
                                                        {
                                                            "label": " C intenta enganar (envia mensajes contradictorios)",
                                                            "value": "bizantino"
                                                        }
                                                    ],
                                                    value="honesto",
                                                    labelStyle={
                                                        "display": "block",
                                                        "marginTop": "16px",
                                                        "fontSize": "18px"
                                                    }
                                                )
                                            ]
                                        ),
                                        html.Div(
                                            style={"marginTop": "25px"},
                                            children=[
                                                html.H4("Previsualizacion del escenario", style={"margin": "0 0 12px 0", "fontSize": "20px"}),
                                                html.Div(
                                                    id="live-preview-panel-1",
                                                    children="Selecciona el comportamiento para previsualizar los nodos.",
                                                    style={"fontSize": "17px", "lineHeight": "1.7", "background": "#f8fafc", "padding": "20px", "borderRadius": "12px", "border": "1px solid #e2e8f0"}
                                                )
                                            ]
                                        ),
                                        html.Div(
                                            className="notice",
                                            style={"marginTop": "25px", "fontSize": "18px", "padding": "22px"},
                                            children=(
                                                "Capa clasica: Gestiona los mensajes enviados por los nodos y permite la deteccion directa de contradicciones."
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
                                    style={"padding": "35px"},
                                    children=[
                                        html.Div(
                                            className="control",
                                            style={"fontSize": "20px", "padding": "25px"},
                                            children=[
                                                html.Label(
                                                    "¿Que mensaje quiere comunicar C?",
                                                    style={"fontWeight": "700", "display": "block", "marginBottom": "16px", "fontSize": "22px"}
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
                                                        "fontSize": "18px"
                                                    }
                                                )
                                            ]
                                        ),
                                        html.Div(
                                            style={"marginTop": "25px"},
                                            children=[
                                                html.H4("Previsualizacion del escenario", style={"margin": "0 0 12px 0", "fontSize": "20px"}),
                                                html.Div(
                                                    id="live-preview-panel-2",
                                                    children="Selecciona el mensaje para previsualizar los nodos.",
                                                    style={"fontSize": "17px", "lineHeight": "1.7", "background": "#f8fafc", "padding": "20px", "borderRadius": "12px", "border": "1px solid #e2e8f0"}
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
                # DIAPOSITIVA 4: RED DISTRIBUIDA (CON CONTROLES Y BOTÓN DE EJECUCIÓN)
                # ----------------------------------------------------
                html.Div(
                    className="slide-section",
                    children=[
                        html.Div(
                            className="slide-inner app-shell",
                            children=[
                                html.H2("Red distribuida y Ejecución"),
                                html.P(
                                    "Visualiza la red, configura las mediciones y ejecuta el experimento.",
                                    className="section-description"
                                ),
                                html.Div(
                                    className="card",
                                    style={"padding": "25px"},
                                    children=[
                                        cyto.Cytoscape(
                                            id="network",
                                            elements=ELEMENTOS,
                                            stylesheet=ESTILOS,
                                            layout={
                                                "name": "preset",
                                                "fit": True,
                                                "padding": 20
                                            },
                                            style={
                                                "height": "340px",
                                                "width": "100%"
                                            },
                                            userZoomingEnabled=False,
                                            userPanningEnabled=False,
                                            boxSelectionEnabled=False
                                        ),
                                        html.Div(
                                            style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "20px", "marginTop": "20px"},
                                            children=[
                                                html.Div(
                                                    id="node-details",
                                                    children=html.P("Selecciona un nodo o canal.", style={"margin": "0", "fontSize": "17px"}),
                                                    style={
                                                        "padding": "18px",
                                                        "background": "#f8fafc",
                                                        "borderRadius": "12px",
                                                        "border": "1px solid #e2e8f0",
                                                        "minHeight": "90px"
                                                    }
                                                ),
                                                html.Div(
                                                    children=[
                                                        html.H4("Mensajes clasicos", style={"margin": "0 0 8px 0", "fontSize": "19px"}),
                                                        html.Div(
                                                            id="message-panel",
                                                            children="Ejecuta el experimento.",
                                                            style={"fontSize": "17px"}
                                                        )
                                                    ],
                                                    style={
                                                        "padding": "18px",
                                                        "background": "#f8fafc",
                                                        "borderRadius": "12px",
                                                        "border": "1px solid #e2e8f0",
                                                        "minHeight": "90px"
                                                    }
                                                )
                                            ]
                                        ),
                                        html.Div(
                                            style={"marginTop": "20px", "padding": "20px", "background": "#f8fafc", "borderRadius": "12px", "border": "1px solid #e2e8f0"},
                                            children=[
                                                html.Label(
                                                    "¿Cuantas mediciones realizaremos?",
                                                    style={"fontWeight": "700", "display": "block", "marginBottom": "10px", "fontSize": "18px"}
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
                                                    },
                                                    tooltip={
                                                        "placement": "bottom",
                                                        "always_visible": True
                                                    }
                                                ),
                                                html.Button(
                                                    "Ejecutar experimento",
                                                    id="run",
                                                    n_clicks=0,
                                                    style={
                                                        "width": "100%",
                                                        "marginTop": "20px",
                                                        "padding": "16px",
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
                # DIAPOSITIVA 5: RESULTADOS 1 (CORRELACIONES DE HARDY Y CIRCUITOS)
                # ----------------------------------------------------
                html.Div(
                    className="slide-section",
                    children=[
                        html.Div(
                            className="slide-inner app-shell",
                            children=[
                                html.H2("Resultados: Correlaciones de Hardy y Circuitos"),
                                html.P(
                                    "Análisis estadístico de las frecuencias cuánticas y representación de los circuitos.",
                                    className="section-description"
                                ),
                                html.Div(
                                    className="layout",
                                    children=[
                                        html.Div(
                                            className="card",
                                            style={"padding": "30px"},
                                            children=[
                                                html.H3("Correlaciones de Hardy", style={"fontSize": "24px"}),
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
                                                    style={"height": "320px"}
                                                ),
                                                html.Div(
                                                    id="hardy-status",
                                                    className="notice",
                                                    style={"fontSize": "17px", "padding": "20px"},
                                                    children=(
                                                        "Ejecuta el experimento "
                                                        "para evaluar las correlaciones."
                                                    )
                                                )
                                            ]
                                        ),
                                        html.Div(
                                            className="card",
                                            style={"padding": "30px"},
                                            children=[
                                                html.H3("Circuito de Hardy", style={"fontSize": "24px"}),
                                                html.Label(
                                                    "Configuracion de medicion",
                                                    style={"fontSize": "18px", "fontWeight": "600"}
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
                                                    style={"marginTop": "8px", "marginBottom": "15px", "fontSize": "17px"}
                                                ),
                                                html.Pre(
                                                    id="circuit-text",
                                                    children=(
                                                        "Ejecuta el experimento "
                                                        "para ver el circuito."
                                                    ),
                                                    style={
                                                        "whiteSpace": "pre-wrap",
                                                        "background": "#f1f5f9",
                                                        "padding": "15px",
                                                        "borderRadius": "10px",
                                                        "fontSize": "13px",
                                                        "maxHeight": "170px",
                                                        "overflow": "auto"
                                                    }
                                                ),
                                                html.H4(
                                                    "Intercambio de entrelazamiento",
                                                    style={"marginTop": "18px", "fontSize": "20px"}
                                                ),
                                                html.Pre(
                                                    id="swap-text",
                                                    children="Esperando ejecucion...",
                                                    style={
                                                        "whiteSpace": "pre-wrap",
                                                        "background": "#f1f5f9",
                                                        "padding": "15px",
                                                        "borderRadius": "10px",
                                                        "fontSize": "13px",
                                                        "maxHeight": "150px",
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
                # DIAPOSITIVA 6: RESULTADOS 2 (DECISIÓN BIZANTINA Y EVALUACIÓN)
                # ----------------------------------------------------
                html.Div(
                    className="slide-section",
                    children=[
                        html.Div(
                            className="slide-inner app-shell",
                            children=[
                                html.H2("Resultados: Evaluación y Decisión del Escenario"),
                                html.P(
                                    "Verificación de consistencia clásica y validación final del protocolo bizantino.",
                                    className="section-description"
                                ),
                                html.Div(
                                    className="card",
                                    style={"padding": "40px"},
                                    children=[
                                        html.H3("Decision del escenario", style={"fontSize": "26px", "marginBottom": "20px"}),
                                        html.Div(
                                            id="protocol-status",
                                            className="notice",
                                            style={"fontSize": "19px", "padding": "25px"},
                                            children=(
                                                "Ejecuta el experimento para "
                                                "evaluar la transmision."
                                            )
                                        ),
                                        html.P(
                                            "Limite cientifico: este prototipo "
                                            "no reproduce todavia el protocolo "
                                            "completo del articulo. La "
                                            "contradiccion se detecta comparando "
                                            "mensajes clasicos; Hardy no "
                                            "identifica automaticamente al "
                                            "responsable.",
                                            style={
                                                "fontSize": "17px",
                                                "color": "#64748b",
                                                "lineHeight": "1.8",
                                                "marginTop": "25px"
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
# 7. NAVEGACIÓN Y AVANCE AUTOMÁTICO AL EJECUTAR
# ============================================================

@app.callback(
    Output("deck-container", "style"),
    Output("slide-index", "data"),
    Output("btn-prev", "disabled"),
    Output("btn-next", "disabled"),
    Output("slide-counter", "children"),
    Input("btn-prev", "n_clicks"),
    Input("btn-next", "n_clicks"),
    Input("run", "n_clicks"),
    State("slide-index", "data"),
    prevent_initial_call=True
)
def navegar_deck(n_prev, n_next, n_run, current_slide):
    if current_slide is None:
        current_slide = 0

    triggered = ctx.triggered_id

    if triggered == "btn-next":
        current_slide = min(current_slide + 1, 5)
    elif triggered == "btn-prev":
        current_slide = max(current_slide - 1, 0)
    elif triggered == "run":
        # Al ejecutar el experimento, avanza automáticamente a la primera diapositiva de resultados (índice 4)
        current_slide = 4

    estilo = {
        "transform": f"translateX(-{current_slide * 100}vw)"
    }

    return (
        estilo,
        current_slide,
        current_slide == 0,
        current_slide == 5,
        f"{current_slide + 1:02d} / 06"
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
                "Escenario de engano (Bizantino activo)",
                style={"color": "#dc2626", "fontWeight": "bold", "marginBottom": "10px", "fontSize": "19px"}
            ),
            html.P(f"- Comandante C envia el mensaje original: {bit_c}", style={"margin": "6px 0", "fontSize": "17px"}),
            html.P(f"- Participante A recibe: {bit_a}", style={"margin": "6px 0", "color": "#1e293b", "fontSize": "17px"}),
            html.P(f"- Participante B recibe: {bit_b} (Contradictorio)", style={"margin": "6px 0", "color": "#dc2626", "fontWeight": "600", "fontSize": "17px"})
        ]
    else:
        contenido = [
            html.Div(
                "Escenario consistente (Honesto)",
                style={"color": "#166534", "fontWeight": "bold", "marginBottom": "10px", "fontSize": "19px"}
            ),
            html.P(f"- Comandante C envia el mensaje original: {bit_c}", style={"margin": "6px 0", "fontSize": "17px"}),
            html.P(f"- Participante A recibe: {bit_a}", style={"margin": "6px 0", "color": "#166534", "fontSize": "17px"}),
            html.P(f"- Participante B recibe: {bit_b} (Coherente)", style={"margin": "6px 0", "color": "#166534", "fontSize": "17px"})
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
        panel = html.P("Selecciona un nodo o canal.", style={"margin": "0", "fontSize": "17px"})
    else:
        if "source" in seleccionado:
            titulo = (
                f"Canal {seleccionado['source']} "
                f"-> {seleccionado['target']}"
            )
        else:
            titulo = f"Nodo {seleccionado.get('label', '')}"

        panel = html.Div([
            html.H4(titulo, style={"margin": "0 0 6px 0", "fontSize": "18px"}),
            html.P(seleccionado.get("description", ""), style={"margin": "0", "fontSize": "16px"})
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
        + "\n\nResultados de la medicion de Bell:\n"
        + str(counts_swap)
        + "\n\nCircuito auxiliar: no implementa el proyector "
        "M especifico del articulo."
    )

    # C. Métricas
    metricas = []

    for prueba in pruebas:
        metricas.append(
            tarjeta(
                prueba["nombre"],
                f"{prueba['probabilidad']:.3%}",
                f"{prueba['frecuencia']} de {prueba['shots']} resultados"
            )
        )

    metricas.append(
        tarjeta(
            "q maximo teorico",
            f"{Q_MAX:.3%}",
            "Valor ideal asociado al estado de Hardy"
        )
    )

    figura = crear_figura_hardy(pruebas)
    validacion = evaluar_hardy_estadistico(pruebas, shots)

    if validacion["valido"]:
        estado_hardy = (
            "Compatible con el criterio exploratorio de Hardy.\n"
            "Las tres primeras frecuencias son suficientemente pequenas "
            "segun el umbral utilizado y la ultima es positiva."
        )
        clase_hardy = "notice notice-ok"
    else:
        estado_hardy = (
            "Las frecuencias no cumplen el criterio exploratorio de Hardy. "
            "Esto no equivale por si solo a una prueba formal del protocolo."
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
                    "Contradiccion clasica introducida",
                    style={"color": "#b91c1c", "margin": "0 0 6px 0", "fontSize": "17px"}
                ),
                html.P(f"C -> A: bit {bit_a}", style={"margin": "4px 0", "fontSize": "16px"}),
                html.P(f"C -> B: bit {bit_b}", style={"margin": "4px 0", "fontSize": "16px"}),
                html.P(
                    "A y B reciben valores distintos.",
                    style={"margin": "4px 0", "fontSize": "16px"}
                )
            ]
        )
    else:
        estado_mensaje = html.Div(
            [
                html.H4(
                    "Mensajes clasicos consistentes",
                    style={"color": "#166534", "margin": "0 0 6px 0", "fontSize": "17px"}
                ),
                html.P(f"C -> A: bit {bit_a}", style={"margin": "4px 0", "fontSize": "16px"}),
                html.P(f"C -> B: bit {bit_b}", style={"margin": "4px 0", "fontSize": "16px"}),
                html.P("Ambos reciben el mismo bit.", style={"margin": "4px 0", "fontSize": "16px"})
            ]
        )

    # E. Decisión exploratoria
    decision = decidir_protocolo(pruebas, mensajes, shots)

    panel_decision = html.Div([
        html.H3(decision["titulo"], style={"fontSize": "22px"}),
        html.P(decision["detalle"], style={"fontSize": "17px"}),
        html.Hr(),
        html.P(
            "Validacion estadistica de Hardy: "
            + ("compatible" if decision["hardy_valido"] else "no validada"),
            style={"fontSize": "17px"}
        ),
        html.P(
            "Consenso en el escenario: "
            + ("si" if decision["consenso"] else "no"),
            style={"fontSize": "17px"}
        ),
        html.P(
            f"Bit recibido por A: {bit_a}; bit recibido por B: {bit_b}.",
            style={"fontSize": "17px"}
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