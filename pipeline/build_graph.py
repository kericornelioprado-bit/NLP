"""
Main pipeline: loads raw corpus, runs spaCy NER + dependency parsing,
normalizes entities/predicates, and outputs graph.json.
"""

import json
import os
import re
from collections import Counter

import spacy
from rapidfuzz import fuzz

from ontology import (
    CLASSES,
    LEMMA_TO_PREDICATE,
    NER_LABEL_TO_CLASS,
    PREDICATES,
    PREDICATE_ANCHORS,
)

CORPUS_DIR = "data/raw"
OUTPUT_PATH = "graph.json"

WN_DIRECTED = {"direct", "helm"}
WN_PRODUCED = {"produce"}
WN_COMPOSED = {"compose", "score", "conduct"}
WN_WROTE = {"write", "author", "script", "pen", "adapt", "novel", "manga"}
WN_FOUNDED = {"found", "establish", "co-found", "cofound", "form", "create"}
WN_RELEASED = {"release", "premiere", "debut", "open", "screen"}
WN_WORKED = {"work", "animate", "design", "draw", "illustrate",
             "collaborate", "perform", "voice", "star", "feature",
             "join", "make", "publish", "play", "appear", "base",
             "inspire", "influence", "include", "contribute",
             "serve", "become", "name", "set"}

KNOWN_PEOPLE = {
    "hayao miyazaki": ["hayao_miyazaki", "Hayao Miyazaki", "Person"],
    "miyazaki": ["hayao_miyazaki", "Hayao Miyazaki", "Person"],
    "isao takahata": ["isao_takahata", "Isao Takahata", "Person"],
    "takahata": ["isao_takahata", "Isao Takahata", "Person"],
    "toshio suzuki": ["toshio_suzuki", "Toshio Suzuki", "Person"],
    "suzuki": ["toshio_suzuki", "Toshio Suzuki", "Person"],
    "joe hisaishi": ["joe_hisaishi", "Joe Hisaishi", "Person"],
    "hisaishi": ["joe_hisaishi", "Joe Hisaishi", "Person"],
}

KNOWN_FILMS = {
    "spirited away": ["spirited_away", "Spirited Away", "Film"],
    "my neighbor totoro": ["my_neighbor_totoro", "My Neighbor Totoro", "Film"],
    "princess mononoke": ["princess_mononoke", "Princess Mononoke", "Film"],
    "howl's moving castle": ["howl_s_moving_castle_film", "Howl's Moving Castle", "Film"],
    "howls moving castle": ["howl_s_moving_castle_film", "Howl's Moving Castle", "Film"],
    "nausicaä of the valley of the wind": ["nausica_of_the_valley_of_the_wind_film", "Nausicaä of the Valley of the Wind", "Film"],
    "kiki's delivery service": ["kiki_s_delivery_service", "Kiki's Delivery Service", "Film"],
    "castle in the sky": ["castle_in_the_sky", "Castle in the Sky", "Film"],
    "laputa": ["castle_in_the_sky", "Castle in the Sky", "Film"],
    "laputa: castle in the sky": ["castle_in_the_sky", "Castle in the Sky", "Film"],
    "grave of the fireflies": ["grave_of_the_fireflies", "Grave of the Fireflies", "Film"],
    "ponyo": ["ponyo", "Ponyo", "Film"],
    "the wind rises": ["the_wind_rises", "The Wind Rises", "Film"],
    "porco rosso": ["porco_rosso", "Porco Rosso", "Film"],
    "the boy and the heron": ["the_boy_and_the_heron", "The Boy and the Heron", "Film"],
    "the castle of cagliostro": ["the_castle_of_cagliostro", "The Castle of Cagliostro", "Film"],
    "the tale of the princess kaguya": ["the_tale_of_the_princess_kaguya", "The Tale of the Princess Kaguya", "Film"],
    "only yesterday": ["only_yesterday", "Only Yesterday", "Film"],
    "pom poko": ["pom_poko", "Pom Poko", "Film"],
}

