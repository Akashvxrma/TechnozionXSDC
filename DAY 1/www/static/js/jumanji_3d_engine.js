/* ==========================================================================
   JUMANJI 3D WORLD — WebGL layer for the Expedition Noir templates
   Requires three.js r149 (global THREE) and jumanji_fx.js (window.JX).

   <body data-world="hub">      cursed board box, crystal dome, jaguar-eye emerald,
                                backlit jungle wall with god-rays, spores, mist
   <body data-world="ambient">  spores + ground mist behind the level screens

   Modules attach themselves when their markup exists on the page:
     .relic-token[data-token]   RelicTokens  — Day 1 Level 2 avatar tokens + stone seal
     .bezel > .crt-glass        FieldRig     — terminal chassis, CRT shader, knob, LEDs

   Public API (window.JX3D):
     setMode('resting' | 'boardOpen' | 'terminalFocus')
     toggleBoard(open?)
     deploy(href, kind)         'board' | 'emerald': open the box, fly the camera, navigate
     stamp(avatarId)            press the stone seal onto a relic token
     signal(name, value)        'link' (bool) | 'telemetry' | 'key'

   No WebGL, or a failed init: <html> gets .jx3d-fallback and the CSS 3D
   perspective fallback in jumanji_3d.css takes over.
   ========================================================================== */
