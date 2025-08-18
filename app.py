import os
from typing import Dict, List, Optional, Tuple

from flask import Flask, render_template, request, send_from_directory, url_for

from spread import (
    create_standard_tarot_deck,
    draw_three_card_spread,
    draw_celtic_cross_spread,
    DEFAULT_REVERSAL_PROBABILITY,
)
from interpreter import TarotInterpreter, parse_spread_markdown, parse_tarot_markdown
from saver import save_read_markdown
from dotenv import load_dotenv


app = Flask(__name__)
load_dotenv()


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
STANDARD_CARDS_DIR = os.path.join(PROJECT_ROOT, "cards", "standard")


# ---------------------------
# Card image filename mapping
# ---------------------------

MAJOR_TO_FILENAME: Dict[str, str] = {
    "The Fool": "RWS_Tarot_00_Fool.jpg",
    "The Magician": "RWS_Tarot_01_Magician.jpg",
    "The High Priestess": "RWS_Tarot_02_High_Priestess.jpg",
    "The Empress": "RWS_Tarot_03_Empress.jpg",
    "The Emperor": "RWS_Tarot_04_Emperor.jpg",
    "The Hierophant": "RWS_Tarot_05_Hierophant.jpg",
    "The Lovers": "RWS_Tarot_06_Lovers.jpg",
    "The Chariot": "RWS_Tarot_07_Chariot.jpg",
    "Strength": "RWS_Tarot_08_Strength.jpg",
    "The Hermit": "RWS_Tarot_09_Hermit.jpg",
    "Wheel of Fortune": "RWS_Tarot_10_Wheel_of_Fortune.jpg",
    "Justice": "RWS_Tarot_11_Justice.jpg",
    "The Hanged Man": "RWS_Tarot_12_Hanged_Man.jpg",
    "Death": "RWS_Tarot_13_Death.jpg",
    "Temperance": "RWS_Tarot_14_Temperance.jpg",
    "The Devil": "RWS_Tarot_15_Devil.jpg",
    "The Tower": "RWS_Tarot_16_Tower.jpg",
    "The Star": "RWS_Tarot_17_Star.jpg",
    "The Moon": "RWS_Tarot_18_Moon.jpg",
    "The Sun": "RWS_Tarot_19_Sun.jpg",
    "Judgement": "RWS_Tarot_20_Judgement.jpg",
    "The World": "RWS_Tarot_21_World.jpg",
}

RANK_TO_NUMBER: Dict[str, int] = {
    "Ace": 1,
    "Two": 2,
    "Three": 3,
    "Four": 4,
    "Five": 5,
    "Six": 6,
    "Seven": 7,
    "Eight": 8,
    "Nine": 9,
    "Ten": 10,
    "Page": 11,
    "Knight": 12,
    "Queen": 13,
    "King": 14,
}

SUIT_TO_PREFIX: Dict[str, str] = {
    "Wands": "Wands",
    "Cups": "Cups",
    "Swords": "Swords",
    "Pentacles": "Pents",  # filenames use PentsXX.jpg
}


def split_card_orientation(card_with_orientation: str) -> Tuple[str, str]:
    if card_with_orientation.endswith("(Reversed)"):
        return card_with_orientation.replace("(Reversed)", "").strip(), "reversed"
    return card_with_orientation, "upright"


def card_title_to_image_filename(title: str) -> Optional[str]:
    """Resolve a base card title (no orientation) to a filename in cards/standard.

    Returns None if it cannot be mapped.
    """
    # Major Arcana
    if title in MAJOR_TO_FILENAME:
        return MAJOR_TO_FILENAME[title]

    # Minor Arcana (e.g., "Ace of Cups", "Three of Swords", "Knight of Pentacles")
    if " of " in title:
        rank, suit = title.split(" of ", 1)
        rank_num = RANK_TO_NUMBER.get(rank)
        suit_prefix = SUIT_TO_PREFIX.get(suit)
        if rank_num is None or suit_prefix is None:
            return None
        return f"{suit_prefix}{rank_num:02d}.jpg"

    return None


