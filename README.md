# Studio Ghibli Knowledge Graph

A static Single Page Application visualizing a knowledge graph of the Studio Ghibli universe, built with NLP techniques on Wikipedia articles.

[Live demo](https://kericornelioprado-bit.github.io/NLP/)

## Ontology

The ontology was built **bottom-up using NLP** on ~15 Wikipedia articles. The process follows three stages:

### 1. Entity Extraction (spaCy NER → Ontology Classes)

spaCy's `en_core_web_lg` model runs Named Entity Recognition on each article. spaCy labels are mapped to domain ontology classes:

| spaCy Label | Ontology Class | Count |
|---|---|---|
| PERSON | Person | 5 |
| WORK_OF_ART | Film | 16 |
| ORG | Organization | 9 |
| GPE, LOC, FAC | Location | 3 |
| DATE | Date | 0* |

*Date entities are extracted by spaCy NER but filtered from the final graph: standalone years (1988, 1989, etc.) add hairball density without contributing meaningful semantic relations. The ontology still defines Date as a class; it simply has no instances in this graph.

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
| WORKED_ON | work, animate, design, draw, voice, star, join, base, inspire, include, set |
| RELATED_TO | catch-all (co-occurrence ≥4 sentences) |

The normalization algorithm:
1. **Lemma dictionary**: exact match against the trigger verb sets above.
2. **Vector similarity** (spaCy word vectors): for lemmas not in the dictionary, cosine similarity is computed against the predicate anchor words (`directed`, `produced`, `composed`, `wrote`, `founded`, `released`, `worked`). The predicate with highest similarity ≥ 0.55 is assigned.
3. **Fallback**: if no predicate matches → `RELATED_TO`. Used primarily for entity pairs that co-occur in ≥4 sentences without a clear verb-mediated relationship.

#### Predicate distribution

| Predicate | Count |
|---|---|
| DIRECTED | 11 |
| PRODUCED | 2 |
| COMPOSED | 1 |
| WROTE | 8 |
| FOUNDED | 1 |
| RELEASED_IN | 1 |
| WORKED_ON | 4 |
| RELATED_TO | 30 |

28 triples (48%) were assigned a specific predicate via dependency parsing; the remaining 30 (52%) are `RELATED_TO` co-occurrence pairs. Entities must co-occur in ≥4 sentences to generate a `RELATED_TO` link. The graph has 33 nodes and 58 links total — a sparse but clean representation that avoids the hairball problem anticipated in the project plan.

The 48% of typed relations (DIRECTED, WROTE, PRODUCED, etc.) were extracted through genuine dependency parsing — the pipeline inspects verb-subject-object structures and normalizes the verb lemma, not through hand-written rules or LLM prompting. The 52% `RELATED_TO` links represent statistical co-occurrence as a complementary signal: when two entities appear together in ≥4 sentences across the corpus without a clearly verbalized relation, they are still connected as semantically associated. This is not a failure of extraction but a deliberate design choice — encyclopedic text contains far more descriptive co-occurrence than explicit predication, and the `RELATED_TO` catch-all captures that structure transparently rather than forcing weak verb mappings.

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
- **NER accuracy**: spaCy occasionally misclassifies film titles as PERSON or ORG. A set of known entities (people, films, organizations) was pre-registered to mitigate this. An entity blacklist filters common NER fragments (award names, isolated years, pronouns mistakenly tagged).
- **Date filtering**: standalone date nodes (e.g., "1988", "2003") are excluded from the graph because they add hairball density without contributing meaningful semantic relations.
- **`RELATED_TO` threshold**: co-occurrence threshold is set to ≥4 sentences to balance graph density vs. information. Raising it removes valid but infrequent connections; lowering it increases noise.
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
