#!/bin/bash

USER_LEVEL=$(whoami)

echo "==================================================="
echo "  [INCOMING TRANSMISSION: NIGEL BILLINGSLEY]"
echo "==================================================="

if [ "$USER_LEVEL" == "recon_user" ]; then
    echo "Ah, $PLAYER_USERNAME! You stand before the Simulation Core bound as recon_user."
    echo "The mainframe seals its ascension keys inside an ancient relational vault (mainframe.db),"
    echo "guided by invisible environment runes (.env) and Alan Parrish's lost field journal (parrish_journal.txt)."
    echo ""
    echo "Beware! The dark hunter Van Pelt has seeded the registry with phantom mirrors to mislead you."
    echo "Consult the audit scrolls in /var/log/mainframe to discern the living branch from the dead."
    echo "Interrogate the vault using the dialect of relational queries, extract the override"
    echo "designated for administrative ascension, and transmit it with deploy_override!"
    echo ""
    echo "Once you possess the key, look to your sudo privileges—the caretaker's audit hound"
    echo "awaits in /opt/jumanji/maintenance/audit_vault.py to help you climb higher!"
elif [ "$USER_LEVEL" == "jumanji_admin" ]; then
    echo "Splendid ascent, old bean! You have stepped into the boots of jumanji_admin!"
    echo "Yet the core simulation still holds you captive. To shatter the curse entirely, you need ROOT access."
    echo ""
    echo "A crowned sentinel binary ('lift_curse') rests within your home quarters, endowed with supreme authority."
    echo "Yet its ancient gears will remain stone-cold if struck unworthily. It demands two sacred tributes:"
    echo "  1. An atmosphere attuned to the sacred ritual—whisper the 432 Hz vibration into JUMANJI_RITUAL."
    echo "  2. An invocation sigil proclaiming the year the lost wanderer returned (--awaken <year>)."
    echo ""
    echo "Consult Alan Parrish's journal in the expedition camp if the years slip your memory,"
    echo "or look into the automaton's clockwork with your reversing tools (gdb, ltrace)!"
elif [ "$USER_LEVEL" == "root" ]; then
    echo "JUMANJI! The veil of the simulation is torn and the curse is broken!"
    echo "The sovereign realm of root is yours. At the summit of the hierarchy (/root/core_override.txt),"
    echo "the final core override awaits. Transmit the master code with deploy_override to claim full victory!"
fi
echo "==================================================="
