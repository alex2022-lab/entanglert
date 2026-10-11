# Entanglert

**Correlaciones de Hardy y acuerdo bizantino** — una exploración interactiva que conecta un fenómeno fundacional de la mecánica cuántica (la paradoja de Hardy) con un problema clásico de sistemas distribuidos (el acuerdo bizantino).

> This effort is supported by Qollab & IonQ.

---

## Índice

1. [¿Qué problema resuelve?](#qué-problema-resuelve)
2. [Qué hace el programa](#qué-hace-el-programa)
3. [Cómo ejecutarlo](#cómo-ejecutarlo)
4. [Cómo interpretar los resultados](#cómo-interpretar-los-resultados)
5. [Arquitectura y archivos](#arquitectura-y-archivos)
6. [Cómo replicarlo o extenderlo](#cómo-replicarlo-o-extenderlo)
7. [Bibliotecas externas, plantillas y licencias](#bibliotecas-externas-plantillas-y-licencias)
8. [Criterios de evaluación](#criterios-de-evaluación)
9. [Licencia y autores](#licencia-y-autores)

---

## ¿Qué problema resuelve?

El **acuerdo bizantino** (problema de los generales bizantinos) es la dificultad de lograr consenso en una red distribuida cuando uno de los nodos puede fallar o, peor, **mentir de forma maliciosa**. En este modelo, un comandante `C` debe transmitir un bit a dos participantes `A` y `B`:

- En el escenario **honesto**, `C` envía el mismo bit a ambos.
- En el escenario **bizantino**, `C` envía mensajes **contradictorios** (a `A` le dice `0` y a `B` le dice `1`).

El proyecto explora de forma **didáctica y visual** si las correlaciones cuánticas —en concreto las **correlaciones de Hardy**— pueden servir como capa de verificación de consistencia, y deja claro cuál es su alcance real: las mediciones de Hardy validan que las correlaciones cuánticas cumplen lo esperado, pero **no identifican por sí solas al nodo traidor**; la contradicción se detecta comparando los mensajes clásicos.

## Qué hace el programa

`Entanglert` es una presentación interactiva de **7 diapositivas** que:

1. Introduce la red de tres nodos y el objetivo.
2. Permite configurar el **comportamiento de C** (honesto / bizantino).
3. Permite elegir el **bit original** que C desea comunicar.
4. Explica y configura el número de **shots** (repeticiones) de la medición cuántica.
5. Muestra la **red distribuida** (grafo SVG interactivo) y ejecuta el experimento.
6. Presenta las **correlaciones de Hardy** (métricas y gráfico) y los **circuitos** de Qiskit.
7. Presenta la **decisión** combinada del escenario.

La parte cuántica ejecuta **cuatro experimentos de Hardy** (mediciones en las bases `D-D`, `D-U`, `U-D` y `U-U`) y una demostración auxiliar de **intercambio de entrelazamiento** con dos pares de Bell. Con los conteos resultantes:

- Calcula las probabilidades de los cuatro patrones.
- Verifica el criterio de Hardy (tres probabilidades ~0 y una positiva).
- Simula la capa clásica de mensajes (`simular_mensajes`).
- Combina ambas capas en una **decisión exploratoria** con tres desenlaces:

| Desenlace | Condición |
|---|---|
| **TRANSMISIÓN NO VALIDADA** | Las correlaciones de Hardy no pasan el criterio. |
| **INCONSISTENCIA ENTRE MENSAJES** | Hardy pasa, pero A y B reciben bits distintos. |
| **CONSENSO SIMULADO** | Hardy pasa y A y B reciben el mismo bit. |

## Cómo ejecutarlo

### En Qollab (recomendado)

El proyecto está pensado para el runtime **JS / Qiskit** de Qollab, que ejecuta Python (Pyodide) en el navegador.

1. Crea un proyecto nuevo en Qollab y sube estos archivos en la **raíz**:
   - `index.html` + `main.js` → activan el modo **proyecto JS/HTML**.
   - `main.css` → hoja de estilos (la carga el runtime automáticamente).
   - `hardy.py` → módulo Python importado desde `main.js` como `hardy`.
   - `requirements.txt` → `qiskit>=2.5.2,<3.0.0`.
2. Pulsa **Run** y elige un backend en el diálogo **Select QPU**.
3. Navega con las flechas, configura el escenario y pulsa **Ejecutar experimento**.

> **Nota sobre IonQ:** los proyectos JS corren en un *iframe* aislado (con *origin `null`*) que puede no alcanzar la API de IonQ (el sandbox solo permite GET/OPTIONS). Para depurar y ver los resultados usa el **simulador integrado** (gratis y local). El código ya usa un único *job* multi-circuito y puertas estándar (`z`, `ry`, `cx`, `h`), por lo que es compatible con el *gateset* de IonQ; la limitación restante es de red, no de circuitos.

### Localmente (solo la lógica cuántica)

```bash
pip install "qiskit>=2.5.2,<3.0.0"
```

```python
# driver_local.py (fuera de la carpeta del proyecto de Qollab)
from qiskit.providers.basic_provider import BasicSimulator
import hardy

backend = BasicSimulator()
r = hardy.ejecutar_protocolo(backend, shots=3000, par="UU", modo="honesto", bit_c=0)

for p in r["pruebas"]:
    print(p["nombre"], f"{p['probabilidad']:.4f}", f"{p['frecuencia']}/{p['shots']}")
print("q máximo teórico:", f"{r['q_max']:.3%}")
print("Decisión:", r["decision"]["titulo"])
```

## Cómo interpretar los resultados

- **Las tres primeras condiciones deben ser ~0**: `P(-- | D,D)`, `P(++ | D,U)` y `P(++ | U,D)` son, en el estado de Hardy ideal, exactamente cero.
- **La condición U-U debe ser positiva**: `P(++ | U,U)` vale en el límite ideal `Q_MAX = (5√5 − 11)/2 ≈ 9.017 %`.
- El **criterio exploratorio** compara cada probabilidad con un umbral `max(0.01, 5/shots)` (un resultado finito no es prueba formal de "cero exacto").
- La **decisión final** cruza la validación de Hardy con la consistencia de los mensajes clásicos: si Hardy falla, la transmisión queda sin validar; si Hardy pasa pero los bits difieren, hay inconsistencia; si ambos coinciden, se registra consenso en este escenario didáctico.

**Límite científico:** este prototipo no reproduce el protocolo *device-independent* completo del artículo. La contradicción se detecta comparando mensajes clásicos; Hardy no identifica automáticamente al responsable.

## Arquitectura y archivos

```
.
├── index.html          # Estructura de las 7 diapositivas (deck)
├── main.css            # Estilos del deck, red y componentes
├── main.js             # UI: navegación, grafo SVG, previsualización, render
├── hardy.py            # Lógica cuántica y del protocolo (importado desde main.js)
├── requirements.txt    # qiskit>=2.5.2,<3.0.0
├── diapositivas.py     # Prototipo original en Dash (referencia)
└── LICENSE             # MIT
```

- **Separación de responsabilidades:** la física (estado de Hardy, circuitos, análisis) vive en `hardy.py`; la presentación (deck, grafo, métricas) vive en `main.js` + `index.html` + `main.css`.
- **Flujo de datos:** `main.js` llama a `hardy.ejecutar_protocolo.callPromising(backend, shots, par, modo, bit)` y recibe un diccionario con `pruebas`, `texto_circuito`, `texto_intercambio`, `q_max`, `mensajes`, `validacion_hardy` y `decision`.
- **Compatibilidad de puertas:** el estado de Hardy se prepara con `Ry(α) · CX · Ry(β)⊗Ry(β)` (ángulos `ALPHA_PREP`, `BETA_PREP`) y la medición en base D con `Z · Ry(θ)` (`THETA_D`), en lugar de `initialize`/`unitary`, que ni `BasicSimulator` ni el *gateset* de IonQ aceptan.
- **Un solo job:** los 5 circuitos se envían en una única llamada `backend.run([...])` para respetar el límite de "un job por ejecución" de IonQ.
- **Sin dependencias de UI externas:** el grafo (SVG), el gráfico de barras y el *deck* están escritos a mano.

## Cómo replicarlo o extenderlo

1. **Cambiar el número de shots:** modifica `min`/`max`/`step` del `<input type="range" id="shots">` en `index.html`.
2. **Añadir una base de medición:** extiende `configuraciones` en `ejecutar_protocolo` (`hardy.py`) y las opciones del `<select id="circuit-pair">`.
3. **Cambiar el criterio estadístico:** edita `evaluar_hardy_estadistico` en `hardy.py`.
4. **Nuevo protocolo cuántico:** reemplaza `construir_circuito_hardy` y `circuito_intercambio` por tus propios circuitos; la interfaz (métricas, gráfico, decisión) se reutiliza.
5. **Añadir una diapositiva:** duplica un `<section class="slide-section">` en `index.html`, actualiza `TOTAL_SLIDES` en `main.js` y ajusta `SLIDE_EJECUCION`/`SLIDE_RESULTADOS`.

Para contribuir, bifurca el proyecto, haz los cambios en `hardy.py` (física) o en los archivos de la interfaz, y abre un *pull request*.

## Bibliotecas externas, plantillas y licencias

El proyecto **no utiliza plantillas ni código de terceros**: toda la interfaz (deck de diapositivas, grafo de red, gráfico de barras) y la lógica del protocolo son código original.

Dependencias externas (todas de código abierto y con autorización de uso):

| Dependencia | Uso | Licencia |
|---|---|---|
| [Qiskit](https://www.ibm.com/quantum/qiskit) | SDK de circuitos y ejecución | Apache License 2.0 |
| `qiskit-ionq` | Cliente para backends de IonQ (provisto por Qollab) | Apache License 2.0 |
| [Manrope](https://fonts.google.com/specimen/Manrope) | Tipografía (opcional, con *fallback* a fuentes del sistema) | SIL Open Font License 1.1 |

Confirmación de licencias: Qiskit y `qiskit-ionq` se distribuyen bajo **Apache 2.0**, que permite uso, modificación y distribución sin restricción adicional; Manrope está bajo **OFL 1.1**. El equipo cuenta con la autorización necesaria para usar estas bibliotecas en este proyecto (el proyecto es, además, un esfuerzo apoyado por **Qollab & IonQ**). La fuente Manrope no se carga por red en tiempo de ejecución (se usa solo como preferencia tipográfica con *fallback* local).

## Criterios de evaluación

### Novedad

Conecta dos mundos que rara vez se presentan juntos: la **paradoja de Hardy** (correlaciones cuánticas no locales) y el **acuerdo bizantino** (consenso en sistemas distribuidos). En lugar de un ejemplo de libro, ejecuta circuitos cuánticos reales en el navegador y cruza su validación estadística con un modelo clásico de mensajes, dejando explícito qué aporta cada capa y qué **no** demuestra. La descomposición del estado de Hardy a puertas estándar (`Ry`/`CX`) es una solución técnica propia que hace el circuito portable entre `BasicSimulator` y los backends de IonQ.

### Ejecución técnica

- Runtime **JS/Qiskit** de Qollab: Python (Pyodide) para la física, HTML/CSS/JS para la presentación.
- Presentación de 7 diapositivas con navegación bloqueada hasta ejecutar el experimento.
- Grafo de red en **SVG** interactivo (selección de nodos/canales con atenuado), gráfico de barras y previsualización dinámica del escenario, todo sin librerías externas.
- Un único *job* multi-circuito para cumplir el límite de "un job por run" de IonQ.
- Manejo de errores que distingue los fallos de red (IonQ) y muestra un mensaje claro.

### Impacto

- **Educativo:** hace accesible la intuición de que las correlaciones cuánticas son estadísticas y de que la detección de un nodo malicioso requiere comparar mensajes, no medir una única correlación.
- **Didáctico y reutilizable:** estructura limpia (física separada de interfaz) que sirve de plantilla para otros protocolos cuánticos interactivos.
- **Demostración honesta:** explicita los límites del modelo, evitando sobrevender los resultados.

### Documentación

- Este `README` cubre problema, funcionamiento, ejecución, interpretación y replicación.
- Las diapositivas guían al usuario con explicaciones (qué son los *shots*, qué significa cada desenlace).
- Comentarios en `hardy.py` explican las decisiones técnicas (descomposición de puertas, un único job, convención de bases).

## Licencia y autores

This project is distributed under the [MIT License](./LICENSE).

Copyright (c) 2026 **Camila Cartes, Víctor Mardones, Alex Sagredo**.
