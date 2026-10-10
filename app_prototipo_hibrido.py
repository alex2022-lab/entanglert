import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit.visualization import plot_histogram

st.set_page_config(page_title="Entanglert", page_icon="", layout="wide")

# ---------- Funciones ----------
def construir_circuito(base, intervencion_c):
    # q0 = A, q1 = B, q2 = C
    qc = QuantumCircuit(3, 3)
    qc.h(0)
    qc.cx(0, 1)
    qc.cx(0, 2)  # prepara el estado GHZ
    if intervencion_c:
        qc.x(2)  # operación Pauli-X sobre el qubit asignado a C
    if base == "X":
        # Medir en X equivale a aplicar H y luego medir en Z.
        qc.h(0)
        qc.h(1)
        qc.h(2)
    qc.measure([0, 1, 2], [0, 1, 2])
    return qc


def dibujar_red(contradiccion, intervencion_c):
    grafo = nx.Graph()
    grafo.add_nodes_from(["A", "B", "C"])
    grafo.add_edges_from([("A", "B"), ("A", "C"), ("B", "C")])
    pos = {"A": (-1, 0), "C": (0, 0.85), "B": (1, 0)}
    fig, ax = plt.subplots(figsize=(6, 3.7))
    nx.draw_networkx_edges(grafo, pos, ax=ax, width=2, edge_color="#94a3b8")
    nx.draw_networkx_nodes(
        grafo, pos, ax=ax, node_size=2100,
        node_color=["#bfdbfe", "#fecaca", "#bfdbfe"],
        edgecolors="#475569", linewidths=1.4
    )
    nx.draw_networkx_labels(grafo, pos, ax=ax, font_size=15, font_weight="bold")
    ax.text(-1, -0.28, "Nodo A", ha="center", fontsize=10)
    ax.text(1, -0.28, "Nodo B", ha="center", fontsize=10)
    ax.text(0, 1.12, "Nodo C", ha="center", fontsize=10, color="#b91c1c")
    if contradiccion:
        ax.annotate("‘Sí’ (1)", xy=(-0.48, 0.35), xytext=(-1.0, 0.56),
                    arrowprops=dict(arrowstyle="->", color="#2563eb", lw=1.8),
                    fontsize=10, color="#1d4ed8", ha="center")
        ax.annotate("‘No’ (0)", xy=(0.48, 0.35), xytext=(1.0, 0.56),
                    arrowprops=dict(arrowstyle="->", color="#dc2626", lw=1.8),
                    fontsize=10, color="#b91c1c", ha="center")
        ax.text(0, -0.58, "C envía mensajes contradictorios", ha="center",
                fontsize=9, color="#b91c1c", fontweight="bold")
    else:
        ax.text(0, -0.58, "No se configuró contradicción clásica", ha="center",
                fontsize=9, color="#166534")
    if intervencion_c:
        ax.text(0, -0.83, "Intervención X en el qubit de C", ha="center",
                fontsize=9, color="#7c3aed")
    ax.set_title("Los tres nodos", fontsize=13, pad=10)
    ax.axis("off")
    fig.tight_layout()
    return fig


def discrepancias_z(counts):
    total = sum(counts.values())
    if not total:
        return 0.0, 0.0, 0.0
    ab = ac = bc = 0
    for cadena, frecuencia in counts.items():
        bits = cadena.replace(" ", "")[::-1]  # orden A, B, C
        a, b, c = map(int, bits[-3:])
        ab += frecuencia * (a != b)
        ac += frecuencia * (a != c)
        bc += frecuencia * (b != c)
    return ab / total, ac / total, bc / total


# ---------- Encabezado ----------
st.title("E N T A N G L E R T")
st.caption("Explora qué ocurre con tres nodos cuando aparecen mensajes contradictorios o se interviene un qubit.")
with st.expander("ⓘ Antes de empezar: ¿qué representa esta simulación?", expanded=False):
    st.write("**NetworkX** dibuja los nodos y los mensajes clásicos. **Qiskit** simula tres qubits preparados en un estado GHZ y mide sus resultados.")
    st.info("Es una simulación de software, no una red cuántica física. Una discrepancia puede generar una alerta, pero no demuestra por sí sola quién la causó.")

# ---------- Controles compactos con ayuda contextual ----------

st.sidebar.header("Experimento")
st.sidebar.caption("Activa solo los cambios que quieras probar")

# Checkbox e ícono en una misma fila
col_check, col_info = st.sidebar.columns([0.88, 0.12])

with col_check:
    contradiccion = st.checkbox(
        "C envía mensajes contradictorios",
        value=True
    )

with col_info:
    with st.popover(""):
        st.markdown("**Contradicción clásica**")
        st.write(
            "C le dice ‘sí’ (1) a A y ‘no’ (0) a B. "
            "Como las instrucciones no coinciden, A y B "
            "pueden detectar que recibieron información diferente."
        )


col_check_x, col_info_x = st.sidebar.columns([0.88, 0.12])

with col_check_x:
    intervencion_c = st.checkbox(
        "Intervenir el qubit de C con X",
        value=False
    )

with col_info_x:
    with st.popover("ⓘ"):
        st.markdown("**Una operación cuántica, no un mensaje**")
        st.write(
            "La puerta X cambia |0⟩ por |1⟩ y |1⟩ por |0⟩. "
            "Aquí se aplica al qubit asociado a C para estudiar "
            "cómo cambia el resultado de la medición. Es una "
            "intervención controlada del experimento; no representa "
            "por sí sola a un atacante real."
        )

