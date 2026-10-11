"""Trabajo cuántico y lógica del protocolo Entanglert (port a Qollab).

Este módulo contiene la preparación del estado de Hardy, la construcción
de los circuitos, la ejecución y el análisis del protocolo. Se importa
desde ``main.js``::

    import * as hardy from 'quantum.hardy';

Las funciones se invocan con ``.callPromising(...)`` y devuelven datos
serializables (dicts, listas, números y cadenas) que se desempaquetan en
JavaScript con ``.toJs()``.

Nota: no se crea ningún backend aquí. El backend lo elige quien pulsa Run
en el diálogo "Select QPU" y llega a este módulo como argumento ``backend``.
"""

import math

from qiskit import QuantumCircuit


# ============================================================
# 1. ESTADO DE HARDY Y MEDICIONES
# ============================================================
# Convención:
# U: base computacional. |0> representa +1 y |1> representa -1.
# D: base alternativa de medición.
#
# IMPORTANTE:
# Los ceros de Hardy son propiedades matemáticas del estado ideal y de las
# mediciones. Los conteos de una simulación finita son estimaciones
# estadísticas.

alpha = math.sqrt((math.sqrt(5) - 1) / 2)
beta = math.sqrt(1 - alpha ** 2)

_estado_sin_normalizar = [
    1.0,
    -alpha / beta,
    -alpha / beta,
    -(1 + alpha ** 2) / alpha ** 2,
]

_norma = math.sqrt(sum(abs(x) ** 2 for x in _estado_sin_normalizar))
ESTADO_HARDY = [complex(x / _norma) for x in _estado_sin_normalizar]

Q_MAX = (5 * math.sqrt(5) - 11) / 2

# Los vectores columna definen la base D. La matriz es real, simétrica y
# ortogonal.
BASE_D = [
    [alpha, beta],
    [beta, -alpha],
]

# Unitaria 4x4 (real y ortogonal) cuya primera columna es ESTADO_HARDY.
# Sirve para preparar el estado con ``unitary``, ya que el simulador básico
# de Qollab (BasicSimulator) no reconoce la instrucción ``initialize``.
# El resto de columnas completa la base ortonormal por Gram-Schmidt.
MATRIZ_HARDY = [
    [0.3002831060007776, 0.12410828034667902, 0.14747608195890924, 0.9341723589627159],
    [-0.3819660112501051, 0.9241763718304449, 0.0, 0.0],
    [-0.3819660112501051, -0.15786817126837643, 0.9105929973100294, 0.0],
    [-0.7861513777574234, -0.32491969623290634, -0.38609739509608965, 0.3568220897730895],
]


def construir_circuito_hardy(base1, base2):
    """Construye el circuito para una pareja de mediciones."""
    if base1 not in ("D", "U") or base2 not in ("D", "U"):
        raise ValueError("Las bases deben ser D o U.")

    qc = QuantumCircuit(2, 2)

    # Preparar el estado de Hardy.
    qc.unitary(MATRIZ_HARDY, [0, 1], label="Estado de Hardy")

    # Cambiar de base antes de medir cuando corresponde.
    if base1 == "D":
        qc.unitary(BASE_D, [0], label="Base D")

    if base2 == "D":
        qc.unitary(BASE_D, [1], label="Base D")

    qc.measure([0, 1], [0, 1])

    return qc


def circuito_intercambio():
    """Demostración auxiliar de intercambio de entrelazamiento.

    Prepara dos pares de Bell y mide los qubits centrales. No implementa el
    proyector M específico que utiliza el artículo.
    """
    qc = QuantumCircuit(4, 2)

    # Primer par de Bell: qubits 0 y 1.
    qc.h(0)
    qc.cx(0, 1)

    # Segundo par de Bell: qubits 2 y 3.
    qc.h(2)
    qc.cx(2, 3)

    # Medición de Bell sobre los qubits centrales 1 y 2.
    qc.cx(1, 2)
    qc.h(1)
    qc.measure([1, 2], [0, 1])

    return qc


def normalizar_counts(counts):
    """Normaliza las cadenas de bits devueltas por Qiskit."""
    normalizados = {}
    for bits, cantidad in counts.items():
        clave = bits.replace(" ", "").zfill(2)
        normalizados[clave] = normalizados.get(clave, 0) + cantidad
    return normalizados


