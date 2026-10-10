from dash import Dash, html, dcc, Input, Output, State, ctx, no_update
import dash_cytoscape as cyto
import plotly.graph_objects as go
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator


# ---------------------------------------------------------------------------
# Funciones y análisis cuántico
# ---------------------------------------------------------------------------
def construir_circuito(base: str, intervencion_c: bool) -> QuantumCircuit:
    # q0 = A, q1 = B, q2 = C
    qc = QuantumCircuit(3, 3)
    qc.h(0)
    qc.cx(0, 1)
    qc.cx(0, 2)  # Prepara un estado GHZ
    if intervencion_c:
        qc.x(2)  # Puerta Pauli-X sobre el qubit asociado a C
    if base == "X":
        qc.h(0)
        qc.h(1)
        qc.h(2)
    qc.measure([0, 1, 2], [0, 1, 2])
    return qc


def discrepancias_z(counts):
    total = sum(counts.values())
    if not total:
        return 0.0, 0.0, 0.0

    ab = ac = bc = 0
    for cadena, frecuencia in counts.items():
        bits = cadena.replace(" ", "")[::-1]
        a, b, c = map(int, bits[-3:])
        ab += frecuencia * (a != b)
        ac += frecuencia * (a != c)
        bc += frecuencia * (b != c)

    return ab / total, ac / total, bc / total


def ejecutar_cuantico(base, intervencion_c, shots):
    circuito = construir_circuito(base, intervencion_c)
    simulador = AerSimulator()
    compilado = transpile(circuito, simulador)
    counts = simulador.run(compilado, shots=int(shots)).result().get_counts()
    return circuito, counts


# ---------------------------------------------------------------------------
# Red interactiva (Cytoscape): Nodos y aristas iniciales
# ---------------------------------------------------------------------------
ELEMENTOS_BASE = [
    {
        "data": {
            "id": "A",
            "label": "A",
            "kind": "node",
            "role": "Nodo A",
            "description": "Participante de la red. Recibe mensajes clásicos y tiene asociado el qubit q0 en el circuito de simulación."
        },
        "position": {"x": 120, "y": 180},
        "classes": "participant"
    },
    {
        "data": {
            "id": "B",
            "label": "B",
            "kind": "node",
            "role": "Nodo B",
            "description": "Participante de la red. Recibe mensajes clásicos y tiene asociado el qubit q1 en el circuito de simulación."
        },
        "position": {"x": 380, "y": 180},
        "classes": "participant"
    },
    {
        "data": {
            "id": "C",
            "label": "C",
            "kind": "node",
            "role": "Nodo C",
            "description": "Nodo C. En el escenario de prueba se configura para enviar mensajes clásicos contradictorios. Su qubit asociado es q2."
        },
        "position": {"x": 250, "y": 40},
        "classes": "participant adversary"
    },
    {
        "data": {
            "id": "AB",
            "source": "A",
            "target": "B",
            "label": "Canal clásico",
            "kind": "edge",
            "description": "Conexión clásica A - B. Representa el intercambio de mensajes clásicos entre participantes."
        },
        "classes": "classic-edge"
    },
    {
        "data": {
            "id": "AC",
            "source": "A",
            "target": "C",
            "label": "Canal clásico",
            "kind": "edge",
            "description": "Conexión clásica A - C. Permite representar mensajes entre A y C."
        },
        "classes": "classic-edge"
    },
    {
        "data": {
            "id": "CB",
            "source": "C",
            "target": "B",
            "label": "Canal clásico",
            "kind": "edge",
            "description": "Conexión clásica C - B. En el escenario contradictorio, C puede enviar NO (0) a B mientras envía SÍ (1) a A."
        },
        "classes": "classic-edge"
    },
]

