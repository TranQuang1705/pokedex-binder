"""Pull TCGplayer card data (via tcgcsv.com) for Japanese Pokémon cards into data/tcgplayer-jp.json.

Runs daily from GitHub Actions. tcgcsv updates around 20:00 UTC; it asks for a custom
User-Agent and ~100 ms between requests, so this script keeps to that.
"""
import json, sys, time, urllib.request
from datetime import datetime, timezone

BASE = "https://tcgcsv.com/tcgplayer"
UA = {"User-Agent": "PokedexBinder/1.0 (+https://github.com/TranQuang1705/pokedex-binder)"}
OUT = "data/tcgplayer-jp.json"


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.load(r)
            time.sleep(0.15)
            return data
        except Exception as e:  # noqa: BLE001
            print(f"  retry {i + 1} {url}: {e}", file=sys.stderr)
            time.sleep(5 * (i + 1))
    raise RuntimeError(f"failed: {url}")


def find_category():
    cats = get(f"{BASE}/categories")["results"]
    for c in cats:
        name = (c.get("name") or "") + " " + (c.get("displayName") or "")
        if "pokemon" in name.lower().replace("é", "e") and "japan" in name.lower():
            return c["categoryId"], c.get("displayName") or c.get("name")
    raise RuntimeError("Pokemon Japan category not found")


def ext(product, key):
    for e in product.get("extendedData") or []:
        if e.get("name") == key:
            return e.get("value") or ""
    return ""


def main():
    cat_id, cat_name = find_category()
    print(f"category {cat_id} {cat_name}")
    groups = get(f"{BASE}/{cat_id}/groups")["results"]
    print(f"{len(groups)} groups")
    out_groups, cards = {}, []
    for gi, g in enumerate(groups):
        gid = g["groupId"]
        try:
            products = get(f"{BASE}/{cat_id}/{gid}/products")["results"]
            prices = get(f"{BASE}/{cat_id}/{gid}/prices")["results"]
        except RuntimeError as e:
            print(f"skip group {gid}: {e}", file=sys.stderr)
            continue
        price_map = {}
        for p in prices:
            v = p.get("marketPrice") or p.get("midPrice") or p.get("lowPrice")
            if v:
                price_map.setdefault(p["productId"], {})[p.get("subTypeName") or "Normal"] = round(float(v), 2)
        n_cards = 0
        for pr in products:
            number = ext(pr, "Number")
            if not number:  # sealed product, not a single card
                continue
            cards.append([pr["productId"], pr.get("name") or "", number, ext(pr, "Rarity"), gid,
                          price_map.get(pr["productId"], {})])
            n_cards += 1
        if n_cards:
            out_groups[gid] = [g.get("name") or "", g.get("abbreviation") or "", (g.get("publishedOn") or "")[:10]]
        if gi % 25 == 0:
            print(f"  {gi}/{len(groups)} groups, {len(cards)} cards")
    if len(cards) < 1000:
        raise RuntimeError(f"only {len(cards)} cards, refusing to overwrite data")
    data = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "category": cat_id,
            "groups": out_groups, "cards": cards}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"wrote {len(cards)} cards in {len(out_groups)} sets")


if __name__ == "__main__":
    main()
