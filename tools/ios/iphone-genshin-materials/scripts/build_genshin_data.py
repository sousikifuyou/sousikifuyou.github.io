#!/usr/bin/env python3
"""genshin-db の data.min.json から、アプリ用の軽量 JSON (genshin-data.json) を生成する。

使い方:
  python3 build_genshin_data.py <data.min.json> <出力先.json> [genshin-dbのバージョン]

genshin-db (https://github.com/theBowja/genshin-db) は npm で配布されている
原神データベース。パッケージ内の src/min/data.min.json を直接読むだけで、
パッケージのコードは実行しない。標準ライブラリのみで動作する。
"""
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

DAY = {"月曜": "Mon", "火曜": "Tue", "水曜": "Wed", "木曜": "Thu", "金曜": "Fri", "土曜": "Sat", "日曜": "Sun"}
DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
ELEMENT = {
    "ELEMENT_PYRO": "Pyro", "ELEMENT_HYDRO": "Hydro", "ELEMENT_ELECTRO": "Electro", "ELEMENT_CRYO": "Cryo",
    "ELEMENT_ANEMO": "Anemo", "ELEMENT_GEO": "Geo", "ELEMENT_DENDRO": "Dendro",
}
WEAPON = {
    "WEAPON_SWORD_ONE_HAND": "Sword", "WEAPON_CLAYMORE": "Claymore", "WEAPON_POLE": "Polearm",
    "WEAPON_BOW": "Bow", "WEAPON_CATALYST": "Catalyst",
}
TRAVELER_ELEMENT = {
    "traveleranemo": "Anemo", "travelergeo": "Geo", "travelerelectro": "Electro", "travelerdendro": "Dendro",
    "travelerhydro": "Hydro", "travelerpyro": "Pyro", "travelercryo": "Cryo",
}
ELEMENT_JA = {"Pyro": "炎", "Hydro": "水", "Electro": "雷", "Cryo": "氷", "Anemo": "風", "Geo": "岩", "Dendro": "草"}

TYPE_TALENT_BOOK = "キャラクター天賦素材"
TYPE_WEAPON_MAT = "武器突破素材"
TYPE_GEM = "キャラクター突破素材"
TYPE_BOSS = "キャラクター育成素材"   # 通常ボス素材・週ボス素材
TYPE_COMMON = "キャラと武器育成素材"  # 雑魚敵ドロップ


def slug(s):
    s = re.sub(r"['’]", "", s.lower())
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def days_of(item):
    return sorted({DAY[d] for d in item.get("daysOfWeek", []) if d in DAY}, key=DAY_ORDER.index)


