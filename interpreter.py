import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from openai import OpenAI, BadRequestError


@dataclass
class PositionInfo:
    index: int
    label: str
    represents: str
    coordinates: Tuple[int, int]


def _project_root_path() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _default_path(filename: str) -> str:
    return os.path.join(_project_root_path(), filename)


def parse_spread_markdown(md_path: Optional[str] = None) -> Dict[str, Dict[int, PositionInfo]]:
    """Parse spread.MD into a mapping of spread key -> position index -> info.

    Supported spread keys:
    - "3card" -> "Three-Card Spread"
    - "celticcross" -> "Celtic Cross"
    """
    if md_path is None:
        md_path = _default_path("spread.MD")

    with open(md_path, "r", encoding="utf-8") as f:
        text = f.read()

    spreads: Dict[str, Dict[int, PositionInfo]] = {}

    section_patterns = [
        ("3card", r"###\s+Three-Card Spread([\s\S]*?)(?:\n---|\Z)"),
        ("celticcross", r"###\s+Celtic Cross.*?([\s\S]*?)(?:\n---|\Z)"),
    ]

    card_header_re = re.compile(r"####\s+Card\s+(\d+)\s+—\s+([^\n]+)")
    represents_re = re.compile(r"-\s+\*\*Represents\*\*:\s+([^\n]+)")
    coords_re = re.compile(r"-\s+\*\*Coordinates\*\*:\s*\(([-\d]+),\s*([-\d]+)\)")

    for key, sec_pat in section_patterns:
        match = re.search(sec_pat, text)
        if not match:
            continue
        section = match.group(1)

        positions: Dict[int, PositionInfo] = {}

        # Iterate over each card subsection
        for card_match in card_header_re.finditer(section):
            idx = int(card_match.group(1))
            label = card_match.group(2).strip()

            # Slice from this header to the next header or end of section
            start = card_match.end()
            next_match = card_header_re.search(section, start)
            end = next_match.start() if next_match else len(section)
            body = section[start:end]

            rep_match = represents_re.search(body)
            represents = rep_match.group(1).strip() if rep_match else ""

            coord_match = coords_re.search(body)
            if coord_match:
                x = int(coord_match.group(1))
                y = int(coord_match.group(2))
                coords = (x, y)
            else:
                coords = (0, 0)

            positions[idx] = PositionInfo(index=idx, label=label, represents=represents, coordinates=coords)

        if positions:
            spreads[key] = positions

    return spreads


def parse_tarot_markdown(md_path: Optional[str] = None) -> Dict[str, Dict[str, List[str]]]:
    """Parse tarot.MD into a mapping of card title -> {upright: [...], reversed: [...]} keywords.

    Extracts Major and Minor Arcana uniformly by looking for #### headings
    followed by - Upright and - Reversed lines.
    """
    if md_path is None:
        md_path = _default_path("tarot.MD")

    with open(md_path, "r", encoding="utf-8") as f:
        text = f.read()

    # Match headings like: #### 0 The Fool or #### Ace of Wands
    heading_re = re.compile(r"^####\s+(?:\d+\s+)?(.+)$", re.MULTILINE)
    upright_re = re.compile(r"-\s+Upright:\s+([^\n]+)")
    reversed_re = re.compile(r"-\s+Reversed:\s+([^\n]+)")

    cards: Dict[str, Dict[str, List[str]]] = {}

    headings = list(heading_re.finditer(text))
    for i, h in enumerate(headings):
        title = h.group(1).strip()
        start = h.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[start:end]

        upr = upright_re.search(body)
        rev = reversed_re.search(body)

        upright_keywords = [s.strip() for s in (upr.group(1).split(",") if upr else []) if s.strip()]
        reversed_keywords = [s.strip() for s in (rev.group(1).split(",") if rev else []) if s.strip()]

        if upright_keywords or reversed_keywords:
            cards[title] = {"upright": upright_keywords, "reversed": reversed_keywords}

    return cards