KNOWN_ORGS = {
    "studio ghibli": ["studio_ghibli", "Studio Ghibli", "Organization"],
    "ghibli": ["studio_ghibli", "Studio Ghibli", "Organization"],
    "toei animation": ["toei_animation", "Toei Animation", "Organization"],
    "toei": ["toei_animation", "Toei Animation", "Organization"],
    "the toei company": ["toei_animation", "Toei Animation", "Organization"],
    "toho": ["toei_animation", "Toei Animation", "Organization"],
    "topcraft": ["topcraft", "Topcraft", "Organization"],
    "tokuma shoten": ["tokuma_shoten", "Tokuma Shoten", "Organization"],
    "tokuma": ["tokuma_shoten", "Tokuma Shoten", "Organization"],
    "nippon animation": ["nippon_animation", "Nippon Animation", "Organization"],
    "tokyo movie shinsha": ["tokyo_movie_shinsha", "Tokyo Movie Shinsha", "Organization"],
    "walt disney studios": ["disney", "Disney", "Organization"],
    "disney": ["disney", "Disney", "Organization"],
    "streamline pictures": ["streamline_pictures", "Streamline Pictures", "Organization"],
    "studio ghibli inc.": ["studio_ghibli", "Studio Ghibli", "Organization"],
}

KNOWN_LOCATIONS = {
    "japan": ["japan", "Japan", "Location"],
    "tokyo": ["tokyo", "Tokyo", "Location"],
    "the united states": ["the_united_states", "United States", "Location"],
    "united states": ["the_united_states", "United States", "Location"],
}

ENTITY_BLACKLIST = {
    "the same year", "between", "five-year-old", "nineteenth-century",
    "half", "and", "the", "it", "he", "she", "they", "his", "her",
    "japanese", "english", "american", "french",
    "the film", "the movie", "the studio", "the series",
    "world war ii", "world war",
}

ENTITY_LABEL_NOISE = {
    "award", "prize", "film award", "best animated",
    "best foreign", "picture of the year",
}

def is_blacklisted(text):
    lower = text.lower().strip().rstrip("'s.,;")
    if lower in ENTITY_BLACKLIST:
        return True
    if len(lower) <= 2:
        return True
    if lower.isdigit() or re.match(r"^\d+$", lower):
        return True
    if re.match(r"^(the|a|an)\s+\d", lower):
        return True
    for noise in ENTITY_LABEL_NOISE:
        if noise in lower:
            return True
    return False


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def load_corpus(directory):
    docs = {}
    for fname in sorted(os.listdir(directory)):
        if fname.endswith(".txt"):
            slug = fname[:-4]
            with open(os.path.join(directory, fname), encoding="utf-8") as f:
                text = f.read()
            if text.strip():
                docs[slug] = text
    print(f"Loaded {len(docs)} documents")
    return docs


def resolve_known(text_clean):
    lower = text_clean.lower().rstrip("'s.,")
    for name, info in KNOWN_PEOPLE.items():
        if lower == name or lower in name or name in lower:
            return info
    for name, info in KNOWN_FILMS.items():
        if lower == name or lower in name or name in lower:
            return info
    for name, info in KNOWN_ORGS.items():
        if lower == name or lower in name or name in lower:
            return info
    for name, info in KNOWN_LOCATIONS.items():
        if lower == name or lower in name or name in lower:
            return info
    return None


def find_slug(text, canonical):
    clean = text.strip().rstrip("'s.,;")
    lower = clean.lower()
    if is_blacklisted(clean):
        return None
    known = resolve_known(clean)
    if known:
        return known[0]
    for slug, info in canonical.items():
        cl = info["label"].lower()
        if lower == cl:
            return slug
        if lower in cl or cl in lower:
            return slug
    for slug, info in canonical.items():
        cl = info["label"].lower()
        if fuzz.partial_ratio(lower, cl) >= 85:
            return slug
    return None