def build(raw, source_version):
    ja = raw["data"]["Japanese"]
    en = raw["data"]["English"]
    versions = raw.get("version", {})
    mats = {v["id"]: v for v in ja["materials"].values()}
    en_mats = {v["id"]: v for v in en["materials"].values()}
    domains = {v["id"]: v for v in ja["domains"].values()}

    def region_of(item):
        return domains.get(item.get("dropDomainId"), {}).get("regionName", "")

    # ---- 曜日素材のシリーズ（同シリーズは id が連番: レア度最低の id を代表にする） ----
    def series(type_text, key_fn):
        fam = defaultdict(list)
        for v in mats.values():
            if v.get("typeText") == type_text and v.get("daysOfWeek"):
                fam[v["id"] - (v.get("rarity", 2) - 2)].append(v)
        out, id2key = [], {}
        for base_id in sorted(fam):
            items = sorted(fam[base_id], key=lambda x: x.get("rarity", 0))
            low = items[0]
            key = key_fn(low, items)
            out.append({
                "key": key,
                "name": key_fn.name_ja(low, items),
                "region": region_of(low),
                "days": days_of(low),
                "items": [x["name"] for x in items],
            })
            for x in items:
                id2key[x["id"]] = key
        return out, id2key

    class TalentKey:
        def __call__(self, low, items):
            en_name = en_mats.get(low["id"], {}).get("name", "")
            return slug(re.sub(r"^Teachings of (the )?", "", en_name)) or str(low["id"])

        @staticmethod
        def name_ja(low, items):
            m = re.search(r"「[^」]+」", low["name"])
            return m.group(0) if m else low["name"]

    class WeaponKey:
        def __call__(self, low, items):
            return slug(en_mats.get(low["id"], {}).get("name", "")) or str(low["id"])

        @staticmethod
        def name_ja(low, items):
            return items[-1]["name"]  # 最高レア名（例: 遠海夷地の金枝）

    talent_series, talent_id2key = series(TYPE_TALENT_BOOK, TalentKey())
    weapon_series, weapon_id2key = series(TYPE_WEAPON_MAT, WeaponKey())

    # ---- 素材分類ヘルパー ----
    def collect(cost_groups):
        ids = []
        for group in cost_groups:
            for it in group or []:
                if it["id"] not in ids:
                    ids.append(it["id"])
        return [mats[i] for i in ids if i in mats]

    def pick(items, type_text, highest=True, exclude_days=False, rarity=None):
        c = [x for x in items if x.get("typeText") == type_text]
        if exclude_days:
            c = [x for x in c if not x.get("daysOfWeek")]
        if rarity is not None:
            c = [x for x in c if x.get("rarity") == rarity]
        if not c:
            return None
        c.sort(key=lambda x: x.get("rarity", 0))
        return (c[-1] if highest else c[0])["name"]

    def talent_info(tal):
        costs = (tal or {}).get("costs", {})
        items = collect(costs.values())
        books = []
        for x in items:
            k = talent_id2key.get(x["id"])
            if k and k not in books:
                books.append(k)
        return {
            "talentBooks": books,
            "weeklyBoss": pick(items, TYPE_BOSS, rarity=5),
            "talentCommon": pick(items, TYPE_COMMON, highest=False),
        }

    def ascension_info(ch):
        items = collect((ch.get("costs") or {}).values())
        local = [x["name"] for x in items if x.get("category") == "EXCHANGE" or "特産" in (x.get("typeText") or "")]
        return {
            "gem": pick(items, TYPE_GEM),
            "boss": pick(items, TYPE_BOSS, rarity=4) or pick(items, TYPE_BOSS),
            "local": local[0] if local else None,
            "common": pick(items, TYPE_COMMON, highest=False),
        }

    char_ver = versions.get("characters", {})
    characters = []
    for key, ch in ja["characters"].items():
        element = ELEMENT.get(ch.get("elementType"))
        if not element:
            continue  # 旅人(空/蛍)・無元素キャラは下で元素別に追加
        entry = {
            "key": key,
            "name": ch["name"],
            "element": element,
            "weapon": WEAPON.get(ch.get("weaponType"), ""),
            "rarity": ch.get("rarity"),
            "region": ch.get("region") or "",
            "version": char_ver.get(key, ""),
        }
        entry.update(talent_info(ja["talents"].get(key)))
        entry["ascension"] = ascension_info(ch)
        characters.append(entry)

    traveler = ja["characters"].get("aether") or ja["characters"].get("lumine")
    if traveler:
        for tkey, element in TRAVELER_ELEMENT.items():
            tal = ja["talents"].get(tkey)
            if not tal:
                continue
            entry = {
                "key": tkey,
                "name": f"旅人（{ELEMENT_JA[element]}）",
                "element": element,
                "weapon": "Sword",
                "rarity": 5,
                "region": "",
                "version": "",
            }
            entry.update(talent_info(tal))
            entry["ascension"] = ascension_info(traveler)
            characters.append(entry)

    characters.sort(key=lambda c: (str(c["version"]) or "0", c["key"]))

    # ---- 武器（★4以上）→ 武器突破素材シリーズ ----
    weapons = []
    for key, w in ja["weapons"].items():
        if (w.get("rarity") or 0) < 4:
            continue
        items = collect((w.get("costs") or {}).values())
        sk = next((weapon_id2key[x["id"]] for x in items if x["id"] in weapon_id2key), None)
        if not sk:
            continue
        weapons.append({
            "key": key,
            "name": w["name"],
            "rarity": w.get("rarity"),
            "weapon": WEAPON.get(w.get("weaponType"), ""),
            "series": sk,
        })
    weapons.sort(key=lambda w: (-w["rarity"], w["key"]))

    game_versions = [v for v in char_ver.values() if re.match(r"^\d+\.\d+$", str(v))]
    latest = max(game_versions, key=lambda v: tuple(map(int, v.split(".")))) if game_versions else ""

    return {
        "schema": 1,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": {"name": "genshin-db", "version": source_version, "gameVersion": latest},
        "talentSeries": talent_series,
        "weaponSeries": weapon_series,
        "characters": characters,
        "weapons": weapons,
    }


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    src, dst = sys.argv[1], sys.argv[2]
    source_version = sys.argv[3] if len(sys.argv) > 3 else ""
    with open(src, encoding="utf-8") as f:
        raw = json.load(f)
    out = build(raw, source_version)

    # 内容に変化がなければ generatedAt も更新しない（無駄なコミットを防ぐ）
    try:
        with open(dst, encoding="utf-8") as f:
            prev = json.load(f)
        if {**prev, "generatedAt": None} == {**out, "generatedAt": None}:
            print("no changes")
            return
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(f"wrote {dst}: {len(out['characters'])} characters, "
          f"{len(out['talentSeries'])} talent series, {len(out['weaponSeries'])} weapon series, "
          f"{len(out['weapons'])} weapons (game {out['source']['gameVersion']})")


if __name__ == "__main__":
    main()
