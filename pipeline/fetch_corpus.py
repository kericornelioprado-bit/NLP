"""
Download Wikipedia article text for the Studio Ghibli corpus.
Saves raw text to data/raw/<slug>.txt
"""

import os
import re
import time
import wikipediaapi

ARTICLES = [
    "Studio Ghibli",
    "Hayao Miyazaki",
    "Isao Takahata",
    "Joe Hisaishi",
    "Toshio Suzuki",
    "Spirited Away",
    "My Neighbor Totoro",
    "Princess Mononoke",
    "Howl's Moving Castle (film)",
    "Nausicaä of the Valley of the Wind (film)",
    "Kiki's Delivery Service",
    "Castle in the Sky",
    "Grave of the Fireflies",
    "Ponyo",
    "The Wind Rises",
]


def slugify(title):
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")


def fetch_articles(output_dir="data/raw"):
    os.makedirs(output_dir, exist_ok=True)
    wiki = wikipediaapi.Wikipedia(
        language="en",
        user_agent="GhibliKnowledgeGraph/1.0 (academic-nlp-project)",
    )

    for title in ARTICLES:
        slug = slugify(title)
        path = os.path.join(output_dir, f"{slug}.txt")
        if os.path.exists(path):
            print(f"[SKIP] {title} already exists")
            continue

        page = wiki.page(title)
        if not page.exists():
            print(f"[MISS] {title} — page not found")
            continue

        text = page.summary
        if text:
            print(f"[OK] {title} — {len(text)} chars (summary only)")
        else:
            print(f"[WARN] {title} — empty summary")
            text = ""

        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        time.sleep(1.2)


if __name__ == "__main__":
    fetch_articles()
