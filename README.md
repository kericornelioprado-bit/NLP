# Studio Ghibli Knowledge Graph

A static Single Page Application visualizing a knowledge graph of the Studio Ghibli universe, built with NLP techniques on Wikipedia articles.

[Live demo](https://github.com/USER/REPO) <!-- Replace with your GitHub Pages URL -->

## Ontology

The ontology was built **bottom-up using NLP** on ~15 Wikipedia articles. The process follows three stages:

### 1. Entity Extraction (spaCy NER → Ontology Classes)

spaCy's `en_core_web_lg` model runs Named Entity Recognition on each article. spaCy labels are mapped to domain ontology classes:

| spaCy Label | Ontology Class | Count |
|---|---|---|
| PERSON | Person | 25 |
| WORK_OF_ART | Film | 17 |
| ORG | Organization | 27 |
| GPE, LOC, FAC | Location | 11 |
| DATE | Date | 26 |

Entities are deduplicated globally using fuzzy matching (`rapidfuzz`, threshold ≥85) and substring overlap. Low-frequency entities (mention count < 2) are discarded to reduce noise. Known entities (main people, films, organizations) are pre-registered to ensure consistent resolution.

### 2. Relation Extraction (Dependency Parsing → Triples)

For each sentence containing at least two recognized entities, the dependency parse is inspected:

- **Subject**: token with dependency `nsubj` or `nsubjpass`
- **Verb**: the head of the subject (lemmatized)
- **Object**: `dobj`, `attr`, `pobj` (via preposition), or agent (via `agent` in passive)

Passive voice is handled: if the subject is `nsubjpass` or in a copular construction (e.g., "…is a film **written** by Hayao Miyazaki"), the agent is extracted and the relation is **reversed** (the agent becomes the source). Verb conjunctions are resolved to capture all verbs in a chain (e.g., "**written, produced, and directed** by Miyazaki" → WROTE + PRODUCED + DIRECTED).

Only triples where **both subject and object** resolve to known entities are retained.

#### Predicate normalization

Raw verb lemmas are reduced to a fixed set of **8 canonical predicates**:

| Predicate | Trigger verbs |
|---|---|
| DIRECTED | direct, helm |
| PRODUCED | produce |
| COMPOSED | compose, score, conduct |
| WROTE | write, author, script, pen, adapt, novel, manga |
| FOUNDED | found, establish, co-found, form, create |
| RELEASED_IN | release, premiere, debut, open, screen |
| WORKED_ON | work, animate, design, draw, voice, star, join |
| RELATED_TO | catch-all (co-occurrence ≥3 sentences) |

The normalization algorithm:
1. **Lemma dictionary**: exact match against the trigger verb sets above.
2. **Vector similarity** (spaCy word vectors): for lemmas not in the dictionary, cosine similarity is computed against the predicate anchor words (`directed`, `produced`, `composed`, `wrote`, `founded`, `released`, `worked`). The predicate with highest similarity ≥ 0.55 is assigned.
3. **Fallback**: if no predicate matches → `RELATED_TO`. Used primarily for entity pairs that co-occur in ≥3 sentences without a clear verb-mediated relationship.

#### Predicate distribution

| Predicate | Count |
|---|---|
| DIRECTED | 14 |
| PRODUCED | 6 |
| COMPOSED | 3 |
| WROTE | 9 |
| FOUNDED | 3 |
| RELEASED_IN | 4 |
| WORKED_ON | 18 |
| RELATED_TO | 483 |

57 triples (10.6%) were assigned a specific predicate via dependency parsing; the remaining 483 (89.4%) are `RELATED_TO` co-occurrence pairs. This asymmetry is expected: most entity co-occurrences in encyclopedic text are descriptive rather than explicitly verbalized relations.

### 3. Output: `graph.json`

The pipeline produces a single JSON file consumed by the D3.js visualization:

```json
{
  "ontology": { "classes": [...], "predicates": [...] },
  "nodes": [{ "id": "...", "label": "...", "class": "...", "mentions": N }],
  "links": [{ "source": "...", "target": "...", "predicate": "...", "sentence": "..." }]
}
```

Each link includes the **source sentence** for evidence inspection in the detail panel.

## Visualization (SPA)

- **D3.js v7** force-directed graph (from CDN)
- **Node color**: by ontology class (legend included)
- **Node size**: proportional to `mentions` (sqrt scale)
- **Edge color/style**: by predicate (dashed for weaker relations)
- **Interactivity**: drag nodes, zoom/pan, class/predicate filters, search, click-to-detail panel with sentence evidence
- **Static**: loads only `graph.json`; no backend, no localStorage

## Known Limitations

- **Coreference resolution is basic**: pronouns (he/she/his) are not resolved. Sentences starting with "It" or "He" referring to a previously mentioned entity will not produce correct triples. This is a known limitation documented as future work.
- **NER accuracy**: spaCy occasionally misclassifies film titles as PERSON or ORG. A set of known entities (people, films, organizations) was pre-registered to mitigate this.
- **`RELATED_TO` over-representation**: the co-occurrence threshold (≥3) was chosen to balance graph density vs. information. Lowering it increases noise; raising it removes valid but infrequent connections.
- **No temporal or spatial reasoning**: the graph encodes only binary relations, not event sequences or geographic precision.

## Reproducing

```bash
# Install dependencies
cd pipeline
pip install -r requirements.txt
python -m spacy download en_core_web_lg

# Download Wikipedia corpus
python fetch_corpus.py

# Build knowledge graph
python build_graph.py

# Serve SPA
cd ..
python -m http.server 8080
```

## Corpus

15 Wikipedia articles (English, summary only):

Studio Ghibli, Hayao Miyazaki, Isao Takahata, Joe Hisaishi, Toshio Suzuki, Spirited Away, My Neighbor Totoro, Princess Mononoke, Howl's Moving Castle, Nausicaä of the Valley of the Wind, Kiki's Delivery Service, Castle in the Sky, Grave of the Fireflies, Ponyo, The Wind Rises
