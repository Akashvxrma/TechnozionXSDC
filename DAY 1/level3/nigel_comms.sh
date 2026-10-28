#!/bin/bash

USER_LEVEL=$(whoami)

echo "==================================================="
echo "  [INCOMING TRANSMISSION: NIGEL BILLINGSLEY]"
echo "==================================================="

if [ "$USER_LEVEL" == "recon_user" ]; then
    echo "Ah, $PLAYER_USERNAME! You stand before the Simulation Core bound as a basic user."
    echo "The mainframe seals its ascension keys inside an ancient tabular vault in this realm,"
    echo "guided by invisible environment runes that point the way."
    echo "Do not merely stare at the surface of the stone—interrogate the vault using the"
    echo "dialect of relational queries, extract the override designated for administrative ascension,"
    echo "and transmit the code into the override terminal to elevate your standing!"
elif [ "$USER_LEVEL" == "jumanji_admin" ]; then
    echo "Splendid ascent, old bean! You walk the halls of administrative power,"
    echo "yet the core simulation still holds you captive. To break the curse entirely, you need ROOT access."
    echo "A crowned binary rests within your personal quarters, endowed with supreme authority."
    echo "Yet its ancient gears remain asleep unless the sacred CHANT of the jungle is whispered"
    echo "into your environment's breath before striking the vessel. Imbue your spirit with the chant,"
    echo "awaken the guardian binary, and seize ultimate dominion!"
elif [ "$USER_LEVEL" == "root" ]; then
    echo "JUMANJI! The veil of the simulation is torn and the curse is broken!"
    echo "The sovereign realm of root is yours. At the very summit of the system's root hierarchy,"
    echo "the final core override awaits. Transmit the master code to permanently purge the mainframe!"
fi
echo "==================================================="
