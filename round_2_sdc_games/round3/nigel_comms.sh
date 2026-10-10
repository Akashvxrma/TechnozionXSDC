#!/bin/bash

USER_LEVEL=$(whoami)

echo "==================================================="
echo "  [INCOMING TRANSMISSION: NIGEL BILLINGSLEY]"
echo "==================================================="

if [ "$USER_LEVEL" == "recon_user" ]; then
    echo "Ah, $PLAYER_USERNAME! You've made it to the simulation core."
    echo "You are currently trapped as a basic user. To escalate your"
    echo "privileges, you must find the hidden database credentials."
    echo "Check for hidden files in this directory using 'ls -la'."
    echo "Read the configuration, query 'mainframe.db' using 'sqlite3',"
    echo "and deploy the discovered code using 'deploy_override'!"
elif [ "$USER_LEVEL" == "jumanji_admin" ]; then
    echo "Brilliant work, old bean! You are now the jumanji_admin."
    echo "To break the curse entirely, you need ROOT access."
    echo "There is a compiled program in your home directory that"
    echo "runs with root privileges. But it requires the magical"
    echo "CHANT to be set in your Environment Variables before you"
    echo "run it. Export the variable and run the program!"
elif [ "$USER_LEVEL" == "root" ]; then
    echo "JUMANJI! You have root access! The curse is broken!"
    echo "Read the /root/core_override.txt file and deploy it with:"
    echo "deploy_override OVERRIDE-ROOT-..."
fi
echo "==================================================="