HOJA_ESTILOS = [
    {
        "selector": "node",
        "style": {
            "label": "data(label)",
            "width": 70,
            "height": 70,
            "font-size": 18,
            "font-weight": "bold",
            "color": "#1e293b",
            "text-valign": "center",
            "text-halign": "center",
            "background-color": "#bfdbfe",
            "border-width": 2,
            "border-color": "#3b82f6",
        }
    },
    {
        "selector": ".adversary",
        "style": {
            "background-color": "#fecaca",
            "border-color": "#dc2626",
            "border-width": 3,
            "color": "#b91c1c"
        }
    },
    {
        "selector": "edge",
        "style": {
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#94a3b8",
            "line-color": "#94a3b8",
            "width": 2.2,
            "label": "data(label)",
            "font-size": 11,
            "color": "#334155",
            "text-background-color": "#ffffff",
            "text-background-opacity": 0.8,
            "text-background-padding": 3,
        }
    },
    {
        "selector": ".selected-node",
        "style": {
            "width": 88,
            "height": 88,
            "border-width": 5,
            "border-color": "#2563eb",
            "shadow-blur": 15,
            "shadow-color": "#3b82f6",
            "shadow-opacity": 0.6,
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
    },
]


def panel_elemento(datos_nodo, datos_arista):
    seleccionado = datos_nodo or datos_arista
    if not seleccionado:
        return html.Div([
            html.H3("Explora la red"),
            html.P("Haz clic en un nodo o en un canal para ver su descripción y detalles."),
        ])
    es_arista = bool(datos_arista)
    titulo = f"Conexión {seleccionado.get('source')} → {seleccionado.get('target')}" if es_arista else f"Nodo {seleccionado.get('label', seleccionado.get('id'))}"
    return html.Div([
        html.H3(titulo),
        html.P(seleccionado.get("description", "Sin descripción disponible.")),
    ])


# ---------------------------------------------------------------------------
# Aplicación Dash
# ---------------------------------------------------------------------------
app = Dash(__name__)
app.title = "Entanglert"

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');
body { margin: 0; background: #f8fafc; color: #0f172a; font-family: 'Manrope', sans-serif; }
.app-shell { max-width: 1400px; margin: 0 auto; padding: 24px; }
.card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 20px; }
.layout { display: grid; grid-template-columns: 1.25fr 1fr; gap: 20px; }
#network { height: 380px; width: 100%; }
.quantum-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
#circuit-text { white-space: pre-wrap; font-family: monospace; font-size: 12px; background: #f1f5f9; padding: 12px; border-radius: 8px; }
.metric-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 12px; }
.metric { background: #f1f5f9; border-radius: 8px; padding: 12px; text-align: center; }
.metric-value { font-size: 18px; font-weight: bold; color: #1e293b; margin-top: 4px; }
.notice { border-radius: 8px; padding: 12px; font-size: 12px; margin-top: 12px; background: #eff6ff; border: 1px solid #bfdbfe; color: #1e40af; }
.notice-warn { background: #fef2f2; border-color: #fecaca; color: #b91c1c; }

/* Tooltips limpios al pasar el mouse */
.tooltip-wrap { position: relative; display: inline-flex; align-items: center; margin-left: 6px; cursor: help; }
.tooltip-icon { display: inline-flex; align-items: center; justify-content: center; width: 16px; height: 16px; background-color: #e2e8f0; color: #475569; border-radius: 50%; font-size: 10px; font-weight: bold; }
.tooltip-text { visibility: hidden; width: 260px; background-color: #1e293b; color: #fff; text-align: left; border-radius: 6px; padding: 8px 10px; position: absolute; z-index: 10; bottom: 125%; left: 50%; transform: translateX(-50%); opacity: 0; transition: opacity 0.2s; font-size: 11px; font-weight: normal; line-height: 1.4; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
.tooltip-wrap:hover .tooltip-text { visibility: visible; opacity: 1; }

.controls-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; align-items: stretch; }
.control-box { background: #f8fafc; border: 1px solid #e2e8f0; padding: 16px; border-radius: 10px; display: flex; flex-direction: column; justify-content: space-between; gap: 10px; }

.control-box label, .control-box span, .control-box div { font-family: 'Manrope', sans-serif; }
.control-box .rc-slider { margin: 12px 0 6px 0; }
"""

app.index_string = app.index_string.replace("</head>", f"<style>{CSS}</style></head>")

app.layout = html.Div(className="app-shell", children=[
    html.H1("E N T A N G L E R T", style={"marginBottom": "4px"}),
    html.P("Explora qué ocurre con tres nodos cuando aparecen mensajes contradictorios o se interviene un qubit.",
           style={"color": "#64748b", "marginBottom": "20px"}),

    html.Div(className="card", children=[
        html.H3("Configuración del Experimento", style={"marginBottom": "16px"}),
        html.Div(className="controls-grid", children=[

            # 1. Contradicción clásica
            html.Div(className="control-box", children=[
                html.Div(children=[
                    html.Div(style={"display": "flex", "alignItems": "center", "marginBottom": "6px"}, children=[
                        dcc.Checklist(
                            id="contradiction-toggle",
                            options=[{"label": " C envía mensajes contradictorios", "value": "on"}],
                            value=["on"],
                            style={"fontSize": "13px", "fontWeight": "600"}
                        ),
                        html.Span(className="tooltip-wrap", children=[
                            html.Span("i", className="tooltip-icon"),
                            html.Span(
                                "C le dice ‘sí’ (1) a A y ‘no’ (0) a B. Como las decisiones no coinciden, los participantes pueden detectar que recibieron información diferente.",
                                className="tooltip-text")
                        ])
                    ]),
                    html.Div("Simula discrepancias en los mensajes clásicos.",
                             style={"fontSize": "11px", "color": "#64748b"})
                ])
            ]),

            # 2. Intervención cuántica
            html.Div(className="control-box", children=[
                html.Div(children=[
                    html.Div(style={"display": "flex", "alignItems": "center", "marginBottom": "6px"}, children=[
                        dcc.Checklist(
                            id="x-toggle",
                            options=[{"label": " Intervenir el qubit de C con X", "value": "on"}],
                            value=[],
                            style={"fontSize": "13px", "fontWeight": "600"}
                        ),
                        html.Span(className="tooltip-wrap", children=[
                            html.Span("i", className="tooltip-icon"),
                            html.Span(
                                "La puerta X intercambia |0⟩ y |1⟩. Aquí se aplica al qubit asociado a C para estudiar cómo cambia el resultado de la medición. Es una intervención controlada del experimento; no representa por sí sola a un atacante real.",
                                className="tooltip-text")
                        ])
                    ]),
                    html.Div("Modifica el estado cuántico del nodo C.", style={"fontSize": "11px", "color": "#64748b"})
                ])
            ]),

            # 3. Base de medición (Sin búsqueda y limpio)
            html.Div(className="control-box", children=[
                html.Div(children=[
                    html.Div(style={"display": "flex", "alignItems": "center", "marginBottom": "8px"}, children=[
                        html.Span("Cómo medir los qubits",
                                  style={"fontWeight": "600", "fontSize": "13px", "color": "#334155"}),
                        html.Span(className="tooltip-wrap", children=[
                            html.Span("i", className="tooltip-icon"),
                            html.Span(
                                "Z · medición directa: Se mide cada qubit en la base computacional y se obtiene 0 o 1.\nX · medir en otra base: Se aplica una puerta Hadamard (H) antes de medir para estudiar correlaciones en la base X.",
                                className="tooltip-text")
                        ])
                    ]),
                    dcc.Dropdown(
                        id="basis-select",
                        options=[
                            {"label": "Z · medición directa", "value": "Z"},
                            {"label": "X · medir en otra base", "value": "X"}
                        ],
                        value="Z",
                        clearable=False,
                        searchable=False,
                        style={"fontSize": "13px"}
                    )
                ])
            ]),

            # 4. Repeticiones (Shots) y Botón
            html.Div(className="control-box", children=[
                html.Div(children=[
                    html.Div(style={"display": "flex", "alignItems": "center", "marginBottom": "8px"}, children=[
                        html.Span("Repeticiones del experimento",
                                  style={"fontWeight": "600", "fontSize": "13px", "color": "#334155"}),
                        html.Span(className="tooltip-wrap", children=[
                            html.Span("i", className="tooltip-icon"),
                            html.Span(
                                "El circuito se ejecuta muchas veces con la misma configuración. Con 1000 repeticiones se obtienen 1000 resultados para contar patrones estables.",
                                className="tooltip-text")
                        ])
                    ]),
                    dcc.Slider(id="shots-slider", min=100, max=3000, step=100, value=1000),
                ]),
                html.Button("▶ Ejecutar experimento", id="run-experiment", n_clicks=0,
                            style={"background": "#2563eb", "color": "white", "border": "none", "padding": "10px 16px",
                                   "borderRadius": "8px", "fontWeight": "bold", "fontSize": "13px", "cursor": "pointer",
                                   "width": "100%"})
            ])
        ])
    ]),

    html.Div(className="layout", children=[
        html.Div(className="card", children=[
            html.H3("1. La red"),
            cyto.Cytoscape(
                id="network",
                elements=ELEMENTOS_BASE,
                stylesheet=HOJA_ESTILOS,
                layout={"name": "preset", "fit": True},
                style={"height": "320px", "width": "100%"},
                userZoomingEnabled=False,
                userPanningEnabled=False,
            ),
            html.Div(id="detail-panel",
                     style={"marginTop": "15px", "padding": "10px", "background": "#f8fafc", "borderRadius": "8px"},
                     children=panel_elemento(None, None)),
        ]),
        html.Div(className="card", children=[
            html.H3("2. El circuito cuántico"),
            html.Div(id="circuit-text", children="Pulsa Ejecutar experimento para generar el circuito."),
        ]),
    ]),

    html.Div(className="card", children=[
        html.H3("3. Resultados"),
        html.Div(id="metrics", className="metric-row"),
        dcc.Graph(id="histogram", config={"displayModeBar": False},
                  figure={"layout": {"margin": {"l": 20, "r": 20, "t": 20, "b": 20}}}),
        html.Div(id="experiment-notice", className="notice",
                 children="Elige la configuración y pulsa Ejecutar experimento para ver los resultados."),
    ])
])


# Callback de la red interactiva
@app.callback(
    Output("detail-panel", "children"),
    Output("network", "elements"),
    Input("network", "tapNodeData"),
    Input("network", "tapEdgeData"),
    Input("contradiction-toggle", "value"),
)
def actualizar_red(datos_nodo, datos_arista, contradiction_toggle):
    seleccionado_id = None
    if ctx.triggered_id == "network" and ctx.triggered[0]["prop_id"].endswith("tapNodeData"):
        seleccionado_id = (datos_nodo or {}).get("id")
    elif ctx.triggered_id == "network" and ctx.triggered[0]["prop_id"].endswith("tapEdgeData"):
        seleccionado_id = (datos_arista or {}).get("id")

    contradiccion = bool(contradiction_toggle and "on" in contradiction_toggle)

    nuevos = []
    for original in ELEMENTOS_BASE:
        e = {"data": dict(original["data"])}
        if "position" in original:
            e["position"] = dict(original["position"])
        classes = original.get("classes", "")

        if seleccionado_id:
            if e["data"]["id"] == seleccionado_id:
                classes += " selected-node" if e["data"].get("kind") == "node" else " selected-edge"
            else:
                classes += " dimmed"

        if e["data"].get("id") == "CB" and contradiccion:
            e["data"]["label"] = "NO (0)"
        elif e["data"].get("id") == "AC" and contradiccion:
            e["data"]["label"] = "SÍ (1)"
        else:
            if e["data"].get("kind") == "edge":
                e["data"]["label"] = "Canal"

        e["classes"] = classes.strip()
        nuevos.append(e)

    panel = panel_elemento(datos_nodo, datos_arista)
    return panel, nuevos


# Callback del experimento cuántico
@app.callback(
    Output("circuit-text", "children"),
    Output("histogram", "figure"),
    Output("metrics", "children"),
    Output("experiment-notice", "children"),
    Output("experiment-notice", "className"),
    Input("run-experiment", "n_clicks"),
    State("basis-select", "value"),
    State("x-toggle", "value"),
    State("contradiction-toggle", "value"),
    State("shots-slider", "value"),
    prevent_initial_call=True,
)
def ejecutar_experimento(n_clicks, base, x_valor, contradiction_valor, shots):
    intervencion = bool(x_valor and "on" in x_valor)
    contradiccion = bool(contradiction_valor and "on" in contradiction_valor)

    circuito, counts = ejecutar_cuantico(base, intervencion, shots)
    texto_circuito = circuito.draw(output="text", fold=-1).single_string()

    etiquetas = sorted(counts.keys())
    valores = [counts[k] for k in etiquetas]

    fig = go.Figure(data=[go.Bar(x=etiquetas, y=valores, marker_color="#3b82f6")])
    fig.update_layout(
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        margin={"l": 30, "r": 10, "t": 10, "b": 30},
        xaxis_title="Resultado de medición", yaxis_title="Frecuencia"
    )

    if base == "Z":
        d_ab, d_ac, d_bc = discrepancias_z(counts)
        metricas = [
            html.Div([html.Div("A frente a B"), html.Div(f"{d_ab:.1%}", className="metric-value")], className="metric"),
            html.Div([html.Div("A frente a C"), html.Div(f"{d_ac:.1%}", className="metric-value")], className="metric"),
            html.Div([html.Div("B frente a C"), html.Div(f"{d_bc:.1%}", className="metric-value")], className="metric"),
        ]
    else:
        total = sum(counts.values()) or 1
        impar = sum(f for c, f in counts.items() if sum(int(b) for b in c.replace(" ", "")) % 2 == 1)
        metricas = [
            html.Div([html.Div("Resultados"), html.Div(f"{total:,}", className="metric-value")], className="metric"),
            html.Div([html.Div("Paridad impar"), html.Div(f"{impar / total:.1%}", className="metric-value")],
                     className="metric"),
            html.Div([html.Div("Base usada"), html.Div("X", className="metric-value")], className="metric"),
        ]

    if contradiccion:
        aviso = "Alerta clásica: C envía decisiones distintas a A y B."
        clase = "notice notice-warn"
    else:
        aviso = "Experimento ejecutado correctamente sin contradicción clásica."
        clase = "notice"

    return texto_circuito, fig, metricas, aviso, clase


if __name__ == "__main__":
    app.run(debug=True)