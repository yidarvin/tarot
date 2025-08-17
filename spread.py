import argparse
import random
from typing import List

from dotenv import load_dotenv


DEFAULT_REVERSAL_PROBABILITY = 0.5


def create_standard_tarot_deck() -> List[str]:
    """Return the 78-card Rider–Waite–Smith style tarot deck as names."""
    majors = [
        "The Fool",
        "The Magician",
        "The High Priestess",
        "The Empress",
        "The Emperor",
        "The Hierophant",
        "The Lovers",
        "The Chariot",
        "Strength",
        "The Hermit",
        "Wheel of Fortune",
        "Justice",
        "The Hanged Man",
        "Death",
        "Temperance",
        "The Devil",
        "The Tower",
        "The Star",
        "The Moon",
        "The Sun",
        "Judgement",
        "The World",
    ]

    suits = ["Wands", "Cups", "Swords", "Pentacles"]
    ranks = [
        "Ace",
        "Two",
        "Three",
        "Four",
        "Five",
        "Six",
        "Seven",
        "Eight",
        "Nine",
        "Ten",
        "Page",
        "Knight",
        "Queen",
        "King",
    ]

    minors = [f"{rank} of {suit}" for suit in suits for rank in ranks]
    deck = majors + minors
    assert len(deck) == 78, "Deck should contain exactly 78 cards"
    return deck


def draw_cards(
    deck: List[str],
    num_cards: int,
    *,
    allow_reversed: bool = False,
    reversal_probability: float = DEFAULT_REVERSAL_PROBABILITY,
) -> List[str]:
    """Draw unique cards from the deck.

    If allow_reversed is True, each drawn card has reversal_probability chance
    to be marked as reversed. reversal_probability is clamped to [0, 1].
    """
    if num_cards < 0:
        raise ValueError("Number of cards must be non-negative")
    if num_cards > len(deck):
        raise ValueError("Cannot draw more cards than exist in the deck")

    drawn = random.sample(deck, num_cards)
    if not allow_reversed:
        return drawn

    # Clamp probability to [0, 1]
    if reversal_probability < 0:
        reversal_probability = 0.0
    elif reversal_probability > 1:
        reversal_probability = 1.0

    with_orientations: List[str] = []
    for name in drawn:
        reversed_card = random.random() < reversal_probability
        with_orientations.append(f"{name} (Reversed)" if reversed_card else name)
    return with_orientations


def main() -> None:
    load_dotenv()  # prepares for future OpenAI usage

    parser = argparse.ArgumentParser(description="Tarot spread CLI")
    parser.add_argument("spread", choices=["3card"], help="Which spread to draw")
    parser.add_argument(
        "--reversed",
        dest="reversed",
        action="store_true",
        default=True,
        help="Enable reversed cards (default: on)",
    )
    parser.add_argument(
        "--no-reversed",
        dest="reversed",
        action="store_false",
        help="Disable reversed cards",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Set RNG seed for reproducible draws",
    )
    parser.add_argument(
        "--reversal-prob",
        type=float,
        default=None,
        help="Probability [0-1] that a drawn card is reversed (default 0.5). Use --no-reversed to disable reversals.",
    )
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    deck = create_standard_tarot_deck()

    if args.spread == "3card":
        allow_reversed = args.reversed
        reversal_probability = (
            DEFAULT_REVERSAL_PROBABILITY if args.reversal_prob is None else args.reversal_prob
        )
        if args.reversal_prob is not None and not (0.0 <= args.reversal_prob <= 1.0):
            raise SystemExit("--reversal-prob must be between 0 and 1")

        cards = draw_cards(
            deck,
            3,
            allow_reversed=allow_reversed,
            reversal_probability=reversal_probability,
        )
        print("Three-card spread:")
        for idx, card in enumerate(cards, start=1):
            print(f"{idx}. {card}")
        return

    raise SystemExit("Unsupported spread type")


if __name__ == "__main__":
    main()