class TarotInterpreter:
    """Interprets tarot draws incrementally using the OpenAI API.

    Each call to interpret_card considers:
    - The selected spread's position semantics from spread.MD
    - The card's keyword meanings from tarot.MD
    - All prior cards and their interpretations in the current spread
    """

    def __init__(
        self,
        spread_key: str,
        *,
        spread_md_path: Optional[str] = None,
        tarot_md_path: Optional[str] = None,
        model: str = "gpt-5",
        temperature: float = 1.0,
    ) -> None:
        load_dotenv()
        self.client = OpenAI()
        self.model = model
        self.temperature = temperature
        self.spread_key = spread_key

        self.spread_map = parse_spread_markdown(spread_md_path)
        if spread_key not in self.spread_map:
            raise ValueError(f"Unsupported spread key: {spread_key}")
        self.positions = self.spread_map[spread_key]

        self.card_meanings = parse_tarot_markdown(tarot_md_path)

    @staticmethod
    def _split_card_orientation(card: str) -> Tuple[str, str]:
        if card.endswith("(Reversed)"):
            base = card.replace("(Reversed)", "").strip()
            return base, "reversed"
        return card, "upright"

    def _lookup_card_keywords(self, base_title: str) -> Dict[str, List[str]]:
        return self.card_meanings.get(base_title, {"upright": [], "reversed": []})

    def _build_messages(
        self,
        *,
        card: str,
        position_index: int,
        prior: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        base_title, orientation = self._split_card_orientation(card)
        keywords = self._lookup_card_keywords(base_title)

        pos = self.positions.get(position_index)
        pos_label = pos.label if pos else f"Card {position_index}"
        pos_coords = pos.coordinates if pos else (0, 0)
        pos_represents = pos.represents if pos else ""

        prior_slim = [
            {
                "position_index": p.get("position_index"),
                "position_label": p.get("position_label"),
                "card": p.get("card"),
                "orientation": p.get("orientation"),
                "summary": p.get("interpretation", ""),
            }
            for p in prior
        ]

        system_prompt = (
            "You are a concise, insightful tarot interpreter."
            " Use the spread position semantics, the card's upright/reversed keywords,"
            " and the prior cards' interpretations to synthesize a relevant, practical interpretation."
            " Keep it to 3-6 sentences. Avoid generic platitudes; be specific to the position."
        )

        user_content = {
            "spread_position": {
                "index": position_index,
                "label": pos_label,
                "coordinates": pos_coords,
                "represents": pos_represents,
            },
            "card": {
                "title": base_title,
                "orientation": orientation,
                "keywords": keywords.get(orientation, []),
                "all_keywords": keywords,
            },
            "prior_cards": prior_slim,
            "instructions": "Interpret this draw for the specified position. If prior cards suggest themes, weave them in briefly."
        }

        # Minimal JSON-ish text payload keeps model input stable across calls
        import json
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
        ]
        return messages

    def interpret_card(
        self,
        *,
        card: str,
        position_index: int,
        prior_interpretations: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        messages = self._build_messages(
            card=card,
            position_index=position_index,
            prior=prior_interpretations or [],
        )

        # Prepare parameters; avoid passing temperature when at default (1.0)
        params = {
            "model": self.model,
            "messages": messages,
        }
        if self.temperature is not None and self.temperature != 1.0:
            params["temperature"] = self.temperature

        try:
            completion = self.client.chat.completions.create(**params)
        except BadRequestError as e:
            # Retry without temperature if it's rejected by the model
            if "temperature" in str(e):
                params.pop("temperature", None)
                completion = self.client.chat.completions.create(**params)
            else:
                raise

        return (completion.choices[0].message.content or "").strip()

    def _build_summary_messages(self, prior: List[Dict[str, str]]) -> List[Dict[str, str]]:
        # Prepare a compact representation of spread positions
        positions_payload = [
            {
                "index": p.index,
                "label": p.label,
                "coordinates": p.coordinates,
                "represents": p.represents,
            }
            for p in sorted(self.positions.values(), key=lambda x: x.index)
        ]

        # Use prior cards and their interpretations
        prior_payload = [
            {
                "position_index": item.get("position_index"),
                "position_label": item.get("position_label"),
                "card": item.get("card"),
                "orientation": item.get("orientation"),
                "interpretation": item.get("interpretation", ""),
            }
            for item in prior
        ]

        system_prompt = (
            "You are a concise, insightful tarot interpreter."
            " Provide a cohesive summary that synthesizes the entire spread."
            " Identify central themes, connecting threads, practical guidance, and likely trajectory."
            " Resolve any tensions between positions or reversals."
            " Output 5-8 sentences, no bullet points."
        )

        import json
        user_content = {
            "spread": {
                "key": self.spread_key,
                "positions": positions_payload,
            },
            "cards": prior_payload,
            "instructions": "Write a final summary for the reading."
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
        ]
        return messages

    def summarize_spread(self, prior_interpretations: List[Dict[str, str]]) -> str:
        messages = self._build_summary_messages(prior_interpretations)

        params = {
            "model": self.model,
            "messages": messages,
        }
        if self.temperature is not None and self.temperature != 1.0:
            params["temperature"] = self.temperature

        try:
            completion = self.client.chat.completions.create(**params)
        except BadRequestError as e:
            if "temperature" in str(e):
                params.pop("temperature", None)
                completion = self.client.chat.completions.create(**params)
            else:
                raise

        return (completion.choices[0].message.content or "").strip()


