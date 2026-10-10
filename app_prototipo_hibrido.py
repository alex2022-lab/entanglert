import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit.visualization import plot_histogram

st.set_page_config(
    page_title="Prototipo híbrido clásico-cuántico",
    page_icon="🔗",
    layout="wide",
)

st.title("Prototipo híbrido clásico-cuántico")
st.caption(
    "Simulación didáctica de tres nodos distribuidos, mensajes contradictorios "
    "y correlaciones de un estado GHZ."
)

st.warning(
    "Es una simulación de software. Las aristas del grafo representan visualmente "
    "la participación de los nodos en un estado cuántico compartido; no representan "
    "una red cuántica física ni garantizan detectar o identificar por sí solas al atacante."
)

# ------------------------- Controles -------------------------
st.sidebar.header("Configuración del experimento")
ataque_clasico = st.sidebar.checkbox(
    "C envía decisiones contradictorias a A y B", value=True
)
alteracion_cuantica = st.sidebar.checkbox(
    "Aplicar una operación X al qubit de C", value=False
)
base_medicion = st.sidebar.radio(
    "Base de medición", ["Z (computacional)", "X (Hadamard + medición)"]
)
shots = st.sidebar.slider("Número de mediciones (shots)", 100, 3000, 1000, 100)
ejecutar = st.sidebar.button("Ejecutar experimento", type="primary")

# Para que la app también muestre un resultado inicial al abrirse.
if "run_experiment" not in st.session_state:
    st.session_state.run_experiment = True
if ejecutar:
    st.session_state.run_experiment = True

# ------------------------- Grafo de la red -------------------------
def dibujar_red(ataque_clasico, alteracion_cuantica):
    G = nx.Graph()
    G.add_nodes_from(["A", "B", "C"])
    G.add_edges_from([("A", "B"), ("A", "C"), ("B", "C")])

    posiciones = {"A": (-1.0, 0.0), "C": (0.0, 0.85), "B": (1.0, 0.0)}
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    nx.draw_networkx_edges(
        G, posiciones, ax=ax, width=2.0, edge_color="#64748b", alpha=0.85
    )
    nx.draw_networkx_nodes(
        G, posiciones, ax=ax, node_size=2300,
        node_color=["#bfdbfe", "#bfdbfe", "#fecaca"], edgecolors="#334155",
        linewidths=1.5,
    )
    nx.draw_networkx_labels(
        G, posiciones, ax=ax, font_size=16, font_weight="bold", font_color="#0f172a"
    )

    ax.text(-1.0, -0.28, "Nodo A", ha="center", fontsize=10)
    ax.text(1.0, -0.28, "Nodo B", ha="center", fontsize=10)
    ax.text(0.0, 1.12, "Nodo C", ha="center", fontsize=10, color="#b91c1c")

    if ataque_clasico:
        ax.annotate(
            "decisión = 1", xy=(-0.72, 0.35), xytext=(-1.15, 0.58),
            arrowprops=dict(arrowstyle="->", color="#2563eb", lw=1.8),
            fontsize=9, color="#1d4ed8", ha="center",
        )
        ax.annotate(
            "decisión = 0", xy=(0.72, 0.35), xytext=(1.12, 0.58),
            arrowprops=dict(arrowstyle="->", color="#dc2626", lw=1.8),
            fontsize=9, color="#b91c1c", ha="center",
        )
        ax.text(
            0, -0.62, "Contradicción clásica detectada",
            ha="center", fontsize=10, color="#b91c1c", fontweight="bold"
        )
    else:
        ax.text(
            0, -0.62, "Mensajes clásicos consistentes",
            ha="center", fontsize=10, color="#166534", fontweight="bold"
        )

    if alteracion_cuantica:
        ax.text(
            0, -0.86, "Operación X aplicada al qubit de C",
            ha="center", fontsize=9, color="#7c3aed"
        )

    ax.set_title("Red distribuida (NetworkX)", fontsize=13, pad=12)
    ax.axis("off")
    fig.tight_layout()
    return fig


# ------------------------- Circuito GHZ -------------------------
def construir_circuito(base, ataque):
    # q0 = A, q1 = B, q2 = C
    qc = QuantumCircuit(3, 3)
    qc.h(0)
    qc.cx(0, 1)
    qc.cx(0, 2)

    if ataque:
        # Intervención de ejemplo sobre el qubit asociado a C.
        qc.x(2)

    if base == "X (Hadamard + medición)":
        # Cambia la base de medición de X a Z mediante H antes de medir.
        qc.h(0)
        qc.h(1)
        qc.h(2)

    qc.measure([0, 1, 2], [0, 1, 2])
    return qc


def analizar_conteos(counts):
    total = sum(counts.values())
    # Qiskit imprime los bits clásicos en orden c2 c1 c0.
    # Convertimos cada cadena a (A, B, C) = (c0, c1, c2).
    registros = []
    for cadena, frecuencia in counts.items():
        bits = cadena.replace(" ", "")[::-1]
        if len(bits) >= 3:
            a, b, c = int(bits[0]), int(bits[1]), int(bits[2])
            registros.append((a, b, c, frecuencia))

    # En la base Z, el estado GHZ ideal produce 000 o 111.
    # Si se aplica X a C, produce 001 o 110, por lo que C difiere de A y B.
    if total == 0:
        return 0.0, 0.0, 0.0

    discrepancia_ab = sum(f for a, b, c, f in registros if a != b) / total
    discrepancia_ac = sum(f for a, b, c, f in registros if a != c) / total
    discrepancia_bc = sum(f for a, b, c, f in registros if b != c) / total
    return discrepancia_ab, discrepancia_ac, discrepancia_bc


