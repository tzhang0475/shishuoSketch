#!/usr/bin/env python3
"""Create the conservative basic Scene audit for W3 Stories.

The records deliberately distinguish identity from physical presence.  A
selected Person whose source role cannot be established from the compact
entry is placed in the off-frame/discussed view rather than silently promoted
to 入画.  All prose is candidate editorial synthesis tied to the Story main
text evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PERSON_WAVE_PATH = Path("data/annotation/person-expansion-wave-3.json")
SC1_PATH = Path("data/derived/sc1-site.json")
OUTPUT_PATH = Path("data/annotation/story-scene-contexts-w3.json")


SCENE_FOCUS = {
    "01-dexing-012": "王朗以識度推重華歆；張華轉述此事，指出只學外在形骸便離華歆更遠。",
    "01-dexing-014": "王祥守護後母珍愛的李樹，遭斫傷後仍跪前請死，母親終於感悟而親愛之。",
    "01-dexing-015": "晉文王談到阮籍的慎密與玄遠，只見品評，未見阮籍本人在場。",
    "01-dexing-016": "王戎回憶與嵇康同居二十年，以未見其喜愠描畫嵇康的神情。",
    "01-dexing-023": "任放之士以裸形自達，樂廣以一句名教中自有樂地回應這場清談。",
    "01-dexing-025": "顧榮在宴席上把炙肉讓給有欲色的役人；後來渡江遇危，才知道那人一直護助自己。",
    "02-yanyu-078": "晉武帝賜山濤不多，謝太傅以欲求者少、施與者忘少替這個數目的問題作解。",
    "02-yanyu-107": "桓玄準備改置直館，追問虎賁中郎將應在何省；潘岳賦序成為當場答問的依據。",
    "03-zhengshi-006": "賈充初定律令，與羊祜一同向鄭沖請教；鄭沖先自謙，羊祜再說明上意，議論才落實。",
    "04-wenxue-069": "本則只留下劉伶所作《酒德頌》及其寄託，人物以作品而非對話出場。",
    "05-fangzheng-012": "杜預赴荊州途中受朝士祖餞，楊濟因不滿而離席；和嶠追到大夏門把他帶回，席間秩序遂復。",
    "07-shijian-005": "少年王夷甫奉父事入見羊祜、山濤，以秀異才辯令二人驚異；羊祜留下了對其後患的判語。",
    "08-shangyu-006": "王濬沖與裴叔則以總角之年拜訪鍾士季，鍾士季在客人離去後品評兩人的才性與後來仕途。",
    "08-shangyu-019": "張華在席間品評褚陶、陸氏兄弟與顧榮，陸機以未出場的才士反問，將品藻推向更寬處。",
    "09-pinzao-008": "劉令初入洛陽，逐一說出對王夷甫、樂彥輔、張茂先、周弘武、杜方叔的觀感。",
    "14-rongzhi-005": "眾人以松風、孤松與玉山形容嵇康的風姿醉態，山濤的評語把人物品評推到畫面中心。",
    "17-shangshi-002": "王濬沖經過黃公酒壚，回憶與嵇康、阮籍在此酣飲的竹林舊遊，感嘆今日已被時勢羈縛。",
    "18-qiyi-002": "嵇康在汲郡山中遇見孫登並相遊；臨別時孫登以才高而保身不足相告。",
    "19-xianyuan-013": "賈充兩段婚姻在李氏與郭氏相見時交疊；郭氏原欲示威，入門卻向李氏跪拜。",
    "20-shujie-005": "郭璞哭弔故友陳述，呼其字嗣祖並說焉知非福；不久大將軍作亂，回應了這句話。",
    "23-rendan-013": "阮渾長成而風度似父，也想學作達人；阮籍以阮咸已先入此流作答。",
    "24-jianao-001": "晉文王席間禮敬近於王者，唯阮籍箕踞長嘯、酣放自若，形成同席中的鮮明反差。",
    "25-paidiao-009": "荀鳴鶴與陸士龍初會張華之席，張華促成二人以雲龍、山鹿互相試對，最後撫掌大笑。",
    "35-huoni-003": "賈充回家抱逗乳母手中的孩子，郭氏因妒殺乳母；孩子不肯另乳，故事以家庭悲劇收束。",
}

PRESENT = {
    "01-dexing-014": {"person-036"},
    "01-dexing-023": {"person-044"},
    "01-dexing-025": {"person-049"},
    "03-zhengshi-006": {"person-038", "person-041"},
    "05-fangzheng-012": {"person-039"},
    "07-shijian-005": {"person-038", "person-043"},
    "08-shangyu-006": {"person-042"},
    "08-shangyu-019": {"person-040"},
    "14-rongzhi-005": {"person-046", "person-043"},
    "17-shangshi-002": {"person-042"},
    "18-qiyi-002": {"person-046"},
    "19-xianyuan-013": {"person-041"},
    "20-shujie-005": {"person-050"},
    "23-rendan-013": {"person-045"},
    "24-jianao-001": {"person-045"},
    "25-paidiao-009": {"person-040"},
    "35-huoni-003": {"person-041"},
}

RESONANCE = {
    "01-dexing-025": "後半仍記顧榮渡江遇危，當年一塊炙肉的善意在亂世中回到他身邊；余韻直接由本則正文留下。",
    "02-yanyu-107": "潘岳的《秋興賦序》在本則中不只是引文，也成了當場制度問答的可追溯文本。",
    "07-shijian-005": "羊祜說「亂天下者」的判語停在少年身上；本則沒有另造後事，只保留這句預言式品評的張力。",
    "14-rongzhi-005": "嵇康的風姿被收束為孤松與玉山，人物不在自述中，而在同時人的形容裡留下餘音。",
    "17-shangshi-002": "嵇康已夭、阮籍已亡，王濬再過酒壚時才感到竹林舊遊邈若山河；死亡與時勢把回憶拉遠。",
    "20-shujie-005": "郭璞哭陳述時說焉知非福，旋即接大將軍作亂；本則以極短的後續驗證收住話頭。",
    "23-rendan-013": "阮籍以阮咸作比較，阮渾的「欲作達」因此被放在家族前例的回聲中，而不是孤立的性格評語。",
    "35-huoni-003": "乳母被殺、孩子拒乳而死，最後郭氏終身無子；家庭動作與後果在同一則中連成冷峻的收束。",
}


def read(path: Path) -> Any:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def claim(text: str, evidence_id: str, assertion_status: str = "inferred") -> dict[str, Any]:
    return {
        "text": text,
        "assertion_status": assertion_status,
        "review_status": "candidate",
        "evidence_ids": [evidence_id],
    }


def build() -> dict[str, Any]:
    wave = read(PERSON_WAVE_PATH)
    story_wave = read(Path("data/annotation/story-expansion-wave-3.json"))
    bundle = read(SC1_PATH)
    people = {
        str(item.get("id") or item.get("person_id")): item
        for item in bundle.get("people", [])
        if isinstance(item, dict) and (item.get("id") or item.get("person_id"))
    }
    story_by_id = {str(item["id"]): item for item in bundle.get("stories", []) if isinstance(item, dict)}
    candidate_ids = {str(item["candidate_id"]): str(item["person_id"]) for item in wave["members"]}
    names = {
        person_id: str(person.get("canonical_name") or person.get("name") or "")
        for person_id, person in people.items()
    }
    records: list[dict[str, Any]] = []
    for selected in story_wave["records"]:
        story_id = str(selected["story_id"])
        story = story_by_id[story_id]
        evidence_id = f"evidence-sc1-{story_id}-main"
        focus = SCENE_FOCUS[story_id]
        selected_people = {
            person_id
            for person_id in story.get("person_ids", [])
            if person_id in people and person_id in set(candidate_ids.values())
        }
        present = PRESENT.get(story_id, set()) & selected_people
        discussed = selected_people - present
        people_rows = []
        for person_id in sorted(selected_people):
            surface = names[person_id]
            role = "present" if person_id in present else "discussed"
            people_rows.append(
                {
                    "person_id": person_id,
                    "surface": surface,
                    "scene_role": role,
                    "source_layers": ["main_text"],
                    "age": {
                        "status": "unknown",
                        "label": None,
                        "start_year": None,
                        "end_year": None,
                        "assertion_status": "unknown",
                        "review_status": "candidate",
                        "evidence_ids": [],
                    },
                    "status": None,
                    "assertion_status": "attested" if role == "present" else "reported",
                    "review_status": "candidate",
                    "evidence_ids": [evidence_id],
                }
            )
        records.append(
            {
                "story_id": story_id,
                "review_status": "candidate",
                "date": {
                    "status": "unknown",
                    "label": None,
                    "start_year": None,
                    "end_year": None,
                    "assertion_status": "unknown",
                    "review_status": "candidate",
                    "evidence_ids": [],
                },
                "places": [],
                "people_at_scene": people_rows,
                "unmaterialized_people": [],
                "positional_context": [],
                "event_background": [claim(focus, evidence_id)],
                "narrative_layers": {
                    "scene_focus": [claim(focus, evidence_id)],
                    # Off-frame identities are rendered from people_at_scene
                    # below.  Do not add a generic ontology explanation as
                    # reader-facing prose; only Story-specific claims belong
                    # in this layer.
                    "off_frame_context": [],
                    "historical_ground": [],
                    "resonance": [claim(RESONANCE[story_id], evidence_id, "inferred")] if story_id in RESONANCE else [],
                },
                "evidence_ids": [evidence_id],
                "notes": [
                    "W3 basic scene audit; roles distinguish resolved identity from physical participation.",
                    f"phase orientation: {selected.get('phase_label') or 'omitted'}",
                ],
            }
        )
    output = {
        "schema": 1,
        "stage": "story-scene-context-pilot",
        "records": sorted(records, key=lambda item: item["story_id"]),
    }
    write(OUTPUT_PATH, output)
    return output


if __name__ == "__main__":
    result = build()
    print(f"built W3 Scene Context records: {len(result['records'])}")
