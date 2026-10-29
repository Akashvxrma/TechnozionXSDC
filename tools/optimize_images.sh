#!/bin/bash
# Generates the AVIF/WebP/resized image variants served by the templates.
# Usage: tools/optimize_images.sh <dir with full-quality source images>
# Requires: brew install webp libavif (sips ships with macOS)
set -euo pipefail

SRC="${1:?source image directory}"
OUT="$(cd "$(dirname "$0")/.." && pwd)/DAY 1/www/static/assets"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

avif() { avifenc -q 62 -s 4 --jobs all "$1" "$2" >/dev/null; }
webp() { cwebp -quiet -q 82 -m 6 -sharp_yuv -alpha_q 100 "$1" -o "$2"; }

# Full-viewport scene backgrounds: same dimensions, modern formats
for n in choose_username_bg gauntlet_jungle_bg jumanji_bg jumanji_expedition_desk; do
    avif "$SRC/$n.jpg" "$OUT/$n.avif"
    webp "$SRC/$n.jpg" "$OUT/$n.webp"
done

# Thumbnails: sized to 3x their CSS box (relics 76px square, tarot cards 114px wide)
thumb() {  # name ext max_px
    sips -Z "$3" "$SRC/$1.$2" --out "$TMP/$1.png" -s format png >/dev/null
    sips -s format jpeg -s formatOptions 82 "$TMP/$1.png" --out "$OUT/$1-$3.jpg" >/dev/null
    avif "$TMP/$1.png" "$OUT/$1-$3.avif"
    webp "$TMP/$1.png" "$OUT/$1-$3.webp"
}
for n in relic_sun_compass relic_obsidian_blade relic_jaguar_fang relic_golden_idol; do thumb "$n" jpg 240; done
for n in curse_quicksand_card curse_monsoon_card curse_stampede_card; do
    # Portrait cards: width drives the 114px box, so bound the long side to keep 342px+ width
    thumb "$n" jpg 540
done

# Avatar portraits: real_*.png are already WebP-encoded (browsers sniff them), only the seaplane JPEG needs variants
sips -Z 1600 "$SRC/real_seaplane.jpg" --out "$TMP/real_seaplane.png" -s format png >/dev/null
avif "$TMP/real_seaplane.png" "$OUT/real_seaplane.avif"
webp "$TMP/real_seaplane.png" "$OUT/real_seaplane.webp"