def find_entities_in_sent(sent, canonical):
    entities_by_token = {}
    for ent in sent.ents:
        clean = ent.text.strip().rstrip("'s.,")
        slug = find_slug(clean, canonical)
        if slug:
            for i in range(ent.start, ent.end):
                entities_by_token[i] = slug
    for token in sent:
        if token.i not in entities_by_token:
            slug = find_slug(token.text, canonical)
            if slug:
                entities_by_token[token.i] = slug
    return entities_by_token


def get_verb_chain(token):
    """Get all verbs in a conjunction chain."""
    verbs = [(token, token.lemma_.lower())]
    for child in token.children:
        if child.dep_ == "conj" and child.pos_ == "VERB":
            verbs.append((child, child.lemma_.lower()))
            for subchild in child.children:
                if subchild.dep_ == "conj" and subchild.pos_ == "VERB":
                    verbs.append((subchild, subchild.lemma_.lower()))
    return verbs


def get_obj_for_verb(verb_token, sent_entities, canonical):
    candidates = []
    for child in verb_token.children:
        if child.dep_ in ("dobj", "attr", "xcomp", "acomp"):
            candidates.append(child)
        elif child.dep_ == "prep":
            for pobj in child.children:
                if pobj.dep_ == "pobj":
                    candidates.append(pobj)
        elif child.dep_ == "conj" and child.pos_ == "VERB":
            for subchild in child.children:
                if subchild.dep_ in ("dobj", "attr"):
                    candidates.append(subchild)
                elif subchild.dep_ == "prep":
                    for pobj in subchild.children:
                        if pobj.dep_ == "pobj":
                            candidates.append(pobj)

    for cand in candidates:
        if cand.i in sent_entities:
            return sent_entities[cand.i]
        text = " ".join(t.text for t in cand.subtree
                        if t.dep_ not in ("det", "punct", "cc", "relcl"))
        slug = find_slug(text, canonical)
        if slug:
            return slug

    return None


def get_agent_for_verb(verb_token, sent_entities, canonical):
    verbs_to_check = [verb_token]
    verbs_to_check.extend(child for child in verb_token.children
                          if child.dep_ == "conj")
    verbs_to_check.extend(other for other in verb_token.head.children
                          if other.dep_ == "conj" and other != verb_token)

    for v in verbs_to_check:
        for child in v.children:
            if child.dep_ == "agent":
                for pobj in child.children:
                    if pobj.dep_ == "pobj":
                        if pobj.i in sent_entities:
                            return sent_entities[pobj.i]
                        text = " ".join(t.text for t in pobj.subtree
                                        if t.dep_ not in ("det", "punct"))
                        slug = find_slug(text, canonical)
                        if slug:
                            return slug
    return None


