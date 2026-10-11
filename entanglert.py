import numpy as np
from dash import Dash, html, dcc, Input, Output, State
import dash_cytoscape as cyto
import plotly.graph_objects as go

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator


# ============================================================
# 1. ESTADO DE HARDY Y MEDICIONES
# ============================================================
# Convencion:
# U: base computacional.
#    |0> representa +1 y |1> representa -1.
#
# D: base alternativa de medicion.
#
# IMPORTANTE:
# Los ceros de Hardy son propiedades matematicas del estado
# ideal y de las mediciones. Los conteos de una simulacion
# finita son estimaciones estadisticas.
# ============================================================

alpha = np.sqrt((np.sqrt(5) - 1) / 2)
beta = np.sqrt(1 - alpha**2)

estado_sin_normalizar = np.array(
    [
        1,
        -alpha / beta,
        -alpha / beta,
        -(1 + alpha**2) / alpha**2
    ],
    dtype=complex
)

ESTADO_HARDY = (
    estado_sin_normalizar
    / np.linalg.norm(estado_sin_normalizar)
)

Q_MAX = (5 * np.sqrt(5) - 11) / 2

# Los vectores columna definen la base D.
# La matriz es real, simetrica y ortogonal.
BASE_D = np.array(
    [
        [alpha, beta],
        [beta, -alpha]
    ],
    dtype=complex
)


def construir_circuito_hardy(base1, base2):
    """Construye el circuito para una pareja de mediciones."""

    if base1 not in ("D", "U") or base2 not in ("D", "U"):
        raise ValueError("Las bases deben ser D o U.")

    qc = QuantumCircuit(2, 2)

    # Preparar el estado de Hardy.
    qc.initialize(ESTADO_HARDY, [0, 1])

    # Cambiar de base antes de medir cuando corresponde.
    if base1 == "D":
        qc.unitary(BASE_D, [0], label="Base D")

    if base2 == "D":
        qc.unitary(BASE_D, [1], label="Base D")

    qc.measure([0, 1], [0, 1])

    return qc


def ejecutar_circuito(qc, shots, seed=42):
    """Ejecuta un circuito en el simulador de Qiskit Aer."""

    simulador = AerSimulator()

    compilado = transpile(
        qc,
        simulador,
        seed_transpiler=seed
    )

    resultado = simulador.run(
        compilado,
        shots=int(shots),
        seed_simulator=seed
    ).result()

    return resultado.get_counts()


def normalizar_counts(counts):
    """Normaliza las cadenas de bits devueltas por Qiskit."""

    normalizados = {}

    for bits, cantidad in counts.items():
        clave = bits.replace(" ", "").zfill(2)
        normalizados[clave] = (
            normalizados.get(clave, 0) + cantidad
        )

    return normalizados


def probabilidad(counts, patron):
    counts = normalizar_counts(counts)
    total = sum(counts.values())

    if total == 0:
        return 0.0

    return counts.get(patron, 0) / total


def evaluar_condiciones_hardy(shots):
    """
    Ejecuta cuatro experimentos independientes.

    DD: P(-- | D,D) debe ser cero.
    DU: P(++ | D,U) debe ser cero.
    UD: P(++ | U,D) debe ser cero.
    UU: P(++ | U,U) debe ser positiva.
    """

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

        counts = ejecutar_circuito(
            circuito,
            shots,
            seed=42 + i
        )

        counts = normalizar_counts(counts)

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
# Prepara dos pares de Bell y mide los qubits centrales.
#
# Este circuito ilustra el concepto general de intercambio
# de entrelazamiento. NO implementa el proyector M especifico
# que utiliza el articulo para preparar el estado de Hardy.
# ============================================================

def circuito_intercambio():
    qc = QuantumCircuit(4, 2)

    # Primer par de Bell: qubits 0 y 1.
    qc.h(0)
    qc.cx(0, 1)

    # Segundo par de Bell: qubits 2 y 3.
    qc.h(2)
    qc.cx(2, 3)

    # Medicion de Bell sobre los qubits centrales 1 y 2.
    qc.cx(1, 2)
    qc.h(1)

    qc.measure([1, 2], [0, 1])

    return qc


def ejecutar_intercambio(shots):
    circuito = circuito_intercambio()

    counts = ejecutar_circuito(
        circuito,
        shots,
        seed=77
    )

    return circuito, normalizar_counts(counts)


