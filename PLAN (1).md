# PLAN.md — Studio Ghibli Knowledge Graph SPA

## Objetivo
Construir una Single Page Application estática que muestre un **knowledge graph** del universo de Studio Ghibli, donde la **ontología se construye bottom-up con técnicas de NLP** (spaCy: NER + dependency parsing) sobre artículos de Wikipedia en inglés. El entregable final es una **URL productiva en GitHub Pages**.

## Restricciones de diseño (no negociables)
- **Todo el procesamiento NLP es offline.** El pipeline en Python corre una vez, genera `graph.json`, y la SPA solo lee ese JSON. No hay backend en runtime.
- **GitHub Pages** sirve únicamente archivos estáticos (`index.html`, `graph.json`, assets). No hay servidor.
- **La ontología debe ser defendible como NLP**, no como "un LLM lo hizo". La columna vertebral es spaCy. Si se usa un LLM, solo para normalización auxiliar, nunca para la extracción primaria.
- **Visualización: D3.js force-directed graph.**

---

## Parte 1 — Pipeline NLP (Python, offline)

### 1.1 Corpus
Descargar el texto de ~15 artículos de Wikipedia (inglés) usando la librería `wikipedia` o `wikipedia-api`. Lista fija:

```
Studio Ghibli
Hayao Miyazaki
Isao Takahata
Joe Hisaishi
Toshio Suzuki
Spirited Away
My Neighbor Totoro
Princess Mononoke
Howl's Moving Castle (film)
Nausicaä of the Valley of the Wind (film)
Kiki's Delivery Service
Castle in the Sky
Grave of the Fireflies
Ponyo
The Wind Rises
```

Guardar el texto crudo en `data/raw/<slug>.txt` para reproducibilidad. Trabajar sobre el resumen + primeras secciones (no el artículo entero, para reducir ruido).

### 1.2 Preprocesamiento
- Cargar `en_core_web_lg` (vectores necesarios para la normalización por similitud; si no está disponible usar `en_core_web_md`, nunca `sm` porque carece de vectores útiles).
- Segmentar en oraciones con el pipeline de spaCy.
- Resolución de correferencia **básica**: dado que `spacy-experimental coref` es frágil, aplicar una heurística simple — dentro de un artículo, mapear pronombres (he/she/it/his/her) a la última entidad PERSON/ORG mencionada del género compatible, y mapear "the studio"/"the film" a la entidad principal del artículo. Documentar esto como limitación.

### 1.3 Extracción de entidades (NER) → instancias de clases
Ejecutar NER de spaCy. Mapear labels de spaCy a **clases de la ontología del dominio**:

| spaCy label      | Clase ontología |
|------------------|-----------------|
| PERSON           | Person          |
| WORK_OF_ART      | Film            |
| ORG              | Organization    |
| GPE, LOC, FAC    | Location        |
| DATE             | Date            |

- Normalizar/deduplicar entidades: lowercasing para matching, fuzzy matching (`rapidfuzz`, umbral ~90) para unir variantes ("Miyazaki" / "Hayao Miyazaki"). Mantener el nombre canónico más largo como `label` del nodo.
- Descartar entidades con frecuencia 1 que no sean del corpus principal (reduce hairball).

### 1.4 Extracción de relaciones (dependency parsing) → triples
Para cada oración, extraer triples crudos **(sujeto, verbo, objeto)** vía dependency parsing:
- Sujeto: token con dep `nsubj` / `nsubjpass`.
- Verbo: su `head` (lematizado).
- Objeto: `dobj`, `pobj` (vía preposición), o `attr`.
- Conservar solo triples donde sujeto **y** objeto sean entidades reconocidas en 1.3.

### 1.5 Normalización de predicados (núcleo "NLP construye la ontología")
Reducir los verbos crudos a un **conjunto cerrado de predicados canónicos**:

```
DIRECTED, PRODUCED, COMPOSED, WROTE, FOUNDED,
RELEASED_IN, WORKED_ON, RELATED_TO (catch-all)
```

Algoritmo de mapeo (en este orden):
1. **Diccionario de lemas** explícito: `direct→DIRECTED`, `compose/score→COMPOSED`, `produce→PRODUCED`, `write/author→WROTE`, `found/establish/co-found→FOUNDED`, `release/premiere→RELEASED_IN`, etc.
2. **Similitud de vectores spaCy**: para lemas no cubiertos, comparar el vector del verbo contra el vector de cada predicado canónico (palabra ancla) y asignar al de mayor similitud si supera umbral (~0.5).
3. Si nada supera el umbral → `RELATED_TO`.

Esto es lo que se documenta en el README como la técnica de construcción de ontología. Guardar también un conteo de cuántos triples cayó en cada predicado (para la defensa de la tarea).

### 1.6 Salida: `graph.json`
Formato consumible directamente por D3:

