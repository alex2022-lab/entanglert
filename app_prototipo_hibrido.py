import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit.visualization import plot_histogram

st.set_page_config(page_title="Entanglert", page_icon="⚛️", layout="wide")


# ---------- Funciones ----------
def construir_circuito(base, intervencion_c):
    # q0 = A, q1 = B, q2 = C
    qc = QuantumCircuit(3, 3)
    qc.h(0)
    qc.cx(0, 1)
    qc.cx(0, 2)  # Prepara un estado GHZ
    if intervencion_c:
        qc.x(2)  # Puerta Pauli-X sobre el qubit asociado a C
    if base == "X":
        # Medición en base X: aplicar H antes de medir en Z
        qc.h(0)
        qc.h(1)
        qc.h(2)
    qc.measure([0, 1, 2], [0, 1, 2])
    return qc


def dibujar_red(contradiccion, intervencion_c):
    grafo = nx.Graph()
    grafo.add_nodes_from(["A", "B", "C"])
    grafo.add_edges_from([("A", "B"), ("A", "C"), ("B", "C")])

    # Posiciones con mayor separación entre los nodos
    pos = {
        "A": (-1.55, 0.0),
        "B": (1.55, 0.0),
        "C": (0.0, 1.55),
    }

    fig, ax = plt.subplots(figsize=(9, 6), dpi=120)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    nx.draw_networkx_edges(
        grafo, pos, ax=ax,
        width=2.2, edge_color="#94a3b8", alpha=0.8
    )

    # El orden corresponde a A, B, C: C queda rojo
    nx.draw_networkx_nodes(
        grafo, pos, ax=ax,
        nodelist=["A", "B", "C"],
        node_size=3400,
        node_color=["#bfdbfe", "#bfdbfe", "#fecaca"],
        edgecolors=["#3b82f6", "#3b82f6", "#dc2626"],
        linewidths=2,
    )

    nx.draw_networkx_labels(
        grafo, pos, ax=ax,
        font_size=19, font_weight="bold", font_color="#1e293b"
    )

    ax.text(-1.55, -0.38, "Nodo A", ha="center", va="top",
            fontsize=12, color="#334155")
    ax.text(1.55, -0.38, "Nodo B", ha="center", va="top",
            fontsize=12, color="#334155")
    ax.text(0, 2.00, "Nodo C", ha="center", va="bottom",
            fontsize=13, color="#b91c1c", fontweight="bold")

    if contradiccion:
        ax.annotate(
            "SÍ (1)",
            xy=(-0.95, 0.45), xytext=(-0.78, 1.00),
            fontsize=12, fontweight="bold", color="#1d4ed8",
            ha="center",
            arrowprops=dict(
                arrowstyle="->", color="#2563eb", lw=2.5,
                connectionstyle="arc3,rad=0.12"
            ),
        )
        ax.annotate(
            "NO (0)",
            xy=(0.95, 0.45), xytext=(0.78, 1.00),
            fontsize=12, fontweight="bold", color="#b91c1c",
            ha="center",
            arrowprops=dict(
                arrowstyle="->", color="#dc2626", lw=2.5,
                connectionstyle="arc3,rad=-0.12"
            ),
        )
        ax.text(
            0, -0.95, "⚠ C envía mensajes contradictorios",
            ha="center", fontsize=12, color="#b91c1c",
            fontweight="bold"
        )
    else:
        ax.text(
            0, -0.95, "C no está configurado para contradecir",
            ha="center", fontsize=12, color="#166534"
        )

    if intervencion_c:
        ax.text(
            0, -1.28, "Puerta X aplicada al qubit de C",
            ha="center", fontsize=11, color="#7c3aed"
        )

    ax.set_title(
        "Red de participantes", fontsize=17,
        fontweight="bold", color="#0f172a", pad=22
    )
    ax.set_xlim(-2.25, 2.25)
    ax.set_ylim(-1.55, 2.45)
    ax.axis("off")
    fig.tight_layout(pad=2)
    return fig