# ============================================================
# 3. MODELO CLASICO DEL COMANDANTE Y CODIFICACION
# ============================================================
# U codifica el bit 0 y D codifica el bit 1 en esta interfaz.
# El modo bizantino introduce una contradiccion controlada en
# los mensajes clasicos recibidos por A y B.
#
# Las mediciones de Hardy se conectan con la decision como una
# comprobacion estadistica de compatibilidad. NO se afirma que
# una medicion aislada identifique automaticamente a C.
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
    """
    Criterio exploratorio para la interfaz, no una certificacion
    device-independent ni una prueba formal de seguridad.
    """
    limite_cero = max(0.01, 5 / int(shots))
    tres_condiciones_cero = all(
        p["probabilidad"] <= limite_cero for p in pruebas[:3]
    )
    condicion_positiva = pruebas[3]["probabilidad"] > limite_cero
    return {
        "valido": tres_condiciones_cero and condicion_positiva,
        "limite": limite_cero,
        "tres_ceros_compatibles": tres_condiciones_cero,
        "positiva_observada": condicion_positiva,
    }


def decidir_protocolo(pruebas, mensajes, shots):
    """
    Une las dos capas del prototipo:
      1) validacion estadistica de las condiciones de Hardy;
      2) comparacion de los mensajes que A y B reciben.

    La contradiccion se conoce porque el escenario clasico la
    genera y A/B comparan sus mensajes. Hardy no atribuye por si
    solo la contradiccion a un participante concreto.
    """
    hardy = evaluar_hardy_estadistico(pruebas, shots)

    if not hardy["valido"]:
        return {
            "titulo": "TRANSMISION NO VALIDADA",
            "clase": "notice notice-warn",
            "detalle": (
                "Las frecuencias observadas no cumplen el criterio "
                "exploratorio de Hardy. El prototipo no acepta la "
                "transmision como validada y no concluye quien es "
                "bizantino."
            ),
            "consenso": False,
            "hardy_valido": False,
        }

    if mensajes["contradiccion"]:
        return {
            "titulo": "INCONSISTENCIA ENTRE MENSAJES",
            "clase": "notice notice-warn",
            "detalle": (
                f"A recibe el bit {mensajes['bit_a']} y B recibe el bit "
                f"{mensajes['bit_b']}. Las estadisticas de Hardy pasan "
                "el criterio exploratorio, pero los mensajes no coinciden. "
                "La inconsistencia se detecta al comparar los mensajes "
                "clasicos; esto no demuestra por si solo que Hardy haya "
                "identificado a C como el responsable."
            ),
            "consenso": False,
            "hardy_valido": True,
        }

    return {
        "titulo": "CONSENSO SIMULADO",
        "clase": "notice notice-ok",
        "detalle": (
            f"A y B reciben el mismo bit ({mensajes['bit_a']}) y las "
            "estadisticas de Hardy pasan el criterio exploratorio. "
            "El escenario didactico acepta el mensaje y registra consenso."
        ),
        "consenso": True,
        "hardy_valido": True,
    }


# ============================================================
# 4. RED INTERACTIVA
# ============================================================

