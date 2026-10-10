FROM debian:bookworm-slim

# Install necessary tools for Round 3
RUN apt-get update && apt-get install -y \
    curl dnsutils grep coreutils jq bash python3 \
    sudo net-tools procps sqlite3 gcc \
    && rm -rf /var/lib/apt/lists/*

# Create Round 3 users
RUN useradd -m -s /bin/bash recon_user
RUN useradd -m -s /bin/bash jumanji_admin

# Setup Round 3 directory
RUN mkdir -p /round3

# Setup Sudo privileges for Round 3
RUN echo "recon_user ALL=(jumanji_admin) SETENV: NOPASSWD: ALL" > /etc/sudoers.d/recon_user
RUN echo "recon_user ALL=(root) SETENV: NOPASSWD: /usr/local/bin/setup_round3.sh" >> /etc/sudoers.d/recon_user
RUN echo 'Defaults:recon_user env_keep += "CTF_TOKEN CHANT"' >> /etc/sudoers.d/recon_user
RUN echo "Defaults:recon_user !authenticate" >> /etc/sudoers.d/recon_user
RUN chmod 0440 /etc/sudoers.d/recon_user

# Copy Round 3 scripts
COPY setup_round3.sh /usr/local/bin/setup_round3.sh
COPY nigel_comms.sh /usr/local/bin/nigel_comms
COPY deploy_override /usr/local/bin/deploy_override
RUN chmod +x /usr/local/bin/setup_round3.sh /usr/local/bin/nigel_comms /usr/local/bin/deploy_override

# Compile SUID Root challenge
COPY lift_curse.c /home/jumanji_admin/lift_curse.c
RUN gcc /home/jumanji_admin/lift_curse.c -o /home/jumanji_admin/lift_curse \
    && chown root:root /home/jumanji_admin/lift_curse \
    && chmod 4755 /home/jumanji_admin/lift_curse \
    && rm /home/jumanji_admin/lift_curse.c

# Set ownership
RUN chown -R recon_user:recon_user /round3 /home/recon_user
RUN chmod -R 700 /root

WORKDIR /round3
CMD ["/bin/bash", "-c", "tail -f /dev/null"]
