FROM debian:bookworm-slim

# Install necessary tools for Level 1 (Simulation Core)
RUN apt-get update && apt-get install -y \
    curl dnsutils grep coreutils jq bash python3 \
    sudo net-tools procps sqlite3 gcc \
    gdb strace binutils file bsdextrautils \
    && rm -rf /var/lib/apt/lists/*

# Create Challenge users
RUN useradd -m -s /bin/bash recon_user
RUN useradd -m -s /bin/bash jumanji_admin

# Setup directories
RUN mkdir -p /level1 /level3 /level2 /opt/jumanji/maintenance /var/log/mainframe

# Setup Sudo privileges:
# 1. Lateral escalation via auditor script (vulnerable to Python module hijacking)
# 2. Setup script execution for container init
RUN echo "recon_user ALL=(jumanji_admin) NOPASSWD: /opt/jumanji/maintenance/audit_vault.py" > /etc/sudoers.d/recon_user
RUN echo "recon_user ALL=(root) SETENV: NOPASSWD: /usr/local/bin/setup_level1.sh, /usr/local/bin/setup_level3.sh, /usr/local/bin/setup_level2.sh" >> /etc/sudoers.d/recon_user
RUN echo 'Defaults:recon_user env_keep += "CTF_TOKEN CHANT JUMANJI_RITUAL"' >> /etc/sudoers.d/recon_user
RUN echo "Defaults:recon_user !authenticate" >> /etc/sudoers.d/recon_user
RUN chmod 0440 /etc/sudoers.d/recon_user

# Copy scripts & binaries
COPY setup_level1.sh /usr/local/bin/setup_level1.sh
COPY nigel_comms.sh /usr/local/bin/nigel_comms
COPY deploy_override /usr/local/bin/deploy_override
COPY audit_vault.py /opt/jumanji/maintenance/audit_vault.py
COPY parrish_journal.txt /level1/parrish_journal.txt

RUN ln -s /usr/local/bin/setup_level1.sh /usr/local/bin/setup_level3.sh && \
    ln -s /usr/local/bin/setup_level1.sh /usr/local/bin/setup_level2.sh && \
    chmod +x /usr/local/bin/setup_level1.sh /usr/local/bin/setup_level3.sh /usr/local/bin/setup_level2.sh /usr/local/bin/nigel_comms /usr/local/bin/deploy_override /opt/jumanji/maintenance/audit_vault.py

# Set ownership and symlinks
RUN chown -R jumanji_admin:jumanji_admin /home/jumanji_admin /opt/jumanji && \
    chmod 755 /opt/jumanji /opt/jumanji/maintenance && \
    chmod 755 /var/log/mainframe
RUN ln -sfn /level1 /level3 && ln -sfn /level1 /level2 && chown -R recon_user:recon_user /level1 /home/recon_user
RUN chmod -R 700 /root

# Compile Stripped SUID Root Challenge (must be owned by root:root with 4755)
COPY lift_curse.c /home/jumanji_admin/lift_curse.c
RUN gcc -O2 /home/jumanji_admin/lift_curse.c -o /home/jumanji_admin/lift_curse \
    && strip --strip-all /home/jumanji_admin/lift_curse \
    && chown root:root /home/jumanji_admin/lift_curse \
    && chmod 4755 /home/jumanji_admin/lift_curse \
    && rm /home/jumanji_admin/lift_curse.c

WORKDIR /level1
CMD ["/bin/bash", "-c", "tail -f /dev/null"]