ELEMENTOS = [
    {
        "data": {
            "id": "A",
            "label": "A",
            "description": (
                "Participante A. En este prototipo visualiza "
                "el mensaje recibido de C y participa en la "
                "representacion de la red distribuida."
            )
        },
        "position": {"x": 130, "y": 190},
        "classes": "participant"
    },
    {
        "data": {
            "id": "B",
            "label": "B",
            "description": (
                "Participante B. Recibe el mensaje de C. "
                "El panel clasico permite comprobar si el "
                "mensaje recibido coincide con el de A."
            )
        },
        "position": {"x": 390, "y": 190},
        "classes": "participant"
    },
    {
        "data": {
            "id": "C",
            "label": "C",
            "description": (
                "General comandante C. En el escenario honesto "
                "envia el mismo bit a A y B. En el escenario "
                "bizantino, el simulador introduce mensajes "
                "contradictorios."
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
            "label": "Canal clasico",
            "description": (
                "Canal clasico A-B. Puede representar el "
                "intercambio de informacion auxiliar entre "
                "participantes."
            )
        },
        "classes": "classic-edge"
    },
    {
        "data": {
            "id": "AC",
            "source": "A",
            "target": "C",
            "label": "Clasico / cuantico",
            "description": (
                "Conexion A-C. La interfaz representa una "
                "conexion distribuida; no simula por si sola "
                "un canal cuantico fisico."
            )
        },
        "classes": "quantum-edge"
    },
    {
        "data": {
            "id": "BC",
            "source": "B",
            "target": "C",
            "label": "Clasico / cuantico",
            "description": (
                "Conexion B-C. La interfaz representa una "
                "conexion distribuida. El experimento de Hardy "
                "se ejecuta por separado en esta version."
            )
        },
        "classes": "quantum-edge"
    }
]


ESTILOS = [
    {
        "selector": "node",
        "style": {
            "label": "data(label)",
            "width": 68,
            "height": 68,
            "background-color": "#bfdbfe",
            "border-color": "#3b82f6",
            "border-width": 2,
            "font-size": 19,
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
            "border-width": 3,
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
            "width": 2,
            "label": "data(label)",
            "font-size": 10,
            "text-background-color": "#ffffff",
            "text-background-opacity": 0.9,
            "text-background-padding": 3
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
            "width": 88,
            "height": 88,
            "border-width": 5,
            "border-color": "#2563eb",
            "z-index": 999
        }
    },
    {
        "selector": ".selected-edge",
        "style": {
            "line-color": "#2563eb",
            "target-arrow-color": "#2563eb",
            "width": 5,
            "z-index": 999
        }
    },
    {
        "selector": ".dimmed",
        "style": {
            "opacity": 0.25
        }
    }
]


# ============================================================
# 5. INTERFAZ DASH
# ============================================================

app = Dash(__name__)
app.title = "Entanglert | Hardy"

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');

body {
    margin: 0;
    background: #f8fafc;
    color: #0f172a;
    font-family: 'Manrope', sans-serif;
}

.app-shell {
    max-width: 1400px;
    margin: auto;
    padding: 24px;
}

.card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 4px 12px rgba(15,23,42,.04);
}

.layout {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
}

.controls {
    display: grid;
    grid-template-columns: repeat(auto-fit,minmax(220px,1fr));
    gap: 16px;
}

.control {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    padding: 15px;
    border-radius: 10px;
}

.metric-row {
    display: grid;
    grid-template-columns: repeat(auto-fit,minmax(170px,1fr));
    gap: 12px;
}

.metric {
    padding: 14px;
    background: #f1f5f9;
    border-radius: 9px;
    overflow-wrap: anywhere;
}

.metric-value {
    font-size: 23px;
    font-weight: 800;
    margin-top: 5px;
}

