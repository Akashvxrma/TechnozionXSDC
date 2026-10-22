#!/bin/bash
# setup_shrine.sh - King-of-the-Hill Shrine Daemon & Exploit Binary
# Used for Phase 3: Shrine KotH

mkdir -p /shrine /var/log/shrine
chmod 777 /shrine

echo "NO_RULER" > /shrine/claim.txt
chmod 666 /shrine/claim.txt

cat << 'CEOF' > /tmp/claim_shrine.c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>

int main(int argc, char *argv[]) {
    if (argc < 2) {
        printf("Usage: claim_shrine <TEAM_ACCESS_CODE>\n");
        printf("Or set environment variable SHRINE_CONQUEROR=<TEAM_CODE>\n");
        return 1;
    }

    char *env_token = getenv("SHRINE_CONQUEROR");
    char team_code[64];
    strncpy(team_code, argv[1], sizeof(team_code) - 1);
    team_code[sizeof(team_code) - 1] = '\0';

    if (env_token && strlen(env_token) > 0) {
        strncpy(team_code, env_token, sizeof(team_code) - 1);
    }

    // Set real and effective UID to root for shrine claim
    setuid(0);
    setgid(0);

    FILE *f = fopen("/shrine/claim.txt", "w");
    if (!f) {
        perror("Failed to claim throne");
        return 1;
    }

    fprintf(f, "%s\n", team_code);
    fclose(f);

    printf("===================================================\n");
    printf("   THE SHRINE HAS FALLEN! NEW RULER PROCLAIMED: %s\n", team_code);
    printf("   Hold the throne while the server clock ticks!\n");
    printf("===================================================\n");
    return 0;
}
CEOF

gcc /tmp/claim_shrine.c -o /usr/local/bin/claim_shrine 2>/dev/null || true
chown root:root /usr/local/bin/claim_shrine 2>/dev/null || true
chmod 4755 /usr/local/bin/claim_shrine 2>/dev/null || true

echo "Shrine King-of-the-Hill initialized on /shrine/claim.txt"