def extract_triples_by_patterns(docs, nlp, canonical):
    triples = []
    found_pairs = set()

    for doc_slug, text in docs.items():
        doc = nlp(text)

        for sent in doc.sents:
            sent_text = sent.text.strip()
            if len(sent_text) < 10:
                continue

            sent_entities = find_entities_in_sent(sent, canonical)
            if len(sent_entities) < 2:
                continue

            for token in sent:
                if token.dep_ not in ("nsubj", "nsubjpass"):
                    continue
                if token.i not in sent_entities:
                    continue

                subj_slug = sent_entities[token.i]

                orig_head = token.head
                verb_heads = []
                is_passive = (token.dep_ == "nsubjpass")

                if orig_head.pos_ == "AUX":
                    found_verb = False
                    for child in orig_head.children:
                        if child.pos_ == "VERB" and child.dep_ in ("xcomp", "acomp"):
                            verb_heads.append(child)
                            found_verb = True
                    if found_verb:
                        is_passive = True
                    else:
                        attr_child = None
                        for child in orig_head.children:
                            if child.dep_ in ("attr", "acomp") and child.pos_ in ("NOUN", "PROPN", "ADJ"):
                                attr_child = child
                                break
                        if attr_child:
                            for child in attr_child.children:
                                if child.pos_ == "VERB" and child.dep_ in ("acl", "amod"):
                                    verb_heads.append(child)
                                    for conj in child.children:
                                        if conj.dep_ == "conj" and conj.pos_ == "VERB":
                                            verb_heads.append(conj)
                                    found_verb = True
                            if found_verb:
                                is_passive = True
                    if not verb_heads:
                        continue
                elif orig_head.pos_ == "VERB":
                    verb_heads = [orig_head]
                else:
                    continue

                for vhead in verb_heads:
                    for _, verb_lemma in get_verb_chain(vhead):
                        pred = map_predicate(verb_lemma, nlp)
                        if not pred:
                            continue

                        if is_passive:
                            obj_slug = get_agent_for_verb(vhead, sent_entities, canonical)
                            if obj_slug and subj_slug != obj_slug:
                                if pred in ("DIRECTED", "PRODUCED", "WROTE", "COMPOSED", "WORKED_ON"):
                                    pair = (obj_slug, subj_slug, pred)
                                else:
                                    pair = (subj_slug, obj_slug, pred)
                                if pair not in found_pairs:
                                    found_pairs.add(pair)
                                    triples.append({
                                        "source": pair[0], "target": pair[1],
                                        "predicate": pred, "sentence": sent_text,
                                    })
                        else:
                            obj_slug = get_obj_for_verb(vhead, sent_entities, canonical)
                            if obj_slug and subj_slug != obj_slug:
                                pair = (subj_slug, obj_slug, pred)
                                if pair not in found_pairs:
                                    found_pairs.add(pair)
                                    triples.append({
                                        "source": subj_slug, "target": obj_slug,
                                        "predicate": pred, "sentence": sent_text,
                                    })

    return triples


def map_predicate(lemma, nlp):
    if lemma in WN_DIRECTED:
        return "DIRECTED"
    if lemma in WN_PRODUCED:
        return "PRODUCED"
    if lemma in WN_COMPOSED:
        return "COMPOSED"
    if lemma in WN_WROTE:
        return "WROTE"
    if lemma in WN_FOUNDED:
        return "FOUNDED"
    if lemma in WN_RELEASED:
        return "RELEASED_IN"
    if lemma in WN_WORKED:
        return "WORKED_ON"
    if lemma in LEMMA_TO_PREDICATE:
        return LEMMA_TO_PREDICATE[lemma]

    try:
        lemma_vec = nlp.vocab[lemma]
    except KeyError:
        return None
    best_score = 0.0
    best_pred = None
    for pred, anchor in PREDICATE_ANCHORS.items():
        try:
            anchor_vec = nlp.vocab[anchor]
        except KeyError:
            continue
        score = lemma_vec.similarity(anchor_vec)
        if score > best_score:
            best_score = score
            best_pred = pred
    if best_score >= 0.55:
        return best_pred
    return None


def extract_entities_from_docs(docs, nlp):
    canonical = {}
    mention_counter = Counter()

    for info_list in [KNOWN_PEOPLE.values(), KNOWN_FILMS.values(),
                       KNOWN_ORGS.values(), KNOWN_LOCATIONS.values()]:
        for v in info_list:
            if v[0] not in canonical:
                canonical[v[0]] = {"label": v[1], "class": v[2]}

    for slug, text in docs.items():
        doc = nlp(text)
        for ent in doc.ents:
            clean = ent.text.strip().rstrip("'s.,")
            if is_blacklisted(clean) or len(clean) < 2:
                continue
            known = resolve_known(clean)
            if known:
                mention_counter[known[0]] += 1
            else:
                cls = NER_LABEL_TO_CLASS.get(ent.label_)
                if cls is None:
                    continue
                eslug = slugify(clean)
                if eslug not in canonical:
                    canonical[eslug] = {"label": clean, "class": cls}
                mention_counter[eslug] += 1

    return canonical, mention_counter