.notice {
    padding: 14px;
    border-radius: 9px;
    background: #eff6ff;
    color: #1e40af;
    margin-top: 14px;
    line-height: 1.65;
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

button {
    cursor: pointer;
}

@media(max-width:800px) {
    .layout {
        grid-template-columns: 1fr;
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
            html.Div(titulo),
            html.Div(valor, className="metric-value"),
            html.Small(descripcion)
        ]
    )


def crear_figura_hardy(pruebas):
    nombres = [p["nombre"] for p in pruebas]
    valores = [p["probabilidad"] for p in pruebas]

    colores = [
        "#dc2626",
        "#f59e0b",
        "#f59e0b",
        "#2563eb"
    ]

    figura = go.Figure()

    figura.add_trace(
        go.Bar(
            x=nombres,
            y=valores,
            marker_color=colores,
            text=[f"{v:.3%}" for v in valores],
            textposition="outside",
            hovertemplate=(
                "%{x}<br>"
                "Probabilidad: %{y:.4%}"
                "<extra></extra>"
            )
        )
    )

    maximo = max(valores) if valores else 0.0

    figura.update_layout(
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin={"l": 50, "r": 20, "t": 35, "b": 70},
        yaxis_title="Probabilidad observada",
        xaxis_title="Condicion de Hardy",
        yaxis_range=[0, max(0.12, maximo * 1.35)],
        font={"family": "Manrope, sans-serif"},
        showlegend=False
    )

    figura.update_yaxes(
        tickformat=".0%",
        gridcolor="#e2e8f0"
    )

    return figura


app.layout = html.Div(
    className="app-shell",
    children=[
        html.H1(
            "E N T A N G L E R T",
            style={"letterSpacing": "3px"}
        ),
        html.P(
            "Correlaciones de Hardy y acuerdo bizantino",
            style={"color": "#64748b"}
        ),

        html.Div(
            className="card",
            children=[
                html.H3("Configuracion experimental"),
                html.P(
                    "Selecciona un escenario clasico y ejecuta "
                    "las mediciones cuanticas."
                ),

                html.Div(
                    className="controls",
                    children=[
                        html.Div(
                            className="control",
                            children=[
                                html.Label("Comportamiento de C"),
                                dcc.RadioItems(
                                    id="modo-c",
                                    options=[
                                        {
                                            "label": " Mensaje consistente",
                                            "value": "honesto"
                                        },
                                        {
                                            "label": " Mensajes contradictorios",
                                            "value": "bizantino"
                                        }
                                    ],
                                    value="honesto",
                                    labelStyle={
                                        "display": "block",
                                        "marginTop": "10px"
                                    }
                                )
                            ]
                        ),

                        html.Div(
                            className="control",
                            children=[
                                html.Label("Bit enviado por C"),
                                dcc.RadioItems(
                                    id="bit-c",
                                    options=[
                                        {"label": " 0", "value": 0},
                                        {"label": " 1", "value": 1}
                                    ],
                                    value=0,
                                    labelStyle={
                                        "display": "block",
                                        "marginTop": "10px"
                                    }
                                )
                            ]
                        ),

                        html.Div(
                            className="control",
                            children=[
                                html.Label("Repeticiones cuanticas"),
                                dcc.Slider(
                                    id="shots",
                                    min=500,
                                    max=10000,
                                    step=500,
                                    value=3000,
                                    marks={
                                        500: "500",
                                        5000: "5k",
                                        10000: "10k"
                                    },
                                    tooltip={
                                        "placement": "bottom",
                                        "always_visible": True
                                    }
                                )
                            ]
                        ),

                        html.Div(
                            className="control",
                            children=[
                                html.Label("Experimento"),
                                html.Button(
                                    "▶ Ejecutar experimento",
                                    id="run",
                                    n_clicks=0,
                                    style={
                                        "width": "100%",
                                        "padding": "12px",
                                        "marginTop": "14px",
                                        "background": "#2563eb",
                                        "color": "white",
                                        "border": "none",
                                        "borderRadius": "8px",
                                        "fontWeight": "bold"
                                    }
                                )
                            ]
                        )
                    ]
                )
            ]
        ),

        html.Div(
            className="layout",
            children=[
                html.Div(
                    className="card",
                    children=[
                        html.H3("1. Red distribuida"),
                        cyto.Cytoscape(
                            id="network",
                            elements=ELEMENTOS,
                            stylesheet=ESTILOS,
                            layout={
                                "name": "preset",
                                "fit": True,
                                "padding": 30
                            },
                            style={
                                "height": "350px",
                                "width": "100%"
                            },
                            userZoomingEnabled=False,
                            userPanningEnabled=False,
                            boxSelectionEnabled=False
                        ),
                        html.Div(
                            id="node-details",
                            children=html.P(
                                "Selecciona un nodo o canal."
                            ),
                            style={
                                "padding": "12px",
                                "background": "#f8fafc",
                                "borderRadius": "8px"
                            }
                        ),
                        html.H4("Mensajes clasicos"),
                        html.Div(
                            id="message-panel",
                            children="Ejecuta el experimento."
                        )
                    ]
                ),

                html.Div(
                    className="card",
                    children=[
                        html.H3("2. Circuito de Hardy"),
                        html.Label("Configuracion de medicion"),
                        dcc.Dropdown(
                            id="circuit-pair",
                            options=[
                                {"label": "D - D", "value": "DD"},
                                {"label": "D - U", "value": "DU"},
                                {"label": "U - D", "value": "UD"},
                                {"label": "U - U", "value": "UU"}
                            ],
                            value="UU",
                            clearable=False
                        ),
                        html.Pre(
                            id="circuit-text",
                            children="Ejecuta el experimento para ver el circuito.",
                            style={
                                "whiteSpace": "pre-wrap",
                                "background": "#f1f5f9",
                                "padding": "14px",
                                "borderRadius": "8px",
                                "fontSize": "12px",
                                "overflowX": "auto"
                            }
                        ),
                        html.H4("Intercambio de entrelazamiento"),
                        html.Pre(
                            id="swap-text",
                            children="Esperando ejecucion...",
                            style={
                                "whiteSpace": "pre-wrap",
                                "background": "#f1f5f9",
                                "padding": "14px",
                                "borderRadius": "8px",
                                "fontSize": "12px",
                                "overflowX": "auto"
                            }
                        )
                    ]
                )
            ]
        ),

        html.Div(
            className="card",
            children=[
                html.H3("3. Verificacion de las correlaciones de Hardy"),
                html.P(
                    "Las tres primeras condiciones deben tener "
                    "probabilidad teorica cero. La condicion U-U "
                    "debe tener probabilidad positiva."
                ),
                html.Div(
                    id="hardy-metrics",
                    className="metric-row"
                ),
                dcc.Graph(
                    id="hardy-chart",
                    config={"displayModeBar": False}
                ),
                html.Div(
                    id="hardy-status",
                    className="notice",
                    children="Ejecuta el experimento para evaluar las correlaciones."
                )
            ]
        ),

        html.Div(
            className="card",
            children=[
                html.H3("4. Decision del protocolo bizantino"),
                html.P(
                    "La decision combina la validacion estadistica de Hardy "
                    "con la comparacion de los bits recibidos por A y B."
                ),
                html.Div(
                    id="protocol-status",
                    className="notice",
                    children=(
                        "Ejecuta el experimento para evaluar la "
                        "transmision y el consenso."
                    )
                ),
                html.P(
                    "Limite cientifico: este es un modelo didactico. "
                    "La contradiccion se introduce en el escenario clasico; "
                    "Hardy no identifica automaticamente al mentiroso. "
                    "El intercambio de entrelazamiento mostrado arriba es "
                    "auxiliar y no implementa el proyector M especifico "
                    "del articulo ni todo el protocolo device-independent."
                ),
                html.P(
                    "Interpretacion: si Hardy no pasa, la transmision queda "
                    "sin validar. Si Hardy pasa pero los bits difieren, se "
                    "marca una inconsistencia. Si Hardy pasa y los bits "
                    "coinciden, se registra consenso en este escenario."
                )
            ]
        )
    ]
)


# ============================================================
# 6. INTERACCION DE LA RED
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
        e = {
            "data": dict(original["data"]),
            "classes": original.get("classes", "")
        }

        if "position" in original:
            e["position"] = dict(original["position"])

        if seleccionado:
            sid = seleccionado.get("id")

            if e["data"]["id"] == sid:
                if "source" in e["data"]:
                    e["classes"] += " selected-edge"
                else:
                    e["classes"] += " selected-node"
            else:
                e["classes"] += " dimmed"

        elementos.append(e)

    if not seleccionado:
        panel = html.P("Selecciona un nodo o canal.")
    else:
        if "source" in seleccionado:
            titulo = (
                f"Canal {seleccionado['source']} "
                f"→ {seleccionado['target']}"
            )
        else:
            titulo = f"Nodo {seleccionado.get('label', '')}"

        panel = html.Div([
            html.H4(titulo),
            html.P(seleccionado.get("description", ""))
        ])

    return panel, elementos


# ============================================================
# 7. EJECUCION Y ANALISIS
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

    # --------------------------------------------------------
    # A. Experimentos de Hardy
    # --------------------------------------------------------

    pruebas, circuitos = evaluar_condiciones_hardy(shots)

    circuito = circuitos[par_seleccionado]

    texto_circuito = circuito.draw(
        output="text",
        fold=-1
    ).single_string()

    # --------------------------------------------------------
    # B. Intercambio de entrelazamiento auxiliar
    # --------------------------------------------------------

    circuito_swap, counts_swap = ejecutar_intercambio(shots)

    texto_swap = (
        circuito_swap.draw(
            output="text",
            fold=-1
        ).single_string()
        + "\n\nResultados de la medicion de Bell:\n"
        + str(counts_swap)
        + "\n\nInterpretacion: se preparan dos pares de Bell "
          "y se mide el par central. Esta es una demostracion "
          "auxiliar de intercambio de entrelazamiento; no "
          "implementa el proyector M especifico del articulo."
    )

    # --------------------------------------------------------
    # C. Metricas
    # --------------------------------------------------------

    metricas = []

    for prueba in pruebas:
        metricas.append(
            tarjeta(
                prueba["nombre"],
                f"{prueba['probabilidad']:.3%}",
                (
                    f"{prueba['frecuencia']} de "
                    f"{prueba['shots']} resultados"
                )
            )
        )

    metricas.append(
        tarjeta(
            "q maximo teorico",
            f"{Q_MAX:.3%}",
            "Valor ideal del estado de Hardy"
        )
    )

    figura = crear_figura_hardy(pruebas)

    # --------------------------------------------------------
    # D. Evaluacion estadistica prudente
    # --------------------------------------------------------
    # Un resultado observado de cero casos no demuestra por si
    # solo que la probabilidad verdadera sea exactamente cero.
    #
    # Este umbral es solo un criterio exploratorio de interfaz,
    # no una prueba formal de seguridad ni un test estadistico
    # completo del protocolo.
    # --------------------------------------------------------

    validacion_hardy = evaluar_hardy_estadistico(pruebas, shots)

    if validacion_hardy["valido"]:
        estado_hardy = (
            "RESULTADO: compatible con las condiciones de Hardy.\n\n"
            "Las tres probabilidades que deberian anularse son "
            "pequenas bajo el criterio exploratorio utilizado, "
            "y U-U presenta una probabilidad positiva.\n\n"
            "Esto comprueba el comportamiento esperado del "
            "estado simulado; no demuestra por si solo un "
            "protocolo bizantino completo."
        )
        clase_hardy = "notice notice-ok"
    else:
        estado_hardy = (
            "RESULTADO: las frecuencias no cumplen claramente "
            "el criterio exploratorio de Hardy.\n\n"
            "Revisa los circuitos, las bases y el numero de "
            "repeticiones. Este criterio no sustituye un "
            "analisis estadistico formal."
        )
        clase_hardy = "notice notice-warn"

    # --------------------------------------------------------
    # E. Mensajes clasicos
    # --------------------------------------------------------

    mensajes = simular_mensajes(bit_c, modo)

    bit_a = mensajes["bit_a"]
    bit_b = mensajes["bit_b"]

    if mensajes["contradiccion"]:
        estado_mensaje = html.Div(
            [
                html.H4(
                    "Contradiccion clasica introducida",
                    style={"color": "#b91c1c"}
                ),
                html.P(f"C → A: bit {bit_a} (base {'U' if bit_a == 0 else 'D'})"),
                html.P(f"C → B: bit {bit_b} (base {'U' if bit_b == 0 else 'D'})"),
                html.P(
                    "A y B recibieron valores distintos. "
                    "El simulador conoce la contradiccion porque "
                    "la introdujo directamente en los mensajes."
                ),
                html.P(
                    "Esto NO significa que Hardy haya detectado "
                    "al nodo C."
                )
            ],
            style={
                "padding": "12px",
                "background": "#fef2f2",
                "borderRadius": "8px"
            }
        )
    else:
        estado_mensaje = html.Div(
            [
                html.H4(
                    "Mensajes clasicos consistentes",
                    style={"color": "#166534"}
                ),
                html.P(f"C → A: bit {bit_a} (base {'U' if bit_a == 0 else 'D'})"),
                html.P(f"C → B: bit {bit_b} (base {'U' if bit_b == 0 else 'D'})"),
                html.P(
                    "Los dos participantes reciben el mismo bit "
                    "en el escenario clasico configurado."
                )
            ],
            style={
                "padding": "12px",
                "background": "#f0fdf4",
                "borderRadius": "8px"
            }
        )

    # --------------------------------------------------------
    # F. Decision integrada: estadisticas de Hardy + consistencia
    # --------------------------------------------------------
    decision = decidir_protocolo(pruebas, mensajes, shots)

    panel_decision = html.Div([
        html.H3(decision["titulo"]),
        html.P(decision["detalle"]),
        html.Hr(),
        html.P(
            "Validacion estadistica de Hardy: "
            + ("compatible" if decision["hardy_valido"] else "no validada")
        ),
        html.P(
            "Consenso en el escenario: "
            + ("si" if decision["consenso"] else "no")
        ),
        html.P(
            "Mensaje enviado a A: "
            f"{bit_a} ({'U' if bit_a == 0 else 'D'}); "
            "mensaje enviado a B: "
            f"{bit_b} ({'U' if bit_b == 0 else 'D'})."
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
