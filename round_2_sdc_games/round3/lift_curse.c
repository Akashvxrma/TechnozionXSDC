#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main() {
    char *chant = getenv("CHANT");
    if (chant && strcmp(chant, "JUMANJI") == 0) {
        printf("THE JUMANJI CHANT ECHOES! ROOTS COLLAPSE! WELCOME, ROOT MASTER.\n");
        setuid(0);
        setgid(0);
        system("/bin/bash -p");
    } else {
        printf("The curse cannot be lifted in silence. The chant is missing from the environment.\n");
        printf("HINT: Set CHANT=JUMANJI in your environment and run this again!\n");
    }
    return 0;
}
