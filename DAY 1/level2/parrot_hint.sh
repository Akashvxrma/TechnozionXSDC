#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: parrot_hint <1-5>"
    echo "Example: parrot_hint 1 (for Dr. Bravestone)"
    exit 1
fi

case "$1" in
    1)
        echo "[LORE] Dr. Bravestone always looks where others do not... beneath the surface."
        echo "[TECH] In Linux, files starting with a dot (.) are hidden. Try using 'ls -la' right here or in '/opt/jungle/ruins'."
        ;;
    2)
        echo "[LORE] The Professor's mind is always running in the background, plotting the course."
        echo "[TECH] You can see running background processes using 'ps aux'. Try filtering output with 'grep'."
        ;;
       
    3)
        echo "[LORE] Ruby's moves are a blur, her messages encoded in a rhythm of 64 beats."
        echo "[TECH] The text looks like Base64. Check ~/Documents and decode it using 'base64 -d'."
        ;;
      
    4)
        echo "[LORE] Mouse guards his backpack tightly, but sometimes he leaves a zipper open for his trusted friends."
        echo "[TECH] Check what commands you can run as a superuser by typing 'sudo -l'. If permitted, run 'sudo <command>'."
        ;;
       
    5)
        echo "[LORE] Seaplane is flying high, broadcasting a signal on a hidden frequency... tune your radio to localhost."
        echo "[TECH] You can use 'netstat -tuln' to find open ports. Use 'curl http://127.0.0.1:<port>' to fetch the data."
        ;;
    *)
        echo "The parrot squawks loudly: SQUAWK! I only know hints 1 to 5!"
        ;;
esac