def build_spread_payload(
    spread_key: str,
    *,
    allow_reversed: bool,
    reversal_probability: float,
    interpret: bool,
    seed: Optional[int] = None,
) -> Dict:
    if seed is not None:
        import random

        random.seed(seed)

    deck = create_standard_tarot_deck()

    if spread_key == "3card":
        drawn = draw_three_card_spread(
            deck,
            allow_reversed=allow_reversed,
            reversal_probability=reversal_probability,
        )
    elif spread_key == "celticcross":
        drawn = draw_celtic_cross_spread(
            deck,
            allow_reversed=allow_reversed,
            reversal_probability=reversal_probability,
        )
    else:
        raise ValueError("Unsupported spread key")

    # Parse spread positions/coordinates
    spread_map = parse_spread_markdown(os.path.join(PROJECT_ROOT, "spread.MD"))
    if spread_key not in spread_map:
        raise ValueError(f"Spread positions not found for {spread_key}")
    positions = spread_map[spread_key]

    # Optional interpreter (gracefully handle missing API key or network issues)
    interpreter: Optional[TarotInterpreter] = None
    interpretations: List[str] = []
    if interpret and os.getenv("OPENAI_API_KEY"):
        try:
            interpreter = TarotInterpreter(spread_key)
        except Exception:
            interpreter = None

    # Fallback meanings from tarot.MD
    card_meanings = parse_tarot_markdown(os.path.join(PROJECT_ROOT, "tarot.MD"))

    prior: List[Dict] = []
    for idx, card in enumerate(drawn, start=1):
        base_title, orientation = split_card_orientation(card)
        interp_text = ""
        if interpreter is not None:
            try:
                interp_text = interpreter.interpret_card(
                    card=card, position_index=idx, prior_interpretations=prior
                )
            except Exception:
                interp_text = ""

        if not interp_text:
            meanings = card_meanings.get(base_title, {"upright": [], "reversed": []})
            kws = meanings.get(orientation, [])
            if kws:
                interp_text = f"Keywords ({orientation}): " + ", ".join(kws)

        # Append to prior context regardless, so later cards can reference earlier ones
        position_label = positions.get(idx).label if positions.get(idx) else f"Card {idx}"
        prior.append(
            {
                "position_index": idx,
                "position_label": position_label,
                "card": card,
                "orientation": orientation,
                "interpretation": interp_text,
            }
        )

    # Geometry: compute board size from coordinates
    xs = [p.coordinates[0] for p in positions.values()]
    ys = [p.coordinates[1] for p in positions.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    card_width = 140
    card_height = 240
    gap_x = 24
    gap_y = 24
    step_x = card_width + gap_x
    step_y = card_height + gap_y

    board_width = (max_x - min_x + 1) * step_x
    board_height = (max_y - min_y + 1) * step_y

    # Prepare card placements
    placements: List[Dict] = []
    for idx, card in enumerate(drawn, start=1):
        base_title, orientation = split_card_orientation(card)
        filename = card_title_to_image_filename(base_title)
        img_url = (
            url_for("serve_card_image", filename=filename) if filename else None
        )

        pos = positions.get(idx)
        coord = pos.coordinates if pos else (0, 0)
        # CSS top grows downward; our y grows upward, so invert against max_y
        left = (coord[0] - min_x) * step_x
        top = (max_y - coord[1]) * step_y

        placements.append(
            {
                "index": idx,
                "title": base_title,
                "raw": card,
                "orientation": orientation,
                "position_label": pos.label if pos else f"Card {idx}",
                "represents": pos.represents if pos else "",
                "coordinates": coord,
                "left": left,
                "top": top,
                "image_url": img_url,
                "filename": filename,
            }
        )

    # Build right-side panel entries from prior
    right_panel = [
        {
            "index": item["position_index"],
            "position_label": item["position_label"],
            "card": item["card"],
            "orientation": item["orientation"],
            "interpretation": item["interpretation"],
            "represents": positions.get(item["position_index"]).represents
            if positions.get(item["position_index"]) else "",
        }
        for item in prior
    ]

    result = {
        "spread_key": spread_key,
        "board": {
            "width": board_width,
            "height": board_height,
            "card_width": card_width,
            "card_height": card_height,
        },
        "cards": placements,
        "panel": right_panel,
    }

    # Save markdown reading for Obsidian, using the same prior data and optional summary
    summary_text = None
    if interpreter is not None:
        try:
            summary_text = interpreter.summarize_spread(prior)
        except Exception:
            summary_text = None
    try:
        save_read_markdown(spread_key=spread_key, prior=prior, summary_text=summary_text)
    except Exception:
        pass

    return result


@app.get("/")
def home() -> str:
    return render_template("spread.html", payload=None)


@app.get("/spread/<spread_key>")
def render_spread(spread_key: str) -> str:
    # Query params for options
    allow_reversed = request.args.get("reversed", "1") != "0"
    interpret = request.args.get("interpret", "1") != "0"
    seed = request.args.get("seed", type=int)
    reversal_probability = request.args.get(
        "reversal_prob", default=DEFAULT_REVERSAL_PROBABILITY, type=float
    )

    payload = build_spread_payload(
        spread_key,
        allow_reversed=allow_reversed,
        reversal_probability=reversal_probability,
        interpret=interpret,
        seed=seed,
    )
    return render_template("spread.html", payload=payload)


@app.get("/cards/<path:filename>")
def serve_card_image(filename: str):
    return send_from_directory(STANDARD_CARDS_DIR, filename)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)