(function () {
    'use strict';

    const THREE = window.THREE;
    const TAU = Math.PI * 2;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const root = document.documentElement;

    /* ------------------------------------------------------------------ *
     * 1. Small math helpers
     * ------------------------------------------------------------------ */

    const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
    const lerp = (a, b, t) => a + (b - a) * t;
    // Frame-rate independent exponential smoothing: the gap closes by the same
    // fraction per second whether we run at 30 or 144 fps.
    const damp = (a, b, k, dt) => a + (b - a) * (1 - Math.exp(-k * dt));
    const easeInOutCubic = t => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
    const easeInQuad = t => t * t;
    const easeOutCubic = t => 1 - Math.pow(1 - t, 3);

    // War-drum heartbeat at 68 BPM: a sharp "lub" on the beat and a softer
    // "dub" a quarter-cycle later, each an exponential decay. Drives the
    // emerald light, the caustics, the seam glow and the audio thump.
    const BEAT = 60 / 68;
    const DUB_AT = 0.24;
    function heartbeat(t) {
        const ph = (t % BEAT) / BEAT;
        const lub = Math.exp(-ph * 12);
        const d = ph - DUB_AT;
        const dub = d > 0 ? 0.65 * Math.exp(-d * 14) : 0;
        return Math.min(1, lub + dub);
    }

    // Integer hash → [0, 1). Math.imul keeps the multiply in 32 bits.
    function hash2(x, y, seed) {
        let h = (Math.imul(x + seed * 1013, 374761393) + Math.imul(y, 668265263)) | 0;
        h = Math.imul(h ^ (h >>> 13), 1274126177);
        h ^= h >>> 16;
        return (h >>> 0) / 4294967296;
    }

    // Periodic value noise: lattice indices wrap at (px, py), so canvas textures
    // built from it tile with no seam when used with RepeatWrapping.
    function vnoise(x, y, px, py, seed) {
        const xi = Math.floor(x), yi = Math.floor(y);
        const xf = x - xi, yf = y - yi;
        const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
        const x0 = ((xi % px) + px) % px, x1 = (x0 + 1) % px;
        const y0 = ((yi % py) + py) % py, y1 = (y0 + 1) % py;
        const a = hash2(x0, y0, seed), b = hash2(x1, y0, seed);
        const c = hash2(x0, y1, seed), d = hash2(x1, y1, seed);
        return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
    }

    function fbm(x, y, px, py, octaves, seed) {
        let sum = 0, amp = 0.5, norm = 0;
        for (let i = 0; i < octaves; i++) {
            sum += amp * vnoise(x, y, px, py, seed + i);
            norm += amp;
            x *= 2; y *= 2; px *= 2; py *= 2; amp *= 0.5;
        }
        return sum / norm;
    }

    /* ------------------------------------------------------------------ *
     * 2. Capability & tier detection
     * ------------------------------------------------------------------ */

    function webglAvailable() {
        try {
            const c = document.createElement('canvas');
            return !!(c.getContext('webgl2') || c.getContext('webgl'));
        } catch (e) {
            return false;
        }
    }

    // high: composer + god-rays + shadows + MSAA   mid: composer + rays
    // low: direct render, no post, fewer spores
    function detectTier() {
        const mem = navigator.deviceMemory || 8;
        const cores = navigator.hardwareConcurrency || 8;
        const small = Math.min(screen.width, screen.height) < 500;
        if (mem <= 2 || cores <= 2) return 'low';
        if (mem <= 4 || cores <= 4 || small) return 'mid';
        return 'high';
    }

    /* ------------------------------------------------------------------ *
     * 3. Procedural canvas textures (no external image assets)
     * ------------------------------------------------------------------ */

    let maxAniso = 1;

    function makeCanvas(w, h) {
        const c = document.createElement('canvas');
        c.width = w;
        c.height = h;
        return [c, c.getContext('2d')];
    }

    function texture(c, { srgb = false, repeat = null } = {}) {
        const t = new THREE.CanvasTexture(c);
        if (srgb) t.encoding = THREE.sRGBEncoding;
        t.anisotropy = maxAniso;
        if (repeat) {
            t.wrapS = t.wrapT = THREE.RepeatWrapping;
            t.repeat.set(repeat[0], repeat[1]);
        }
        return t;
    }

    // A palette entry is either a CSS colour or a canvas to tile as a pattern.
    // Patterns are made per context, so the same palette paints any canvas.
    const ink = (g, v) => (typeof v === 'string' ? v : g.createPattern(v, 'repeat'));

    // Ironwood: grain runs along x. Ring count along y is an integer (28) so
    // sin(v·28·2π) is periodic, and the fbm warp is periodic too → seamless tile.
    function woodTile(size, seed, dark, light) {
        const [c, g] = makeCanvas(size, size);
        const img = g.createImageData(size, size);
        const d = img.data;
        for (let y = 0; y < size; y++) {
            for (let x = 0; x < size; x++) {
                const u = x / size, v = y / size;
                const warp = fbm(u * 3, v * 12, 3, 12, 3, seed);
                const rings = 0.5 + 0.5 * Math.sin((v * 28 + warp * 4) * TAU);
                const pores = vnoise(u * 96, v * 384, 96, 384, seed + 7);
                const t = clamp(0.55 * Math.pow(rings, 1.6) + 0.3 * warp + 0.15 * pores, 0, 1);
                const i = (y * size + x) * 4;
                d[i] = lerp(dark[0], light[0], t);
                d[i + 1] = lerp(dark[1], light[1], t);
                d[i + 2] = lerp(dark[2], light[2], t);
                d[i + 3] = 255;
            }
        }
        g.putImageData(img, 0, 0);
        return c;
    }

    // Wet mossy stone: fbm body, ridged noise for cracks, a second fbm for moss
    // patches. Returns colour and height canvases from the same field.
    function stoneTile(size, seed) {
        const [c, g] = makeCanvas(size, size);
        const [hc, hg] = makeCanvas(size, size);
        const img = g.createImageData(size, size);
        const himg = hg.createImageData(size, size);
        const d = img.data, h = himg.data;
        for (let y = 0; y < size; y++) {
            for (let x = 0; x < size; x++) {
                const u = x / size, v = y / size;
                const n = fbm(u * 8, v * 8, 8, 8, 5, seed);
                // Ridged noise: 1 − |2n − 1| peaks along the zero-crossings → thin
                // crack lines. A second noise masks most of them so cracks stay sparse.
                const ridge = 1 - Math.abs(fbm(u * 5, v * 5, 5, 5, 3, seed + 3) * 2 - 1);
                const crackMask = clamp((vnoise(u * 3, v * 3, 3, 3, seed + 5) - 0.55) * 4, 0, 1);
                const crack = clamp((ridge - 0.965) / 0.03, 0, 1) * crackMask;
                const moss = clamp((fbm(u * 4, v * 4, 4, 4, 4, seed + 11) - 0.56) / 0.14, 0, 1) * 0.8;
                const i = (y * size + x) * 4;
                const s = 34 + n * 46;
                d[i] = lerp(s * 0.92, 26, moss) * (1 - crack * 0.6);
                d[i + 1] = lerp(s, 58, moss) * (1 - crack * 0.6);
                d[i + 2] = lerp(s * 0.88, 24, moss) * (1 - crack * 0.6);
                d[i + 3] = 255;
                const hv = clamp(n * 0.75 + moss * 0.25 - crack * 0.6, 0, 1) * 255;
                h[i] = h[i + 1] = h[i + 2] = hv;
                h[i + 3] = 255;
            }
        }
        g.putImageData(img, 0, 0);
        hg.putImageData(himg, 0, 0);
        return { color: c, height: hc };
    }

    function radialSprite(size, stops) {
        const [c, g] = makeCanvas(size, size);
        const grd = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
        stops.forEach(([o, col]) => grd.addColorStop(o, col));
        g.fillStyle = grd;
        g.fillRect(0, 0, size, size);
        return c;
    }

    /* ---- Gold-inlay animal reliefs (unit space, facing right) ---- */

    const ANIMALS = {
        elephant(g) {
            g.beginPath();
            g.ellipse(-0.1, 0, 0.62, 0.4, 0, 0, TAU);
            g.ellipse(0.55, -0.14, 0.3, 0.32, 0, 0, TAU);
            g.rect(-0.62, 0.12, 0.18, 0.58);
            g.rect(-0.32, 0.18, 0.17, 0.52);
            g.rect(0.08, 0.18, 0.17, 0.52);
            g.rect(0.32, 0.12, 0.17, 0.58);
            g.fill();
            g.lineCap = 'round';
            g.lineWidth = 0.15;
            g.beginPath();
            g.moveTo(0.78, -0.06);
            g.quadraticCurveTo(1.0, 0.3, 0.86, 0.62);
            g.quadraticCurveTo(0.82, 0.74, 0.94, 0.72);
            g.stroke();
            g.lineWidth = 0.05;
            g.beginPath();
            g.moveTo(-0.7, -0.08);
            g.quadraticCurveTo(-0.86, 0.12, -0.8, 0.34);
            g.stroke();
        },
        rhino(g) {
            g.beginPath();
            g.ellipse(-0.08, 0, 0.66, 0.36, 0, 0, TAU);
            g.moveTo(0.42, -0.26); g.lineTo(0.95, -0.06); g.lineTo(1.02, 0.14); g.lineTo(0.5, 0.24); g.closePath();
            g.moveTo(0.86, -0.08); g.lineTo(1.04, -0.5); g.lineTo(0.97, -0.04); g.closePath();
            g.moveTo(0.68, -0.18); g.lineTo(0.77, -0.4); g.lineTo(0.8, -0.15); g.closePath();
            g.moveTo(0.44, -0.24); g.lineTo(0.47, -0.44); g.lineTo(0.56, -0.25); g.closePath();
            g.rect(-0.6, 0.15, 0.2, 0.45);
            g.rect(-0.3, 0.2, 0.2, 0.4);
            g.rect(0.08, 0.2, 0.2, 0.4);
            g.rect(0.32, 0.15, 0.2, 0.45);
            g.fill();
            g.lineCap = 'round';
            g.lineWidth = 0.05;
            g.beginPath();
            g.moveTo(-0.72, -0.08);
            g.quadraticCurveTo(-0.86, 0.06, -0.82, 0.24);
            g.stroke();
        },
        monkey(g) {
            g.beginPath();
            g.ellipse(0, 0.15, 0.3, 0.4, 0, 0, TAU);
            g.ellipse(0.12, -0.38, 0.22, 0.22, 0, 0, TAU);
            g.ellipse(0.3, -0.32, 0.12, 0.09, 0, 0, TAU);
            g.ellipse(-0.08, -0.42, 0.08, 0.08, 0, 0, TAU);
            g.ellipse(0.14, 0.5, 0.28, 0.11, 0, 0, TAU);
            g.fill();
            g.lineCap = 'round';
            g.lineWidth = 0.1;
            g.beginPath();
            g.moveTo(0.12, -0.05);
            g.quadraticCurveTo(0.42, 0.1, 0.36, 0.36);
            g.stroke();
            g.lineWidth = 0.07;
            g.beginPath();
            g.moveTo(-0.24, 0.42);
            g.bezierCurveTo(-0.8, 0.6, -0.95, 0.0, -0.66, -0.1);
            g.quadraticCurveTo(-0.5, -0.12, -0.52, 0.04);
            g.stroke();
        },
        crocodile(g) {
            g.beginPath();
            g.ellipse(-0.05, 0, 0.55, 0.16, 0, 0, TAU);
            g.moveTo(0.42, -0.1); g.lineTo(1.0, -0.02); g.lineTo(1.0, 0.06); g.lineTo(0.42, 0.13); g.closePath();
            g.moveTo(-0.45, -0.12); g.lineTo(-1.02, 0.05); g.lineTo(-0.45, 0.15); g.closePath();
            for (let i = 0; i < 7; i++) {
                const x = -0.5 + i * 0.14;
                g.moveTo(x, -0.12); g.lineTo(x + 0.06, -0.24); g.lineTo(x + 0.12, -0.12); g.closePath();
            }
            g.rect(-0.35, 0.08, 0.1, 0.24);
            g.rect(0.2, 0.08, 0.1, 0.24);
            g.fill();
        }
    };

    function drawAnimal(g, name, x, y, s, flip, style) {
        g.save();
        g.translate(x, y);
        g.scale(flip ? -s : s, s);
        g.fillStyle = style;
        g.strokeStyle = style;
        ANIMALS[name](g);
        g.restore();
    }

    function spacedText(g, text, x, y, spacing) {
        const chars = [...text];
        const widths = chars.map(ch => g.measureText(ch).width);
        const total = widths.reduce((a, b) => a + b, 0) + spacing * (chars.length - 1);
        let cx = x - total / 2;
        g.textAlign = 'left';
        chars.forEach((ch, i) => {
            g.fillText(ch, cx, y);
            cx += widths[i] + spacing;
        });
    }

    function wrapLines(g, text, maxW) {
        const words = text.split(' ');
        const lines = [];
        let line = '';
        words.forEach(w => {
            const test = line ? line + ' ' + w : w;
            if (g.measureText(test).width > maxW && line) {
                lines.push(line);
                line = w;
            } else {
                line = test;
            }
        });
        if (line) lines.push(line);
        return lines;
    }

    // Every board surface is painted four times with different "inks": colour,
    // bump height, roughness and metalness. Gold leaf is white in the metal pass
    // and dark in the roughness pass, so the PBR shader makes it shine while the
    // wood stays matte, all from one set of drawing code.
    function passPalettes(woodCanvas) {
        return {
            color: { wood: woodCanvas, panel: 'rgba(0,0,0,0.38)', gold: '#d4a640', goldDeep: '#7a5512', tileA: '#0e3b22', tileB: '#2b170a', rune: '#d4a640', ink: '#d4a640', shadow: 'rgba(0,0,0,0.75)', vignette: true },
            bump: { wood: woodCanvas, panel: 'rgba(0,0,0,0.25)', gold: '#ffffff', goldDeep: '#bbbbbb', tileA: '#a0a0a0', tileB: '#8a8a8a', rune: '#ffffff', ink: '#ffffff', shadow: '#000000' },
            rough: { wood: '#d6d6d6', panel: null, gold: '#4d4d4d', goldDeep: '#707070', tileA: '#8a8a8a', tileB: '#c8c8c8', rune: '#4d4d4d', ink: '#4d4d4d', shadow: '#ffffff' },
            metal: { wood: '#000000', panel: null, gold: '#ffffff', goldDeep: '#ffffff', tileA: '#000000', tileB: '#000000', rune: '#ffffff', ink: '#ffffff', shadow: '#000000' }
        };
    }

    function goldBorder(g, w, h, P, inset) {
        g.strokeStyle = P.gold;
        g.lineWidth = 7;
        g.strokeRect(inset, inset, w - inset * 2, h - inset * 2);
        g.lineWidth = 2.5;
        g.strokeRect(inset + 16, inset + 16, w - (inset + 16) * 2, h - (inset + 16) * 2);
        [[inset, inset], [w - inset, inset], [inset, h - inset], [w - inset, h - inset]].forEach(([x, y]) => {
            g.save();
            g.translate(x, y);
            g.rotate(Math.PI / 4);
            g.fillStyle = P.gold;
            g.fillRect(-14, -14, 28, 28);
            g.restore();
        });
    }

    // The board face: an Archimedean spiral of trail squares winding from the
    // rim into the crystal-dome socket, with an animal medallion in each corner.
    // 1536 px across 3.2 world units → 480 px per unit.
    function paintBoardFace(g, W, H, P) {
        g.fillStyle = ink(g, P.wood);
        g.fillRect(0, 0, W, H);
        if (P.panel) {
            g.fillStyle = P.panel;
            g.fillRect(40, 40, W - 80, H - 80);
        }
        goldBorder(g, W, H, P, 30);

        const cx = W / 2, cy = H / 2;
        const aspect = 1.4;
        // r(θ) = r0 − (r0 − r1)·θ/θmax, stretched by the board aspect so the
        // path follows the rectangle. Tiles are placed at equal arc length.
        const r0 = 448, r1 = 300, thetaMax = 2.35 * TAU;
        const at = th => {
            const r = r0 - (r0 - r1) * th / thetaMax;
            return [cx + Math.cos(th - Math.PI / 2) * r * aspect, cy + Math.sin(th - Math.PI / 2) * r];
        };
        let prev = at(0), acc = 0, n = 0;
        for (let th = 0; th < thetaMax; th += 0.002) {
            const p = at(th);
            acc += Math.hypot(p[0] - prev[0], p[1] - prev[1]);
            if (acc >= 64) {
                acc = 0;
                const ang = Math.atan2(p[1] - prev[1], p[0] - prev[0]);
                g.save();
                g.translate(p[0], p[1]);
                g.rotate(ang);
                g.fillStyle = n % 7 === 6 ? P.rune : (n % 2 ? P.tileA : P.tileB);
                g.fillRect(-26, -26, 52, 52);
                g.strokeStyle = P.gold;
                g.lineWidth = 3;
                g.strokeRect(-26, -26, 52, 52);
                g.restore();
                n++;
            }
            prev = p;
        }

        // Dome socket: dome radius 0.46 → 221 px
        g.strokeStyle = P.gold;
        g.lineWidth = 12;
        g.beginPath(); g.arc(cx, cy, 238, 0, TAU); g.stroke();
        g.lineWidth = 3;
        g.beginPath(); g.arc(cx, cy, 262, 0, TAU); g.stroke();
        for (let i = 0; i < 24; i++) {
            const a = (i / 24) * TAU;
            g.beginPath();
            g.moveTo(cx + Math.cos(a) * 246, cy + Math.sin(a) * 246);
            g.lineTo(cx + Math.cos(a) * 262, cy + Math.sin(a) * 262);
            g.stroke();
        }

        const med = [['elephant', 150, 150, false], ['rhino', W - 150, 150, true], ['monkey', 150, H - 150, false], ['crocodile', W - 150, H - 150, true]];
        med.forEach(([name, x, y, flip]) => {
            g.fillStyle = P.panel ? 'rgba(0,0,0,0.45)' : ink(g, P.wood);
            g.beginPath(); g.arc(x, y, 84, 0, TAU); g.fill();
            g.strokeStyle = P.gold;
            g.lineWidth = 6;
            g.beginPath(); g.arc(x, y, 84, 0, TAU); g.stroke();
            g.lineWidth = 2;
            g.beginPath(); g.arc(x, y, 72, 0, TAU); g.stroke();
            drawAnimal(g, name, x, y + 4, 52, flip, P.gold);
        });

        if (P.vignette) {
            const v = g.createRadialGradient(cx, cy, H * 0.3, cx, cy, W * 0.62);
            v.addColorStop(0, 'rgba(0,0,0,0)');
            v.addColorStop(1, 'rgba(0,0,0,0.55)');
            g.fillStyle = v;
            g.fillRect(0, 0, W, H);
        }
    }

    // Lid exterior across both wings: carved JUMANJI title and gold reliefs.
    function paintLidOuter(g, W, H, P, fontsReady) {
        g.fillStyle = ink(g, P.wood);
        g.fillRect(0, 0, W, H);
        goldBorder(g, W, H, P, 30);

        // Vine scrollwork along the top and bottom rails
        g.strokeStyle = P.goldDeep;
        g.lineWidth = 4;
        [110, H - 110].forEach(y => {
            g.beginPath();
            for (let x = 120; x <= W - 120; x += 8) {
                const yy = y + Math.sin(x * 0.03) * 14;
                if (x === 120) g.moveTo(x, yy); else g.lineTo(x, yy);
            }
            g.stroke();
            g.fillStyle = P.goldDeep;
            for (let x = 150; x < W - 120; x += 94) {
                g.beginPath();
                g.ellipse(x, y + Math.sin(x * 0.03) * 14 - 16, 9, 20, 0.6, 0, TAU);
                g.fill();
            }
        });

        drawAnimal(g, 'monkey', 250, 270, 96, false, P.gold);
        drawAnimal(g, 'monkey', W - 250, 270, 96, true, P.gold);
        drawAnimal(g, 'elephant', 280, H - 280, 120, false, P.gold);
        drawAnimal(g, 'rhino', W - 280, H - 280, 112, true, P.gold);

        if (fontsReady) {
            g.font = '900 172px Cinzel, Georgia, serif';
            g.textBaseline = 'middle';
            // Carved: dark recess offset down-right, then the gold leaf on top
            g.fillStyle = P.shadow;
            spacedText(g, 'JUMANJI', W / 2 + 5, H / 2 + 7, 26);
            g.fillStyle = P.ink;
            spacedText(g, 'JUMANJI', W / 2, H / 2, 26);
        }
    }

    // Lid interior, one wing each. Text is from the 1995 box.
    const INNER_TEXT = {
        left: { title: 'JUMANJI', body: 'Adventurers beware: do not begin unless you intend to finish.' },
        right: { title: null, body: 'The exciting consequences of the game will vanish only when a player has reached Jumanji and called out its name.' }
    };

    function paintLidInner(g, W, H, P, side, fontsReady) {
        g.fillStyle = ink(g, P.wood);
        g.fillRect(0, 0, W, H);
        if (P.panel) {
            g.fillStyle = P.panel;
            g.fillRect(0, 0, W, H);
        }
        goldBorder(g, W, H, P, 28);
        const copy = INNER_TEXT[side];
        if (!fontsReady) return;
        g.textBaseline = 'middle';
        let y = 250;
        if (copy.title) {
            g.font = '900 110px Cinzel, Georgia, serif';
            g.fillStyle = P.shadow;
            spacedText(g, copy.title, W / 2 + 3, y + 4, 12);
            g.fillStyle = P.ink;
            spacedText(g, copy.title, W / 2, y, 12);
            y += 150;
        } else {
            drawAnimal(g, 'elephant', W / 2, y, 90, false, P.gold);
            y += 170;
        }
        g.font = '700 46px Cinzel, Georgia, serif';
        g.textAlign = 'center';
        wrapLines(g, copy.body, W - 170).forEach(line => {
            g.fillStyle = P.shadow;
            g.fillText(line, W / 2 + 2, y + 3);
            g.fillStyle = P.ink;
            g.fillText(line, W / 2, y);
            y += 70;
        });
    }

    const PBR_KEYS = ['map', 'bumpMap', 'roughnessMap', 'metalnessMap'];

    // Build {map, bumpMap, roughnessMap, metalnessMap} from one painter.
    function pbrSet(W, H, painter, palettes) {
        const out = {};
        [['color', 'map'], ['bump', 'bumpMap'], ['rough', 'roughnessMap'], ['metal', 'metalnessMap']].forEach(([pass, key]) => {
            const [c, g] = makeCanvas(W, H);
            painter(g, W, H, palettes[pass]);
            out[key] = texture(c, { srgb: pass === 'color' });
            out[key]._paint = () => {
                g.clearRect(0, 0, W, H);
                painter(g, W, H, palettes[pass]);
                out[key].needsUpdate = true;
            };
        });
        out.repaint = () => PBR_KEYS.forEach(k => out[k]._paint());
        return out;
    }

    // Leaf atlas, 2×2 cells: monstera, palm frond, heart leaf, fern.
    function leafAtlas(size) {
        const [c, g] = makeCanvas(size, size);
        const s = size / 2;
        g.fillStyle = '#fff';
        g.strokeStyle = '#fff';

        const cell = (ix, iy, fn) => {
            g.save();
            g.beginPath();
            g.rect(ix * s, iy * s, s, s);
            g.clip();
            g.translate(ix * s + s / 2, iy * s + s * 0.96);
            fn();
            g.restore();
        };

        cell(0, 0, () => {
            g.beginPath();
            g.moveTo(0, 0);
            g.bezierCurveTo(-s * 0.56, -s * 0.16, -s * 0.5, -s * 0.84, 0, -s * 0.9);
            g.bezierCurveTo(s * 0.5, -s * 0.84, s * 0.56, -s * 0.16, 0, 0);
            g.fill();
            g.globalCompositeOperation = 'destination-out';
            g.lineWidth = s * 0.03;
            for (let i = 0; i < 7; i++) {
                const yy = -s * (0.16 + i * 0.1);
                [-1, 1].forEach(side => {
                    g.beginPath();
                    g.moveTo(side * s * 0.1, yy);
                    g.lineTo(side * s * 0.62, yy - s * 0.14);
                    g.stroke();
                });
            }
            for (let i = 0; i < 4; i++) {
                g.beginPath();
                g.ellipse((i % 2 ? 1 : -1) * s * 0.14, -s * (0.25 + i * 0.13), s * 0.025, s * 0.045, 0, 0, TAU);
                g.fill();
            }
            g.globalCompositeOperation = 'source-over';
        });

        cell(1, 0, () => {
            g.lineWidth = s * 0.014;
            g.beginPath();
            g.moveTo(0, 0);
            g.quadraticCurveTo(-s * 0.05, -s * 0.5, -s * 0.18, -s * 0.9);
            g.stroke();
            for (let i = 1; i < 26; i++) {
                const t = i / 26;
                const x = -s * 0.1 * t - s * 0.13 * t * t;
                const y = -s * 0.9 * t;
                const len = s * 0.36 * Math.sin(Math.PI * Math.min(1, t * 1.1));
                [-1, 1].forEach(side => {
                    g.save();
                    g.translate(x, y);
                    g.rotate(side * 1.05 - 0.15);
                    g.beginPath();
                    g.ellipse(0, -len / 2, s * 0.018, Math.max(1, len / 2), 0, 0, TAU);
                    g.fill();
                    g.restore();
                });
            }
        });

        cell(0, 1, () => {
            g.beginPath();
            g.moveTo(0, -s * 0.05);
            g.bezierCurveTo(-s * 0.48, -s * 0.2, -s * 0.42, -s * 0.78, -s * 0.06, -s * 0.66);
            g.lineTo(0, -s * 0.58);
            g.lineTo(s * 0.06, -s * 0.66);
            g.bezierCurveTo(s * 0.42, -s * 0.78, s * 0.48, -s * 0.2, 0, -s * 0.05);
            g.fill();
            g.lineWidth = s * 0.012;
            g.beginPath();
            g.moveTo(0, 0);
            g.lineTo(0, -s * 0.08);
            g.stroke();
        });

        cell(1, 1, () => {
            g.lineWidth = s * 0.012;
            g.beginPath();
            g.moveTo(0, 0);
            g.quadraticCurveTo(s * 0.08, -s * 0.5, 0, -s * 0.92);
            g.stroke();
            for (let i = 1; i < 18; i++) {
                const t = i / 18;
                const y = -s * 0.92 * t;
                const x = s * 0.072 * Math.sin(Math.PI * t);
                const len = s * 0.3 * (1 - t * 0.75);
                [-1, 1].forEach(side => {
                    for (let j = 0; j < 5; j++) {
                        g.beginPath();
                        g.ellipse(x + side * (j + 0.6) * len / 5.5, y - j * s * 0.006, len / 11, s * 0.016, side * 0.3, 0, TAU);
                        g.fill();
                    }
                });
            }
        });
        return c;
    }

    /* ------------------------------------------------------------------ *
     * 4. Shared GLSL & environment
     * ------------------------------------------------------------------ */

    const GLSL_NOISE = /* glsl */`
        float hash12(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
        float vnoise2(vec2 p) {
            vec2 i = floor(p), f = fract(p);
            vec2 u = f * f * (3.0 - 2.0 * f);
            return mix(mix(hash12(i), hash12(i + vec2(1.0, 0.0)), u.x),
                       mix(hash12(i + vec2(0.0, 1.0)), hash12(i + 1.0), u.x), u.y);
        }
        float fbm2(vec2 p) {
            float v = 0.0, a = 0.5;
            for (int i = 0; i < 5; i++) { v += a * vnoise2(p); p = p * 2.03 + vec2(1.7, 9.2); a *= 0.5; }
            return v;
        }
    `;

    const FULLSCREEN_VERT = /* glsl */`
        varying vec2 vUv;
        void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }
    `;

    // Procedural environment for PBR reflections: dark canopy dome, a warm sun
    // lobe behind the board, a soft key from front-left and an emerald bounce.
    function buildEnvironment(renderer) {
        const pm = new THREE.PMREMGenerator(renderer);
        const scene = new THREE.Scene();
        const mat = new THREE.ShaderMaterial({
            side: THREE.BackSide,
            vertexShader: `varying vec3 vDir; void main() { vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
            fragmentShader: `
                varying vec3 vDir;
                void main() {
                    vec3 d = normalize(vDir);
                    vec3 col = mix(vec3(0.008, 0.02, 0.012), vec3(0.05, 0.12, 0.07), smoothstep(-0.2, 0.7, d.y));
                    col += vec3(1.8, 1.3, 0.6) * pow(max(dot(d, normalize(vec3(0.0, 0.35, -1.0))), 0.0), 18.0);
                    col += vec3(0.9, 0.8, 0.6) * pow(max(dot(d, normalize(vec3(-0.5, 0.8, 0.5))), 0.0), 6.0) * 0.7;
                    col += vec3(0.0, 0.55, 0.22) * pow(max(dot(d, normalize(vec3(0.0, -0.3, 1.0))), 0.0), 4.0) * 0.35;
                    gl_FragColor = vec4(col, 1.0);
                }`
        });
        scene.add(new THREE.Mesh(new THREE.SphereGeometry(10, 48, 24), mat));
        const rt = pm.fromScene(scene, 0.02);
        pm.dispose();
        mat.dispose();
        return rt.texture;
    }

    /* ------------------------------------------------------------------ *
     * 5. Bioluminescent spores — curl-noise drift on the CPU
     * ------------------------------------------------------------------ */

    class Spores {
        constructor(count, bounds, pixelRatio) {
            this.count = count;
            this.bounds = bounds;
            const pos = new Float32Array(count * 3);
            const size = new Float32Array(count);
            const phase = new Float32Array(count);
            const hue = new Float32Array(count);
            this.vel = new Float32Array(count * 3);
            for (let i = 0; i < count; i++) {
                pos[i * 3] = lerp(bounds.min.x, bounds.max.x, Math.random());
                pos[i * 3 + 1] = lerp(bounds.min.y, bounds.max.y, Math.random());
                pos[i * 3 + 2] = lerp(bounds.min.z, bounds.max.z, Math.random());
                size[i] = 0.6 + Math.pow(Math.random(), 3) * 2.4;
                phase[i] = Math.random();
                hue[i] = Math.random() < 0.18 ? 0.85 + Math.random() * 0.15 : Math.random() * 0.25;
            }
            const geo = new THREE.BufferGeometry();
            geo.setAttribute('position', new THREE.BufferAttribute(pos, 3).setUsage(THREE.DynamicDrawUsage));
            geo.setAttribute('aSize', new THREE.BufferAttribute(size, 1));
            geo.setAttribute('aPhase', new THREE.BufferAttribute(phase, 1));
            geo.setAttribute('aHue', new THREE.BufferAttribute(hue, 1));
            this.uniforms = {
                uTime: { value: 0 },
                uPx: { value: pixelRatio },
                uScale: { value: 60 },
                uCurse: { value: 0 },
                uIntensity: { value: 1 }
            };
            const mat = new THREE.ShaderMaterial({
                uniforms: this.uniforms,
                transparent: true,
                depthWrite: false,
                blending: THREE.AdditiveBlending,
                vertexShader: /* glsl */`
                    attribute float aSize, aPhase, aHue;
                    uniform float uTime, uPx, uScale, uCurse;
                    varying vec3 vColor;
                    varying float vAlpha;
                    void main() {
                        vec4 mv = modelViewMatrix * vec4(position, 1.0);
                        gl_Position = projectionMatrix * mv;
                        float depth = -mv.z;
                        // Each mote twinkles at its own rate and phase
                        float tw = 0.55 + 0.45 * sin(uTime * (1.1 + aPhase * 1.4) + aPhase * 6.2831);
                        // Perspective size attenuation: size ∝ 1 / view depth
                        gl_PointSize = aSize * uPx * uScale / max(depth, 0.1) * (0.75 + 0.25 * tw);
                        vec3 phosphor = vec3(0.0, 1.0, 0.4);
                        vec3 gold = vec3(1.0, 0.84, 0.3);
                        vec3 ruby = vec3(1.0, 0.27, 0.2);
                        vColor = mix(mix(phosphor, gold, aHue), ruby, uCurse);
                        // Fade out with distance (fake fog) and right in front of the lens
                        vAlpha = tw * exp(-depth * 0.06) * smoothstep(0.3, 1.4, depth);
                    }`,
                fragmentShader: /* glsl */`
                    uniform float uIntensity;
                    varying vec3 vColor;
                    varying float vAlpha;
                    void main() {
                        float d = length(gl_PointCoord - 0.5);
                        float halo = smoothstep(0.5, 0.0, d);
                        float core = smoothstep(0.14, 0.0, d);
                        gl_FragColor = vec4(vColor * (1.0 + core * 2.0), (halo * halo * 0.7 + core) * vAlpha * uIntensity);
                    }`
            });
            this.points = new THREE.Points(geo, mat);
            this.points.frustumCulled = false;
            this.points.userData.occHide = true;
        }

        // Curl of the vector potential
        //   ψ = ( sin(a·y + t)·cos(a·z), sin(a·z + t)·cos(a·x), sin(a·x + t)·cos(a·y) )
        // A curl field is divergence-free, so motes swirl like smoke instead of
        // clumping into sinks. Two octaves give large lazy loops with fine eddies.
        static curl(x, y, z, t, out) {
            out[0] = out[1] = out[2] = 0;
            for (let o = 0; o < 2; o++) {
                const a = o === 0 ? 0.35 : 0.9;
                const amp = o === 0 ? 1 : 0.45;
                const sx = Math.sin(a * x + t), cx = Math.cos(a * x + t);
                const sy = Math.sin(a * y + t), cy = Math.cos(a * y + t);
                const sz = Math.sin(a * z + t), cz = Math.cos(a * z + t);
                const sax = Math.sin(a * x), cax = Math.cos(a * x);
                const say = Math.sin(a * y), cay = Math.cos(a * y);
                const saz = Math.sin(a * z), caz = Math.cos(a * z);
                out[0] += amp * a * (-sx * say - cz * cax);
                out[1] += amp * a * (-sy * saz - cx * cay);
                out[2] += amp * a * (-sz * sax - cy * caz);
            }
        }

        // pointer: { ray: THREE.Ray, vel: THREE.Vector3 (world units/s) } or null
        update(dt, t, speed, pointer) {
            const pos = this.points.geometry.attributes.position.array;
            const vel = this.vel;
            const b = this.bounds;
            const c = [0, 0, 0];
            const tt = t * 0.12;
            const follow = Math.min(1, dt * 1.4);
            for (let i = 0; i < this.count; i++) {
                const k = i * 3;
                let x = pos[k], y = pos[k + 1], z = pos[k + 2];
                Spores.curl(x, y, z, tt, c);
                vel[k] += (c[0] * speed - vel[k]) * follow;
                vel[k + 1] += (c[1] * speed + 0.02 - vel[k + 1]) * follow;
                vel[k + 2] += (c[2] * speed - vel[k + 2]) * follow;

                if (pointer) {
                    // Squared distance from the mote to the pointer ray: |w|² − (w·d)²
                    const o = pointer.ray.origin, d = pointer.ray.direction;
                    const wx = x - o.x, wy = y - o.y, wz = z - o.z;
                    const s = wx * d.x + wy * d.y + wz * d.z;
                    if (s > 0) {
                        const dist2 = wx * wx + wy * wy + wz * wz - s * s;
                        const R = 0.35 + s * 0.08;
                        if (dist2 < R * R) {
                            const f = Math.pow(1 - Math.sqrt(Math.max(0, dist2)) / R, 2) * 0.9;
                            vel[k] += pointer.vel.x * f;
                            vel[k + 1] += pointer.vel.y * f;
                            vel[k + 2] += pointer.vel.z * f;
                        }
                    }
                }

                x += vel[k] * dt; y += vel[k + 1] * dt; z += vel[k + 2] * dt;
                // Wrap around the volume so the density stays constant
                if (x < b.min.x) x = b.max.x; else if (x > b.max.x) x = b.min.x;
                if (y < b.min.y) y = b.max.y; else if (y > b.max.y) y = b.min.y;
                if (z < b.min.z) z = b.max.z; else if (z > b.max.z) z = b.min.z;
                pos[k] = x; pos[k + 1] = y; pos[k + 2] = z;
            }
            this.points.geometry.attributes.position.needsUpdate = true;
            this.uniforms.uTime.value = t;
        }
    }

    // Domain-warped fbm ground mist: fbm(p + fbm(p)) bends the noise into
    // rolling, smoke-like tendrils rather than blotches. `plane` picks which
    // two world axes feed the noise (xz for floor layers, xy for veils).
    function mistMaterial(color, opacity, scale, speed, plane = 'xz') {
        return new THREE.ShaderMaterial({
            transparent: true,
            depthWrite: false,
            uniforms: {
                uTime: { value: 0 },
                uColor: { value: new THREE.Color(color) },
                uOpacity: { value: opacity },
                uScale: { value: scale },
                uSpeed: { value: speed },
                uCurse: { value: 0 }
            },
            vertexShader: `varying vec2 vUv; varying vec3 vWorld;
                void main() { vUv = uv; vec4 w = modelMatrix * vec4(position, 1.0); vWorld = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`,
            fragmentShader: GLSL_NOISE + /* glsl */`
                uniform float uTime, uOpacity, uScale, uSpeed, uCurse;
                uniform vec3 uColor;
                varying vec2 vUv;
                varying vec3 vWorld;
                void main() {
                    vec2 p = vWorld.${plane} * uScale + vec2(uTime * 0.02, uTime * 0.012) * uSpeed;
                    float n = fbm2(p + fbm2(p * 1.7 - uTime * 0.03 * uSpeed));
                    float edge = smoothstep(0.0, 0.3, vUv.x) * smoothstep(1.0, 0.7, vUv.x) * smoothstep(0.0, 0.3, vUv.y) * smoothstep(1.0, 0.7, vUv.y);
                    float a = smoothstep(0.35, 0.85, n) * uOpacity * edge;
                    gl_FragColor = vec4(mix(uColor, vec3(0.5, 0.12, 0.08), uCurse), a);
                }`
        });
    }

    /* ------------------------------------------------------------------ *
     * 6. Composer: scene → occlusion → radial-blur god-rays → composite
     * ------------------------------------------------------------------ */

    class Composer {
        constructor(renderer, samples) {
            this.renderer = renderer;
            const gl2 = renderer.capabilities.isWebGL2;
            const hdr = gl2 && (renderer.extensions.has('EXT_color_buffer_float') || renderer.extensions.has('EXT_color_buffer_half_float'));
            // Linear HDR target: tone mapping and sRGB happen once, in the composite.
            this.main = new THREE.WebGLRenderTarget(1, 1, { type: hdr ? THREE.HalfFloatType : THREE.UnsignedByteType, samples: gl2 ? samples : 0 });
            this.occ = new THREE.WebGLRenderTarget(1, 1);
            this.rays = new THREE.WebGLRenderTarget(1, 1);
            this.cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
            this.quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2));
            this.quad.frustumCulled = false;
            this.quadScene = new THREE.Scene();
            this.quadScene.add(this.quad);

            // GPU Gems 3, ch. 13 "Volumetric Light Scattering as a Post-Process":
            // march from each pixel toward the light's screen position, summing the
            // occlusion buffer with exponential decay. Bright gaps between trunks
            // smear into shafts; the per-pixel dither hides sample banding.
            this.raysMat = new THREE.ShaderMaterial({
                uniforms: {
                    tOcc: { value: this.occ.texture },
                    uLight: { value: new THREE.Vector2(0.5, 0.8) },
                    uDensity: { value: 0.92 },
                    uWeight: { value: 0.038 },
                    uDecay: { value: 0.965 },
                    uExposure: { value: 1.0 }
                },
                vertexShader: FULLSCREEN_VERT,
                fragmentShader: /* glsl */`
                    #define SAMPLES 48
                    uniform sampler2D tOcc;
                    uniform vec2 uLight;
                    uniform float uDensity, uWeight, uDecay, uExposure;
                    varying vec2 vUv;
                    void main() {
                        vec2 delta = (vUv - uLight) * uDensity / float(SAMPLES);
                        // Interleaved gradient noise offsets the march start per pixel
                        float dither = fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715))));
                        vec2 uv = vUv - delta * dither;
                        float illum = 1.0;
                        vec3 acc = vec3(0.0);
                        for (int i = 0; i < SAMPLES; i++) {
                            uv -= delta;
                            acc += texture2D(tOcc, clamp(uv, 0.0, 1.0)).rgb * illum * uWeight;
                            illum *= uDecay;
                        }
                        gl_FragColor = vec4(acc * uExposure, 1.0);
                    }`
            });

            this.compMat = new THREE.ShaderMaterial({
                uniforms: {
                    tMain: { value: this.main.texture },
                    tRays: { value: this.rays.texture },
                    uRayTint: { value: new THREE.Color(1.0, 0.86, 0.55) },
                    uRayStrength: { value: 1 },
                    uExposure: { value: 1.0 },
                    uTime: { value: 0 },
                    uFade: { value: 1 },
                    uFlash: { value: 0 },
                    uCurse: { value: 0 }
                },
                vertexShader: FULLSCREEN_VERT,
                fragmentShader: /* glsl */`
                    uniform sampler2D tMain, tRays;
                    uniform vec3 uRayTint;
                    uniform float uRayStrength, uExposure, uTime, uFade, uFlash, uCurse;
                    varying vec2 vUv;
                    // Narkowicz's fitted ACES filmic curve
                    vec3 aces(vec3 x) { return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0); }
                    vec3 toSRGB(vec3 c) { return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(0.0031308, c)); }
                    void main() {
                        vec2 cc = vUv - 0.5;
                        float r2 = dot(cc, cc);
                        // Lateral chromatic aberration ∝ r²: zero at the centre, a thin
                        // red/cyan fringe toward the corners like an old lens.
                        float ca = 0.012 * r2;
                        vec3 col;
                        col.r = texture2D(tMain, vUv - cc * ca).r;
                        col.g = texture2D(tMain, vUv).g;
                        col.b = texture2D(tMain, vUv + cc * ca).b;
                        col += texture2D(tRays, vUv).rgb * uRayTint * uRayStrength;
                        col = aces(col * uExposure);
                        col = toSRGB(col);
                        col *= mix(1.0, 0.38, smoothstep(0.12, 0.62, r2 * 1.6));
                        float n = fract(sin(dot(gl_FragCoord.xy + fract(uTime) * 91.7, vec2(12.9898, 78.233))) * 43758.5453);
                        col += (n - 0.5) * 0.035;
                        col = mix(col, col * vec3(1.3, 0.5, 0.45), uCurse);
                        col += uFlash * vec3(0.35, 1.0, 0.55);
                        col = mix(col, vec3(0.008, 0.039, 0.02), uFade);
                        gl_FragColor = vec4(col, 1.0);
                    }`
            });
        }

        setSize(w, h) {
            this.main.setSize(w, h);
            const hw = Math.max(1, w >> 1), hh = Math.max(1, h >> 1);
            this.occ.setSize(hw, hh);
            this.rays.setSize(hw, hh);
        }

        pass(material, target) {
            this.quad.material = material;
            this.renderer.setRenderTarget(target);
            this.renderer.render(this.quadScene, this.cam);
        }
    }

    /* ------------------------------------------------------------------ *
     * 7. Spatial audio on the JX bus (Module D)
     * ------------------------------------------------------------------ */

    class JungleAudio {
        constructor() {
            this.unlocked = false;
            this.g = null;
            // Never create the AudioContext before a user gesture
            const unlock = () => { this.unlocked = true; };
            window.addEventListener('pointerdown', unlock, { once: true, passive: true });
            window.addEventListener('keydown', unlock, { once: true });
        }

        get enabled() {
            return !!(window.JX && JX.sfx && JX.sfx.enabled && JX.audio && this.unlocked);
        }

        graph() {
            if (!this.enabled) return null;
            if (!this.g) this.g = JX.audio.graph();
            return this.g && this.g.ctx.state === 'running' ? this.g : null;
        }

        // HRTF panner at a world position; the listener follows the camera.
        panner(pos) {
            const { ctx, out } = this.g;
            const p = ctx.createPanner();
            p.panningModel = 'HRTF';
            p.distanceModel = 'inverse';
            p.refDistance = 2;
            p.rolloffFactor = 0.8;
            if (p.positionX) {
                p.positionX.value = pos.x; p.positionY.value = pos.y; p.positionZ.value = pos.z;
            } else {
                p.setPosition(pos.x, pos.y, pos.z);
            }
            p.connect(out);
            return p;
        }

        listen(camera) {
            const g = this.graph();
            if (!g) return;
            const L = g.ctx.listener;
            const p = camera.position;
            const f = new THREE.Vector3(0, 0, -1).applyQuaternion(camera.quaternion);
            const u = new THREE.Vector3(0, 1, 0).applyQuaternion(camera.quaternion);
            if (L.positionX) {
                const t = g.ctx.currentTime;
                L.positionX.setTargetAtTime(p.x, t, 0.05); L.positionY.setTargetAtTime(p.y, t, 0.05); L.positionZ.setTargetAtTime(p.z, t, 0.05);
                L.forwardX.setTargetAtTime(f.x, t, 0.05); L.forwardY.setTargetAtTime(f.y, t, 0.05); L.forwardZ.setTargetAtTime(f.z, t, 0.05);
                L.upX.setTargetAtTime(u.x, t, 0.05); L.upY.setTargetAtTime(u.y, t, 0.05); L.upZ.setTargetAtTime(u.z, t, 0.05);
            } else {
                L.setPosition(p.x, p.y, p.z);
                L.setOrientation(f.x, f.y, f.z, u.x, u.y, u.z);
            }
        }

        // Low sine thump with a pitch drop; the lowpass opens as the lid opens,
        // so a closed box sounds muffled.
        thump(pos, strength, openness) {
            const g = this.graph();
            if (!g) return;
            const { ctx } = g;
            const t = ctx.currentTime;
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            const lp = ctx.createBiquadFilter();
            lp.type = 'lowpass';
            lp.frequency.value = 140 + openness * 520;
            osc.type = 'sine';
            osc.frequency.setValueAtTime(62, t);
            osc.frequency.exponentialRampToValueAtTime(36, t + 0.22);
            gain.gain.setValueAtTime(0.0001, t);
            gain.gain.exponentialRampToValueAtTime(0.22 * strength, t + 0.012);
            gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.3);
            osc.connect(lp).connect(gain).connect(this.panner(pos));
            osc.start(t);
            osc.stop(t + 0.32);
        }

        // Stone-on-wood grind: bandpassed noise sweeping up, with a jittery
        // amplitude so it reads as grit rather than hiss.
        scrape(pos, dur) {
            const g = this.graph();
            if (!g) return;
            const { ctx } = g;
            const t = ctx.currentTime;
            const len = Math.floor(ctx.sampleRate * dur);
            const buf = ctx.createBuffer(1, len, ctx.sampleRate);
            const d = buf.getChannelData(0);
            let jitter = 0;
            for (let i = 0; i < len; i++) {
                if (i % 220 === 0) jitter = 0.4 + Math.random() * 0.6;
                d[i] = (Math.random() * 2 - 1) * jitter;
            }
            const src = ctx.createBufferSource();
            src.buffer = buf;
            const bp = ctx.createBiquadFilter();
            bp.type = 'bandpass';
            bp.Q.value = 0.9;
            bp.frequency.setValueAtTime(200, t);
            bp.frequency.exponentialRampToValueAtTime(900, t + dur);
            const gain = ctx.createGain();
            gain.gain.setValueAtTime(0.0001, t);
            gain.gain.exponentialRampToValueAtTime(0.16, t + 0.15);
            gain.gain.setValueAtTime(0.16, t + dur * 0.7);
            gain.gain.exponentialRampToValueAtTime(0.0001, t + dur);
            src.connect(bp).connect(gain).connect(this.panner(pos));
            src.start(t);
        }

        thud(pos) {
            const g = this.graph();
            if (!g) return;
            const { ctx } = g;
            const t = ctx.currentTime;
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'triangle';
            osc.frequency.setValueAtTime(110, t);
            osc.frequency.exponentialRampToValueAtTime(48, t + 0.18);
            gain.gain.setValueAtTime(0.0001, t);
            gain.gain.exponentialRampToValueAtTime(0.3, t + 0.008);
            gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.35);
            osc.connect(gain).connect(this.panner(pos));
            osc.start(t);
            osc.stop(t + 0.4);
        }
    }

    /* ------------------------------------------------------------------ *
     * 8. The cursed board box (Module A) & 3D Animal Piece
     * ------------------------------------------------------------------ */

    function getTrackPoint3D(th) {
        const W = 1536, H = 1056;
        const cx = W / 2, cy = H / 2;
        const aspect = 1.4;
        const r0 = 448, r1 = 300, thetaMax = 2.35 * TAU;
        const clampedTh = Math.max(0, Math.min(thetaMax, th));
        const r = r0 - (r0 - r1) * clampedTh / thetaMax;
        const px = cx + Math.cos(clampedTh - Math.PI / 2) * r * aspect;
        const py = cy + Math.sin(clampedTh - Math.PI / 2) * r;
        const x3d = (px / W - 0.5) * 3.2;
        const z3d = (py / H - 0.5) * 2.2;
        return new THREE.Vector3(x3d, 0.02, z3d);
    }

    function getTrackAngle3D(th) {
        const p1 = getTrackPoint3D(th);
        const p2 = getTrackPoint3D(th + 0.03);
        return Math.atan2(p2.x - p1.x, p2.z - p1.z);
    }

    function buildAnimalToken(goldMat) {
        const group = new THREE.Group();
        group.name = 'animalToken';

        const bronzeMat = new THREE.MeshStandardMaterial({
            color: 0x724925,
            roughness: 0.36,
            metalness: 0.85,
            envMapIntensity: 1.2
        });

        const eyeMat = new THREE.MeshBasicMaterial({
            color: 0x00ff66
        });

        // Plinth base
        const plinth = new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.15, 0.035, 32), bronzeMat);
        plinth.position.y = 0.018;
        plinth.castShadow = true;
        group.add(plinth);

        const plinthTrim = new THREE.Mesh(new THREE.TorusGeometry(0.14, 0.015, 12, 32), goldMat);
        plinthTrim.rotation.x = Math.PI / 2;
        plinthTrim.position.y = 0.02;
        group.add(plinthTrim);

        // Torso
        const body = new THREE.Mesh(new THREE.BoxGeometry(0.15, 0.11, 0.24), bronzeMat);
        body.position.set(0, 0.10, 0);
        body.castShadow = true;
        group.add(body);

        // Muscular shoulder hump
        const hump = new THREE.Mesh(new THREE.SphereGeometry(0.08, 16, 12), bronzeMat);
        hump.position.set(0, 0.14, -0.03);
        hump.scale.set(0.9, 0.8, 1.2);
        hump.castShadow = true;
        group.add(hump);

        // Head
        const head = new THREE.Mesh(new THREE.ConeGeometry(0.065, 0.14, 16), bronzeMat);
        head.rotation.x = Math.PI / 2 + 0.25;
        head.position.set(0, 0.12, 0.14);
        head.castShadow = true;
        group.add(head);

        // Large front horn
        const horn1 = new THREE.Mesh(new THREE.ConeGeometry(0.022, 0.11, 12), goldMat);
        horn1.rotation.x = -Math.PI / 7;
        horn1.position.set(0, 0.19, 0.16);
        horn1.castShadow = true;
        group.add(horn1);

        // Secondary small horn
        const horn2 = new THREE.Mesh(new THREE.ConeGeometry(0.016, 0.06, 12), goldMat);
        horn2.rotation.x = -Math.PI / 7;
        horn2.position.set(0, 0.15, 0.10);
        horn2.castShadow = true;
        group.add(horn2);

        // 4 Legs
        const legGeo = new THREE.CylinderGeometry(0.022, 0.026, 0.08, 12);
        [[-0.055, 0.065], [0.055, 0.065], [-0.055, -0.065], [0.055, -0.065]].forEach(([lx, lz]) => {
            const leg = new THREE.Mesh(legGeo, bronzeMat);
            leg.position.set(lx, 0.045, lz);
            leg.castShadow = true;
            group.add(leg);
        });

        // Ears
        [[-0.045, 0.16, 0.07], [0.045, 0.16, 0.07]].forEach(([ex, ey, ez]) => {
            const ear = new THREE.Mesh(new THREE.ConeGeometry(0.014, 0.038, 8), bronzeMat);
            ear.position.set(ex, ey, ez);
            ear.rotation.z = ex > 0 ? -0.4 : 0.4;
            group.add(ear);
        });

        // Glowing Emerald Eyes
        [[-0.038, 0.13, 0.15], [0.038, 0.13, 0.15]].forEach(([ex, ey, ez]) => {
            const eye = new THREE.Mesh(new THREE.SphereGeometry(0.011, 8, 8), eyeMat);
            eye.position.set(ex, ey, ez);
            group.add(eye);
        });

        // Pulsing Aura Ring around base
        const auraGeo = new THREE.RingGeometry(0.15, 0.22, 32);
        const auraMat = new THREE.MeshBasicMaterial({
            color: 0xffd700,
            transparent: true,
            opacity: 0.8,
            side: THREE.DoubleSide,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        });
        const aura = new THREE.Mesh(auraGeo, auraMat);
        aura.rotation.x = -Math.PI / 2;
        aura.position.y = 0.005;
        aura.userData.occHide = true;
        group.add(aura);

        // Mark all meshes inside as belonging to the animal token
        group.traverse(o => {
            if (o.isMesh) {
                o.userData.isAnimalToken = true;
            }
        });

        return { group, aura, bronzeMat, eyeMat };
    }

    const BOARD = { w: 3.2, d: 2.2, baseH: 0.56, wingH: 0.56, tilt: 0.38 };

    function buildBoard() {
        const { w, d, baseH, wingH } = BOARD;
        const group = new THREE.Group();
        group.rotation.x = BOARD.tilt; // lean the box toward the camera on its lectern

        const woodCanvas = woodTile(512, 3, [18, 9, 4], [74, 40, 18]);
        const woodDarkCanvas = woodTile(512, 9, [12, 6, 3], [52, 28, 12]);
        const woodTex = texture(woodCanvas, { srgb: true, repeat: [2, 1] });
        const woodBump = texture(woodCanvas, { repeat: [2, 1] });
        const palettes = passPalettes(woodCanvas);
        const darkPalettes = passPalettes(woodDarkCanvas);

        const pbrMat = set => new THREE.MeshStandardMaterial({
            map: set.map, bumpMap: set.bumpMap, bumpScale: 2.2,
            roughnessMap: set.roughnessMap, metalnessMap: set.metalnessMap,
            roughness: 1, metalness: 1, envMapIntensity: 1.1
        });

        const caseMat = new THREE.MeshStandardMaterial({ map: woodTex, bumpMap: woodBump, bumpScale: 0.5, roughness: 0.62, metalness: 0, envMapIntensity: 0.6 });
        const goldMat = new THREE.MeshStandardMaterial({ color: 0xd4a640, metalness: 1, roughness: 0.3, emissive: 0x000000 });

        // Board face on the top (+y) of the base box
        const face = pbrSet(1536, 1056, paintBoardFace, palettes);
        const faceMat = pbrMat(face);
        const base = new THREE.Mesh(new THREE.BoxGeometry(w, baseH, d), [caseMat, caseMat, faceMat, caseMat, caseMat, caseMat]);
        base.position.y = -baseH / 2;
        base.castShadow = base.receiveShadow = true;
        group.add(base);

        const trim = (len, x, z, rotY) => {
            const m = new THREE.Mesh(new THREE.BoxGeometry(len, 0.03, 0.04), goldMat);
            m.position.set(x, 0.006, z);
            m.rotation.y = rotY;
            return m;
        };
        group.add(trim(w, 0, d / 2 - 0.02, 0), trim(w, 0, -d / 2 + 0.02, 0));
        group.add(trim(d, w / 2 - 0.02, 0, Math.PI / 2), trim(d, -w / 2 + 0.02, 0, Math.PI / 2));

        const ring = new THREE.Mesh(new THREE.TorusGeometry(0.475, 0.035, 16, 96), goldMat);
        ring.rotation.x = Math.PI / 2;
        ring.position.y = 0.01;
        group.add(ring);

        // Procedural 3D Animal Game Piece (Rhino Totem) on the spiral track
        const token = buildAnimalToken(goldMat);
        const startPos = getTrackPoint3D(0);
        token.group.position.copy(startPos);
        token.group.rotation.y = getTrackAngle3D(0);
        group.add(token.group);

        // Lid wings. Each hinges on its outer top edge; rotating the pivot by π
        // lays the hollow tray flat beside the base, flush with its bottom.
        let fontsReady = false;
        const outer = pbrSet(1536, 1056, (g, W, H, P) => paintLidOuter(g, W, H, P, fontsReady), darkPalettes);
        const innerL = pbrSet(768, 1056, (g, W, H, P) => paintLidInner(g, W, H, P, 'left', fontsReady), palettes);
        const innerR = pbrSet(768, 1056, (g, W, H, P) => paintLidInner(g, W, H, P, 'right', fontsReady), palettes);

        // Per-wing UV window onto the shared lid-exterior canvas
        const halfOf = (set, offsetX) => {
            const s = {};
            PBR_KEYS.forEach(k => {
                const t = set[k].clone();
                t.repeat.set(0.5, 1);
                t.offset.set(offsetX, 0);
                t.needsUpdate = true;
                s[k] = t;
            });
            return s;
        };
        // The inner face is the plate's −y side. After the π hinge swing it faces
        // up but its UVs are mirrored in both axes — a 180° texture turn fixes it.
        const turned = set => {
            PBR_KEYS.forEach(k => {
                set[k].center.set(0.5, 0.5);
                set[k].rotation = Math.PI;
            });
            return set;
        };

        const outerL = halfOf(outer, 0), outerR = halfOf(outer, 0.5);
        turned(innerL);
        turned(innerR);

        const wings = [-1, 1].map(side => {
            const pivot = new THREE.Group();
            pivot.position.set(side * w / 2, 0, 0);
            const body = new THREE.Group();
            body.position.x = -side * w / 4;
            pivot.add(body);

            const plateW = w / 2 - 0.006; // leave a hairline seam for the emerald glow
            const plate = new THREE.Mesh(
                new THREE.BoxGeometry(plateW, 0.06, d),
                [caseMat, caseMat, pbrMat(side < 0 ? outerL : outerR), pbrMat(side < 0 ? innerL : innerR), caseMat, caseMat]
            );
            plate.position.set(side * 0.003, wingH - 0.03, 0);
            plate.castShadow = plate.receiveShadow = true;
            body.add(plate);

            const wallH = wingH - 0.06;
            const wall = (sx, sz, x, z) => {
                const m = new THREE.Mesh(new THREE.BoxGeometry(sx, wallH, sz), caseMat);
                m.position.set(x, wallH / 2, z);
                m.castShadow = m.receiveShadow = true;
                body.add(m);
            };
            wall(plateW, 0.05, side * 0.003, d / 2 - 0.025);
            wall(plateW, 0.05, side * 0.003, -d / 2 + 0.025);
            wall(0.05, d - 0.1, side * (w / 4 - 0.025), 0);
            wall(0.05, d - 0.1, -side * (w / 4 - 0.025) + side * 0.006, 0);

            [[1, 1], [1, -1], [-1, 1], [-1, -1]].forEach(([ix, iz]) => {
                const cap = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.08, 0.12), goldMat);
                cap.position.set(side * 0.003 + ix * (plateW / 2 - 0.05), wingH - 0.03, iz * (d / 2 - 0.05));
                body.add(cap);
            });

            [-0.7, 0.7].forEach(z => {
                const h = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 0.32, 16), goldMat);
                h.rotation.x = Math.PI / 2;
                h.position.set(side * w / 4, 0.0, z);
                body.add(h);
            });

            group.add(pivot);
            return { pivot, side, progress: 0 };
        });

        // Emerald light leaking through the seam of the closed lid
        const seamLine = new THREE.Mesh(
            new THREE.BoxGeometry(0.012, 0.02, d - 0.04),
            new THREE.MeshBasicMaterial({ color: new THREE.Color(0x00ff66).multiplyScalar(4) })
        );
        seamLine.position.y = wingH - 0.02;
        group.add(seamLine);

        const glowTex = texture(radialSprite(128, [[0, 'rgba(255,255,255,1)'], [0.25, 'rgba(255,255,255,0.45)'], [1, 'rgba(255,255,255,0)']]));
        const seamGlow = new THREE.Mesh(
            new THREE.PlaneGeometry(0.5, d * 1.05),
            new THREE.MeshBasicMaterial({ map: glowTex, color: 0x33ff88, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false })
        );
        seamGlow.rotation.x = -Math.PI / 2;
        seamGlow.position.y = wingH + 0.004;
        seamGlow.userData.occHide = true;
        group.add(seamGlow);

        // Crystal dome: physically based transmission (refracts the board below),
        // plus a thin additive shell that fakes chromatic dispersion at the rim.
        const domeGeo = new THREE.SphereGeometry(0.46, 64, 32, 0, TAU, 0, Math.PI / 2);
        const dome = new THREE.Mesh(domeGeo, new THREE.MeshPhysicalMaterial({
            color: 0xffffff, metalness: 0, roughness: 0.15, transmission: 1, thickness: 0.35, ior: 1.5,
            specularIntensity: 1, envMapIntensity: 1.4, attenuationColor: new THREE.Color(0xd8ffe6), attenuationDistance: 2.5
        }));
        group.add(dome);

        const dispersion = new THREE.Mesh(domeGeo, new THREE.ShaderMaterial({
            transparent: true,
            depthWrite: false,
            blending: THREE.AdditiveBlending,
            uniforms: { uTime: { value: 0 }, uStrength: { value: 0.9 } },
            vertexShader: `varying vec3 vN; varying vec3 vV;
                void main() { vec4 mv = modelViewMatrix * vec4(position, 1.0); vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }`,
            fragmentShader: /* glsl */`
                uniform float uTime, uStrength;
                varying vec3 vN; varying vec3 vV;
                void main() {
                    // Fresnel term: 0 facing the eye, 1 at grazing angles
                    float f = 1.0 - abs(dot(normalize(vN), normalize(vV)));
                    // Dispersion: glass bends blue more than red, so each channel's
                    // rim peaks at a slightly different grazing angle.
                    vec3 rim = vec3(pow(f, 2.4), pow(f, 2.9), pow(f, 3.5));
                    // Thin-film interference sweep for the oily rainbow edge
                    rim *= 0.55 + 0.45 * cos(6.2831 * (f * 1.7 + vec3(0.0, 0.33, 0.67)) + uTime * 0.25);
                    gl_FragColor = vec4(rim * uStrength, 1.0);
                }`
        }));
        dispersion.scale.setScalar(1.006);
        dispersion.userData.occHide = true;
        group.add(dispersion);

        // Jaguar-eye emerald: a lathed brilliant cut (8 facets) stretched into an
        // almond, with a painted iris and slit pupil on its table.
        const profile = [[0.001, 0], [0.2, 0.07], [0.21, 0.09], [0.13, 0.17], [0.001, 0.175]].map(([x, y]) => new THREE.Vector2(x, y));
        const gemMat = new THREE.MeshPhysicalMaterial({
            color: 0x0d7a3a, emissive: 0x00ff66, emissiveIntensity: 0.6, roughness: 0.06, metalness: 0,
            clearcoat: 1, clearcoatRoughness: 0.05, flatShading: true, envMapIntensity: 2
        });
        const gem = new THREE.Mesh(new THREE.LatheGeometry(profile, 8), gemMat);
        gem.scale.set(1.35, 1, 1);
        gem.rotation.y = Math.PI / 8;
        group.add(gem);

        const [ic, ig] = makeCanvas(256, 256);
        const iris = ig.createRadialGradient(128, 128, 10, 128, 128, 126);
        iris.addColorStop(0, '#fff3a0');
        iris.addColorStop(0.35, '#ffb300');
        iris.addColorStop(0.7, '#2bd36a');
        iris.addColorStop(1, 'rgba(0,80,30,0)');
        ig.fillStyle = iris;
        ig.beginPath(); ig.arc(128, 128, 126, 0, TAU); ig.fill();
        ig.strokeStyle = 'rgba(80,40,0,0.35)';
        for (let i = 0; i < 60; i++) {
            const a = (i / 60) * TAU;
            ig.beginPath();
            ig.moveTo(128 + Math.cos(a) * 30, 128 + Math.sin(a) * 30);
            ig.lineTo(128 + Math.cos(a) * 100, 128 + Math.sin(a) * 100);
            ig.stroke();
        }
        ig.fillStyle = '#020a05';
        ig.beginPath(); ig.ellipse(128, 128, 14, 92, 0, 0, TAU); ig.fill();
        const irisTex = texture(ic, { srgb: true });
        // alphaTest (not blending) keeps it in the opaque pass, so the
        // transmissive dome can see it.
        const irisMesh = new THREE.Mesh(
            new THREE.CircleGeometry(0.115, 48),
            new THREE.MeshStandardMaterial({ map: irisTex, emissiveMap: irisTex, emissive: 0xffffff, emissiveIntensity: 0.9, alphaTest: 0.4, roughness: 0.2 })
        );
        irisMesh.rotation.x = -Math.PI / 2;
        irisMesh.scale.set(1.35, 1, 1);
        irisMesh.position.y = 0.177;
        group.add(irisMesh);

        const gemLight = new THREE.PointLight(0x00ff66, 0, 4.2, 2);
        gemLight.position.y = 0.3;
        group.add(gemLight);

        // Glow halo drawn on top once the lid is open (sprites are transparent,
        // so they can't be seen through the transmissive dome).
        const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: 0x22ff77, blending: THREE.AdditiveBlending, depthTest: false, depthWrite: false, opacity: 0 }));
        halo.scale.setScalar(1.5);
        halo.position.y = 0.12;
        halo.renderOrder = 20;
        halo.userData.occHide = true;
        group.add(halo);

        // Caustic ripples: light refracted through the dome onto the board around
        // it. Classic iterated-trig water caustic (joltz0r's tileable loop): each
        // iteration warps the domain with sin/cos and accumulates 1/length() of a
        // scaled offset, which spikes along thin bright filaments.
        const caustics = new THREE.Mesh(
            new THREE.RingGeometry(0.48, 1.15, 96, 1),
            new THREE.ShaderMaterial({
                transparent: true,
                depthWrite: false,
                blending: THREE.AdditiveBlending,
                uniforms: { uTime: { value: 0 }, uPulse: { value: 0 }, uOpen: { value: 0 } },
                vertexShader: `varying vec2 vP; void main() { vP = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
                fragmentShader: /* glsl */`
                    uniform float uTime, uPulse, uOpen;
                    varying vec2 vP;
                    float caustic(vec2 p, float t) {
                        vec2 i = p;
                        float c = 1.0;
                        const float inten = 0.005;
                        for (int n = 0; n < 4; n++) {
                            float tt = t * (1.0 - (3.5 / float(n + 1)));
                            i = p + vec2(cos(tt - i.x) + sin(tt + i.y), sin(tt - i.y) + cos(tt + i.x));
                            // Guard the divisions: sin/cos hitting zero would give
                            // inf/NaN, which an HDR target keeps and smears.
                            vec2 s = vec2(sin(i.x + tt), cos(i.y + tt));
                            s = sign(s) * max(abs(s), vec2(1e-3));
                            c += 1.0 / max(length(p * s / inten), 1e-3);
                        }
                        c /= 4.0;
                        c = 1.17 - pow(c, 1.4);
                        return clamp(pow(abs(c), 8.0), 0.0, 1.5);
                    }
                    void main() {
                        float r = length(vP);
                        float mask = smoothstep(0.48, 0.56, r) * smoothstep(1.15, 0.7, r);
                        float c = caustic(vP * 7.0 + 20.0, uTime * 0.45);
                        gl_FragColor = vec4(vec3(0.1, 1.0, 0.45) * c * mask * (0.25 + uPulse * 0.9) * uOpen, 1.0);
                    }`
            })
        );
        caustics.rotation.x = -Math.PI / 2;
        caustics.position.y = 0.004;
        caustics.userData.occHide = true;
        group.add(caustics);

        // Repaint text-bearing canvases once Cinzel has loaded
        const fontLoad = document.fonts && document.fonts.load ? document.fonts.load('900 64px Cinzel') : Promise.resolve();
        Promise.race([fontLoad, new Promise(r => setTimeout(r, 2500))]).then(() => {
            fontsReady = true;
            outer.repaint();
            PBR_KEYS.forEach(k => { outerL[k].needsUpdate = true; outerR[k].needsUpdate = true; });
            innerL.repaint();
            innerR.repaint();
        });

        const pickables = [];
        group.traverse(o => {
            if (o.isMesh && o !== caustics && o !== seamGlow && o !== dispersion && o !== token.aura) {
                pickables.push(o);
            }
        });

        return {
            group, wings, dome, gem, gemMat, gemLight, halo, seamLine, seamGlow, caustics, dispersion, goldMat, pickables,
            gemLocal: new THREE.Vector3(0, 0.12, 0),
            openness: 0,
            isOpen: false,
            animalToken: token.group,
            animalAura: token.aura
        };
    }

    // Stone lectern under the tilted board, on a plinth, on mossy ground.
    function buildLectern() {
        const stone = stoneTile(512, 21);
        // ExtrudeGeometry UVs are in world units, so repeat = tiles per unit
        const map = texture(stone.color, { srgb: true, repeat: [0.7, 0.7] });
        const bump = texture(stone.height, { repeat: [0.7, 0.7] });
        const mat = new THREE.MeshStandardMaterial({ map, bumpMap: bump, bumpScale: 2, roughness: 0.92, metalness: 0, envMapIntensity: 0.35 });

        // Profile in the (z, y) plane. The top edges are the board's bottom face
        // corners pushed through the same x-rotation as the board:
        //   y' = y·cosθ − z·sinθ,  z' = y·sinθ + z·cosθ
        const th = BOARD.tilt, c = Math.cos(th), s = Math.sin(th);
        const yl = -BOARD.baseH;
        const rot = zl => ({ y: yl * c - zl * s, z: yl * s + zl * c });
        // Depth matches board depth 2.2 (half 1.1) so lectern top doesn't protrude front/back
        const front = rot(1.06), back = rot(-1.06);
        const bottom = -1.4;
        const shape = new THREE.Shape();
        // Shape x = −world z (rotateY(π/2) below maps shape x onto −z)
        shape.moveTo(-1.20, bottom);
        shape.lineTo(-front.z, front.y);
        shape.lineTo(-back.z, back.y);
        shape.lineTo(1.40, bottom);
        shape.closePath();
        // Board width is 3.2. Set lectern pillar width to 3.04 (+ 0.06 bevel = 3.10)
        // so it sits strictly underneath the base box with 0.05 clearance from wing hinges,
        // preventing the stone from clipping/protruding into the wings when opened 180°.
        const width = 3.04;
        const geo = new THREE.ExtrudeGeometry(shape, { depth: width, bevelEnabled: true, bevelThickness: 0.03, bevelSize: 0.03, bevelSegments: 2 });
        // Extrusion runs along +z; turn it so it runs along world x.
        geo.rotateY(Math.PI / 2);
        geo.translate(-width / 2, 0, 0);
        const lectern = new THREE.Mesh(geo, mat);
        lectern.receiveShadow = true;
        lectern.castShadow = true;

        // BoxGeometry UVs are 0..1 per face, so the plinth needs its own repeat
        const plinthMap = texture(stone.color, { srgb: true, repeat: [3.6, 2.4] });
        const plinthBump = texture(stone.height, { repeat: [3.6, 2.4] });
        const plinth = new THREE.Mesh(
            new THREE.BoxGeometry(5.6, 0.4, 4.4),
            new THREE.MeshStandardMaterial({ map: plinthMap, bumpMap: plinthBump, bumpScale: 2, roughness: 0.95, metalness: 0, envMapIntensity: 0.3 })
        );
        plinth.position.set(0, -1.6, 0.15);
        plinth.receiveShadow = true;

        const groundMap = texture(stone.color, { srgb: true, repeat: [10, 10] });
        const ground = new THREE.Mesh(
            new THREE.CircleGeometry(48, 48),
            new THREE.MeshStandardMaterial({ map: groundMap, color: 0x5a6a58, roughness: 1, metalness: 0, envMapIntensity: 0.2 })
        );
        ground.rotation.x = -Math.PI / 2;
        ground.position.y = -1.8;
        ground.receiveShadow = true;

        const g = new THREE.Group();
        g.add(lectern, plinth, ground);
        return g;
    }

    // Backlit jungle: glowing haze wall, trunks, vines and hanging fronds. The
    // wall is the god-ray emitter; everything in front of it occludes.
    function buildJungle() {
        const g = new THREE.Group();
        const hot = new THREE.Vector3(0, 1.6, -32);

        const wall = new THREE.Mesh(
            new THREE.PlaneGeometry(110, 48),
            new THREE.ShaderMaterial({
                fog: false,
                uniforms: { uTime: { value: 0 }, uHot: { value: hot } },
                vertexShader: `varying vec3 vW; void main() { vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`,
                fragmentShader: GLSL_NOISE + /* glsl */`
                    uniform float uTime;
                    uniform vec3 uHot;
                    varying vec3 vW;
                    void main() {
                        vec2 p = (vW.xy - uHot.xy) * vec2(0.055, 0.1);
                        float r2 = dot(p, p);
                        float core = exp(-r2 * 30.0);
                        float halo = exp(-r2 * 3.2);
                        float haze = fbm2(vW.xy * 0.08 + vec2(uTime * 0.01, 0.0));
                        vec3 col = vec3(0.002, 0.012, 0.006)
                                 + vec3(0.03, 0.14, 0.065) * halo * (0.7 + 0.6 * haze)
                                 + vec3(2.6, 2.0, 0.95) * core;
                        gl_FragColor = vec4(col, 1.0);
                    }`
            })
        );
        wall.position.set(0, 8, -32);
        wall.userData.emitter = true;
        g.add(wall);

        const woodCanvas = woodTile(256, 31, [8, 6, 4], [34, 26, 16]);
        const bark = texture(woodCanvas, { srgb: true, repeat: [1, 6] });
        bark.rotation = Math.PI / 2;
        const barkMat = new THREE.MeshStandardMaterial({ map: bark, color: 0x6a5a48, roughness: 1, metalness: 0, envMapIntensity: 0.2 });
        // Trunks leave a lane behind the board so the hot spot shows through.
        const trunks = [[-3.2, -9, 0.45], [3.6, -11, 0.55], [-6.5, -7, 0.7], [7.2, -8.5, 0.8], [-1.6, -16, 0.6], [1.9, -18, 0.5], [-9.5, -13, 1.0], [10.5, -15, 1.1], [-4.8, -21, 0.9], [5.2, -23, 0.8], [-13, -9, 1.2], [13.5, -10, 1.2], [3.1, -26, 0.45], [-7.8, -26, 1.0]];
        trunks.forEach(([x, z, r]) => {
            const m = new THREE.Mesh(new THREE.CylinderGeometry(r * 0.8, r, 34, 10, 1, true), barkMat);
            m.position.set(x, 14, z);
            m.rotation.z = (Math.random() - 0.5) * 0.08;
            g.add(m);
        });

        const vineMat = new THREE.MeshStandardMaterial({ color: 0x0c2414, roughness: 0.9 });
        for (let i = 0; i < 14; i++) {
            const x0 = (Math.random() - 0.5) * 22;
            const z0 = -6 - Math.random() * 16;
            const drop = 4 + Math.random() * 9;
            const pts = [];
            for (let k = 0; k <= 8; k++) {
                const t = k / 8;
                pts.push(new THREE.Vector3(x0 + Math.sin(t * 3 + i) * 0.4 + t * (Math.random() - 0.5), 16 - drop * t - Math.sin(t * Math.PI) * 0.8, z0));
            }
            g.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 40, 0.03 + Math.random() * 0.04, 5), vineMat));
        }

        // Fronds: four instanced meshes, one per atlas cell
        const atlas = leafAtlas(1024);
        const leaves = [];
        for (let cell = 0; cell < 4; cell++) {
            const t = texture(atlas, {});
            t.repeat.set(0.5, 0.5);
            t.offset.set((cell % 2) * 0.5, cell < 2 ? 0.5 : 0);
            const mat = new THREE.MeshStandardMaterial({ map: t, color: 0x0a2a16, alphaTest: 0.5, side: THREE.DoubleSide, roughness: 0.75, metalness: 0, envMapIntensity: 0.25 });
            const geo = new THREE.PlaneGeometry(1, 1);
            geo.translate(0, 0.5, 0); // pivot at the stem
            const count = 18;
            const mesh = new THREE.InstancedMesh(geo, mat, count);
            const base = [];
            const dummy = new THREE.Object3D();
            for (let i = 0; i < count; i++) {
                const fg = i < 3; // a few big fronds hanging into the top corners
                const sideSign = i % 2 ? 1 : -1;
                if (fg) {
                    dummy.position.set(sideSign * (4.8 + Math.random() * 2.2), 4.6 + Math.random() * 1.2, -0.5 + Math.random() * 1.5);
                    dummy.rotation.set(Math.PI + (Math.random() - 0.5) * 0.5, Math.random() * 0.8, sideSign * (0.5 + Math.random() * 0.6));
                    dummy.scale.setScalar(2.4 + Math.random() * 1.4);
                } else {
                    dummy.position.set((Math.random() - 0.5) * 26, -1 + Math.random() * 9, -5 - Math.random() * 18);
                    dummy.rotation.set((Math.random() - 0.5) * 1.2, Math.random() * TAU, (Math.random() - 0.5) * 2.4);
                    dummy.scale.setScalar(1.4 + Math.random() * 2.6);
                }
                dummy.updateMatrix();
                mesh.setMatrixAt(i, dummy.matrix);
                base.push({ p: dummy.position.clone(), r: dummy.rotation.clone(), s: dummy.scale.x, phase: Math.random() * TAU });
            }
            mesh.userData.leafBase = base;
            mesh.userData.occMat = new THREE.MeshBasicMaterial({ color: 0x000000, map: t, alphaTest: 0.5, side: THREE.DoubleSide });
            leaves.push(mesh);
            g.add(mesh);
        }

        // Mist: two low ground layers and a veil between the trunks
        const mists = [];
        [[-1.72, 0.2, 0.16, 1], [-1.35, 0.12, 0.11, 0.7]].forEach(([y, op, sc, sp]) => {
            const m = new THREE.Mesh(new THREE.PlaneGeometry(46, 34), mistMaterial(0x1c4a30, op, sc, sp));
            m.rotation.x = -Math.PI / 2;
            m.position.set(0, y, -6);
            m.userData.occHide = true;
            mists.push(m);
            g.add(m);
        });
        const veil = new THREE.Mesh(new THREE.PlaneGeometry(50, 14), mistMaterial(0x245a3a, 0.1, 0.12, 0.6, 'xy'));
        veil.position.set(0, 3, -12);
        veil.userData.occHide = true;
        mists.push(veil);
        g.add(veil);

        return { group: g, wall, hot, leaves, mists };
    }

    /* ------------------------------------------------------------------ *
     * 9. Jumanji3DWorld — scene, camera rig, loop
     * ------------------------------------------------------------------ */

    const MODES = ['resting', 'boardOpen', 'terminalFocus'];

    class Jumanji3DWorld {
        constructor({ world }) {
            this.kind = world === 'hub' ? 'hub' : 'ambient';
            this.tier = detectTier();
            this.mode = 'resting';
            this.t = 0;
            this.frame = 0;
            this.last = performance.now();
            this.ft = 1 / 60;
            this.adaptTimer = 0;
            this.acc = 0;
            this.modules = [];
            this.tweens = [];
            this.pointer = { x: 0, y: 0, vx: 0, vy: 0, active: false, lastMove: 0 };
            this.link = true;
            this.cursed = document.body.classList.contains('is-cursed');
            this.curseMix = this.cursed ? 1 : 0;
            this.fade = 1;
            this.flash = 0;
            this.deploying = false;
            this.viewport = { w: innerWidth, h: innerHeight };

            if (!THREE || !webglAvailable()) {
                this.fallback();
                return;
            }
            try {
                this.init();
            } catch (e) {
                console.warn('[JX3D] WebGL init failed, using CSS fallback', e);
                this.teardownCanvas();
                this.fallback();
            }
        }

        /* ---------- setup ---------- */

        init() {
            const hub = this.kind === 'hub';
            this.useComposer = hub && this.tier !== 'low';
            this.maxDpr = Math.min(window.devicePixelRatio || 1, 2, this.tier === 'high' ? 2 : this.tier === 'mid' ? 1.5 : 1);
            this.dpr = this.maxDpr;

            const canvas = document.createElement('canvas');
            canvas.id = 'jumanji-3d-canvas';
            canvas.setAttribute('aria-hidden', 'true');
            document.body.prepend(canvas);
            this.canvas = canvas;

            this.renderer = new THREE.WebGLRenderer({
                canvas,
                antialias: !this.useComposer,
                alpha: !hub,
                powerPreference: hub ? 'high-performance' : 'default'
            });
            maxAniso = this.renderer.capabilities.getMaxAnisotropy();
            this.renderer.setClearColor(0x000000, 0);
            if (this.useComposer) {
                this.renderer.toneMapping = THREE.NoToneMapping;
            } else {
                this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
                this.renderer.outputEncoding = THREE.sRGBEncoding;
            }

            this.scene = new THREE.Scene();
            this.camera = new THREE.PerspectiveCamera(hub ? 38 : 50, innerWidth / innerHeight, 0.05, 140);
            this.raycaster = new THREE.Raycaster();
            this.audio = new JungleAudio();

            if (hub) this.buildHub();
            else this.buildAmbient();

            this.resize();
            this.bindEvents();
            this.attachModules();

            root.classList.add('jx3d-live');
            this.loop = this.loop.bind(this);
            this.raf = requestAnimationFrame(this.loop);
        }

        buildHub() {
            const r = this.renderer;
            const high = this.tier === 'high';
            this.scene.background = new THREE.Color(0x020a05);
            this.scene.fog = new THREE.FogExp2(0x020c06, 0.034);
            this.scene.environment = buildEnvironment(r);

            if (high) {
                r.shadowMap.enabled = true;
                r.shadowMap.type = THREE.PCFSoftShadowMap;
                r.shadowMap.autoUpdate = false;
            }

            const hemi = new THREE.HemisphereLight(0x2f6a45, 0x030704, 0.32);
            const key = new THREE.DirectionalLight(0xffe2a8, 1.5);
            key.position.set(-4, 8, 5);
            if (high) {
                key.castShadow = true;
                key.shadow.mapSize.set(1024, 1024);
                key.shadow.camera.left = -5; key.shadow.camera.right = 5;
                key.shadow.camera.top = 4; key.shadow.camera.bottom = -4;
                key.shadow.camera.near = 1; key.shadow.camera.far = 20;
                key.shadow.bias = -0.0006;
                key.shadow.normalBias = 0.02;
            }
            const rim = new THREE.DirectionalLight(0xffc870, 1.6);
            rim.position.set(0, 5, -12);
            const fill = new THREE.DirectionalLight(0x8fd8a8, 0.3);
            fill.position.set(5, 2, 6);
            this.scene.add(hemi, key, rim, fill);

            this.board = buildBoard();
            this.scene.add(this.board.group);
            this.board.group.updateMatrixWorld(true);
            this.scene.add(buildLectern());
            this.jungle = buildJungle();
            this.scene.add(this.jungle.group);

            const count = this.tier === 'high' ? 480 : this.tier === 'mid' ? 360 : 220;
            this.spores = new Spores(count, new THREE.Box3(new THREE.Vector3(-8, -2.2, -9), new THREE.Vector3(8, 5, 6)), this.dpr);
            this.scene.add(this.spores.points);

            if (this.useComposer) {
                this.composer = new Composer(r, high ? 4 : 0);
                this.raysEnabled = true;
                this.blackMat = new THREE.MeshBasicMaterial({ color: 0x000000 });
                this.collectOccluders();
            }

            // Camera rig. Each mode is a direction from the look-at target plus a
            // distance solved from the slot size, so the box fills the hero from
            // phones to ultrawide monitors.
            this.slot = document.querySelector('[data-jx3d-slot]') || document.querySelector('.emblem');
            this.rig = {
                pos: new THREE.Vector3(0, 1.4, 14),
                look: new THREE.Vector3(0, 0.1, 0),
                anchor: { x: innerWidth / 2, y: innerHeight * 0.4 },
                shake: 0
            };
            this.parallax = new THREE.Vector2();

            // Initial state: board is strictly closed by default
            this.setOpenImmediate(false);
            this.setMode('resting');
            this.snapCamera();
            this.prepareSlot();
            this.syncHubUI(false);
            this.tween({ dur: reduceMotion ? 0.01 : 1.0, ease: easeOutCubic, update: k => { this.fade = 1 - k; } });
        }

        buildAmbient() {
            const count = this.tier === 'high' ? 260 : this.tier === 'mid' ? 200 : 140;
            this.spores = new Spores(count, new THREE.Box3(new THREE.Vector3(-9, -4, -10), new THREE.Vector3(9, 6, 5)), this.dpr);
            this.spores.uniforms.uIntensity.value = 0.85;
            this.scene.add(this.spores.points);

            this.mists = [];
            [[-3.4, 0.22, 0.14, 1], [-2.8, 0.14, 0.1, 0.7]].forEach(([y, op, sc, sp]) => {
                const m = new THREE.Mesh(new THREE.PlaneGeometry(40, 30), mistMaterial(0x2c6a44, op, sc, sp));
                m.rotation.x = -Math.PI / 2;
                m.position.set(0, y, -4);
                this.mists.push(m);
                this.scene.add(m);
            });

            this.rig = {
                pos: new THREE.Vector3(0, 0.6, 8),
                look: new THREE.Vector3(0, 0.2, 0),
                anchor: null,
                shake: 0
            };
            this.parallax = new THREE.Vector2();
            this.fade = 0;
        }

        // Swap every opaque mesh to black for the occlusion pass; leaves keep
        // their alpha-tested silhouette; the haze wall keeps its glow.
        collectOccluders() {
            this.occluders = [];
            this.occHidden = [];
            this.scene.traverse(o => {
                if (o.userData.occHide || o.isPoints || o.isSprite) {
                    this.occHidden.push(o);
                } else if (o.isMesh && !o.userData.emitter) {
                    this.occluders.push({ mesh: o, occ: o.userData.occMat || this.blackMat, mat: null });
                }
            });
        }

        // Make the hero slot the board's click/keyboard target.
        prepareSlot() {
            const slot = this.slot;
            if (!slot) return;
            slot.setAttribute('data-jx3d-slot', '');
            slot.setAttribute('role', 'button');
            slot.setAttribute('tabindex', '0');
            this.updateSlotLabel();
            const activate = (e) => this.activate(e);
            slot.addEventListener('click', activate);
            slot.addEventListener('keydown', e => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    activate(e);
                }
            });
            slot.addEventListener('pointermove', e => {
                const hit = this.pick(e.clientX, e.clientY);
                slot.classList.toggle('is-over-board', !!hit);
                if (hit && hit.object.userData && hit.object.userData.isAnimalToken) {
                    slot.setAttribute('title', 'Expedition Animal Totem · Click to roll your fate');
                } else if (this.board && this.board.isOpen) {
                    slot.setAttribute('title', 'Jumanji Board · Click totem to roll, or edge to close');
                } else {
                    slot.setAttribute('title', 'Cursed Jumanji Box · Click to unseal');
                }
            });
            slot.addEventListener('pointerleave', () => slot.classList.remove('is-over-board'));
        }

        updateSlotLabel() {
            if (!this.slot) return;
            this.slot.setAttribute('aria-label', this.board.isOpen ? 'Click totem to roll or close board' : 'Open the Jumanji board');
            this.slot.setAttribute('aria-pressed', String(this.board.isOpen));
        }

        pick(clientX, clientY) {
            if (!this.board) return null;
            const ndc = new THREE.Vector2((clientX / innerWidth) * 2 - 1, -(clientY / innerHeight) * 2 + 1);
            // setFromCamera unprojects with projectionMatrixInverse, which already
            // includes the view offset, so picking matches the shifted frame.
            this.raycaster.setFromCamera(ndc, this.camera);
            const hits = this.raycaster.intersectObjects(this.board.pickables, true);
            return hits[0] || null;
        }

        bindEvents() {
            this.onResize = () => this.resize();
            window.addEventListener('resize', this.onResize);

            window.addEventListener('pointermove', e => {
                const now = performance.now();
                const nx = (e.clientX / innerWidth) * 2 - 1;
                const ny = -(e.clientY / innerHeight) * 2 + 1;
                const dt = Math.max(0.008, (now - this.pointer.lastMove) / 1000);
                if (this.pointer.active && dt < 0.2) {
                    // NDC velocity, low-passed so a single jumpy event can't fling motes
                    this.pointer.vx = lerp(this.pointer.vx, (nx - this.pointer.x) / dt, 0.4);
                    this.pointer.vy = lerp(this.pointer.vy, (ny - this.pointer.y) / dt, 0.4);
                }
                this.pointer.x = nx;
                this.pointer.y = ny;
                this.pointer.active = true;
                this.pointer.lastMove = now;

                if (this.kind === 'hub') {
                    const hit = this.pick(e.clientX, e.clientY);
                    if (this.slot) this.slot.classList.toggle('is-over-board', !!hit);
                    document.body.style.cursor = hit ? 'pointer' : '';
                }
            }, { passive: true });

            // Stop rendering entirely while the tab is in the background
            document.addEventListener('visibilitychange', () => {
                if (document.hidden) {
                    cancelAnimationFrame(this.raf);
                    this.raf = null;
                } else if (!this.raf) {
                    this.last = performance.now();
                    this.raf = requestAnimationFrame(this.loop);
                }
            });

            // Back/forward cache: undo a half-finished deploy fade
            window.addEventListener('pageshow', e => {
                if (e.persisted && this.deploying) {
                    this.deploying = false;
                    this.fade = 0;
                    this.flash = 0;
                    this.setMode('resting');
                }
            });

            this.observeCurse();

            if (this.kind === 'hub') {
                // Direct manual interaction on the 3D board scene
                document.addEventListener('click', e => {
                    // Ignore clicks on header navigation, links or buttons
                    if (e.target.closest && (e.target.closest('header') || e.target.closest('a') || e.target.closest('button'))) return;
                    const hit = this.pick(e.clientX, e.clientY);
                    if (hit) {
                        this.activate(e);
                    }
                });
            } else {
                // Ambient pages lean in while a terminal has focus
                document.addEventListener('focusin', e => {
                    if (e.target.closest && e.target.closest('.crt-glass')) this.setMode('terminalFocus');
                });
                document.addEventListener('focusout', e => {
                    if (e.target.closest && e.target.closest('.crt-glass')) this.setMode('resting');
                });
            }
        }

        observeCurse() {
            new MutationObserver(() => {
                this.cursed = document.body.classList.contains('is-cursed');
                this.modules.forEach(m => m.onCurse && m.onCurse(this.cursed));
            }).observe(document.body, { attributes: true, attributeFilter: ['class'] });
        }

        attachModules() {
            if (document.querySelector('.relic-token[data-token]')) {
                try { this.modules.push(new RelicTokens(this)); } catch (e) { console.warn('[JX3D] tokens unavailable', e); }
            }
            document.querySelectorAll('.bezel').forEach(bezel => {
                const glass = bezel.querySelector('.crt-glass');
                if (glass) this.modules.push(new FieldRig(this, bezel, glass, true));
            });
        }

        resize() {
            const w = innerWidth, h = innerHeight;
            this.viewport = { w, h };
            this.renderer.setPixelRatio(this.dpr);
            this.renderer.setSize(w, h, false);
            this.camera.aspect = w / h;
            this.camera.updateProjectionMatrix();
            if (this.composer) this.composer.setSize(Math.floor(w * this.dpr), Math.floor(h * this.dpr));
            if (this.spores) this.spores.uniforms.uPx.value = this.dpr;
        }

        setDpr(v) {
            this.dpr = clamp(v, 0.6, this.maxDpr);
            this.resize();
        }

        // Dynamic resolution: if the smoothed frame time stays over budget, step
        // the pixel ratio down (and drop god-rays at the bottom); recover slowly.
        adapt(dt) {
            this.ft = this.ft * 0.95 + dt * 0.05;
            this.adaptTimer += dt;
            if (this.adaptTimer < 2) return;
            this.adaptTimer = 0;
            if (this.ft > 1 / 46 && this.dpr > 0.6) {
                this.setDpr(this.dpr - 0.25);
                if (this.dpr <= 0.85 && this.composer) this.raysEnabled = false;
            } else if (this.ft < 1 / 58 && this.dpr < this.maxDpr) {
                this.setDpr(this.dpr + 0.25);
            }
        }

        /* ---------- tweens ---------- */

        tween({ dur, delay = 0, ease = t => t, update, done }) {
            this.tweens.push({ t0: this.t + delay, dur, ease, update, done });
        }

        runTweens() {
            for (let i = this.tweens.length - 1; i >= 0; i--) {
                const tw = this.tweens[i];
                if (this.t < tw.t0) continue;
                const k = clamp((this.t - tw.t0) / tw.dur, 0, 1);
                tw.update(tw.ease(k));
                if (k >= 1) {
                    this.tweens.splice(i, 1);
                    if (tw.done) tw.done();
                }
            }
        }

        /* ---------- board ---------- */

        setOpenImmediate(open) {
            const b = this.board;
            b.isOpen = open;
            b.wings.forEach(wg => {
                wg.progress = open ? 1 : 0;
                wg.pivot.rotation.z = wg.side < 0 ? Math.PI * wg.progress : -Math.PI * wg.progress;
            });
            b.openness = open ? 1 : 0;
            this.updateSlotLabel();
            this.syncHubUI(open);
        }

        toggleBoard(open) {
            if (!this.board) return;
            const b = this.board;
            const target = typeof open === 'boolean' ? open : !b.isOpen;
            if (target === b.isOpen) return;
            b.isOpen = target;
            this.updateSlotLabel();
            this.syncHubUI(target);
            this.setMode(target ? 'boardOpen' : 'resting');
            if (reduceMotion) {
                this.setOpenImmediate(target);
                return;
            }
            // Left wing first, right a beat later. Each swing eases in and out,
            // then a small damped overshoot sells the weight as it lands.
            b.wings.forEach((wg, i) => {
                const from = wg.progress;
                const to = target ? 1 : 0;
                const hingeWorld = new THREE.Vector3(wg.side * BOARD.w / 2, 0, 0).applyMatrix4(b.group.matrixWorld);
                this.tween({
                    dur: 1.5,
                    delay: i * 0.2,
                    ease: t => {
                        const e = easeInOutCubic(t);
                        return t > 0.82 ? e + Math.sin((t - 0.82) / 0.18 * Math.PI) * 0.1 * (1 - t) : e;
                    },
                    update: k => {
                        wg.progress = lerp(from, to, k);
                        wg.pivot.rotation.z = wg.side < 0 ? Math.PI * wg.progress : -Math.PI * wg.progress;
                    },
                    done: () => {
                        this.rig.shake = 0.6;
                        this.audio.thud(hingeWorld);
                    }
                });
                setTimeout(() => this.audio.scrape(hingeWorld, 1.3), i * 200);
            });
        }

        syncHubUI(open) {
            const orbText = document.getElementById('orb-text');
            if (open) {
                if (orbText) {
                    orbText.innerHTML = 'The board unseals with ancient groan;<br>Touch the beast of carved bronze stone.';
                    orbText.classList.remove('is-surfacing');
                    void orbText.offsetWidth;
                    orbText.classList.add('is-surfacing');
                }
            } else {
                if (orbText) {
                    orbText.innerHTML = 'The board is sealed with ancient bronze;<br>Touch the wood to break the bonds.';
                    orbText.classList.remove('is-surfacing');
                    void orbText.offsetWidth;
                    orbText.classList.add('is-surfacing');
                }
            }
        }

        activate(e) {
            if (!this.board) return;
            // 1. If board is closed, clicking anywhere on it unseals it!
            if (!this.board.isOpen) {
                this.toggleBoard(true);
                return;
            }

            // 2. If board is open:
            if (this.animatingToken || this.deploying) return;

            // If a pointer event was passed, inspect hit object
            if (e && typeof e.clientX === 'number') {
                const hit = this.pick(e.clientX, e.clientY);
                if (hit) {
                    // Check if clicked an outer wing mesh
                    let isWing = false;
                    for (const wg of this.board.wings) {
                        if (hit.object === wg.pivot || (wg.pivot && wg.pivot.children && (wg.pivot.children.includes(hit.object) || (wg.pivot.children[0] && wg.pivot.children[0].children && wg.pivot.children[0].children.includes(hit.object))))) {
                            isWing = true;
                            break;
                        }
                    }
                    const isAnimal = !!(hit.object.userData && hit.object.userData.isAnimalToken);
                    if (isWing && !isAnimal) {
                        // Explicit click on opened lid wing closes the board
                        this.toggleBoard(false);
                        return;
                    }
                }
            }

            // Default activation when open: roll expedition!
            this.rollExpedition();
        }

        rollExpedition() {
            if (!this.board || this.animatingToken || this.deploying) return;
            const b = this.board;
            const config = window.PLAYER_EXPEDITION || {};
            const orbText = document.getElementById('orb-text');

            // 1. Check unlocked state
            if (!config.isUnlocked) {
                if (this.audio) this.audio.scrape(b.animalToken.position.clone().applyMatrix4(b.group.matrixWorld), 0.5);
                this.shakeToken(0.4);
                if (orbText && config.lockedRiddle) {
                    orbText.innerHTML = config.lockedRiddle.replace(/\n/g, '<br>');
                    orbText.classList.remove('is-surfacing');
                    void orbText.offsetWidth;
                    orbText.classList.add('is-surfacing');
                }
                return;
            }

            // 2. Check completed state
            if (config.isDone) {
                this.spinToken();
                if (orbText && config.completedRiddle) {
                    orbText.innerHTML = config.completedRiddle.replace(/\n/g, '<br>');
                    orbText.classList.remove('is-surfacing');
                    void orbText.offsetWidth;
                    orbText.classList.add('is-surfacing');
                }
                return;
            }

            // 3. Active Roll
            this.animatingToken = true;
            if (orbText) {
                orbText.innerHTML = 'The dice are rolled...<br>The jungle answers to your step.';
                orbText.classList.remove('is-surfacing');
                void orbText.offsetWidth;
                orbText.classList.add('is-surfacing');
            }

            const steps = config.steps || 5;
            const style = config.movementStyle || 'hop';

            let targetTh = 0.55;
            if (config.targetLevel === 'l3') {
                targetTh = 1.35;
            } else if (config.targetLevel === 'day2') {
                targetTh = 2.2 * Math.PI;
            }

            const startTh = 0;
            const deltaTh = (targetTh - startTh) / steps;
            const stepDuration = style === 'heavy' ? 0.38 : style === 'charge' ? 0.16 : 0.28;

            let currentStep = 0;
            const executeStep = () => {
                if (currentStep >= steps) {
                    this.onTokenArrived(config);
                    return;
                }

                const sTh = startTh + currentStep * deltaTh;
                const eTh = startTh + (currentStep + 1) * deltaTh;
                const token = b.animalToken;
                const jumpHeight = style === 'heavy' ? 0.08 : style === 'charge' ? 0.05 : 0.13;

                this.tween({
                    dur: stepDuration,
                    ease: t => t,
                    update: progress => {
                        const curTh = lerp(sTh, eTh, progress);
                        const pt = getTrackPoint3D(curTh);
                        const ang = getTrackAngle3D(curTh);

                        const hopY = Math.sin(progress * Math.PI) * jumpHeight;
                        token.position.set(pt.x, pt.y + hopY, pt.z);
                        token.rotation.y = ang;

                        if (style === 'heavy') {
                            token.rotation.x = Math.sin(progress * Math.PI) * -0.15;
                        } else if (style === 'hop') {
                            token.rotation.x = Math.sin(progress * Math.PI) * -0.22;
                        }
                    },
                    done: () => {
                        currentStep++;
                        const tokenWorld = token.position.clone().applyMatrix4(b.group.matrixWorld);
                        if (this.audio) {
                            this.audio.thump(tokenWorld, style === 'heavy' ? 0.9 : 0.5, true);
                        }
                        if (style === 'heavy') {
                            this.rig.shake = 0.3;
                        }
                        const pause = style === 'charge' ? 20 : (style === 'heavy' ? 120 : 60);
                        setTimeout(executeStep, pause);
                    }
                });
            };

            executeStep();
        }

        onTokenArrived(config) {
            const b = this.board;
            const orbText = document.getElementById('orb-text');

            b.gemMat.emissiveIntensity = 4.0;
            b.gemLight.intensity = 8.0;
            this.flash = 0.4;
            this.rig.shake = 0.5;

            if (orbText && config.riddle) {
                orbText.innerHTML = config.riddle.replace(/\n/g, '<br>');
                orbText.classList.remove('is-surfacing');
                void orbText.offsetWidth;
                orbText.classList.add('is-surfacing');
            }

            setTimeout(() => {
                this.deploy(config.targetUrl || '/hub', 'emerald');
            }, 2000);
        }

        shakeToken(dur) {
            const token = this.board.animalToken;
            const basePos = token.position.clone();
            this.tween({
                dur: dur || 0.4,
                update: k => {
                    const decay = 1 - k;
                    token.position.x = basePos.x + (Math.random() - 0.5) * 0.04 * decay;
                    token.position.z = basePos.z + (Math.random() - 0.5) * 0.04 * decay;
                },
                done: () => {
                    token.position.copy(basePos);
                }
            });
        }

        spinToken() {
            const token = this.board.animalToken;
            const baseRotY = token.rotation.y;
            this.tween({
                dur: 1.0,
                ease: easeOutCubic,
                update: k => {
                    token.rotation.y = baseRotY + k * Math.PI * 2;
                }
            });
        }

        /* ---------- camera ---------- */

        // Distance at which `worldSize` spans `px` screen pixels. The visible
        // height at distance d is 2·d·tan(fov/2) over the viewport height, and
        // width scales by the same aspect, so one formula fits either axis.
        fitDistance(worldSize, px) {
            const fov = THREE.MathUtils.degToRad(this.camera.fov);
            return (worldSize * this.viewport.h) / (Math.max(px, 1) * 2 * Math.tan(fov / 2));
        }

        modeTarget(mode) {
            const vw = this.viewport.w, vh = this.viewport.h;
            if (this.kind !== 'hub') {
                const z = mode === 'terminalFocus' ? 5.6 : 8;
                return { pos: new THREE.Vector3(0, 0.6, z), look: new THREE.Vector3(0, 0.2, 0), anchor: null };
            }
            const rect = this.slot ? this.slot.getBoundingClientRect() : { left: vw * 0.2, top: vh * 0.1, width: vw * 0.6, height: vh * 0.5 };
            const anchor = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
            if (mode === 'boardOpen') {
                // Crane overhead and frame the whole open board in the viewport
                const look = new THREE.Vector3(0, -0.15, 0.05);
                const d = Math.max(this.fitDistance(7.0, Math.min(vw * 0.94, 1200)), this.fitDistance(3.4, vh * 0.6));
                const dir = new THREE.Vector3(0, 1.25, 0.66).normalize();
                return { pos: look.clone().addScaledVector(dir, d), look, anchor: { x: vw / 2, y: vh / 2 } };
            }
            if (mode === 'terminalFocus') {
                // Dive into the jaguar's eye
                const gem = this.board.gemLocal.clone().applyMatrix4(this.board.group.matrixWorld);
                const normal = new THREE.Vector3(0, 1, 0).applyQuaternion(this.board.group.quaternion);
                return { pos: gem.clone().addScaledVector(normal, 0.95).add(new THREE.Vector3(0, 0, 0.35)), look: gem, anchor: { x: vw / 2, y: vh / 2 } };
            }
            // resting: fit the box (wider once open) into the slot, by width or
            // height, whichever is tighter.
            const look = new THREE.Vector3(0, 0.05, 0);
            const open = this.board.openness;
            const worldW = lerp(4.8, 6.8, open);
            const worldH = lerp(3.0, 2.6, open); // closed: box + lectern top must clear the caption
            const d = Math.max(this.fitDistance(worldW, rect.width), this.fitDistance(worldH, rect.height));
            const dir = new THREE.Vector3(0, 0.3, 1).normalize();
            return { pos: look.clone().addScaledVector(dir, d), look, anchor };
        }

        snapCamera() {
            const tgt = this.modeTarget(this.mode);
            this.rig.pos.copy(tgt.pos);
            this.rig.look.copy(tgt.look);
            if (tgt.anchor) this.rig.anchor = { ...tgt.anchor };
        }

        setMode(mode) {
            if (MODES.includes(mode)) this.mode = mode;
        }

        updateCamera(dt) {
            const tgt = this.modeTarget(this.mode);
            const k = this.mode === 'terminalFocus' ? 2.2 : this.mode === 'boardOpen' ? 1.8 : 1.6;
            const rig = this.rig;
            const hub = this.kind === 'hub';

            // Mouse parallax: orbit the eye a little around the target
            if (!reduceMotion) {
                this.parallax.x = damp(this.parallax.x, this.pointer.x, 3, dt);
                this.parallax.y = damp(this.parallax.y, this.pointer.y, 3, dt);
            }
            const pos = tgt.pos.clone();
            pos.x += this.parallax.x * (hub ? 0.45 : 0.8);
            pos.y += this.parallax.y * (hub ? 0.22 : 0.4);
            if (!reduceMotion) {
                // Slow handheld drift
                pos.x += Math.sin(this.t * 0.21) * 0.06;
                pos.y += Math.sin(this.t * 0.17 + 1.3) * 0.04;
            }

            rig.pos.x = damp(rig.pos.x, pos.x, k, dt);
            rig.pos.y = damp(rig.pos.y, pos.y, k, dt);
            rig.pos.z = damp(rig.pos.z, pos.z, k, dt);
            rig.look.x = damp(rig.look.x, tgt.look.x, k * 1.2, dt);
            rig.look.y = damp(rig.look.y, tgt.look.y, k * 1.2, dt);
            rig.look.z = damp(rig.look.z, tgt.look.z, k * 1.2, dt);

            this.camera.position.copy(rig.pos);
            if (rig.shake > 0.001) {
                // Landing shake: high-frequency jitter decaying exponentially
                const s = rig.shake * 0.025;
                this.camera.position.x += (Math.random() - 0.5) * s;
                this.camera.position.y += (Math.random() - 0.5) * s;
                rig.shake *= Math.exp(-dt * 7);
            }
            this.camera.lookAt(rig.look);

            if (tgt.anchor && rig.anchor) {
                // Pin the look-at point to the slot centre on screen, including
                // while the page scrolls. setViewOffset shifts the projection
                // itself, so perspective doesn't skew. Resting follows scroll
                // tightly; mode changes glide.
                const follow = this.mode === 'resting' ? 20 : 3;
                rig.anchor.x = damp(rig.anchor.x, tgt.anchor.x, follow, dt);
                rig.anchor.y = damp(rig.anchor.y, tgt.anchor.y, follow, dt);
                const { w, h } = this.viewport;
                this.camera.setViewOffset(w, h, w / 2 - rig.anchor.x, h / 2 - rig.anchor.y, w, h);
            } else if (this.camera.view && this.camera.view.enabled) {
                this.camera.clearViewOffset();
            }
        }

        /* ---------- deploy ---------- */

        deploy(href, kind) {
            if (this.deploying) return;
            this.deploying = true;
            const go = () => { location.href = href; };
            if (!this.board || reduceMotion) {
                go();
                return;
            }
            const wasOpen = this.board.isOpen;
            this.toggleBoard(true);
            const lead = wasOpen ? 0 : 0.9;
            setTimeout(() => this.setMode(kind === 'emerald' ? 'terminalFocus' : 'boardOpen'), lead * 1000);
            const total = lead + 1.3;
            this.tween({ dur: 0.45, delay: total - 0.55, update: k => { this.flash = Math.sin(k * Math.PI) * 0.5; } });
            this.tween({ dur: 0.5, delay: total - 0.45, update: k => { this.fade = k; } });
            // Navigate on a timer, not on the tween, so a stalled frame can't trap the user
            setTimeout(go, total * 1000);
        }

        /* ---------- per-frame ---------- */

        loop(now) {
            this.raf = requestAnimationFrame(this.loop);
            const raw = Math.min(0.05, Math.max(0.001, (now - this.last) / 1000));
            this.last = now;
            this.frame++;
            this.adapt(raw);
            // The ambient layer only needs ~30 fps; leave GPU time for the terminal.
            this.acc += raw;
            if (this.kind === 'ambient' && this.frame % 2) return;
            const dt = Math.min(0.1, this.acc);
            this.acc = 0;
            this.t += dt;
            this.update(dt);
            this.render();
        }

        pointerRay() {
            if (!this.pointer.active || reduceMotion) return null;
            this.raycaster.setFromCamera(new THREE.Vector2(this.pointer.x, this.pointer.y), this.camera);
            // Pointer NDC velocity → world velocity at depth ~4: one NDC unit
            // spans tan(fov/2)·depth world units vertically (× aspect across).
            const tanH = Math.tan(THREE.MathUtils.degToRad(this.camera.fov) / 2) * 4;
            const right = new THREE.Vector3(1, 0, 0).applyQuaternion(this.camera.quaternion);
            const up = new THREE.Vector3(0, 1, 0).applyQuaternion(this.camera.quaternion);
            const vel = right.multiplyScalar(this.pointer.vx * tanH * this.camera.aspect * 0.08).addScaledVector(up, this.pointer.vy * tanH * 0.08);
            this.pointer.vx *= 0.85;
            this.pointer.vy *= 0.85;
            return { ray: this.raycaster.ray, vel };
        }

        update(dt) {
            this.runTweens();
            this.curseMix = damp(this.curseMix, this.cursed ? 1 : 0, 3, dt);
            this.updateCamera(dt);
            this.camera.updateMatrixWorld();

            const sporeSpeed = (reduceMotion ? 0.15 : 0.55) * (1 + this.curseMix * 1.5);
            this.spores.update(dt, this.t, sporeSpeed, this.pointerRay());
            this.spores.uniforms.uCurse.value = this.curseMix;

            if (this.kind === 'hub') {
                this.updateHub(dt);
            } else {
                this.mists.forEach(m => {
                    m.material.uniforms.uTime.value = this.t;
                    m.material.uniforms.uCurse.value = this.curseMix;
                });
            }

            this.modules.forEach(m => m.update && m.update(dt, this.t));
        }

        updateHub(dt) {
            const b = this.board;
            const pulse = reduceMotion ? 0.5 : heartbeat(this.t);
            b.openness = Math.min(b.wings[0].progress, b.wings[1].progress);
            const open = b.openness;
            const closedness = 1 - Math.max(b.wings[0].progress, b.wings[1].progress);

            b.gemMat.emissiveIntensity = 0.35 + pulse * 1.6;
            b.gemLight.intensity = (0.6 + pulse * 3.2) * (0.15 + open * 0.85);
            b.halo.material.opacity = (0.18 + pulse * 0.35) * open;
            b.halo.scale.setScalar(1.3 + pulse * 0.35 + (this.mode === 'terminalFocus' ? 1.2 : 0));
            b.seamLine.visible = closedness > 0.02;
            b.seamGlow.material.opacity = (0.25 + pulse * 0.75) * closedness;
            b.caustics.material.uniforms.uTime.value = this.t;
            b.caustics.material.uniforms.uPulse.value = pulse;
            b.caustics.material.uniforms.uOpen.value = open;
            b.dispersion.material.uniforms.uTime.value = this.t;

            if (b.animalAura) {
                b.animalAura.scale.setScalar(1 + 0.15 * Math.sin(this.t * 3));
                b.animalAura.material.opacity = (0.5 + 0.3 * Math.sin(this.t * 3)) * open;
            }

            // Hovering the box warms the gold inlays
            const hover = this.slot && this.slot.classList.contains('is-over-board') ? 1 : 0;
            const e = damp(b.goldMat.emissive.r, hover * 0.12, 6, dt);
            b.goldMat.emissive.setRGB(e, e * 0.7, e * 0.15);

            this.jungle.wall.material.uniforms.uTime.value = this.t;
            this.jungle.mists.forEach(m => { m.material.uniforms.uTime.value = this.t; });

            // Fronds sway: per-instance rotation around the stem, phase-shifted
            if (!reduceMotion && this.frame % 2 === 0) {
                const dummy = this._dummy || (this._dummy = new THREE.Object3D());
                this.jungle.leaves.forEach(mesh => {
                    mesh.userData.leafBase.forEach((lb, i) => {
                        dummy.position.copy(lb.p);
                        dummy.rotation.set(lb.r.x + Math.sin(this.t * 0.6 + lb.phase) * 0.05, lb.r.y, lb.r.z + Math.sin(this.t * 0.8 + lb.phase * 1.7) * 0.06);
                        dummy.scale.setScalar(lb.s);
                        dummy.updateMatrix();
                        mesh.setMatrixAt(i, dummy.matrix);
                    });
                    mesh.instanceMatrix.needsUpdate = true;
                });
            }

            // Heartbeat thump on each "lub" and "dub", only while the hero is on screen
            const beatIdx = Math.floor(this.t / BEAT);
            const ph = (this.t % BEAT) / BEAT;
            const rect = this.slot ? this.slot.getBoundingClientRect() : null;
            const heroVisible = !rect || (rect.bottom > 0 && rect.top < this.viewport.h);
            if (!reduceMotion && heroVisible && this.audio.enabled) {
                const gemWorld = b.gemLocal.clone().applyMatrix4(b.group.matrixWorld);
                if (beatIdx !== this.lastBeat) {
                    this.lastBeat = beatIdx;
                    this.audio.listen(this.camera);
                    this.audio.thump(gemWorld, 0.8, open);
                } else if (ph >= DUB_AT && this.lastDub !== beatIdx) {
                    this.lastDub = beatIdx;
                    this.audio.thump(gemWorld, 0.45, open);
                }
            } else {
                this.lastBeat = beatIdx;
                this.lastDub = beatIdx;
            }
        }

        render() {
            const r = this.renderer;
            if (!this.composer) {
                r.setRenderTarget(null);
                r.render(this.scene, this.camera);
                return;
            }
            const C = this.composer;
            if (r.shadowMap.enabled) r.shadowMap.needsUpdate = true;
            r.setRenderTarget(C.main);
            r.render(this.scene, this.camera);

            let rayStrength = 0;
            if (this.raysEnabled) {
                // Occlusion pass: black silhouettes over the glowing haze wall
                const bg = this.scene.background;
                const fog = this.scene.fog;
                this.scene.background = null;
                this.scene.fog = null;
                this.occluders.forEach(o => { o.mat = o.mesh.material; o.mesh.material = o.occ; });
                this.occHidden.forEach(o => { o._vis = o.visible; o.visible = false; });
                r.setRenderTarget(C.occ);
                r.setClearColor(0x000000, 1);
                r.clear();
                r.render(this.scene, this.camera);
                this.occluders.forEach(o => { o.mesh.material = o.mat; });
                this.occHidden.forEach(o => { o.visible = o._vis; });
                this.scene.background = bg;
                this.scene.fog = fog;
                r.setClearColor(0x000000, 0);

                // Light position in screen UV; fade the rays if the source drifts
                // far off-screen or behind the camera.
                const lp = this.jungle.hot.clone().project(this.camera);
                C.raysMat.uniforms.uLight.value.set(lp.x * 0.5 + 0.5, lp.y * 0.5 + 0.5);
                const off = Math.max(Math.abs(lp.x), Math.abs(lp.y));
                rayStrength = lp.z > 1 ? 0 : clamp(1.8 - off * 0.6, 0, 1);
                C.pass(C.raysMat, C.rays);
            }

            const u = C.compMat.uniforms;
            u.uRayStrength.value = rayStrength * 0.9;
            u.uTime.value = this.t;
            u.uFade.value = this.fade;
            u.uFlash.value = this.flash;
            u.uCurse.value = this.curseMix * 0.6;
            C.pass(C.compMat, null);
        }

        /* ---------- public API ---------- */

        stamp(id) {
            this.modules.forEach(m => m.stamp && m.stamp(id));
        }

        signal(name, value) {
            if (name === 'link') this.link = !!value;
            this.modules.forEach(m => m.signal && m.signal(name, value));
        }

        teardownCanvas() {
            if (this.canvas) this.canvas.remove();
            if (this.renderer) this.renderer.dispose();
            this.renderer = null;
        }

        dispose() {
            cancelAnimationFrame(this.raf);
            window.removeEventListener('resize', this.onResize);
            this.modules.forEach(m => m.dispose && m.dispose());
            this.teardownCanvas();
            root.classList.remove('jx3d-live');
        }

        /* ---------- no WebGL: CSS 3D perspective fallback ---------- */

        fallback() {
            root.classList.add('jx3d-fallback');
            this.fallbackMode = true;
            const emblem = document.querySelector('.emblem');
            if (emblem && !reduceMotion) {
                window.addEventListener('pointermove', e => {
                    const x = e.clientX / innerWidth - 0.5;
                    const y = e.clientY / innerHeight - 0.5;
                    emblem.style.setProperty('--tilt-x', (-y * 14).toFixed(2) + 'deg');
                    emblem.style.setProperty('--tilt-y', (x * 18).toFixed(2) + 'deg');
                }, { passive: true });
            }
            // The terminal chassis is mostly CSS, so it still mounts without WebGL
            document.querySelectorAll('.bezel').forEach(bezel => {
                const glass = bezel.querySelector('.crt-glass');
                if (glass) this.modules.push(new FieldRig(this, bezel, glass, false));
            });
            if (this.modules.length) {
                // Drive LED decay without a render loop
                let last = performance.now();
                const tick = now => {
                    const dt = Math.min(0.1, (now - last) / 1000);
                    last = now;
                    this.modules.forEach(m => m.update && m.update(dt, now / 1000));
                    requestAnimationFrame(tick);
                };
                requestAnimationFrame(tick);
            }
            this.observeCurse();
        }
    }

    /* ------------------------------------------------------------------ *
     * 10. Relic tokens (Module B)
     *     One offscreen renderer draws every token and blits it into a 2D
     *     canvas inside its card, so tokens live in the DOM: they scroll,
     *     clip and tilt with the card, and need only one WebGL context.
     * ------------------------------------------------------------------ */

    const TOKEN_R = 0.62;
    const TOKEN_CSS = 64 * 1.8; // canvas overhangs the 64px slot for stamp dust

    const METALS = {
        bronze: { color: 0xb0703a, metalness: 1, roughness: 0.34 },
        redBronze: { color: 0xa8402a, metalness: 1, roughness: 0.3 },
        steel: { color: 0xc8d0d8, metalness: 1, roughness: 0.2 },
        brass: { color: 0xd4a843, metalness: 1, roughness: 0.28 },
        gold: { color: 0xd4a640, metalness: 1, roughness: 0.26 },
        leather: { color: 0x4a2a14, metalness: 0, roughness: 0.7 },
        enamel: { color: 0x6b7448, metalness: 0.3, roughness: 0.45 },
        varnish: { color: 0x7a4a22, metalness: 0, roughness: 0.32 }
    };

    const metal = name => new THREE.MeshStandardMaterial(METALS[name]);

    function extrude(shape, depth, bevel) {
        const g = new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: true, bevelThickness: bevel, bevelSize: bevel, bevelSegments: 2, curveSegments: 16 });
        g.translate(0, 0, -depth / 2);
        return g;
    }

    const EMBLEMS = {
        // Bravestone: bronze compass whose needle swings toward the pointer
        bravestone(parts) {
            const g = new THREE.Group();
            g.add(new THREE.Mesh(new THREE.TorusGeometry(0.34, 0.032, 12, 64), metal('bronze')));
            for (let i = 0; i < 4; i++) {
                const tick = new THREE.Mesh(new THREE.BoxGeometry(0.035, 0.1, 0.03), metal('bronze'));
                const a = (i / 4) * TAU;
                tick.position.set(Math.sin(a) * 0.255, Math.cos(a) * 0.255, 0);
                tick.rotation.z = -a;
                g.add(tick);
            }
            const needle = new THREE.Group();
            const north = new THREE.Shape([new THREE.Vector2(0, 0.29), new THREE.Vector2(-0.055, 0), new THREE.Vector2(0.055, 0)]);
            const south = new THREE.Shape([new THREE.Vector2(0, -0.29), new THREE.Vector2(0.055, 0), new THREE.Vector2(-0.055, 0)]);
            needle.add(new THREE.Mesh(extrude(north, 0.025, 0.01), metal('redBronze')));
            needle.add(new THREE.Mesh(extrude(south, 0.025, 0.01), metal('steel')));
            needle.position.z = 0.03;
            g.add(needle);
            const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.05, 20), metal('gold'));
            cap.rotation.x = Math.PI / 2;
            cap.position.z = 0.05;
            g.add(cap);
            parts.needle = needle;
            return g;
        },
        // Ruby: steel dagger laid across the token
        ruby() {
            const g = new THREE.Group();
            const blade = new THREE.Shape([new THREE.Vector2(0, 0.44), new THREE.Vector2(-0.055, 0.3), new THREE.Vector2(-0.06, -0.02), new THREE.Vector2(0.06, -0.02), new THREE.Vector2(0.055, 0.3)]);
            g.add(new THREE.Mesh(extrude(blade, 0.02, 0.014), metal('steel')));
            const guard = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.045, 0.06), metal('bronze'));
            guard.position.y = -0.05;
            g.add(guard);
            const grip = new THREE.Mesh(new THREE.CylinderGeometry(0.032, 0.036, 0.2, 16), metal('leather'));
            grip.position.y = -0.17;
            g.add(grip);
            const pommel = new THREE.Mesh(new THREE.SphereGeometry(0.05, 20, 12), metal('bronze'));
            pommel.position.y = -0.3;
            g.add(pommel);
            g.rotation.z = -Math.PI / 4;
            return g;
        },
        // Finbar: safari canteen with cap and strap
        finbar() {
            const g = new THREE.Group();
            const body = new THREE.Mesh(new THREE.CylinderGeometry(0.27, 0.27, 0.12, 48), metal('enamel'));
            body.rotation.x = Math.PI / 2;
            body.position.y = -0.04;
            g.add(body);
            const seam = new THREE.Mesh(new THREE.TorusGeometry(0.272, 0.014, 8, 64), metal('steel'));
            seam.position.y = -0.04;
            g.add(seam);
            const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.06, 0.08, 16), metal('steel'));
            neck.position.y = 0.26;
            g.add(neck);
            const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.068, 0.068, 0.05, 20), metal('brass'));
            cap.position.y = 0.31;
            g.add(cap);
            const strap = new THREE.Mesh(new THREE.TorusGeometry(0.36, 0.022, 8, 48, Math.PI * 1.1), metal('leather'));
            strap.rotation.z = -0.05 * Math.PI;
            strap.position.set(0, -0.04, -0.02);
            g.add(strap);
            return g;
        },
        // Oberon: brass sextant whose index arm idles back and forth
        oberon(parts) {
            const g = new THREE.Group();
            const apex = new THREE.Vector3(0, 0.32, 0);
            const arc = new THREE.Mesh(new THREE.TorusGeometry(0.56, 0.026, 8, 40, Math.PI / 3), metal('brass'));
            arc.position.copy(apex);
            arc.rotation.z = Math.PI + Math.PI / 3; // span 240°..300°, hanging under the apex
            g.add(arc);
            [-1, 1].forEach(s => {
                const bar = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.56, 0.03), metal('brass'));
                bar.position.set(apex.x + Math.sin(s * Math.PI / 6) * 0.28, apex.y - Math.cos(Math.PI / 6) * 0.28, 0);
                bar.rotation.z = s * Math.PI / 6;
                g.add(bar);
            });
            for (let i = 0; i <= 8; i++) {
                const a = Math.PI + Math.PI / 3 + (i / 8) * (Math.PI / 3);
                const t = new THREE.Mesh(new THREE.BoxGeometry(0.012, 0.05, 0.02), metal('gold'));
                t.position.set(apex.x + Math.cos(a) * 0.53, apex.y + Math.sin(a) * 0.53, 0.02);
                t.rotation.z = a - Math.PI / 2;
                g.add(t);
            }
            const arm = new THREE.Group();
            arm.position.set(apex.x, apex.y, 0.03);
            const armBar = new THREE.Mesh(new THREE.BoxGeometry(0.026, 0.6, 0.036), metal('bronze'));
            armBar.position.y = -0.3;
            arm.add(armBar);
            g.add(arm);
            const scope = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.04, 0.34, 16), metal('steel'));
            scope.rotation.z = Math.PI / 2;
            scope.position.set(0, 0.1, 0.04);
            g.add(scope);
            parts.arm = arm;
            g.position.y = -0.02;
            return g;
        },
        // Seaplane: biplane propeller that spins up on hover
        seaplane(parts) {
            const g = new THREE.Group();
            const prop = new THREE.Group();
            const shape = new THREE.Shape();
            shape.moveTo(-0.03, 0.05);
            shape.quadraticCurveTo(-0.1, 0.24, -0.05, 0.43);
            shape.quadraticCurveTo(0, 0.47, 0.05, 0.43);
            shape.quadraticCurveTo(0.1, 0.24, 0.03, 0.05);
            shape.closePath();
            [0, Math.PI].forEach(a => {
                const blade = new THREE.Mesh(extrude(shape, 0.025, 0.012), metal('varnish'));
                blade.rotation.y = 0.35; // blade pitch
                const holder = new THREE.Group();
                holder.add(blade);
                holder.rotation.z = a;
                prop.add(holder);
            });
            const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.075, 0.075, 0.08, 24), metal('brass'));
            hub.rotation.x = Math.PI / 2;
            prop.add(hub);
            const spinner = new THREE.Mesh(new THREE.ConeGeometry(0.06, 0.09, 24), metal('gold'));
            spinner.rotation.x = Math.PI / 2;
            spinner.position.z = 0.08;
            prop.add(spinner);
            prop.rotation.z = 0.4;
            g.add(prop);
            parts.prop = prop;
            return g;
        }
    };

    function tokenFace(woodCanvas, stamped) {
        const S = 512;
        const [c, g] = makeCanvas(S, S);
        const [ec, eg] = makeCanvas(S, S);
        g.save();
        g.beginPath(); g.arc(S / 2, S / 2, S / 2, 0, TAU); g.clip();
        g.translate(S / 2, S / 2);
        g.rotate(0.6);
        g.drawImage(woodCanvas, -S, -S, S * 2, S * 2);
        g.restore();
        const v = g.createRadialGradient(S / 2, S / 2, S * 0.15, S / 2, S / 2, S / 2);
        v.addColorStop(0, 'rgba(0,0,0,0)');
        v.addColorStop(1, 'rgba(0,0,0,0.55)');
        g.fillStyle = v;
        g.fillRect(0, 0, S, S);
        g.strokeStyle = '#d4a640';
        g.lineWidth = 6;
        for (let i = 0; i < 24; i++) {
            const a = (i / 24) * TAU;
            g.beginPath();
            g.moveTo(S / 2 + Math.cos(a) * 214, S / 2 + Math.sin(a) * 214);
            g.lineTo(S / 2 + Math.cos(a) * 240, S / 2 + Math.sin(a) * 240);
            g.stroke();
        }
        g.strokeStyle = 'rgba(0,0,0,0.6)';
        g.lineWidth = 3;
        g.beginPath(); g.arc(S / 2, S / 2, 202, 0, TAU); g.stroke();

        eg.fillStyle = '#000';
        eg.fillRect(0, 0, S, S);
        if (stamped) {
            // The seal's carving: a ring of jaguar rosettes pressed into the
            // wood, inlaid with glowing emerald (same strokes on the emissive map).
            [g, eg].forEach((ctx, pass) => {
                ctx.strokeStyle = pass ? '#00ff66' : '#1fd96a';
                ctx.lineWidth = 9;
                ctx.beginPath(); ctx.arc(S / 2, S / 2, 194, 0, TAU); ctx.stroke();
                for (let i = 0; i < 16; i++) {
                    const a = (i / 16) * TAU + 0.1;
                    const x = S / 2 + Math.cos(a) * 172, y = S / 2 + Math.sin(a) * 172;
                    ctx.lineWidth = 4;
                    ctx.strokeStyle = pass ? '#00aa44' : '#2b1608';
                    ctx.beginPath(); ctx.ellipse(x, y, 11, 8, a, 0.3, TAU - 0.4); ctx.stroke();
                    ctx.fillStyle = pass ? '#00aa44' : '#2b1608';
                    ctx.beginPath(); ctx.arc(x, y, 3, 0, TAU); ctx.fill();
                }
            });
        }
        return { map: texture(c, { srgb: true }), emissive: texture(ec, { srgb: true }) };
    }

    class RelicTokens {
        constructor(world) {
            this.world = world;
            this.slots = [...document.querySelectorAll('.relic-token[data-token]')];
            this.tokens = new Map();
            this.queue = [];
            this.active = null;

            const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
            renderer.setPixelRatio(1);
            renderer.outputEncoding = THREE.sRGBEncoding;
            renderer.toneMapping = THREE.ACESFilmicToneMapping;
            renderer.toneMappingExposure = 1.1;
            renderer.setClearColor(0x000000, 0);
            this.renderer = renderer;

            this.scene = new THREE.Scene();
            this.scene.environment = buildEnvironment(renderer);
            this.camera = new THREE.PerspectiveCamera(26, 1, 0.1, 20);
            this.camera.position.set(0, 0, 4.6);
            this.key = new THREE.DirectionalLight(0xfff0d0, 2.2);
            this.key.position.set(1.5, 2, 3);
            const rim = new THREE.DirectionalLight(0x66ffaa, 0.6);
            rim.position.set(-2, -1.5, -1);
            this.scene.add(this.key, rim, new THREE.AmbientLight(0x3a5a40, 0.4));

            const woodCanvas = woodTile(256, 5, [16, 8, 4], [70, 38, 16]);
            this.faces = { plain: tokenFace(woodCanvas, false), stamped: tokenFace(woodCanvas, true) };
            this.rimMat = new THREE.MeshStandardMaterial({ color: 0xb08a3a, metalness: 1, roughness: 0.38 });
            this.rimStampedMat = new THREE.MeshStandardMaterial({ color: 0xe8c25a, metalness: 1, roughness: 0.18, emissive: 0x3a2a00, emissiveIntensity: 0.6 });
            this.rimGeo = RelicTokens.rimGeometry();

            this.buildStamp();
            this.buildDust();

            const px = Math.round(TOKEN_CSS * Math.min(window.devicePixelRatio || 1, 2));
            this.renderer.setSize(px, px, false);
            this.slots.forEach(slot => this.mountSlot(slot, px));
            document.body.classList.add('jx3d-tokens');
        }

        // Profile of the rim band, lathed around y then turned to face +z
        static rimGeometry() {
            const pts = [[0.565, 0.08], [0.6, 0.075], [TOKEN_R, 0.05], [TOKEN_R, -0.05], [0.6, -0.075], [0.565, -0.08]].map(([x, y]) => new THREE.Vector2(x, y));
            const g = new THREE.LatheGeometry(pts, 72);
            g.rotateX(Math.PI / 2);
            return g;
        }

        mountSlot(slot, px) {
            const id = slot.dataset.token;
            const card = slot.closest('.avatar-card') || slot.parentElement;
            const canvas = document.createElement('canvas');
            canvas.className = 'relic-token__canvas';
            canvas.width = canvas.height = px;
            slot.appendChild(canvas);
            const glare = document.createElement('span');
            glare.className = 'card-glare';
            glare.setAttribute('aria-hidden', 'true');
            card.appendChild(glare);

            const group = new THREE.Group();
            const rim = new THREE.Mesh(this.rimGeo, this.rimMat);
            const faceGeo = new THREE.CircleGeometry(0.566, 72);
            const faceMat = new THREE.MeshStandardMaterial({ map: this.faces.plain.map, roughness: 0.6, metalness: 0, emissive: 0x000000 });
            const front = new THREE.Mesh(faceGeo, faceMat);
            front.position.z = 0.072;
            const back = new THREE.Mesh(faceGeo, faceMat);
            back.position.z = -0.072;
            back.rotation.y = Math.PI;
            const inner = new THREE.Mesh(new THREE.TorusGeometry(0.47, 0.012, 8, 72), this.rimMat);
            inner.position.z = 0.075;
            const parts = {};
            const emblem = (EMBLEMS[id] || EMBLEMS.bravestone)(parts);
            emblem.position.z = 0.13;
            group.add(rim, front, back, inner, emblem);
            group.visible = false;
            this.scene.add(group);

            const token = {
                id, slot, card, canvas, ctx: canvas.getContext('2d'), group, rim, inner, faceMat, parts,
                rx: 0, ry: 0, trx: 0, try: 0, lx: 1.5, ly: 2,
                hover: false, dirty: true, spin: 0, stamped: false, anim: null
            };
            if (card.querySelector('.seal')) this.applyStamped(token);
            this.tokens.set(id, token);

            if (!reduceMotion) {
                card.addEventListener('pointermove', e => {
                    const r = card.getBoundingClientRect();
                    const pxn = ((e.clientX - r.left) / r.width) * 2 - 1;
                    const pyn = ((e.clientY - r.top) / r.height) * 2 - 1;
                    token.hover = true;
                    // Card tilts in CSS; the token tilts further in 3D for depth
                    card.style.setProperty('--rx', (-pyn * 7).toFixed(2) + 'deg');
                    card.style.setProperty('--ry', (pxn * 9).toFixed(2) + 'deg');
                    card.style.setProperty('--gx', ((pxn + 1) * 50).toFixed(1) + '%');
                    card.style.setProperty('--gy', ((pyn + 1) * 50).toFixed(1) + '%');
                    token.trx = pyn * 0.5;
                    token.try = pxn * 0.62;
                    // Key light follows the pointer, so the specular glint slides
                    token.lx = pxn * 2.6;
                    token.ly = -pyn * 2.6;
                    token.dirty = true;
                });
                card.addEventListener('pointerleave', () => {
                    token.hover = false;
                    card.style.setProperty('--rx', '0deg');
                    card.style.setProperty('--ry', '0deg');
                    token.trx = token.try = 0;
                    token.lx = 1.5;
                    token.ly = 2;
                    token.dirty = true;
                });
            }
        }

        applyStamped(token) {
            token.stamped = true;
            token.faceMat.map = this.faces.stamped.map;
            token.faceMat.emissiveMap = this.faces.stamped.emissive;
            token.faceMat.emissive.setRGB(1, 1, 1);
            token.faceMat.emissiveIntensity = 0.8;
            token.faceMat.needsUpdate = true;
            token.rim.material = this.rimStampedMat;
            token.inner.material = this.rimStampedMat;
            token.dirty = true;
        }

        buildStamp() {
            const stone = stoneTile(256, 41);
            const mat = new THREE.MeshStandardMaterial({ map: texture(stone.color, { srgb: true }), bumpMap: texture(stone.height), bumpScale: 2, roughness: 0.9 });
            const g = new THREE.Group();
            const body = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 0.66, 0.42, 48), mat);
            body.rotation.x = Math.PI / 2;
            g.add(body);
            const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.26, 0.5, 24), mat);
            neck.rotation.x = Math.PI / 2;
            neck.position.z = 0.45;
            g.add(neck);
            const knob = new THREE.Mesh(new THREE.SphereGeometry(0.26, 24, 16), mat);
            knob.position.z = 0.8;
            g.add(knob);
            const band = new THREE.Mesh(new THREE.TorusGeometry(0.64, 0.03, 8, 64), new THREE.MeshStandardMaterial({ color: 0xd4a640, metalness: 1, roughness: 0.3 }));
            band.position.z = 0.1;
            g.add(band);
            g.visible = false;
            this.stampMesh = g;
            this.scene.add(g);
        }

        buildDust() {
            const n = 80;
            const geo = new THREE.BufferGeometry();
            geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3), 3).setUsage(THREE.DynamicDrawUsage));
            geo.setAttribute('aLife', new THREE.BufferAttribute(new Float32Array(n), 1).setUsage(THREE.DynamicDrawUsage));
            this.dustVel = new Float32Array(n * 3);
            this.dust = new THREE.Points(geo, new THREE.ShaderMaterial({
                transparent: true,
                depthWrite: false,
                uniforms: { uSize: { value: 26 } },
                vertexShader: `attribute float aLife; uniform float uSize; varying float vLife;
                    void main() { vLife = aLife; vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_Position = projectionMatrix * mv; gl_PointSize = uSize * (0.4 + aLife) / -mv.z; }`,
                fragmentShader: `varying float vLife;
                    void main() { float d = length(gl_PointCoord - 0.5); float a = smoothstep(0.5, 0.1, d) * vLife * 0.85; gl_FragColor = vec4(vec3(0.79, 0.65, 0.42) * (0.6 + vLife * 0.4), a); }`
            }));
            this.dust.visible = false;
            this.dust.frustumCulled = false;
            this.scene.add(this.dust);
        }

        burst() {
            const pos = this.dust.geometry.attributes.position.array;
            const life = this.dust.geometry.attributes.aLife.array;
            for (let i = 0; i < life.length; i++) {
                const a = Math.random() * TAU;
                const r = TOKEN_R * (0.95 + Math.random() * 0.2);
                pos[i * 3] = Math.cos(a) * r;
                pos[i * 3 + 1] = Math.sin(a) * r;
                pos[i * 3 + 2] = 0.05;
                const sp = 1.1 + Math.random() * 1.4;
                this.dustVel[i * 3] = Math.cos(a) * sp;
                this.dustVel[i * 3 + 1] = Math.sin(a) * sp;
                this.dustVel[i * 3 + 2] = 0.4 + Math.random() * 0.9;
                life[i] = 1;
            }
            this.dust.visible = true;
        }

        stamp(id) {
            const token = this.tokens.get(id);
            if (!token || token.stamped || this.queue.includes(token) || this.active === token) return;
            if (reduceMotion) {
                this.applyStamped(token);
                return;
            }
            this.queue.push(token);
        }

        visible(token) {
            const r = token.slot.getBoundingClientRect();
            return r.width > 0 && r.bottom > 0 && r.top < innerHeight;
        }

        update(dt) {
            // A queued stamp waits until its card is back on screen (flag-solved
            // fires inside the terminal, before the dashboard returns).
            if (!this.active && this.queue.length && this.visible(this.queue[0])) {
                this.active = this.queue.shift();
                this.active.anim = { t: -0.6, hit: false };
                this.active.hover = false;
            }

            this.tokens.forEach(t => {
                const settling = Math.abs(t.rx - t.trx) > 0.002 || Math.abs(t.ry - t.try) > 0.002;
                const spinning = t.parts.prop && (t.hover || t.spin > 0.05);
                const alive = t.hover && (t.parts.needle || t.parts.arm);
                if (!(t.dirty || t.anim || settling || spinning || alive)) return;
                if (!this.visible(t)) return;

                t.rx = damp(t.rx, t.trx, 9, dt);
                t.ry = damp(t.ry, t.try, 9, dt);
                t.group.rotation.set(t.rx, t.ry, 0);
                this.key.position.set(t.lx, t.ly, 3);

                if (t.parts.prop) {
                    t.spin = damp(t.spin, t.hover ? 14 : 0, t.hover ? 1.5 : 0.8, dt);
                    t.parts.prop.rotation.z += t.spin * dt;
                }
                if (t.parts.needle) {
                    // Needle settles toward the pointer like a damped compass
                    const target = t.hover ? Math.atan2(-t.lx, t.ly) : 0;
                    t.parts.needle.rotation.z = damp(t.parts.needle.rotation.z, target + Math.sin(this.world.t * 3) * 0.04, 4, dt);
                }
                if (t.parts.arm) t.parts.arm.rotation.z = Math.sin(this.world.t * 1.2) * (t.hover ? 0.35 : 0.1);

                if (t.anim) this.stepStamp(t, dt);
                this.draw(t);
                t.dirty = false;
            });
        }

        // Stamp timeline (seconds): fall 0→0.38 with a gravity-like ease-in,
        // impact + dust + card shake, hold to 0.52, lift away by 1.15.
        stepStamp(t, dt) {
            const a = t.anim;
            a.t += dt;
            const s = this.stampMesh;
            const contactZ = 0.42;
            if (a.t < 0) {
                s.visible = false;
            } else if (a.t < 0.38) {
                s.visible = true;
                const k = easeInQuad(a.t / 0.38);
                s.position.z = lerp(3.4, contactZ, k);
                s.rotation.z = (1 - k) * 0.6;
            } else if (a.t < 0.52) {
                s.visible = true;
                if (!a.hit) {
                    a.hit = true;
                    this.burst();
                    this.applyStamped(t);
                    t.card.classList.remove('is-impact');
                    void t.card.offsetWidth;
                    t.card.classList.add('is-impact');
                    if (window.JX && JX.sfx.stamp) JX.sfx.stamp();
                }
                // Squash on impact
                t.group.scale.set(1.04, 1.04, 0.82);
                s.position.z = contactZ;
            } else if (a.t < 1.15) {
                const k = easeOutCubic((a.t - 0.52) / 0.63);
                t.group.scale.set(lerp(1.04, 1, k), lerp(1.04, 1, k), lerp(0.82, 1, k));
                s.position.z = lerp(contactZ, 3.6, k);
            } else {
                s.visible = false;
                t.group.scale.set(1, 1, 1);
                t.anim = null;
                this.active = null;
            }

            // Dust: ballistic arcs with drag; gravity pulls "down" into the parchment (−z)
            if (this.dust.visible) {
                const pos = this.dust.geometry.attributes.position.array;
                const life = this.dust.geometry.attributes.aLife.array;
                let alive = false;
                for (let i = 0; i < life.length; i++) {
                    if (life[i] <= 0) continue;
                    alive = true;
                    const k = i * 3;
                    this.dustVel[k] *= 1 - dt * 2.5;
                    this.dustVel[k + 1] *= 1 - dt * 2.5;
                    this.dustVel[k + 2] -= 3 * dt;
                    pos[k] += this.dustVel[k] * dt;
                    pos[k + 1] += this.dustVel[k + 1] * dt;
                    pos[k + 2] = Math.max(0, pos[k + 2] + this.dustVel[k + 2] * dt);
                    life[i] = Math.max(0, life[i] - dt * 1.3);
                }
                this.dust.geometry.attributes.position.needsUpdate = true;
                this.dust.geometry.attributes.aLife.needsUpdate = true;
                if (!alive) this.dust.visible = false;
            }
        }

        draw(t) {
            this.tokens.forEach(o => { o.group.visible = o === t; });
            const fx = this.active === t;
            const stampVis = this.stampMesh.visible, dustVis = this.dust.visible;
            this.stampMesh.visible = fx && stampVis;
            this.dust.visible = fx && dustVis;
            this.renderer.render(this.scene, this.camera);
            this.stampMesh.visible = stampVis;
            this.dust.visible = dustVis;
            t.ctx.clearRect(0, 0, t.canvas.width, t.canvas.height);
            t.ctx.drawImage(this.renderer.domElement, 0, 0, t.canvas.width, t.canvas.height);
            // Drop shadow on the parchment slides opposite the tilt
            t.canvas.style.setProperty('--sx', (-t.ry * 6).toFixed(1) + 'px');
            t.canvas.style.setProperty('--sy', (4 + t.rx * 6).toFixed(1) + 'px');
        }

        dispose() {
            this.renderer.dispose();
        }
    }

    /* ------------------------------------------------------------------ *
     * 11. Field rig: terminal chassis, CRT shader, knob, switch, LEDs (Module C)
     * ------------------------------------------------------------------ */

    const CRT_FRAG = /* glsl */`
        uniform vec2 uRes;
        uniform float uTime, uFlicker, uGlow, uCurse, uActivity;
        varying vec2 vUv;
        float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
        void main() {
            vec2 c = vUv * 2.0 - 1.0;
            // Barrel distortion r' = r(1 + k·r²): what a curved tube does to the
            // raster. We can't warp the live DOM text, so instead the curved
            // coordinates place the rounded glass edge and its glow.
            vec2 cc = c * (1.0 + 0.035 * dot(c, c));
            vec2 edge = 1.0 - abs(cc);
            float aspect = uRes.x / uRes.y;
            float d = min(edge.x * aspect, edge.y);
            float inside = smoothstep(0.0, 0.015, min(edge.x, edge.y));

            // Phosphor bleed hugging the glass rim
            float bleed = exp(-d * 14.0);
            // Scanlines: one dark row every 3 device pixels, kept light so text stays crisp
            float scan = (0.5 + 0.5 * cos(gl_FragCoord.y * 2.0944)) * 0.09;
            // Rolling refresh band drifting down the tube
            float bandY = fract(uTime * 0.07);
            float band = exp(-pow((1.0 - vUv.y - bandY) * 14.0, 2.0));
            // Keystroke flicker: a per-frame random brightness wobble
            float fl = (hash(vec2(floor(uTime * 60.0), 3.1)) - 0.5) * uFlicker;
            // Curse: static snow + a red bleed
            float snow = hash(gl_FragCoord.xy + fract(uTime) * 113.0) * uCurse;

            vec3 glow = vec3(0.0, 1.0, 0.42) * (bleed * 0.42 + band * 0.05 + max(fl, 0.0) * 0.12 + uActivity * bleed * 0.25) * uGlow;
            glow = mix(glow, vec3(1.0, 0.16, 0.1) * (bleed * 0.6 + snow * 0.22), uCurse);
            float vign = smoothstep(0.55, 1.35, length(c)) * 0.35;
            float dark = scan * uGlow + (1.0 - inside) + max(-fl, 0.0) * 0.18 + vign + snow * 0.1;
            // Premultiplied output: rgb adds light, alpha darkens what's beneath
            gl_FragColor = vec4(glow * inside, clamp(dark, 0.0, 0.92));
        }`;

    class FieldRig {
        constructor(world, bezel, glass, webgl) {
            this.world = world;
            this.bezel = bezel;
            this.glass = glass;
            this.flicker = 0;
            this.activity = 0;
            this.curse = document.body.classList.contains('is-cursed') ? 1 : 0;
            const store = window.JX ? JX.store : { get: () => null, set: () => {} };
            this.store = store;
            this.on = store.get('jx-crt') !== 'off';
            this.glow = parseFloat(store.get('jx-crt-glow') || '60');
            this.hasCurseLed = !!document.getElementById('curse-banner');

            bezel.classList.add('field-rig');
            this.buildPanel(webgl);
            if (webgl) this.buildShader();
            this.applyPower();
            if (this.curse) this.onCurse(true);

            // Keystroke flicker: xterm's hidden textarea bubbles keydown through the glass
            this.onKey = () => {
                if (!reduceMotion) this.flicker = 1;
            };
            glass.addEventListener('keydown', this.onKey, true);

            // The panel takes height from the bezel; let xterm refit.
            requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
        }

        buildPanel(webgl) {
            const p = document.createElement('div');
            p.className = 'rig-panel';
            p.innerHTML = `
                <span class="rig-led" data-led="link" data-state="on" title="Field link"><i aria-hidden="true"></i><span>Link</span></span>
                ${this.hasCurseLed ? '<span class="rig-led rig-led--curse" data-led="curse" data-state="off" title="Curse alarm"><i aria-hidden="true"></i><span>Curse</span></span>' : ''}
                <span class="rig-grille" aria-hidden="true"></span>
                ${webgl ? `<span class="rig-knob-wrap"><span class="rig-knob" role="slider" tabindex="0" aria-label="Screen glow" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(this.glow)}"><span class="rig-knob__cap" aria-hidden="true"></span></span><span class="rig-label" aria-hidden="true">Glow</span></span>` : ''}
                <button class="rig-switch" type="button" role="switch" aria-checked="${this.on}" aria-label="Screen effects">
                    <span class="rig-switch__plate" aria-hidden="true"><span class="rig-switch__lever"></span></span>
                    <span class="rig-label" aria-hidden="true">Screen</span>
                </button>`;
            this.glass.insertAdjacentElement('afterend', p);
            this.panel = p;
            this.ledLink = p.querySelector('[data-led="link"]');
            this.ledCurse = p.querySelector('[data-led="curse"]');
            this.knob = p.querySelector('.rig-knob');
            this.switchEl = p.querySelector('.rig-switch');

            this.switchEl.addEventListener('click', () => {
                this.on = !this.on;
                this.store.set('jx-crt', this.on ? 'on' : 'off');
                if (window.JX) JX.sfx.chirp(this.on ? 520 : 300, 0.05, 'square', 0.04);
                this.applyPower();
            });

            if (this.knob) {
                this.setGlow(this.glow);
                let drag = null;
                this.knob.addEventListener('pointerdown', e => {
                    this.knob.setPointerCapture(e.pointerId);
                    drag = { x: e.clientX, y: e.clientY, v: this.glow };
                });
                this.knob.addEventListener('pointermove', e => {
                    if (!drag) return;
                    // Drag up or right to turn clockwise
                    this.setGlow(drag.v + (drag.y - e.clientY) * 0.7 + (e.clientX - drag.x) * 0.7);
                });
                const end = () => { drag = null; };
                this.knob.addEventListener('pointerup', end);
                this.knob.addEventListener('pointercancel', end);
                this.knob.addEventListener('wheel', e => {
                    e.preventDefault();
                    this.setGlow(this.glow - Math.sign(e.deltaY) * 5);
                }, { passive: false });
                this.knob.addEventListener('keydown', e => {
                    const step = { ArrowUp: 5, ArrowRight: 5, ArrowDown: -5, ArrowLeft: -5, PageUp: 20, PageDown: -20 }[e.key];
                    if (step) {
                        e.preventDefault();
                        this.setGlow(this.glow + step);
                    } else if (e.key === 'Home' || e.key === 'End') {
                        e.preventDefault();
                        this.setGlow(e.key === 'Home' ? 0 : 100);
                    }
                });
            }
        }

        setGlow(v) {
            this.glow = clamp(Math.round(v), 0, 100);
            // 0..100 maps onto a 270° knob sweep, −135° to +135°
            this.knob.style.setProperty('--angle', (-135 + this.glow * 2.7) + 'deg');
            this.knob.setAttribute('aria-valuenow', String(this.glow));
            this.store.set('jx-crt-glow', String(this.glow));
        }

        applyPower() {
            this.switchEl.setAttribute('aria-checked', String(this.on));
            this.glass.classList.toggle('crt-off', !this.on);
            if (this.canvas) this.canvas.hidden = !this.on;
        }

        buildShader() {
            const canvas = document.createElement('canvas');
            canvas.className = 'crt-shader';
            canvas.setAttribute('aria-hidden', 'true');
            this.glass.appendChild(canvas);
            try {
                this.renderer = new THREE.WebGLRenderer({ canvas, alpha: true, premultipliedAlpha: true, antialias: false });
            } catch (e) {
                canvas.remove();
                return;
            }
            this.canvas = canvas;
            this.glass.classList.add('has-crt-shader');
            this.renderer.setClearColor(0x000000, 0);
            this.uniforms = {
                uRes: { value: new THREE.Vector2(1, 1) },
                uTime: { value: 0 },
                uFlicker: { value: 0 },
                uGlow: { value: 0.6 },
                uCurse: { value: this.curse },
                uActivity: { value: 0 }
            };
            this.scene = new THREE.Scene();
            const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({
                uniforms: this.uniforms,
                vertexShader: FULLSCREEN_VERT,
                fragmentShader: CRT_FRAG,
                transparent: true,
                blending: THREE.NoBlending,
                depthTest: false
            }));
            quad.frustumCulled = false;
            this.scene.add(quad);
            this.cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
            this.ro = new ResizeObserver(() => this.resize());
            this.ro.observe(this.glass);
            this.resize();
        }

        resize() {
            if (!this.renderer) return;
            const r = this.glass.getBoundingClientRect();
            if (!r.width || !r.height) return;
            const dpr = Math.min(window.devicePixelRatio || 1, 2);
            this.renderer.setPixelRatio(dpr);
            this.renderer.setSize(r.width, r.height, false);
            this.uniforms.uRes.value.set(r.width * dpr, r.height * dpr);
        }

        signal(name, value) {
            if (name === 'link') this.setLed(this.ledLink, value ? 'on' : 'off');
            else if (name === 'telemetry') this.activity = 1;
            else if (name === 'key') this.onKey();
        }

        onCurse(cursed) {
            this.curse = cursed ? 1 : 0;
            if (this.ledCurse) this.setLed(this.ledCurse, cursed ? 'alarm' : 'off');
        }

        setLed(el, state) {
            if (el) el.dataset.state = state;
        }

        update(dt, t) {
            this.flicker *= Math.exp(-dt * 9);
            this.activity *= Math.exp(-dt * 5);
            // Telemetry blink: the link LED flares on traffic
            if (this.ledLink && this.ledLink.dataset.state !== 'off') {
                this.ledLink.dataset.state = this.activity > 0.25 ? 'busy' : 'on';
            }
            if (!this.renderer || !this.on) return;
            const r = this.glass.getBoundingClientRect();
            if (!r.width || r.bottom < 0 || r.top > innerHeight) return;
            const u = this.uniforms;
            if (Math.abs(u.uRes.value.x - r.width * Math.min(window.devicePixelRatio || 1, 2)) > 2) this.resize();
            u.uTime.value = reduceMotion ? 0 : t;
            u.uFlicker.value = this.flicker;
            u.uActivity.value = this.activity;
            u.uGlow.value = this.glow / 100;
            u.uCurse.value = damp(u.uCurse.value, this.curse, 4, dt);
            this.renderer.render(this.scene, this.cam);
        }

        dispose() {
            this.glass.removeEventListener('keydown', this.onKey, true);
            if (this.ro) this.ro.disconnect();
            if (this.renderer) this.renderer.dispose();
        }
    }

    /* ------------------------------------------------------------------ *
     * 12. Boot
     * ------------------------------------------------------------------ */

    function boot() {
        const world = document.body.dataset.world;
        if (!world || window.JX3D) return;
        window.Jumanji3DWorld = Jumanji3DWorld;
        window.JX3D = new Jumanji3DWorld({ world });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
})();
