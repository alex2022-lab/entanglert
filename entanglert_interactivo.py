
import numpy as np
from dash import Dash, html, dcc, Input, Output, State, ctx
import dash_cytoscape as cyto
import plotly.graph_objects as go

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator


# ============================================================
# 1. ESTADO DE HARDY
# ============================================================
# Base U:
# |0> = resultado +1
# |1> = resultado -1
#
# Base D:
# |d>      = alpha |0> + beta |1>
# |d_perp> = beta  |0> - alpha |1>
#
# Los coeficientes se eligen para alcanzar q_max de Hardy.

alpha = np.sqrt((np.sqrt(5) - 1) / 2)
beta = np.sqrt(1 - alpha**2)

estado_sin_normalizar = np.array([
    1,
    -alpha / beta,
    -alpha / beta,
    -(1 + alpha**2) / alpha**2
], dtype=complex)

ESTADO_HARDY = (
    estado_sin_normalizar
    / np.linalg.norm(estado_sin_normalizar)
)

Q_MAX = (5 * np.sqrt(5) - 11) / 2

# Matriz cuyos vectores columna son los estados de la base D.
BASE_D = np.array([
    [alpha, beta],
    [beta, -alpha]
], dtype=complex)


def construir_circuito_hardy(base1, base2):
    """
    Simula un par en el estado de Hardy.

    base1 y base2 pueden ser U o D.
    El resultado 0 representa +1 y el resultado 1 representa -1.
    """
    qc = QuantumCircuit(2, 2)

    qc.initialize(ESTADO_HARDY, [0, 1])

    if base1 == "D":
        qc.unitary(BASE_D, [0], label="Medición D")

    if base2 == "D":
        qc.unitary(BASE_D, [1], label="Medición D")

    qc.measure([0, 1], [0, 1])

    return qc


def ejecutar_hardy(base1, base2, shots, seed=42):
    qc = construir_circuito_hardy(base1, base2)
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

    counts = resultado.get_counts()

    return qc, counts


def probabilidades(counts):
    """
    Qiskit devuelve las cadenas clásicas como c1c0.
    Para dos qubits, los resultados se interpretan como:
    primer bit = resultado del qubit 1;
    segundo bit = resultado del qubit 0.
    """
    total = sum(counts.values()) or 1

    return {
        bits.replace(" ", "").zfill(2): frecuencia / total
        for bits, frecuencia in counts.items()
    }


def probabilidad(counts, patron):
    return probabilidades(counts).get(patron, 0.0)


def evaluar_condiciones_hardy(shots):
    """
    Comprueba las cuatro condiciones de Hardy mediante
    cuatro experimentos independientes.

    00 en la base U representa (+1,+1).
    11 en la base D representa (-1,-1).
    """
    configuraciones = [
        ("D", "D", "P(-- | D,D)", "11", "cero"),
        ("D", "U", "P(++ | D,U)", "00", "cero"),
        ("U", "D", "P(++ | U,D)", "00", "cero"),
        ("U", "U", "P(++ | U,U)", "00", "positiva"),
    ]

    resultados = []
    circuitos = {}

    for i, (b1, b2, nombre, patron, tipo) in enumerate(
        configuraciones
    ):
        circuito, counts = ejecutar_hardy(
            b1, b2, shots, seed=42 + i
        )

        circuitos[f"{b1}{b2}"] = circuito

        p = probabilidad(counts, patron)

        resultados.append({
            "nombre": nombre,
            "base1": b1,
            "base2": b2,
            "probabilidad": p,
            "frecuencia": counts.get(patron, 0),
            "shots": shots,
            "tipo": tipo,
            "counts": counts
        })

    return resultados, circuitos


# ============================================================
# 2. INTERCAMBIO DE ENTRELAZAMIENTO
# ============================================================
# Esta función representa una demostración de intercambio
# de entrelazamiento mediante dos pares de Bell.
#
# No es el proyector de Hardy M del artículo. Se muestra
# como experimento auxiliar para distinguir ambos mecanismos.


def circuito_intercambio():
    qc = QuantumCircuit(4, 2)

    # Par de Bell A-B
    qc.h(0)
    qc.cx(0, 1)

    # Par de Bell A-C
    qc.h(2)
    qc.cx(2, 3)

    # Medición de Bell sobre los qubits centrales 1 y 2.
    qc.cx(1, 2)
    qc.h(1)
    qc.measure([1, 2], [0, 1])

    return qc