def _texto(qc):
    """Dibuja el circuito en texto plano (no requiere Qiskit Visualizations)."""
    dibujo = qc.draw(output="text", fold=-1)
    single = getattr(dibujo, "single_string", None)
    if callable(single):
        return single()
    return str(dibujo)


# ============================================================
# 2. MODELO CLÁSICO DEL COMANDANTE Y CODIFICACIÓN
# ============================================================
# U codifica el bit 0 y D codifica el bit 1 en esta interfaz.
# El modo bizantino introduce una contradicción controlada en los mensajes
# clásicos recibidos por A y B.

def simular_mensajes(bit_c, modo):
    bit_a = int(bit_c)
    bit_b = int(bit_c)

    if modo == "bizantino":
        bit_b = 1 - bit_a

    return {
        "bit_a": bit_a,
        "bit_b": bit_b,
        "contradiccion": bit_a != bit_b,
    }


def evaluar_hardy_estadistico(pruebas, shots):
    """Criterio exploratorio para la interfaz.

    No es una certificación device-independent ni una prueba formal de
    seguridad.
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
    """Une la validación estadística de Hardy con la comparación de mensajes.

    La contradicción se conoce porque el escenario clásico la genera y A/B
    comparan sus mensajes. Hardy no atribuye por sí solo la contradicción a
    un participante concreto.
    """
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
            "hardy_valido": False,
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
            "hardy_valido": True,
        }

    return {
        "titulo": "CONSENSO SIMULADO",
        "clase": "notice notice-ok",
        "detalle": (
            f"A y B reciben el mismo bit ({mensajes['bit_a']}) y "
            "las estadísticas de Hardy pasan el criterio exploratorio."
        ),
        "consenso": True,
        "hardy_valido": True,
    }


# ============================================================
# 3. EJECUCIÓN DEL PROTOCOLO
# ============================================================

def ejecutar_protocolo(backend, shots, par, modo, bit_c):
    """Ejecuta el experimento completo y devuelve todos los resultados."""
    shots = int(shots)

    configuraciones = [
        ("D", "D", "P(-- | D,D)", "11", "cero"),
        ("D", "U", "P(++ | D,U)", "00", "cero"),
        ("U", "D", "P(++ | U,D)", "00", "cero"),
        ("U", "U", "P(++ | U,U)", "00", "positiva"),
    ]

    circuitos_hardy = [
        construir_circuito_hardy(b1, b2)
        for b1, b2, *_ in configuraciones
    ]
    circuito_swap = circuito_intercambio()

    # Un único job con los cinco circuitos (en IonQ solo se permite un job
    # por ejecución).
    job = backend.run(circuitos_hardy + [circuito_swap], shots=shots)
    resultado = job.result()

    pruebas = []
    for i, (b1, b2, nombre, patron, tipo) in enumerate(configuraciones):
        counts = normalizar_counts(resultado.get_counts(i))
        total = sum(counts.values())
        frecuencia = counts.get(patron, 0)
        p = frecuencia / total if total else 0.0

        pruebas.append({
            "nombre": nombre,
            "base1": b1,
            "base2": b2,
            "patron": patron,
            "probabilidad": p,
            "frecuencia": frecuencia,
            "shots": total,
            "tipo": tipo,
        })

    indice_par = {"DD": 0, "DU": 1, "UD": 2, "UU": 3}.get(par, 3)
    texto_circuito = _texto(circuitos_hardy[indice_par])

    counts_swap = normalizar_counts(resultado.get_counts(4))
    texto_intercambio = (
        _texto(circuito_swap)
        + "\n\nResultados de la medición de Bell:\n"
        + str(counts_swap)
        + "\n\nCircuito auxiliar: no implementa el proyector M "
        "específico del artículo."
    )

    mensajes = simular_mensajes(bit_c, modo)
    validacion_hardy = evaluar_hardy_estadistico(pruebas, shots)
    decision = decidir_protocolo(pruebas, mensajes, shots)

    return {
        "pruebas": pruebas,
        "texto_circuito": texto_circuito,
        "texto_intercambio": texto_intercambio,
        "q_max": Q_MAX,
        "mensajes": mensajes,
        "validacion_hardy": validacion_hardy,
        "decision": decision,
    }