base_label = st.sidebar.radio("Cómo medir los qubits", ["Z · medición directa", "X · medir en otra base"], index=0)
base = "Z" if base_label.startswith("Z") else "X"
with st.sidebar.popover(""):
    st.markdown("**Z · medición directa**")
    st.write("Se mide el qubit directamente y se obtiene 0 o 1. Es como leer el valor en la base computacional.")
    st.markdown("**X · otra perspectiva**")
    st.write("Antes de medir, el circuito aplica una puerta Hadamard (H) a cada qubit. Después se mide y se estudian las correlaciones desde la base X. No es ‘más medición’: es medir de otra manera.")

shots = st.sidebar.slider("Repeticiones del experimento", 100, 3000, 1000, 100)
with st.sidebar.popover(""):
    st.write("También se llaman *shots*. El circuito se ejecuta muchas veces con la misma configuración. Con 1000 repeticiones, por ejemplo, se obtienen 1000 resultados para contar patrones. Más repeticiones suelen dar frecuencias más estables, pero no hacen que la simulación sea más ‘cuántica’.")

ejecutar = st.sidebar.button("▶ Ejecutar experimento", type="primary", use_container_width=True)

# ---------- Vista principal ----------
red_col, quantum_col = st.columns([1, 1.15], gap="large")
with red_col:
    st.subheader("1. La red")
    st.pyplot(dibujar_red(contradiccion, intervencion_c), use_container_width=True)
    st.caption("El dibujo representa participantes y mensajes clásicos; las líneas no son canales cuánticos físicos.")
with quantum_col:
    st.subheader("2. El circuito cuántico")
    circuito_preview = construir_circuito(base, intervencion_c)
    st.code(circuito_preview.draw(output="text"), language="text")
    with st.expander("ⓘ ¿Cómo leer este circuito?"):
        st.write("Cada línea horizontal representa un qubit: A, B o C. H prepara una superposición; las puertas CX enlazan los qubits y preparan el estado GHZ. La X opcional interviene el qubit de C. Las cajas de medición convierten el resultado en bits clásicos.")

st.divider()
st.subheader("3. Resultado")
if ejecutar:
    circuito = construir_circuito(base, intervencion_c)
    simulador = AerSimulator()
    with st.spinner("Ejecutando las mediciones..."):
        compilado = transpile(circuito, simulador)
        counts = simulador.run(compilado, shots=shots).result().get_counts()
    st.success("¡Experimento terminado!")

    if base == "Z":
        d_ab, d_ac, d_bc = discrepancias_z(counts)
        c1, c2, c3 = st.columns(3)
        c1.metric("A frente a B", f"{d_ab:.1%}")
        c2.metric("A frente a C", f"{d_ac:.1%}")
        c3.metric("B frente a C", f"{d_bc:.1%}")
        with st.expander("ⓘ ¿Qué significa ‘discrepancia’?"):
            st.write("Es la proporción de repeticiones en que dos nodos obtuvieron bits distintos. En la base Z, el GHZ ideal sin intervención produce 000 o 111, por lo que los tres bits coinciden. La operación X sobre C produce un patrón donde C difiere de A y B.")
    else:
        total = sum(counts.values())
        impar = sum(freq for cadena, freq in counts.items()
                    if sum(int(b) for b in cadena.replace(" ", "")) % 2 == 1)
        c1, c2, c3 = st.columns(3)
        c1.metric("Resultados obtenidos", f"{total:,}")
        c2.metric("Paridad impar", f"{impar / total:.1%}" if total else "—")
        c3.metric("Base usada", "X")
        with st.expander("ⓘ ¿Qué significa paridad?"):
            st.write("Se suman los tres bits de cada resultado. Si la suma es impar (por ejemplo, 001), cuenta como paridad impar. En este circuito GHZ ideal, medir los tres qubits en X permite comprobar una correlación global; la puerta X en C no tiene por qué cambiar esta prueba concreta.")

    hist_fig = plot_histogram(counts)
    st.pyplot(hist_fig, use_container_width=True)
    with st.expander("Ver conteos exactos"):
        st.json(dict(sorted(counts.items())))

    st.markdown("#### Lectura del escenario")
    if contradiccion:
        st.error("**Alerta clásica:** A y B recibieron decisiones distintas de C. La regla demostrativa rechaza esta ronda por contradicción.")
    elif intervencion_c and base == "Z":
        st.warning("**Resultado cuántico para revisar:** la intervención X cambia el patrón esperado en la base Z. Esto no identifica automáticamente quién causó el cambio.")
    else:
        st.success("**Sin contradicción clásica configurada.** Revisa el histograma y las métricas para interpretar el resultado cuántico de este escenario.")
else:
    st.info("Elige la configuración de la izquierda y pulsa **Ejecutar experimento** para generar los resultados.")

with st.expander("ⓘ Glosario breve"):
    st.markdown("- **Qubit:** unidad básica de información cuántica simulada.\n- **GHZ:** estado entrelazado de tres qubits usado para estudiar correlaciones.\n- **Hadamard (H):** puerta que cambia la base de medición.\n- **X:** puerta que intercambia los estados |0⟩ y |1⟩.\n- **Shot:** una repetición del circuito.\n- **Histograma:** barras que muestran cuántas veces apareció cada resultado.")