def discrepancias_z(counts):
    total = sum(counts.values())
    if not total:
        return 0.0, 0.0, 0.0

    ab = ac = bc = 0
    for cadena, frecuencia in counts.items():
        # Qiskit presenta los bits clásicos como c2 c1 c0.
        # c0 corresponde a A, c1 a B y c2 a C.
        bits = cadena.replace(" ", "")[::-1]
        a, b, c = map(int, bits[-3:])
        ab += frecuencia * (a != b)
        ac += frecuencia * (a != c)
        bc += frecuencia * (b != c)

    return ab / total, ac / total, bc / total


# ---------- Encabezado ----------
st.title("E N T A N G L E R T")
st.caption(
    "Explora qué ocurre con tres nodos cuando aparecen mensajes "
    "contradictorios o se interviene un qubit."
)

with st.expander(
    "ⓘ Antes de empezar: ¿qué representa esta simulación?",
    expanded=False
):
    st.write(
        "**NetworkX** dibuja los nodos y los mensajes clásicos. "
        "**Qiskit** simula tres qubits preparados en un estado GHZ "
        "y mide sus resultados."
    )
    st.info(
        "Es una simulación de software, no una red cuántica física. "
        "Una discrepancia puede generar una alerta, pero no demuestra "
        "por sí sola quién la causó."
    )


# ---------- Controles de configuración ----------
st.sidebar.header("Experimento")
st.sidebar.caption("Activa solo los cambios que quieras probar.")

col_check, col_info = st.sidebar.columns([0.88, 0.12])
with col_check:
    contradiccion = st.checkbox(
        "C envía mensajes contradictorios", value=True
    )
with col_info:
    with st.popover("ⓘ"):
        st.markdown("**Contradicción clásica**")
        st.write(
            "C le dice ‘sí’ (1) a A y ‘no’ (0) a B. Como las decisiones "
            "no coinciden, los participantes pueden detectar que "
            "recibieron información diferente."
        )

col_check_x, col_info_x = st.sidebar.columns([0.88, 0.12])
with col_check_x:
    intervencion_c = st.checkbox(
        "Intervenir el qubit de C con X", value=False
    )
with col_info_x:
    with st.popover("ⓘ"):
        st.markdown("**Una operación cuántica, no un mensaje**")
        st.write(
            "La puerta X intercambia |0⟩ y |1⟩. Aquí se aplica al qubit "
            "asociado a C para estudiar cómo cambia el resultado de la "
            "medición. Es una intervención controlada del experimento; "
            "no representa por sí sola a un atacante real."
        )

col_base, col_base_info = st.sidebar.columns([0.82, 0.18])
with col_base:
    st.markdown("**Cómo medir los qubits**")
with col_base_info:
    with st.popover(""):
        st.markdown("**Z · medición directa**")
        st.write(
            "Se mide cada qubit en la base computacional y se obtiene "
            "0 o 1."
        )
        st.markdown("**X · medir en otra base**")
        st.write(
            "Se aplica una puerta Hadamard (H) a cada qubit antes de "
            "medir. Así se estudian las correlaciones en la base X; "
            "no significa hacer más mediciones."
        )

base_label = st.sidebar.radio(
    "Selecciona la base",
    ["Z · medición directa", "X · medir en otra base"],
    index=0,
    label_visibility="collapsed",
)
base = "Z" if base_label.startswith("Z") else "X"

col_shots, col_shots_info = st.sidebar.columns([0.88, 0.12])
with col_shots:
    shots = st.slider(
        "Repeticiones del experimento", 100, 3000, 1000, 100
    )
with col_shots_info:
    with st.popover("ⓘ"):
        st.markdown("**¿Qué son los shots?**")
        st.write(
            "El circuito se ejecuta muchas veces con la misma "
            "configuración. Con 1000 repeticiones se obtienen 1000 "
            "resultados para contar patrones. Más repeticiones suelen "
            "dar frecuencias más estables, pero no hacen que la "
            "simulación sea más cuántica."
        )

ejecutar = st.sidebar.button(
    "▶ Ejecutar experimento", type="primary", use_container_width=True
)


# ---------- Visualización principal ----------
# Se da un poco más de ancho a la red que al circuito.
red_col, quantum_col = st.columns([1.25, 1], gap="large")

with red_col:
    st.subheader("1. La red")
    fig_red = dibujar_red(contradiccion, intervencion_c)
    st.pyplot(fig_red, use_container_width=True)
    plt.close(fig_red)
    st.caption(
        "Los nodos representan participantes y las flechas, mensajes "
        "clásicos. No representan canales cuánticos físicos."
    )