def extract_cooccurrence_links(docs, nlp, canonical, min_cooccur=3):
    pair_counter = Counter()
    pair_sentence = {}

    for slug, text in docs.items():
        doc = nlp(text)
        for sent in doc.sents:
            sent_text = sent.text.strip()
            if len(sent_text) < 15:
                continue
            sent_entities = set(find_entities_in_sent(sent, canonical).values())
            for token in sent:
                eslug = find_slug(token.text, canonical)
                if eslug:
                    sent_entities.add(eslug)
            if len(sent_entities) >= 2:
                entities_list = sorted(sent_entities)
                for i, a in enumerate(entities_list):
                    for b in entities_list[i + 1:]:
                        pair_counter[(a, b)] += 1
                        pair_sentence[(a, b)] = sent_text

    triples = []
    for (a, b), count in pair_counter.items():
        if count >= min_cooccur:
            triples.append({
                "source": a, "target": b,
                "predicate": "RELATED_TO",
                "sentence": pair_sentence.get((a, b), ""),
            })
    return triples


def build_graph():
    print("Loading spaCy model...")
    nlp = spacy.load("en_core_web_lg")

    print("Loading corpus...")
    docs = load_corpus(CORPUS_DIR)

    print("Extracting entities...")
    canonical, mention_counter = extract_entities_from_docs(docs, nlp)
    print(f"Canonical entities: {len(canonical)}")

    print("Extracting triples (pattern-based)...")
    pattern_triples = extract_triples_by_patterns(docs, nlp, canonical)
    print(f"Pattern-based triples: {len(pattern_triples)}")

    print("Extracting co-occurrence links...")
    cooccur_triples = extract_cooccurrence_links(docs, nlp, canonical, min_cooccur=4)
    print(f"Co-occurrence triples: {len(cooccur_triples)}")

    pattern_pairs = set()
    for t in pattern_triples:
        pattern_pairs.add((t["source"], t["target"]))
        pattern_pairs.add((t["target"], t["source"]))

    filtered_cooccur = [t for t in cooccur_triples
                        if (t["source"], t["target"]) not in pattern_pairs]

    all_triples = pattern_triples + filtered_cooccur

    important_ids = set()
    for t in all_triples:
        important_ids.add(t["source"])
        important_ids.add(t["target"])

    core_slugs = set()
    for info_list in [KNOWN_PEOPLE.values(), KNOWN_FILMS.values(),
                       KNOWN_ORGS.values(), KNOWN_LOCATIONS.values()]:
        for v in info_list:
            core_slugs.add(v[0])

    nodes = []
    for slug in sorted(canonical):
        if slug not in canonical:
            continue
        info = canonical[slug]
        mentions = mention_counter.get(slug, 0)
        if info["class"] == "Date":
            continue
        if slug in core_slugs:
            pass
        elif mentions >= 2:
            nlinks = sum(1 for t in all_triples
                         if (t["source"] == slug or t["target"] == slug)
                         and t["predicate"] != "RELATED_TO")
            if nlinks == 0:
                continue
        else:
            continue
        nodes.append({
            "id": slug,
            "label": info["label"],
            "class": info["class"],
            "mentions": mentions,
        })

    node_ids = {n["id"] for n in nodes}

    links = []
    link_set = set()
    for t in all_triples:
        if t["source"] not in node_ids or t["target"] not in node_ids:
            continue
        key = (t["source"], t["target"], t["predicate"])
        if key in link_set:
            continue
        link_set.add(key)
        links.append(t)

    graph = {
        "ontology": {"classes": CLASSES, "predicates": PREDICATES},
        "nodes": nodes,
        "links": links,
    }

    predicate_counts = Counter(l["predicate"] for l in links)
    print("\nPredicate distribution:")
    for p in PREDICATES:
        print(f"  {p}: {predicate_counts.get(p, 0)}")

    class_counts = Counter(n["class"] for n in nodes)
    print("\nClass distribution:")
    for c in CLASSES:
        print(f"  {c}: {class_counts.get(c, 0)}")

    print(f"\nTotal nodes: {len(nodes)}")
    print(f"Total links: {len(links)}")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    print(f"\nGraph written to {OUTPUT_PATH}")

    return predicate_counts


if __name__ == "__main__":
    build_graph()