```json
{
  "ontology": {
    "classes": ["Person", "Film", "Organization", "Location", "Date"],
    "predicates": ["DIRECTED", "PRODUCED", "COMPOSED", "WROTE",
                   "FOUNDED", "RELEASED_IN", "WORKED_ON", "RELATED_TO"]
  },
  "nodes": [
    { "id": "hayao_miyazaki", "label": "Hayao Miyazaki", "class": "Person", "mentions": 42 }
  ],
  "links": [
    { "source": "hayao_miyazaki", "target": "spirited_away",
      "predicate": "DIRECTED", "sentence": "Miyazaki directed Spirited Away..." }
  ]
}
```

Incluir la oración fuente (`sentence`) en cada link → alimenta el panel de detalle y sirve de evidencia.

### 1.7 Estructura del repo de pipeline
```
pipeline/
  fetch_corpus.py        # descarga Wikipedia → data/raw/
  build_graph.py         # spaCy NER + deps + normalización → graph.json
  ontology.py            # diccionarios de clases y predicados
  requirements.txt       # spacy, wikipedia-api, rapidfuzz
data/raw/
graph.json               # se copia a la carpeta de la SPA
```

---

## Parte 2 — SPA (estática, D3.js)

### 2.1 Archivos
Un solo `index.html` con CSS y JS inline (o `index.html` + `app.js` + `style.css`). Cargar D3 v7 desde CDN. Cargar `graph.json` con `fetch('./graph.json')`.

### 2.2 Visualización
- **Force-directed graph** de D3 (`forceSimulation` con `forceLink`, `forceManyBody`, `forceCenter`, `forceCollide`).
- **Color de nodo por clase** (Person, Film, Organization, Location, Date) con leyenda.
- **Tamaño de nodo por `mentions`** (escala raíz cuadrada).
- **Color/estilo de arista por predicado**; etiqueta del predicado visible al hover o siempre según densidad.
- Drag de nodos, zoom y pan.

### 2.3 Interacción
- **Filtros**: checkboxes para mostrar/ocultar clases de entidad y tipos de predicado.
- **Búsqueda**: input que resalta y centra un nodo por nombre.
- **Panel de detalle**: al hacer clic en un nodo, mostrar su clase, sus relaciones (predicado + entidad conectada) y la oración fuente. Al hacer clic en una arista, mostrar la oración fuente.
- **Highlight de vecinos**: al seleccionar un nodo, atenuar los no conectados.

### 2.4 Restricciones técnicas de la SPA
- Sin frameworks pesados; D3 vanilla es suficiente. (Si se prefiere React, mantenerlo en un solo archivo con CDN — pero vanilla es más simple para GitHub Pages.)
- **No usar `localStorage`/`sessionStorage`**.
- Rutas relativas (`./graph.json`) para que funcione bajo el subpath de GitHub Pages (`usuario.github.io/repo/`).
- Diseño responsive; el SVG ocupa el viewport, paneles flotantes encima.

---

## Parte 3 — Deploy (GitHub Pages)

### 3.1 Estructura del repo final (lo que se publica)
```
/ (root del repo o /docs)
  index.html
  app.js
  style.css
  graph.json
```

### 3.2 Pasos
1. Crear repo público en GitHub.
2. Colocar los archivos estáticos en la raíz (o en `/docs`).
3. Settings → Pages → Source: branch `main`, carpeta `/ (root)` o `/docs`.
4. Verificar que `graph.json` carga (revisar consola por errores de ruta/CORS — con rutas relativas no debe haber problema).
5. La URL productiva queda como `https://<usuario>.github.io/<repo>/`.

> Nota: mantener el código del `pipeline/` en el repo (o en uno aparte) para reproducibilidad y defensa de la tarea, pero **no es necesario para que la página funcione** — la página solo necesita `graph.json` ya generado.

---

## Parte 4 — Entregables para la tarea
1. **URL productiva** de GitHub Pages (el entregable oficial).
2. **README.md** explicando la ontología: las clases, los predicados, y la técnica NLP de normalización (sección 1.5) con los conteos de triples por predicado.
3. Código del pipeline reproducible.

## Criterios de aceptación
- [ ] El grafo carga y se renderiza sin errores en la URL pública.
- [ ] Hay al menos 5 clases de entidad y los 8 predicados representados.
- [ ] Los filtros por clase y predicado funcionan.
- [ ] El clic en nodo/arista muestra la oración fuente.
- [ ] El README documenta explícitamente cómo NLP construyó la ontología (NER → clases, dependency parsing → triples, normalización por lema+vectores → predicados).
- [ ] Las relaciones mostradas son mayoritariamente correctas en una inspección manual de ~10 aristas.

## Riesgos y mitigaciones conocidas
- **Ruido en relaciones (SVO crudo):** mitigar filtrando a entidades conocidas y normalizando predicados; aceptar `RELATED_TO` como catch-all honesto.
- **Correferencia débil:** documentar como limitación; la heurística simple basta para la tarea.
- **Hairball visual:** limitar corpus a ~15 artículos, descartar entidades de frecuencia 1, usar `forceCollide` y filtros.
- **Rutas en GitHub Pages:** usar siempre rutas relativas.