with quantum_col:
    st.subheader("2. El circuito cuántico")
    circuito_preview = construir_circuito(base, intervencion_c)
    st.code(circuito_preview.draw(output="text"), language="text")
    with st.expander("ⓘ ¿Cómo leer este circuito?"):
        st.write(
            "Cada línea horizontal representa un qubit: A, B o C. "
            "H prepara una superposición; las puertas CX preparan el "
            "estado GHZ. La X opcional interviene el qubit de C. "
            "Las mediciones producen bits clásicos."
        )


# ---------- Resultados ----------
st.divider()
st.subheader("3. Resultado")

if ejecutar:
    circuito = construir_circuito(base, intervencion_c)
    simulador = AerSimulator()

    with st.spinner("Ejecutando las mediciones..."):
        compilado = transpile(circuito, simulador)
        counts = simulador.run(
            compilado, shots=shots
        ).result().get_counts()

    st.success("¡Experimento terminado!")

    if base == "Z":
        d_ab, d_ac, d_bc = discrepancias_z(counts)
        c1, c2, c3 = st.columns(3)
        c1.metric("A frente a B", f"{d_ab:.1%}")
        c2.metric("A frente a C", f"{d_ac:.1%}")
        c3.metric("B frente a C", f"{d_bc:.1%}")

        with st.expander("ⓘ ¿Qué significa ‘discrepancia’?"):
            st.write(
                "Es la proporción de repeticiones en que dos nodos "
                "obtuvieron bits distintos. En la base Z, el estado GHZ "
                "ideal sin intervención produce 000 o 111. La puerta X "
                "sobre C invierte el bit de C, por lo que este difiere "
                "de A y B en el modelo ideal."
            )
    else:
        total = sum(counts.values())
        impar = sum(
            frecuencia
            for cadena, frecuencia in counts.items()
            if sum(int(bit) for bit in cadena.replace(" ", "")) % 2 == 1
        )

        c1, c2, c3 = st.columns(3)
        c1.metric("Resultados obtenidos", f"{total:,}")
        c2.metric(
            "Paridad impar",
            f"{impar / total:.1%}" if total else "—"
        )
        c3.metric("Base usada", "X")

        with st.expander("ⓘ ¿Qué significa paridad?"):
            st.write(
                "Se suman los tres bits de cada resultado. Si la suma "
                "es impar, como en 001, se cuenta como paridad impar. "
                "En este circuito GHZ ideal, la medición conjunta en X "
                "permite estudiar una correlación global. Aplicar X a C "
                "no tiene por qué cambiar esta prueba concreta."
            )

    hist_fig = plot_histogram(counts)
    st.pyplot(hist_fig, use_container_width=True)
    plt.close(hist_fig)

    with st.expander("Ver conteos exactos"):
        st.json(dict(sorted(counts.items())))

    st.markdown("#### Lectura del escenario")
    if contradiccion:
        st.error(
            "**Alerta clásica:** en el escenario configurado, C envía "
            "decisiones distintas a A y B. La regla demostrativa rechaza "
            "esta ronda por contradicción."
        )
    elif intervencion_c and base == "Z":
        st.warning(
            "**Resultado cuántico para revisar:** la intervención X "
            "cambia el patrón esperado en la base Z. Esto no identifica "
            "automáticamente quién causó el cambio."
        )
    else:
        st.success(
            "**Sin contradicción clásica configurada.** Revisa el "
            "histograma y las métricas para interpretar el resultado "
            "cuántico de este escenario."
        )
else:
    st.info(
        "Elige la configuración de la izquierda y pulsa "
        "**Ejecutar experimento** para generar los resultados."
    )


with st.expander("ⓘ Glosario breve"):
    st.markdown(
        "- **Qubit:** unidad básica de información cuántica simulada.\n"
        "- **GHZ:** estado entrelazado de tres qubits usado para estudiar correlaciones.\n"
        "- **Hadamard (H):** puerta que cambia la base de medición.\n"
        "- **X:** puerta que intercambia los estados |0⟩ y |1⟩.\n"
        "- **Shot:** una repetición del circuito.\n"
        "- **Histograma:** barras que muestran cuántas veces apareció cada resultado."
    )
