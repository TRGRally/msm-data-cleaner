import requests
from bs4 import BeautifulSoup, Tag
import pandas as pd
from collections import OrderedDict, defaultdict
import sqlite3

url = "https://mysingingmonsters.fandom.com/wiki/Monsters"


# the script auto-detects elements that have "Element" in the tag title (e.g. Air_Element, Water_Element)
# these elements don't have "Element" in their name, so we need to tell the script they exist
KNOWN_ELEMENTS = [
    "Legendary Monsters", "Spooktacle", "Festival of Yay", "Season of Love",
    "Eggs-Travaganza", "SummerSong", "Feast-Ember", "Beat Hereafter",
    "Echoes of Eco", "Anniversary Month", "Crescendo Moon", "SkyPainting",
    "Life-Formula", "Cloverspell", "MindBoggle", "Perplexplore",
    "Celestials", "Dipsters",
]
KNOWN_ELEMENTS_MAP = {k.lower(): k for k in KNOWN_ELEMENTS}


def check_known_elements(label: str) -> str | None:
    return KNOWN_ELEMENTS_MAP.get(norm_text(label).lower())


# the wiki has a capitalisation typo in the element titles. Common is "ShLep" and Rare is "shLep". "shLep" is correct
# element titles are metadata that aren't rendered but used for tooltips, the script uses these not the rendered text
PREFERRED_CASE = {
    "shlep": "shLep",   # enforce correct casing
}


def fix_casing(name: str) -> str:
    k = norm_key(name)
    return PREFERRED_CASE.get(k, norm_text(name))


# manual list of mythical monsters and the island they belong to, so we can specify their "true" type
TRUE_MYTHICAL_TYPE = {
    "G'joob": "Plant",
    "Strombonin": "Cold",
    "Yawstrich": "Air",
    "Anglow": "Water",
    "Hyehehe": "Earth",
    "Buzzinga": "Haven",
    "Cherubble": "Oasis",
    "Bleatnik": "Plant",
    "Cranchee": "Cold",
    "Sporerow": "Air",
    "Pinghound": "Water",
    "Wheezel": "Earth",
    "Knurv": "Haven",
    "shLep": "Oasis",
}


# appends the island specifier to a monster if it contains a Mythical element, from the list above
def apply_mythical_override(common_key: str, elements: list[str]) -> list[str]:
    island = MYTHICAL_TYPE_BY_KEY.get(common_key)
    out = []
    for element in elements:
        if island and element.strip().lower() == "mythical":
            out.append(f"Mythical ({island})")
        else:
            out.append(element)
    return out


def norm_text(s: str) -> str:
    if s is None:
        return ""
    return " ".join(s.replace("\xa0", " ").strip().split())


# makes all quotes the same and lowercases
def norm_key(name: str) -> str:
    return norm_text(name).replace("\u2019", "'").lower()


MYTHICAL_TYPE_BY_KEY = {norm_key(k): v for k, v in TRUE_MYTHICAL_TYPE.items()}


# makes rare/epic/adult variants map to their common monster
def common_key_from_variant(name: str) -> str:
    norm = norm_text(name)
    lower = norm.lower()
    for pref in ("rare ", "epic ", "adult "):
        if lower.startswith(pref):
            return norm_key(norm[len(pref):])
    return norm_key(norm)


# skips the headers of tables
def is_header_row(tr: Tag) -> bool:
    return tr.find("th", recursive=False) is not None


# any <td> that isn't an element icon is the monster, which contains the name
def monster_name_from_td(td: Tag):
    for a in td.find_all("a", title=True):
        t = norm_text(a["title"])
        if not t.endswith(" Element"):
            return t
    return None


# separates primordial elements from regular ones by checking the image URL (the only difference???)
def span_is_primordial(span: Tag) -> bool:
    a = span.find("a")
    img = a.find("img")
    if not img:
        return False

    src = img.get("src")
    data_src = img.get("data-src")

    return "primordial" in ((src or "") + (data_src or "")).lower()


