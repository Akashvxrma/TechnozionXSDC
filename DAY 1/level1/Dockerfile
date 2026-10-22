FROM debian:bookworm-slim

# Install necessary tools for Level 1
RUN apt-get update && apt-get install -y \
    curl dnsutils grep coreutils jq bash python3 \
    nfs-common ftp openssh-client sudo net-tools procps \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Create Level 1 users
RUN useradd -m -s /bin/bash recon_user
RUN useradd -m -s /bin/bash finbar_admin

# Setup Avatar directories
RUN mkdir -p /bravestone /finbar /ruby /oberon /seaplane

# Setup Sudo privileges for Level 1
RUN echo "recon_user ALL=(finbar_admin) NOPASSWD: /bin/cat /home/finbar_admin/flag.txt" > /etc/sudoers.d/recon_user
RUN echo "recon_user ALL=(root) SETENV: NOPASSWD: /usr/local/bin/setup_level1.sh" >> /etc/sudoers.d/recon_user
RUN echo 'Defaults:recon_user env_keep += "CTF_TOKEN"' >> /etc/sudoers.d/recon_user
RUN echo "Defaults:recon_user !authenticate" >> /etc/sudoers.d/recon_user
RUN chmod 0440 /etc/sudoers.d/recon_user

# Copy Level 1 scripts
COPY setup_level1.sh /usr/local/bin/setup_level1.sh
COPY parrot_hint.sh /usr/local/bin/parrot_hint
COPY complete /usr/local/bin/complete
RUN chmod +x /usr/local/bin/setup_level1.sh /usr/local/bin/parrot_hint /usr/local/bin/complete

# Set ownership
RUN chown -R recon_user:recon_user /bravestone /ruby /oberon /seaplane /home/recon_user
RUN chmod -R 700 /root

WORKDIR /bravestone
CMD ["/bin/bash", "-c", "tail -f /dev/null"]
