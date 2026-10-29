#!/bin/bash
# Server-side deploy, run on the EC2 host:  deploy/deploy.sh [--nginx]
#   1. git pull   2. build minified/hashed/precompressed static assets   3. (--nginx) install + reload nginx config
#   4. restart the game server
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ESBUILD_VERSION=0.24.2
ESBUILD_SHA256=aa469e907204bade7c37df6376f7ce3562574e937a61984ba8b89db63e03883a
ESBUILD="$ROOT/tools/bin/esbuild"

git pull --ff-only

if [ ! -x "$ESBUILD" ] || [ "$("$ESBUILD" --version)" != "$ESBUILD_VERSION" ]; then
    tmp="$(mktemp -d)"
    curl -fsSL -o "$tmp/esbuild.tgz" "https://registry.npmjs.org/@esbuild/linux-x64/-/linux-x64-$ESBUILD_VERSION.tgz"
    echo "$ESBUILD_SHA256  $tmp/esbuild.tgz" | sha256sum -c --quiet -
    tar -xzf "$tmp/esbuild.tgz" -C "$tmp"
    mkdir -p "$ROOT/tools/bin"
    install -m 755 "$tmp/package/bin/esbuild" "$ESBUILD"
    rm -rf "$tmp"
fi
command -v brotli >/dev/null || sudo DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get install -y -qq brotli

python3 tools/build_static.py --esbuild "$ESBUILD"

if [ "${1:-}" = "--nginx" ]; then
    dpkg -s libnginx-mod-http-brotli-filter libnginx-mod-http-brotli-static >/dev/null 2>&1 \
        || sudo DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get install -y -qq libnginx-mod-http-brotli-filter libnginx-mod-http-brotli-static
    # Headroom for one WebSocket + one upstream connection per player terminal
    sudo sed -i -E 's/^(\s*)worker_connections [0-9]+;/\1worker_connections 4096;/' /etc/nginx/nginx.conf
    grep -q '^worker_rlimit_nofile' /etc/nginx/nginx.conf \
        || sudo sed -i 's/^worker_processes auto;/worker_processes auto;\nworker_rlimit_nofile 16384;/' /etc/nginx/nginx.conf

    site=/etc/nginx/sites-available/jumanji-ctf
    backup="/etc/nginx/jumanji-ctf.bak-$(date +%s)"
    sudo cp "$site" "$backup"
    sudo cp "$ROOT/deploy/nginx-jumanji-ctf.conf" "$site"
    if ! sudo nginx -t; then
        echo "nginx config test failed, restoring $backup" >&2
        sudo cp "$backup" "$site"
        exit 1
    fi
    sudo systemctl reload nginx
fi

sudo systemctl restart jumanji-ctf
sleep 3
systemctl is-active jumanji-ctf
