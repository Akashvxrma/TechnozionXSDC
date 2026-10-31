#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/*
 * The Jumanji Sentinel of the Jaguar Throne
 * SUID root binary guarding the Simulation Core Root Override.
 */

// Helper to decode stack-obfuscated strings
static void xor_decode(char *dst, const unsigned char *src, size_t len, unsigned char key) {
    for (size_t i = 0; i < len; i++) {
        dst[i] = (char)(src[i] ^ key);
    }
    dst[len] = '\0';
}

int main(int argc, char *argv[]) {
    // Obfuscated string: "JUMANJI_RITUAL" ^ 0x5C
    // J=0x4A^0x5C=0x16, U=0x55^0x5C=0x09, M=0x4D^0x5C=0x11, A=0x41^0x5C=0x1D, N=0x4E^0x5C=0x12, J=0x16, I=0x49^0x5C=0x15, _=0x5F^0x5C=0x03, R=0x52^0x5C=0x0E, I=0x15, T=0x54^0x5C=0x08, U=0x09, A=0x1D, L=0x4C^0x5C=0x10
    const unsigned char enc_env_name[] = { 0x16, 0x09, 0x11, 0x1D, 0x12, 0x16, 0x15, 0x03, 0x0E, 0x15, 0x08, 0x09, 0x1D, 0x10 };
    char env_name[15];
    xor_decode(env_name, enc_env_name, 14, 0x5C);

    // Obfuscated string: "CHANT_432HZ" ^ 0x5C
    // C=0x43^0x5C=0x1F, H=0x48^0x5C=0x14, A=0x1D, N=0x12, T=0x08, _=0x03, 4=0x34^0x5C=0x68, 3=0x33^0x5C=0x6F, 2=0x32^0x5C=0x6E, H=0x14, Z=0x5A^0x5C=0x06
    const unsigned char enc_target_chant[] = { 0x1F, 0x14, 0x1D, 0x12, 0x08, 0x03, 0x68, 0x6F, 0x6E, 0x14, 0x06 };
    char target_chant[12];
    xor_decode(target_chant, enc_target_chant, 11, 0x5C);

    // Obfuscated target sigil: "1995" ^ 0x5C
    // 1=0x31^0x5C=0x6D, 9=0x39^0x5C=0x65, 9=0x65, 5=0x35^0x5C=0x69
    const unsigned char enc_target_sigil[] = { 0x6D, 0x65, 0x65, 0x69 };
    char target_sigil[5];
    xor_decode(target_sigil, enc_target_sigil, 4, 0x5C);

    // Retrieve environment ritual
    char *ritual = getenv(env_name);
    if (!ritual) {
        ritual = getenv("CHANT"); // Backward compatibility
    }

    // Step 1: Check Ritual Atmosphere
    if (!ritual || (strcmp(ritual, target_chant) != 0 && strcmp(ritual, "JUMANJI") != 0 && strcmp(ritual, "CHANT_432HZ") != 0)) {
        printf("\n================================================================================\n");
        printf("[JUMANJI ALTAR] The stone jaguar's eyes remain cold, lifeless grey stone.\n");
        printf("================================================================================\n");
        printf("\"The surrounding jungle air carries no ritual breath.\n");
        printf(" Imbue your environment with the sacred vibration of JUMANJI_RITUAL before\n");
        printf(" approaching the Jaguar Altar.\"\n\n");
        printf("(Hint: Read the extracts in parrish_journal.txt or listen to nigel_comms)\n");
        printf("================================================================================\n\n");
        return 1;
    }

    // Step 2: Check Invocation Argument
    if (argc < 3 || strcmp(argv[1], "--awaken") != 0) {
        printf("\n================================================================================\n");
        printf("[JUMANJI ALTAR] The jaguar's ruby eyes flare red! The temple floor shakes!\n");
        printf("================================================================================\n");
        printf("\"The jungle breath stirs the beast, yet the stone seal remains firmly locked.\n");
        printf(" The sentinel demands the hunter's awakening sigil upon challenge:\n");
        printf(" Challenge the automaton with the rite: %s --awaken <SIGIL>\"\n\n", argv[0]);
        printf("(Hint: Consult Alan Parrish's journal or inspect the mechanical heart)\n");
        printf("================================================================================\n\n");
        return 2;
    }

    // Step 3: Validate Sigil
    char *supplied_sigil = argv[2];
    if (strcmp(supplied_sigil, target_sigil) != 0 && strcmp(supplied_sigil, "1995") != 0 && strcmp(supplied_sigil, "JUMANJI") != 0) {
        printf("\n================================================================================\n");
        printf("[JUMANJI ALTAR] A deafening roar echoes through the canopy! Iron thorns shoot out!\n");
        printf("================================================================================\n");
        printf("\"The sigil '%s' is discordant with the sacred harmony.\n", supplied_sigil);
        printf(" The mechanical heart rejects this frequency.\n");
        printf(" Peer into the automaton's internal clockwork (gdb/ltrace) to align the true numeric rune.\"\n");
        printf("================================================================================\n\n");
        return 3;
    }

    // Full Success: Elevate to root and execute root shell
    printf("\n================================================================================\n");
    printf("[THE JUMANJI CHANT RESOUNDS ACROSS THE JUNGLE! ROOTS COLLAPSE!]\n");
    printf("================================================================================\n");
    printf("The stone jaguar shatters! The deep canopy yields supreme authority!\n");
    printf("JUMANJI! Welcome to the sovereign apex of the Simulation Core, Root Master.\n");
    printf("Claim your Core Override at /root/core_override.txt\n");
    printf("================================================================================\n\n");

    setresuid(0, 0, 0);
    setresgid(0, 0, 0);
    execl("/bin/bash", "bash", "-p", NULL);

    return 0;
}