def ejecutar_intercambio(shots):
    qc = circuito_intercambio()
    simulador = AerSimulator()

    compilado = transpile(qc, simulador)
    counts = simulador.run(
        compilado,
        shots=int(shots),
        seed_simulator=77
    ).result().get_counts()

    return qc, counts


# ============================================================
# 3. RED INTERACTIVA
# ============================================================

ELEMENTOS = [
    {
        "data": {
            "id": "A",
            "label": "A",
            "description": (
                "Participante A. Distribuye recursos cuánticos, "
                "prepara estados y verifica correlaciones. "
                "En el protocolo completo tiene un papel especial "
                "en la preparación y el intercambio de entrelazamiento."
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
                "Participante B. Recibe el mensaje de C, "
                "comprueba las correlaciones de Hardy y compara "
                "la información pertinente con A."
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
                "General comandante C. Debe transmitir el mismo "
                "bit a A y B. El modelo permite representar "
                "mensajes contradictorios como escenario adversario."
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
            "label": "Mensajes clásicos",
            "description": (
                "Canal clásico A-B. Los participantes pueden "
                "intercambiar información de confirmación."
            )
        },
        "classes": "classic-edge"
    },
    {
        "data": {
            "id": "AC",
            "source": "A",
            "target": "C",
            "label": "Clásico / cuántico",
            "description": (
                "Conexión A-C. En el protocolo se distribuyen "
                "recursos cuánticos y se comunican resultados "
                "y datos auxiliares."
            )
        },
        "classes": "quantum-edge"
    },
    {
        "data": {
            "id": "BC",
            "source": "B",
            "target": "C",
            "label": "Clásico / cuántico",
            "description": (
                "Conexión B-C. Permite estudiar la correlación "
                "que debe ayudar a B a verificar el mensaje "
                "que C pretendía transmitir."
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
            "border-color": "#2563eb"
        }
    },
    {
        "selector": ".selected-edge",
        "style": {
            "line-color": "#2563eb",
            "target-arrow-color": "#2563eb",
            "width": 5
        }
    },
    {
        "selector": ".dimmed",
        "style": {"opacity": 0.25}
    }
]


# ============================================================
# 4. INTERFAZ DASH
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
    grid-template-columns: repeat(auto-fit,minmax(150px,1fr));
    gap: 12px;
}

.metric {
    padding: 14px;
    background: #f1f5f9;
    border-radius: 9px;
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
    line-height: 1.6;
}

.notice-warn {
    background: #fef2f2;
    color: #991b1b;
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
    "</head>", f"<style>{CSS}</style></head>"
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


app.layout = html.Div(
    className="app-shell",
    children=[
        html.H1("E N T A N G L E R T"),
        html.P(
            "Acuerdo bizantino cuántico mediante correlaciones "
            "de Hardy e intercambio de entrelazamiento.",
            style={"color": "#64748b"}
        ),

        html.Div(
            className="card",
            children=[
                html.H3("Configuración experimental"),

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
                                        {"label": " 0 / Sí", "value": 0},
                                        {"label": " 1 / No", "value": 1}
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
                                html.Label("Repeticiones"),
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
                                    }
                                )
                            ]
                        ),

                        html.Div(
                            className="control",
                            children=[
                                html.Label("Experimento"),
                                html.Button(
                                    "▶ Ejecutar protocolo",
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
                            userPanningEnabled=False
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
                        )
                    ]
                ),

                html.Div(
                    className="card",
                    children=[
                        html.H3("2. Circuito de Hardy"),
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
                            children=(
                                "Ejecuta el experimento para "
                                "visualizar el circuito."
                            ),
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
                            children="Esperando ejecución...",
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
                html.H3("3. Verificación de Hardy"),
                html.P(
                    "Se comprueban las tres probabilidades que "
                    "deben anularse y la probabilidad positiva "
                    "de la combinación U-U."
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
                    id="protocol-status",
                    className="notice",
                    children="Configura el experimento y ejecútalo."
                )
            ]
        )
    ]
)


# ============================================================
# 5. INTERACCIÓN DE LA RED
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
                e["classes"] += (
                    " selected-edge"
                    if "source" in e["data"]
                    else " selected-node"
                )
            else:
                e["classes"] += " dimmed"

        elementos.append(e)

    if not seleccionado:
        panel = html.P("Selecciona un nodo o canal.")
    else:
        titulo = (
            f"Canal {seleccionado['source']} → "
            f"{seleccionado['target']}"
            if "source" in seleccionado
            else f"Nodo {seleccionado['label']}"
        )

        panel = html.Div([
            html.H4(titulo),
            html.P(seleccionado.get("description", ""))
        ])

    return panel, elementos