# insanely convoluted way to detect if we are currently looking at an element icon
def element_from_span(span: Tag) -> str | None:
    a = span.find("a")
    if not a:
        return None
    title = norm_text(a.get("title") or a.get_text(strip=True))
    if not title:
        return None

    element = None

    # "... Element"
    if title.endswith(" Element"):
        element = title[:-len(" Element")].strip()
    # "Element ..."
    elif title.startswith("Element "):
        element = title[len("Element "):].strip()
    else:
        # known element names that don't include the word "Element" in the tag title e.g. "Legendary Monsters" element
        known = check_known_elements(title)
        if known:
            element = known
        else:
            # tries <a> text in case tooltip is missing or wrong
            txt = norm_text(a.get_text(strip=True))
            known2 = check_known_elements(txt)
            if known2:
                element = known2
    # not an element
    if not element:
        return None
    # checks if it should be a primordial
    if span_is_primordial(span):
        return f"{element} (Primordial)"
    return element


def elements_from_td(td: Tag):
    # all are <span typeof="mw:File">. first is monster image, rest are element icons (hopefully)
    spans = td.find_all("span", attrs={"typeof": "mw:File"})
    if len(spans) < 2:
        return []  # rare/epic/adult variants don't list their elements on the wiki page, these get added on later

    # try all but first
    labels = []
    for span in spans[1:]:
        label = element_from_span(span)
        if label:
            labels.append(label)

    # remove duplicates
    out, seen = [], set()
    for i in labels:
        if i not in seen:
            out.append(i)
            seen.add(i)

    return out


# scrape logic

resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
resp.raise_for_status()
soup = BeautifulSoup(resp.text, "html.parser")

tables = soup.select("table.article-table")[:12]  # the first 12 tables have the monster data, the rest is wiki nav

# keeping track of common monsters seen + their elements, then link rare/epic/adult variants found
elements_by_common = OrderedDict()
variants_by_common = defaultdict(lambda: {"rare": False, "epic": False, "adult": False})

for tbl in tables:
    tbody = tbl.find("tbody") or tbl
    for tr in tbody.find_all("tr", recursive=False):
        if is_header_row(tr):
            continue
        for td in tr.find_all("td", recursive=False):
            name = monster_name_from_td(td)
            if not name:
                continue

            elements = elements_from_td(td)
            # common monsters have elements listed, so we can add them directly
            if elements:
                key = norm_key(name)
                display_name = fix_casing(name)
                if key not in elements_by_common:
                    elements_by_common[key] = {"display": display_name, "elements": elements}
                else:
                    # merge elements if we see it again
                    current = elements_by_common[key]["elements"]
                    for element in elements:
                        if element not in current:
                            current.append(element)

            # rare/epic/adult variants get their elements from the common monster later
            # this is because we might not have encountered the common monster yet
            else:
                low = norm_text(name).lower()
                if low.startswith("rare "):
                    common_key = common_key_from_variant(name)
                    variants_by_common[common_key]["rare"] = True
                elif low.startswith("epic "):
                    common_key = common_key_from_variant(name)
                    variants_by_common[common_key]["epic"] = True
                elif low.startswith("adult "):
                    common_key = common_key_from_variant(name)
                    variants_by_common[common_key]["adult"] = True

# generating the final list of rows for the csv
ordered_rows = []  # (display name, [elements])
for common_key, info in elements_by_common.items():
    common_display_name = info["display"]
    elements = apply_mythical_override(common_key, info["elements"])

    # place common first
    ordered_rows.append((common_display_name, elements))

    # then common, rare, epic versions
    variants = variants_by_common.get(common_key, {})
    if variants.get("rare"):
        ordered_rows.append((f"Rare {common_display_name}", elements))
    if variants.get("epic"):
        ordered_rows.append((f"Epic {common_display_name}", elements))
    if variants.get("adult"):
        ordered_rows.append((f"Adult {common_display_name}", elements))

# csv for free
df = pd.DataFrame({
    "Species": [m for m, _ in ordered_rows],
    "Elements": [", ".join(e) for _, e in ordered_rows],
})
df.to_csv("./other data/msm_monster_elements.csv", index=False)
print(f"Saved {len(df)} rows to ./other data/msm_monster_elements.csv")



