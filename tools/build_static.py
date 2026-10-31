#!/usr/bin/env python3
"""Build minified, content-hashed, precompressed copies of the static JS/CSS into static/dist/.

app.py serves a dist file only while its manifest entry's source hash matches the current source file,
so a stale build can never be served: edited sources fall back to the unminified original until rebuilt.

Usage: tools/build_static.py [--esbuild PATH]
Needs: esbuild (minifier), brotli CLI (optional; .br files skipped without it)
"""
import argparse
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'DAY 1', 'www', 'static')
DIST = os.path.join(STATIC, 'dist')
MANIFEST = os.path.join(DIST, 'manifest.json')

# Our own sources get minified; vendor files are already minified upstream and are only hashed + compressed
MINIFY = ['js/jumanji_3d_engine.js', 'js/jumanji_login_3d.js', 'js/jumanji_fx.js',
          'css/jumanji_design_system.css', 'css/jumanji_auth.css', 'css/jumanji_3d.css', 'css/jumanji_admin.css',
          'vendor/xterm.css', 'vendor/fonts/core.css', 'vendor/fonts/hud.css']
COPY = ['vendor/three.min.js', 'vendor/socket.io.min.js', 'vendor/xterm.js', 'vendor/xterm-addon-fit.js']

KEEP_OLD_SECONDS = 7 * 24 * 3600  # old hashed files stay for pages/browsers still referencing them


def md5(data):
    return hashlib.md5(data).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--esbuild', default=shutil.which('esbuild') or 'esbuild')
    args = ap.parse_args()
    has_esbuild = shutil.which(args.esbuild) or (os.path.isfile(args.esbuild) and os.access(args.esbuild, os.X_OK))
    if not has_esbuild:
        print('warning: esbuild CLI not found, copying assets without minification', file=sys.stderr)
    brotli = shutil.which('brotli')
    if not brotli:
        print('warning: brotli CLI not found, skipping .br files', file=sys.stderr)

    manifest = {}
    for rel in MINIFY + COPY:
        src_path = os.path.join(STATIC, rel)
        with open(src_path, 'rb') as f:
            src = f.read()
        if rel in MINIFY and has_esbuild:
            # No --keep-names: it injects top-level helper vars that would collide with inline page globals.
            # Without a format, esbuild never renames top-level (global) names of plain scripts.
            out = subprocess.run([args.esbuild, '--minify', '--log-level=warning',
                                  '--loader=' + rel.rsplit('.', 1)[1]],
                                 input=src, capture_output=True, check=True).stdout
        else:
            out = src
        stem, ext = rel.rsplit('.', 1)
        dist_rel = 'dist/%s.%s.%s' % (stem, md5(out)[:10], ext)
        dist_path = os.path.join(STATIC, dist_rel)
        os.makedirs(os.path.dirname(dist_path), exist_ok=True)
        if not os.path.exists(dist_path):
            tmp = dist_path + '.tmp'
            with open(tmp, 'wb') as f:
                f.write(out)
            os.replace(tmp, dist_path)
        # Compressed siblings are written atomically; a missing one (e.g. brotli installed later) is filled in
        if not os.path.exists(dist_path + '.gz'):
            with open(dist_path + '.gz.tmp', 'wb') as f:
                f.write(gzip.compress(out, compresslevel=9, mtime=0))
            os.replace(dist_path + '.gz.tmp', dist_path + '.gz')
        if brotli and not os.path.exists(dist_path + '.br'):
            subprocess.run([brotli, '-q', '11', '-f', '-o', dist_path + '.br.tmp', dist_path], check=True)
            os.replace(dist_path + '.br.tmp', dist_path + '.br')
        manifest[rel] = {'src_md5': md5(src)[:10], 'file': dist_rel}
        print('%-32s %8d -> %8d  %s' % (rel, len(src), len(out), dist_rel))

    # Files dropped from the manifest are retired, then deleted once no cached page can still reference them
    try:
        with open(MANIFEST) as f:
            previous = json.load(f)
    except (OSError, ValueError):
        previous = {}
    live = {e['file'] for e in manifest.values()}
    now = time.time()
    retired = {k: v for k, v in previous.get('_retired', {}).items() if k not in live}
    for rel, e in previous.items():
        if rel != '_retired' and e['file'] not in live:
            retired.setdefault(e['file'], now)
    for f_rel, since in list(retired.items()):
        if now - since > KEEP_OLD_SECONDS:
            for suffix in ('', '.gz', '.br'):
                try:
                    os.remove(os.path.join(STATIC, f_rel + suffix))
                except OSError:
                    pass
            del retired[f_rel]
    manifest['_retired'] = retired

    tmp = MANIFEST + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(manifest, f, indent=1, sort_keys=True)
    os.replace(tmp, MANIFEST)

if __name__ == '__main__':
    main()
