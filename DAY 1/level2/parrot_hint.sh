#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: parrot_hint <1-5>"
    echo "Example: parrot_hint 1 (for Dr. Bravestone)"
    exit 1
fi

case "$1" in
    1)
        echo "[LORE] Dr. Bravestone always looks where ordinary travelers do not... beneath the surface."
        echo "[HINT] The jungle shields its ancient relics behind the dot of an unseen compass. Journey into the ruins (/opt/jungle/ruins) and list all things—especially that which cloaks itself in the stealth of a dot."
        ;;
    2)
        echo "[LORE] The Professor's mind wanders as a silent specter, continually plotting in the shadows."
        echo "[HINT] Survey the procession of active spirits marching across the system's ledger. Examine the living tasks and their unspoken words, and his hidden relic shall emerge."
        ;;
    3)
        echo "[LORE] Ruby's martial cadence is a whirlwind, her messages encoded in a rhythm of sixty-four beats."
        echo "[HINT] Deep in her chamber of records (~/Documents), ancient scrolls appear scrambled in strange symbols. Unfold the sixty-four folds of her cipher to reveal her secret."
        ;;
    4)
        echo "[LORE] Mouse guards his munitions pack with his life, yielding only when addressed with supreme authority."
        echo "[HINT] Inquire what elevated privileges the overseers have granted to your soul... a single whispered command from the heights of power unlocks the zoologist's satchel."
        ;;
    5)
        echo "[LORE] Seaplane is cruising high above the canopy, broadcasting a clandestine pulse."
        echo "[HINT] Tune your receiver to the internal airwaves that listen within this very machine. Intercept the silent frequency waiting on your loopback radio to catch his signal out of thin air."
        ;;
    *)
        echo "The parrot squawks loudly: SQUAWK! I only know hints 1 to 5!"
        ;;
esac