# ============================================================
# 6. EJECUCIÓN DEL EXPERIMENTO
# ============================================================

@app.callback(
    Output("circuit-text", "children"),
    Output("swap-text", "children"),
    Output("hardy-metrics", "children"),
    Output("hardy-chart", "figure"),
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
    n_clicks, shots, modo, bit_c, par_seleccionado
):
    shots = int(shots)

    # Verificación estadística de las condiciones de Hardy.
    pruebas, circuitos = evaluar_condiciones_hardy(shots)

    # Circuito seleccionado para mostrar.
    circuito = circuitos[par_seleccionado]
    texto_circuito = circuito.draw(
        output="text",
        fold=-1
    ).single_string()

    # Intercambio de entrelazamiento auxiliar.
    circuito_swap, counts_swap = ejecutar_intercambio(shots)

    texto_swap = (
        circuito_swap.draw(
            output="text",
            fold=-1
        ).single_string()
        + "\n\nResultados de la medición de Bell:\n"
        + str(counts_swap)
        + "\n\nNota: esta demostración usa pares de Bell y "
          "no implementa el proyector de Hardy M del artículo."
    )

    # Métricas de Hardy.
    metricas = []

    for prueba in pruebas:
        p = prueba["probabilidad"]
        metricas.append(
            tarjeta(
                prueba["nombre"],
                f"{p:.3%}",
                f"{prueba['frecuencia']} de {shots} resultados"
            )
        )

    metricas.append(
        tarjeta(
            "q máximo teórico",
            f"{Q_MAX:.3%}",
            "Valor ideal del estado de Hardy"
        )
    )

    # Gráfico de probabilidades observadas.
    nombres = [p["nombre"] for p in pruebas]
    valores = [p["probabilidad"] for p in pruebas]

    figura = go.Figure()

    figura.add_trace(
        go.Bar(
            x=nombres,
            y=valores,
            marker_color=[
                "#dc2626",
                "#f59e0b",
                "#f59e0b",
                "#2563eb"
            ],
            text=[f"{v:.3%}" for v in valores],
            textposition="outside"
        )
    )

    figura.update_layout(
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin={"l": 45, "r": 20, "t": 30, "b": 60},
        yaxis_title="Probabilidad observada",
        yaxis_range=[0, max(0.12, max(valores) * 1.3)],
        xaxis_title="Condición de Hardy"
    )

    # Criterio estadístico aproximado:
    # las probabilidades nulas deben ser compatibles con cero,
    # mientras que la probabilidad UU debe ser claramente positiva.
    #
    # Se evita exigir que una frecuencia finita sea exactamente cero.
    limite_cero = max(0.01, 5 / shots)
    p_positiva = pruebas[3]["probabilidad"]

    ceros_compatibles = all(
        p["probabilidad"] <= limite_cero
        for p in pruebas[:3]
    )

    positiva_observada = p_positiva > limite_cero

    if ceros_compatibles and positiva_observada:
        estado_hardy = (
            "Las frecuencias observadas son compatibles "
            "con las condiciones de Hardy bajo este criterio "
            "aproximado."
        )
    else:
        estado_hardy = (
            "Las frecuencias no satisfacen claramente "
            "el criterio aproximado de Hardy. Revisa el "
            "número de repeticiones y las mediciones."
        )

    # Escenario clásico de mensajes.
    mensaje_a = int(bit_c)
    mensaje_b = int(bit_c)

    if modo == "bizantino":
        mensaje_b = 1 - mensaje_a

    if mensaje_a != mensaje_b:
        estado_clasico = (
            f"Escenario adversario configurado: A recibe {mensaje_a} "
            f"y B recibe {mensaje_b}. Existe una contradicción "
            "clásica introducida en el modelo."
        )
    else:
        estado_clasico = (
            f"C transmite el bit {mensaje_a} a ambos participantes "
            "en el escenario clásico configurado."
        )

    estado = (
        estado_hardy + "\n\n"
        + estado_clasico + "\n\n"
        + "Importante: la prueba de Hardy y la contradicción "
          "clásica se muestran como experimentos separados. "
          "Este prototipo no demuestra todavía que el protocolo "
          "completo detecte automáticamente al traidor."
    )

    clase = (
        "notice notice-warn"
        if modo == "bizantino" or not (
            ceros_compatibles and positiva_observada
        )
        else "notice"
    )

    return (
        texto_circuito,
        texto_swap,
        metricas,
        figura,
        estado,
        clase
    )


if __name__ == "__main__":
    app.run(debug=True)