# ------------------------- Diseño de la página -------------------------
col_red, col_circuito = st.columns([1, 1.25], gap="large")

with col_red:
    st.subheader("1. Participantes y comunicación")
    st.pyplot(
        dibujar_red(ataque_clasico, alteracion_cuantica),
        use_container_width=True,
    )
    st.markdown(
        "- **A y B:** reciben decisiones de C.\n"
        "- **C:** puede enviar mensajes contradictorios.\n"
        "- **Estado GHZ:** los tres qubits se preparan en un estado entrelazado "
        "para estudiar correlaciones entre mediciones."
    )

with col_circuito:
    st.subheader("2. Preparación y medición cuántica")
    qc_preview = construir_circuito(base_medicion, alteracion_cuantica)
    st.code(qc_preview.draw(output="text"), language="text")
    st.caption(
        "Circuito de tres qubits: H y dos CNOT preparan el estado GHZ. "
        "La operación X opcional modela una intervención sobre el qubit de C. "
        "La medición en X se implementa aplicando H antes de medir."
    )

st.divider()
st.subheader("3. Resultado del experimento")

if st.session_state.run_experiment:
    qc = construir_circuito(base_medicion, alteracion_cuantica)
    simulador = AerSimulator()
    circuito_compilado = transpile(qc, simulador)
    resultado = simulador.run(circuito_compilado, shots=shots).result()
    counts = resultado.get_counts()

    m1, m2, m3 = st.columns(3)
    if base_medicion == "Z (computacional)":
        d_ab, d_ac, d_bc = analizar_conteos(counts)
        m1.metric("Discrepancia A–B", f"{d_ab:.1%}")
        m2.metric("Discrepancia A–C", f"{d_ac:.1%}")
        m3.metric("Discrepancia B–C", f"{d_bc:.1%}")
        st.caption(
            "En la base Z, el GHZ ideal produce resultados iguales para A, B y C. "
            "La discrepancia mide con qué frecuencia una pareja obtiene bits distintos."
        )
    else:
        # En la base X, para GHZ ideal la paridad de los tres bits es par.
        # Una X aplicada a C conmuta con mediciones X, por lo que no se espera que
        # esta operación concreta cambie el patrón de medición X.
        total = sum(counts.values())
        odd_parity = 0
        for cadena, frecuencia in counts.items():
            bits = cadena.replace(" ", "")
            if sum(int(bit) for bit in bits) % 2 == 1:
                odd_parity += frecuencia
        parity_error = odd_parity / total if total else 0.0
        m1.metric("Paridad impar observada", f"{parity_error:.1%}")
        m2.metric("Mediciones", f"{total}")
        m3.metric("Base elegida", "X")
        st.caption(
            "Para el GHZ ideal, las mediciones en X tienen paridad global par. "
            "La operación X en C conmuta con esta medición y no tiene por qué "
            "ser visible en esta base; comparar bases ayuda a caracterizar la intervención."
        )

    hist_fig = plot_histogram(counts)
    st.pyplot(hist_fig, use_container_width=True)

    st.markdown("**Conteos de medición**")
    st.json(dict(sorted(counts.items())))

    # Regla híbrida didáctica: contradicción clásica tiene prioridad.
    if ataque_clasico:
        st.error(
            "DECISIÓN: RECHAZAR LA RONDA — se detectaron decisiones clásicas contradictorias."
        )
        explicacion = (
            "La contradicción entre los mensajes de C basta para rechazar esta ronda "
            "en la regla didáctica. El resultado cuántico se registra como evidencia adicional."
        )
    elif alteracion_cuantica and base_medicion == "Z (computacional)":
        st.warning(
            "DECISIÓN: PENDIENTE DE VERIFICACIÓN — se observa una intervención cuántica en la prueba Z."
        )
        explicacion = (
            "La intervención X sobre el qubit C altera las correlaciones esperadas en Z. "
            "Esto no identifica por sí solo quién causó la alteración."
        )
    else:
        st.success(
            "DECISIÓN: ACEPTAR PROVISIONALMENTE — no se detectó contradicción clásica en esta configuración."
        )
        explicacion = (
            "La aceptación es provisional y depende de los controles incluidos en este ejemplo. "
            "No equivale a una garantía formal de seguridad."
        )
    st.write(explicacion)

else:
    st.info("Configura los controles de la barra lateral y pulsa «Ejecutar experimento».")

st.divider()
st.subheader("4. Cómo interpretar la visualización")
st.markdown(
    """
    - **NetworkX** muestra los participantes y la contradicción clásica entre mensajes.
    - **Qiskit** muestra el circuito que prepara y mide el estado GHZ de tres qubits.
    - **Histograma** muestra cuántas veces se obtuvo cada resultado de medición.
    - **Discrepancias** resumen diferencias entre bits medidos; son señales del experimento,
      no una identificación automática de un nodo malicioso.
    """
)
