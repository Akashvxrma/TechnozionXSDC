/* ==========================================================================
   JUMANJI LOGIN — procedural moonlit temple clearing
   Three.js r149 (global build). No models and no image files: every mesh and
   texture is generated here, so nothing can 404.

   The UI bridge (focus dolly, submit surge, ripple, password reveal, field-note
   dismiss) runs with or without WebGL. Without it, body gets .no-webgl and the
   CSS gradient backdrop takes over.

   Exposes window.JumanjiLogin = { setFocus(bool), surge() } once running.
   ========================================================================== */
(function () {
    'use strict';

    const doc = document;
    const body = doc.body;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Called at the bottom, once every const below is initialised
    function boot() {
        const ui = initUI();

        const canvas = doc.getElementById('jungle');
        if (!canvas || !window.THREE || !webglAvailable()) {
            body.classList.add('no-webgl');
            return;
        }

        let engine;
        try {
            engine = createEngine(canvas);
        } catch (err) {
            console.warn('[jumanji-login] WebGL scene failed, using CSS backdrop.', err);
            body.classList.add('no-webgl');
            return;
        }
        ui.attach(engine);
        window.JumanjiLogin = engine;
    }

    /* ======================================================================
       UI bridge
       ====================================================================== */

    function initUI() {
        let engine = null;
        const form = doc.querySelector('[data-login-form]');
        const google = doc.querySelector('[data-google]');

        // Camera glides toward the altar while any credential field has focus
        if (form) {
            form.addEventListener('focusin', () => engine && engine.setFocus(true));
            form.addEventListener('focusout', () => {
                setTimeout(() => {
                    if (engine && !form.contains(doc.activeElement)) engine.setFocus(false);
                }, 0);
            });

            form.addEventListener('submit', (e) => {
                if (form.dataset.sent) { e.preventDefault(); return; }
                form.dataset.sent = '1';
                const btn = form.querySelector('[type="submit"]');
                if (btn) {
                    btn.setAttribute('aria-busy', 'true');
                    const label = btn.querySelector('[data-label]');
                    if (label) label.textContent = 'Entering the jungle…';
                }
                if (!engine || reduceMotion) return; // submit natively, no theatre
                e.preventDefault();
                engine.surge();
                setTimeout(() => form.submit(), 900);
            });
        }

        // Google: same surge, then follow the link (plain left clicks only)
        if (google) {
            google.addEventListener('click', (e) => {
                if (!engine || reduceMotion || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
                e.preventDefault();
                engine.surge();
                setTimeout(() => { window.location.href = google.href; }, 650);
            });
        }

        // Back/forward cache restores the page mid-submit: reset it
        window.addEventListener('pageshow', (e) => {
            if (!e.persisted || !form) return;
            delete form.dataset.sent;
            const btn = form.querySelector('[type="submit"]');
            if (btn) {
                btn.removeAttribute('aria-busy');
                const label = btn.querySelector('[data-label]');
                if (label) label.textContent = label.dataset.label;
            }
        });

        // Ripple from the exact press point
        doc.querySelectorAll('[data-ripple]').forEach((el) => {
            el.addEventListener('pointerdown', (e) => {
                if (reduceMotion) return;
                const r = el.getBoundingClientRect();
                const size = Math.max(r.width, r.height) * 2.2;
                const dot = doc.createElement('span');
                dot.className = 'ripple';
                dot.style.width = dot.style.height = size + 'px';
                dot.style.left = (e.clientX - r.left - size / 2) + 'px';
                dot.style.top = (e.clientY - r.top - size / 2) + 'px';
                el.appendChild(dot);
                dot.addEventListener('animationend', () => dot.remove());
            });
        });

        // Password reveal
        doc.querySelectorAll('[data-reveal]').forEach((btn) => {
            const input = doc.getElementById(btn.getAttribute('aria-controls'));
            if (!input) return;
            btn.addEventListener('click', () => {
                const show = input.type === 'password';
                input.type = show ? 'text' : 'password';
                btn.setAttribute('aria-pressed', String(show));
                btn.textContent = show ? 'Hide' : 'Show';
                input.focus();
            });
        });

        // Field note dismiss
        doc.querySelectorAll('[data-dismiss]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const note = btn.closest('.field-note');
                if (!note) return;
                if (reduceMotion) { note.remove(); return; }
                note.classList.add('is-leaving');
                note.addEventListener('animationend', () => note.remove(), { once: true });
            });
        });

        return { attach(e) { engine = e; } };
    }

    function webglAvailable() {
        try {
            const c = doc.createElement('canvas');
            return !!(window.WebGLRenderingContext && (c.getContext('webgl2') || c.getContext('webgl')));
        } catch (e) {
            return false;
        }
    }

    /* ======================================================================
       Procedural noise (tileable value noise over a lookup table)
       ====================================================================== */

    const RND = (() => {
        let s = 0x9e3779b9;
        const out = new Float32Array(256 * 256);
        for (let i = 0; i < out.length; i++) {
            s ^= s << 13; s ^= s >>> 17; s ^= s << 5;
            out[i] = (s >>> 0) / 4294967296;
        }
        return out;
    })();

    function lattice(ix, iy, seed) {
        return RND[(((iy + seed * 31) & 255) << 8) | ((ix + seed * 17) & 255)];
    }

    function vnoise(x, y, period, seed) {
        const xi = Math.floor(x), yi = Math.floor(y);
        const xf = x - xi, yf = y - yi;
        const x0 = ((xi % period) + period) % period, y0 = ((yi % period) + period) % period;
        const x1 = (x0 + 1) % period, y1 = (y0 + 1) % period;
        const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
        const a = lattice(x0, y0, seed), b = lattice(x1, y0, seed);
        const c = lattice(x0, y1, seed), d = lattice(x1, y1, seed);
        return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
    }

    // x, y in [0, period): tiles seamlessly
    function fbm(x, y, period, octaves, seed) {
        let sum = 0, amp = 0.5, norm = 0;
        for (let i = 0; i < octaves; i++) {
            sum += amp * vnoise(x, y, period, seed + i * 7);
            norm += amp;
            x *= 2; y *= 2; period *= 2; amp *= 0.5;
        }
        return sum / norm;
    }

    function smoothstep(a, b, x) {
        const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
        return t * t * (3 - 2 * t);
    }

    function makeCanvas(w, h) {
        const c = doc.createElement('canvas');
        c.width = w; c.height = h;
        return c;
    }

    // Per-pixel painter: fn(u, v, out) writes 0..255 RGB(A) into out
    function paint(w, h, fn, alpha) {
        const c = makeCanvas(w, h);
        const ctx = c.getContext('2d');
        const img = ctx.createImageData(w, h);
        const d = img.data;
        const out = [0, 0, 0, 255];
        let i = 0;
        for (let y = 0; y < h; y++) {
            for (let x = 0; x < w; x++) {
                out[3] = 255;
                fn(x / w, y / h, out);
                d[i++] = out[0]; d[i++] = out[1]; d[i++] = out[2]; d[i++] = alpha ? out[3] : 255;
            }
        }
        ctx.putImageData(img, 0, 0);
        return c;
    }

    function seeded(seed) {
        let s = seed >>> 0 || 1;
        return () => {
            s ^= s << 13; s ^= s >>> 17; s ^= s << 5;
            return (s >>> 0) / 4294967296;
        };
    }

    /* ======================================================================
       Engine
       ====================================================================== */

    function createEngine(canvas) {
        const T = THREE;
        const V3 = T.Vector3;
        const small = Math.min(window.innerWidth, window.innerHeight) < 700;
        const TEX = small ? 256 : 512;
        const rand = seeded(1995);

        /* ---------- Renderer ---------- */

        const renderer = new T.WebGLRenderer({ canvas, antialias: !small, powerPreference: 'high-performance' });
        let dpr = Math.min(window.devicePixelRatio || 1, 2);
        renderer.setPixelRatio(dpr);
        renderer.outputEncoding = T.sRGBEncoding;
        renderer.toneMapping = T.ACESFilmicToneMapping;
        renderer.toneMappingExposure = reduceMotion ? 1.3 : 0.05;
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = T.PCFSoftShadowMap;
        const maxAniso = Math.min(8, renderer.capabilities.getMaxAnisotropy());

        const scene = new T.Scene();
        const FOG = new T.Color(0x081512);
        scene.background = FOG;
        scene.fog = new T.FogExp2(FOG, 0.05);

        const camera = new T.PerspectiveCamera(36, 1, 0.1, 90);

        const uTime = { value: 0 };
        const shared = { surge: 0, pulse: 0 };

        /* ---------- Environment map: moonlit sky for brass & glass ---------- */

        const pmrem = new T.PMREMGenerator(renderer);
        const envScene = new T.Scene();
        envScene.add(new T.Mesh(
            new T.SphereGeometry(10, 32, 16),
            new T.ShaderMaterial({
                side: T.BackSide,
                vertexShader: `
                    varying vec3 vP;
                    void main() { vP = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
                fragmentShader: `
                    varying vec3 vP;
                    void main() {
                        float h = vP.y;
                        vec3 c = mix(vec3(0.01, 0.03, 0.02), vec3(0.16, 0.22, 0.32), smoothstep(-0.2, 0.9, h));
                        c += pow(max(dot(vP, normalize(vec3(-0.45, 0.7, -0.55))), 0.0), 40.0) * vec3(1.4, 1.5, 1.8);
                        c += vec3(0.0, 0.5, 0.22) * pow(max(dot(vP, vec3(0.0, -0.2, 1.0)), 0.0), 6.0) * 0.6;
                        gl_FragColor = vec4(c, 1.0);
                    }`
            })
        ));
        scene.environment = pmrem.fromScene(envScene, 0.04).texture;
        pmrem.dispose();

        /* ---------- Textures ---------- */

        function tex(canvasEl, { color = true, repeat = 1 } = {}) {
            const t = new T.CanvasTexture(canvasEl);
            if (color) t.encoding = T.sRGBEncoding;
            t.anisotropy = maxAniso;
            if (repeat !== 1) {
                t.wrapS = t.wrapT = T.RepeatWrapping;
                t.repeat.set(repeat, repeat);
            }
            return t;
        }

        // Weathered temple stone with lichen in the low spots
        const stoneCanvas = paint(TEX, TEX, (u, v, o) => {
            const n = fbm(u * 8, v * 8, 8, 4, 3);
            const fine = fbm(u * 32, v * 32, 32, 2, 9);
            const crack = 1 - smoothstep(0, 0.03, Math.abs(fbm(u * 4, v * 4, 4, 4, 21) - 0.5));
            const moss = smoothstep(0.58, 0.78, fbm(u * 5, v * 5, 5, 3, 40));
            const g = 0.3 + n * 0.5 + (fine - 0.5) * 0.18 - crack * 0.25;
            o[0] = 255 * g * (0.46 - moss * 0.22);
            o[1] = 255 * g * (0.5 + moss * 0.1);
            o[2] = 255 * g * (0.46 - moss * 0.2);
        });
        const stoneMap = tex(stoneCanvas);
        const stoneBump = tex(stoneCanvas, { color: false });

        // Forest floor: dark loam, leaf litter and moss
        const groundCanvas = paint(TEX, TEX, (u, v, o) => {
            const n = fbm(u * 6, v * 6, 6, 4, 61);
            const litter = fbm(u * 40, v * 40, 40, 2, 70);
            const moss = smoothstep(0.42, 0.7, fbm(u * 3, v * 3, 3, 4, 80));
            const g = 0.25 + n * 0.45 + (litter - 0.5) * 0.3;
            o[0] = 255 * g * (0.28 - moss * 0.12);
            o[1] = 255 * g * (0.26 + moss * 0.16);
            o[2] = 255 * g * (0.18 - moss * 0.04);
        });
        const groundMap = tex(groundCanvas, { repeat: 16 });
        const groundBump = tex(groundCanvas, { color: false, repeat: 16 });

        // Bark: vertical fibres
        const barkCanvas = paint(TEX / 2, TEX, (u, v, o) => {
            const n = fbm(u * 24, v * 3, 24, 3, 90);
            const ridge = Math.abs(fbm(u * 12, v * 1.5, 12, 3, 95) - 0.5) * 2;
            const g = 0.18 + n * 0.3 + ridge * 0.25;
            o[0] = 255 * g * 0.42; o[1] = 255 * g * 0.38; o[2] = 255 * g * 0.3;
        });
        const barkMap = tex(barkCanvas);
        barkMap.wrapS = barkMap.wrapT = T.RepeatWrapping;
        barkMap.repeat.set(2, 3);

        // Mahogany grain, shared by the lid base and the side panels
        function woodPixel(u, v, o, aspect) {
            const warp = fbm(u * 2, v * 2, 2, 3, 11) * 7;
            const rings = 0.5 + 0.5 * Math.sin((v * 38 * aspect + warp) * Math.PI);
            const streak = fbm(u * 64, (v * 4) % 4, 64, 2, 15);
            const g = 0.55 + rings * 0.3 + (streak - 0.5) * 0.35;
            o[0] = 255 * Math.min(1, 0.42 * g + 0.03);
            o[1] = 255 * 0.2 * g;
            o[2] = 255 * 0.1 * g;
        }

        // Brass with verdigris
        const brassCanvas = paint(128, 128, (u, v, o) => {
            const n = fbm(u * 6, v * 6, 6, 4, 120);
            const verd = smoothstep(0.6, 0.75, fbm(u * 4, v * 4, 4, 3, 130));
            const g = 0.75 + n * 0.35;
            o[0] = 255 * Math.min(1, g * (0.78 - verd * 0.5));
            o[1] = 255 * Math.min(1, g * (0.58 - verd * 0.08));
            o[2] = 255 * Math.min(1, g * (0.27 + verd * 0.18));
        });
        const brassMap = tex(brassCanvas);
        const brassRough = tex(paint(128, 128, (u, v, o) => {
            const r = 90 + fbm(u * 8, v * 8, 8, 3, 140) * 140;
            o[0] = o[1] = o[2] = r;
        }), { color: false });

        // Soft round glow for halos and fake bloom
        const glowCanvas = makeCanvas(128, 128);
        (() => {
            const g = glowCanvas.getContext('2d');
            const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
            grad.addColorStop(0, 'rgba(255,255,255,1)');
            grad.addColorStop(0.2, 'rgba(255,255,255,0.55)');
            grad.addColorStop(0.5, 'rgba(255,255,255,0.12)');
            grad.addColorStop(1, 'rgba(255,255,255,0)');
            g.fillStyle = grad;
            g.fillRect(0, 0, 128, 128);
        })();
        const glowMap = tex(glowCanvas);

        /* ---------- The lid: carved relief, redrawn once Cinzel loads ---------- */

        const LW = small ? 768 : 1024, LH = Math.round(LW * 1.46 / 2.46);
        const k = LW / 1024; // carvings are authored at 1024 wide
        const lidWood = paint(LW, LH, (u, v, o) => woodPixel(u, v, o, 0.6));
        const lidCanvas = makeCanvas(LW, LH);
        const lidBumpCanvas = makeCanvas(LW, LH);

        function drawLid() {
            [[lidCanvas, false], [lidBumpCanvas, true]].forEach(([c, bump]) => {
                const ctx = c.getContext('2d');
                ctx.setTransform(1, 0, 0, 1, 0, 0);
                if (bump) {
                    ctx.fillStyle = '#9a9a9a';
                    ctx.fillRect(0, 0, LW, LH);
                    ctx.globalAlpha = 0.35;
                    ctx.drawImage(lidWood, 0, 0);
                    ctx.globalAlpha = 1;
                } else {
                    ctx.drawImage(lidWood, 0, 0);
                }
                ctx.scale(k, k);
                carveLid(ctx, bump);
            });
        }

        // Recessed groove: a lit lower lip under a dark cut
        function groove(ctx, bump, w, path, fill) {
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
            ctx.lineWidth = w;
            if (!bump) {
                ctx.save();
                ctx.translate(1.6, 2.2);
                path();
                ctx.strokeStyle = ctx.fillStyle = 'rgba(255, 190, 120, 0.16)';
                fill ? ctx.fill() : ctx.stroke();
                ctx.restore();
            }
            path();
            ctx.strokeStyle = ctx.fillStyle = bump ? '#1c1c1c' : 'rgba(14, 5, 2, 0.88)';
            fill ? ctx.fill() : ctx.stroke();
        }

        function carveLid(ctx, bump) {
            const W = 1024, H = 608, cx = W / 2, cy = H / 2;

            // Double frame
            groove(ctx, bump, 6, () => { ctx.beginPath(); ctx.rect(18, 18, W - 36, H - 36); });
            groove(ctx, bump, 3, () => { ctx.beginPath(); ctx.rect(44, 44, W - 88, H - 88); });

            // Teeth between the frames
            groove(ctx, bump, 2.5, () => {
                ctx.beginPath();
                for (let x = 30, up = true; x <= W - 30; x += 14, up = !up) {
                    ctx.lineTo(x, up ? 24 : 38);
                }
                ctx.moveTo(30, H - 24);
                for (let x = 30, up = true; x <= W - 30; x += 14, up = !up) {
                    ctx.lineTo(x, up ? H - 24 : H - 38);
                }
                for (let y = 44, left = true; y <= H - 44; y += 14, left = !left) {
                    ctx.moveTo(left ? 24 : 38, y);
                    ctx.lineTo(left ? 38 : 24, y + 14);
                    ctx.moveTo(W - (left ? 24 : 38), y);
                    ctx.lineTo(W - (left ? 38 : 24), y + 14);
                }
            });

            // Corner spirals
            [[96, 96], [W - 96, 96], [96, H - 96], [W - 96, H - 96]].forEach(([sx, sy], i) => {
                const dir = i % 2 ? -1 : 1;
                groove(ctx, bump, 4.5, () => {
                    ctx.beginPath();
                    for (let a = 0; a <= Math.PI * 4.6; a += 0.08) {
                        const r = 3 + a * 2.7;
                        ctx.lineTo(sx + Math.cos(a * dir) * r, sy + Math.sin(a * dir) * r);
                    }
                });
            });

            // Vines from the spirals toward the medallion, with leaves
            [-1, 1].forEach((side) => {
                const x0 = side < 0 ? 150 : W - 150, x1 = side < 0 ? 330 : W - 330;
                groove(ctx, bump, 3.5, () => {
                    ctx.beginPath();
                    for (let t = 0; t <= 1; t += 0.02) {
                        const x = x0 + (x1 - x0) * t;
                        ctx.lineTo(x, cy + Math.sin(t * Math.PI * 3) * 34);
                    }
                });
                for (let t = 0.08; t < 1; t += 0.14) {
                    const x = x0 + (x1 - x0) * t;
                    const y = cy + Math.sin(t * Math.PI * 3) * 34;
                    const flip = Math.round(t / 0.14) % 2 ? 1 : -1;
                    groove(ctx, bump, 1, () => {
                        ctx.beginPath();
                        ctx.ellipse(x + 6 * side, y + flip * 16, 16, 6, flip * 0.9 * side, 0, Math.PI * 2);
                    }, true);
                }
            });

            // Medallion around the crystal: rings and a carved sunburst
            groove(ctx, bump, 5, () => { ctx.beginPath(); ctx.arc(cx, cy, 128, 0, Math.PI * 2); });
            groove(ctx, bump, 3, () => { ctx.beginPath(); ctx.arc(cx, cy, 150, 0, Math.PI * 2); });
            groove(ctx, bump, 3, () => {
                ctx.beginPath();
                for (let i = 0; i < 48; i++) {
                    const a = (i / 48) * Math.PI * 2;
                    const r1 = 158, r2 = i % 2 ? 176 : 196;
                    ctx.moveTo(cx + Math.cos(a) * r1, cy + Math.sin(a) * r1);
                    ctx.lineTo(cx + Math.cos(a) * r2, cy + Math.sin(a) * r2);
                }
            });

            // Lettering
            const carvedText = (txt, size, y, spacing) => {
                ctx.font = `900 ${size}px Cinzel, "Trajan Pro", Georgia, serif`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                if ('letterSpacing' in ctx) ctx.letterSpacing = spacing + 'px';
                if (!bump) {
                    ctx.fillStyle = 'rgba(255, 196, 130, 0.2)';
                    ctx.fillText(txt, cx + 2, y + 3);
                }
                ctx.fillStyle = bump ? '#161616' : 'rgba(16, 6, 2, 0.92)';
                ctx.fillText(txt, cx, y);
                if ('letterSpacing' in ctx) ctx.letterSpacing = '0px';
            };
            carvedText('JUMANJI', 78, 100, 14);
            carvedText('TECHNOZION X SDC', 26, H - 92, 8);

            // Diamond row under the medallion
            for (let x = 300; x <= W - 300; x += 28) {
                groove(ctx, bump, 1, () => {
                    ctx.beginPath();
                    ctx.moveTo(x, H - 132); ctx.lineTo(x + 8, H - 124);
                    ctx.lineTo(x, H - 116); ctx.lineTo(x - 8, H - 124);
                    ctx.closePath();
                }, true);
            }
        }

        drawLid();
        const lidMap = tex(lidCanvas);
        const lidBump = tex(lidBumpCanvas, { color: false });
        if (doc.fonts && doc.fonts.load) {
            doc.fonts.load('900 78px Cinzel').then(() => {
                drawLid();
                lidMap.needsUpdate = true;
                lidBump.needsUpdate = true;
            }).catch(() => { /* fallback serif already drawn */ });
        }

        // Side panels: grain with a carved zigzag band
        const sideCanvas = paint(512, 96, (u, v, o) => woodPixel(u, v, o, 0.2));
        const sideBumpCanvas = makeCanvas(512, 96);
        [[sideCanvas, false], [sideBumpCanvas, true]].forEach(([c, bump]) => {
            const ctx = c.getContext('2d');
            if (bump) { ctx.fillStyle = '#9a9a9a'; ctx.fillRect(0, 0, 512, 96); }
            groove(ctx, bump, 3, () => { ctx.beginPath(); ctx.rect(10, 12, 492, 72); });
            groove(ctx, bump, 3, () => {
                ctx.beginPath();
                for (let x = 18, up = true; x <= 494; x += 16, up = !up) ctx.lineTo(x, up ? 30 : 66);
            });
        });
        const sideMap = tex(sideCanvas);
        const sideBump = tex(sideBumpCanvas, { color: false });

        // Rune glyphs for the altar's middle tier (emissive)
        const runeCanvas = makeCanvas(512, 128);
        (() => {
            const g = runeCanvas.getContext('2d');
            const r = seeded(77);
            g.fillStyle = '#000';
            g.fillRect(0, 0, 512, 128);
            g.strokeStyle = '#fff';
            g.lineWidth = 3;
            g.lineCap = 'round';
            for (let i = 0; i < 12; i++) {
                const x = 22 + i * 41, y = 64;
                g.beginPath();
                const kind = Math.floor(r() * 5);
                if (kind === 0) { g.arc(x, y, 10, 0, Math.PI * 2); g.moveTo(x, y - 18); g.lineTo(x, y + 18); }
                if (kind === 1) { g.moveTo(x - 12, y + 14); g.lineTo(x, y - 16); g.lineTo(x + 12, y + 14); g.closePath(); }
                if (kind === 2) { for (let a = 0; a < 9; a += 0.2) g.lineTo(x + Math.cos(a) * a * 1.5, y + Math.sin(a) * a * 1.5); }
                if (kind === 3) { g.moveTo(x - 12, y - 14); g.lineTo(x + 12, y + 14); g.moveTo(x + 12, y - 14); g.lineTo(x - 12, y + 14); g.moveTo(x - 14, y); g.lineTo(x + 14, y); }
                if (kind === 4) { g.rect(x - 10, y - 14, 20, 28); g.moveTo(x - 10, y); g.lineTo(x + 10, y); }
                g.stroke();
            }
        })();
        const runeMap = tex(runeCanvas);

        // Fern frond with alpha
        const fernCanvas = makeCanvas(128, 256);
        (() => {
            const g = fernCanvas.getContext('2d');
            const pt = (t) => [64 + Math.sin(t * 2.2) * 14 * t, 252 - t * 244];
            g.strokeStyle = '#2e4a22';
            g.lineWidth = 3;
            g.beginPath();
            for (let t = 0; t <= 1; t += 0.02) g.lineTo(...pt(t));
            g.stroke();
            for (let t = 0.06; t < 0.97; t += 0.035) {
                const [x, y] = pt(t);
                const len = 52 * Math.pow(1 - t, 0.6) * Math.min(1, t * 5);
                const shade = 40 + Math.round(t * 40);
                g.fillStyle = `rgb(${shade - 12}, ${shade + 50}, ${shade - 8})`;
                [-1, 1].forEach((s) => {
                    g.beginPath();
                    g.ellipse(x + s * len * 0.5, y - len * 0.12, len * 0.5, 4.5, s * -0.25, 0, Math.PI * 2);
                    g.fill();
                });
            }
        })();
        const fernMap = tex(fernCanvas);

        /* ---------- Materials ---------- */

        const M = {
            stone: new T.MeshStandardMaterial({ map: stoneMap, bumpMap: stoneBump, bumpScale: 0.05, roughness: 0.94, envMapIntensity: 0.25 }),
            rune: new T.MeshStandardMaterial({
                map: stoneMap, bumpMap: stoneBump, bumpScale: 0.05, roughness: 0.94, envMapIntensity: 0.25,
                emissive: new T.Color(0x00ff66), emissiveMap: runeMap, emissiveIntensity: 0.2
            }),
            ground: new T.MeshStandardMaterial({ map: groundMap, bumpMap: groundBump, bumpScale: 0.06, roughness: 1, envMapIntensity: 0.15 }),
            bark: new T.MeshStandardMaterial({ map: barkMap, color: 0x8a8070, roughness: 1, envMapIntensity: 0.1 }),
            leaf: new T.MeshStandardMaterial({ color: 0x0d2316, roughness: 0.9, flatShading: true, envMapIntensity: 0.2 }),
            moss: new T.MeshStandardMaterial({ color: 0x2c4a22, roughness: 1, flatShading: true, envMapIntensity: 0.2 }),
            vine: new T.MeshStandardMaterial({ color: 0x1d3318, roughness: 0.9, envMapIntensity: 0.2 }),
            fern: new T.MeshStandardMaterial({ map: fernMap, alphaTest: 0.45, side: T.DoubleSide, roughness: 0.85, envMapIntensity: 0.3 }),
            lid: new T.MeshStandardMaterial({ map: lidMap, bumpMap: lidBump, bumpScale: 0.025, roughness: 0.6, envMapIntensity: 0.5 }),
            side: new T.MeshStandardMaterial({ map: sideMap, bumpMap: sideBump, bumpScale: 0.02, roughness: 0.62, envMapIntensity: 0.5 }),
            woodDark: new T.MeshStandardMaterial({ color: 0x1a0b05, roughness: 0.7 }),
            brass: new T.MeshStandardMaterial({ map: brassMap, roughnessMap: brassRough, metalness: 0.92, roughness: 1, envMapIntensity: 1.2 }),
            dome: new T.MeshPhysicalMaterial({
                color: 0x0a6a36, emissive: new T.Color(0x00ff6a), emissiveIntensity: 0.5,
                roughness: 0.04, metalness: 0, clearcoat: 1, clearcoatRoughness: 0.04,
                transparent: true, opacity: 0.88, envMapIntensity: 1.8
            })
        };

        /* ---------- Helpers ---------- */

        // Position-keyed displacement keeps shared edges closed on non-indexed faces
        function roughen(geo, amt, freq) {
            const p = geo.attributes.position;
            for (let i = 0; i < p.count; i++) {
                const x = p.getX(i), y = p.getY(i), z = p.getZ(i);
                const n = Math.sin(x * freq + 1.3) * Math.sin(y * freq * 1.7 + 0.4) * Math.sin(z * freq * 1.3 + 2.1)
                    + 0.5 * Math.sin(x * freq * 2.9 + z * freq * 2.3 + y * 3.1);
                p.setXYZ(i, x + n * amt, y + n * amt * 0.6, z + n * amt);
            }
            geo.computeVertexNormals();
            return geo;
        }

        function mesh(geo, mat, x, y, z, shadow = true) {
            const m = new T.Mesh(geo, mat);
            m.position.set(x, y, z);
            m.castShadow = shadow;
            m.receiveShadow = true;
            scene.add(m);
            return m;
        }

        const dummy = new T.Object3D();
        function instanced(geo, mat, items, place, shadow = false) {
            const im = new T.InstancedMesh(geo, mat, items);
            for (let i = 0; i < items; i++) {
                dummy.position.set(0, 0, 0);
                dummy.rotation.set(0, 0, 0);
                dummy.scale.set(1, 1, 1);
                place(dummy, i);
                dummy.updateMatrix();
                im.setMatrixAt(i, dummy.matrix);
            }
            im.castShadow = shadow;
            im.receiveShadow = true;
            scene.add(im);
            return im;
        }

        /* ---------- Ground & clearing ---------- */

        const ground = new T.Mesh(new T.PlaneGeometry(90, 90), M.ground);
        ground.rotation.x = -Math.PI / 2;
        ground.receiveShadow = true;
        scene.add(ground);

        // Flagstones ringing the altar, some missing
        instanced(new T.BoxGeometry(1, 0.14, 1), M.stone, 34, (d, i) => {
            const ring = i < 14 ? 3.1 : 4.4;
            const a = (i / (i < 14 ? 14 : 20)) * Math.PI * 2 + rand() * 0.2;
            const r = ring + (rand() - 0.5) * 0.4;
            d.position.set(Math.cos(a) * r, 0.02 - rand() * 0.05, Math.sin(a) * r);
            d.rotation.set((rand() - 0.5) * 0.06, a + (rand() - 0.5) * 0.4, (rand() - 0.5) * 0.06);
            const s = 0.9 + rand() * 0.6;
            d.scale.set(s * 1.1, 1, s * 0.8);
            if (rand() < 0.15) d.scale.set(0.001, 0.001, 0.001);
        });

        /* ---------- Altar ---------- */

        const altar = [
            [4.8, 0.5, 3.6, 0.25, M.stone],
            [3.8, 0.55, 2.8, 0.775, [M.rune, M.rune, M.stone, M.stone, M.rune, M.rune]],
            [3.0, 0.22, 2.1, 1.16, M.stone]
        ];
        altar.forEach(([w, h, d, y, mat]) => {
            mesh(roughen(new T.BoxGeometry(w, h, d, 10, 3, 8), 0.025, 2.2), mat, 0, y, 0);
        });

        // Moss creeping over tier edges
        instanced(new T.IcosahedronGeometry(1, 1), M.moss, small ? 70 : 130, (d) => {
            const tier = altar[Math.floor(rand() * 2)];
            const [w, h, dd, y] = tier;
            const onX = rand() < 0.5;
            const sx = rand() < 0.5 ? -1 : 1;
            d.position.set(
                onX ? sx * w / 2 : (rand() - 0.5) * w,
                y + h / 2 - rand() * h * 0.7,
                onX ? (rand() - 0.5) * dd : sx * dd / 2
            );
            const s = 0.03 + rand() * 0.06;
            d.scale.set(s * 1.8, s * 0.5, s * 1.8);
            d.rotation.set(rand(), rand() * 6, rand());
        });

        /* ---------- The game box ---------- */

        const box = new T.Group();
        scene.add(box);
        const BW = 2.36, BH = 0.3, BD = 1.36, BY = 1.27;

        const bodyMesh = new T.Mesh(new T.BoxGeometry(BW, BH, BD), [M.side, M.side, M.woodDark, M.woodDark, M.side, M.side]);
        bodyMesh.position.y = BY + BH / 2;
        const lidMesh = new T.Mesh(new T.BoxGeometry(2.46, 0.08, 1.46), [M.side, M.side, M.lid, M.woodDark, M.side, M.side]);
        lidMesh.position.y = BY + BH + 0.04;
        [bodyMesh, lidMesh].forEach((m) => { m.castShadow = m.receiveShadow = true; box.add(m); });

        const LID_TOP = BY + BH + 0.08;
        const rivetGeo = new T.SphereGeometry(0.017, 8, 6);
        function brass(geo, x, y, z) {
            const m = new T.Mesh(geo, M.brass);
            m.position.set(x, y, z);
            m.castShadow = true;
            box.add(m);
            return m;
        }

        // Corner brackets with rivets
        const plateX = new T.BoxGeometry(0.014, BH + 0.02, 0.22);
        const plateZ = new T.BoxGeometry(0.22, BH + 0.02, 0.014);
        const capA = new T.BoxGeometry(0.26, 0.014, 0.07);
        const capB = new T.BoxGeometry(0.07, 0.014, 0.26);
        [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(([sx, sz]) => {
            const ex = sx * (BW / 2 + 0.007), ez = sz * (BD / 2 + 0.007);
            const cy = BY + BH / 2;
            brass(plateX, ex, cy, sz * (BD / 2 - 0.1));
            brass(plateZ, sx * (BW / 2 - 0.1), cy, ez);
            [-0.08, 0.08].forEach((dy) => {
                brass(rivetGeo, ex + sx * 0.008, cy + dy, sz * (BD / 2 - 0.12));
                brass(rivetGeo, sx * (BW / 2 - 0.12), cy + dy, ez + sz * 0.008);
            });
            const lx = sx * (1.23 - 0.13), lz = sz * (0.73 - 0.035);
            brass(capA, lx, LID_TOP + 0.007, lz);
            brass(capB, sx * (1.23 - 0.035), LID_TOP + 0.007, sz * (0.73 - 0.13));
            brass(rivetGeo, sx * (1.23 - 0.05), LID_TOP + 0.016, sz * (0.73 - 0.05));
        });

        // Front clasp
        brass(new T.BoxGeometry(0.24, 0.17, 0.016), 0, BY + BH / 2, BD / 2 + 0.008);
        brass(new T.BoxGeometry(0.09, 0.13, 0.02), 0, LID_TOP - 0.06, 0.73 + 0.012);
        const ring = brass(new T.TorusGeometry(0.035, 0.009, 8, 20), 0, BY + 0.1, BD / 2 + 0.03);
        ring.rotation.x = 0.3;

        // Crystal dome, bezel and inner fire
        const DOME_R = 0.27;
        const dome = new T.Mesh(new T.SphereGeometry(DOME_R, 48, 20, 0, Math.PI * 2, 0, Math.PI / 2), M.dome);
        dome.position.y = LID_TOP;
        box.add(dome);
        const bezel = brass(new T.TorusGeometry(DOME_R + 0.015, 0.03, 12, 48), 0, LID_TOP + 0.01, 0);
        bezel.rotation.x = Math.PI / 2;
        const core = new T.Mesh(
            new T.SphereGeometry(0.11, 24, 16),
            new T.MeshBasicMaterial({ color: 0x9dffc7, toneMapped: false, transparent: true, opacity: 0.9 })
        );
        core.position.y = LID_TOP + 0.08;
        box.add(core);

        function halo(scale, opacity) {
            const s = new T.Sprite(new T.SpriteMaterial({
                map: glowMap, color: 0x2bff88, transparent: true, opacity,
                blending: T.AdditiveBlending, depthWrite: false, toneMapped: false
            }));
            s.position.set(0, LID_TOP + 0.12, 0);
            s.scale.setScalar(scale);
            s.userData.base = scale;
            s.userData.opacity = opacity;
            scene.add(s);
            return s;
        }
        const halos = [halo(1.1, 0.75), halo(3.6, 0.22), halo(9, 0.07)];

        /* ---------- Lighting ---------- */

        scene.add(new T.HemisphereLight(0x46658a, 0x12261a, 0.9));

        const MOON_DIR = new V3(-0.42, 0.78, -0.47).normalize();
        const moon = new T.DirectionalLight(0xa6bfff, 2.1);
        moon.position.copy(MOON_DIR).multiplyScalar(18);
        moon.castShadow = true;
        moon.shadow.mapSize.set(small ? 1024 : 2048, small ? 1024 : 2048);
        Object.assign(moon.shadow.camera, { left: -9, right: 9, top: 9, bottom: -9, near: 1, far: 40 });
        moon.shadow.bias = -0.0006;
        moon.shadow.normalBias = 0.02;
        scene.add(moon);

        // Faint front fill so the carved front never drops to black
        const fill = new T.DirectionalLight(0x7d96c0, 0.55);
        fill.position.set(2, 4, 9);
        scene.add(fill);

        const crystalLight = new T.PointLight(0x2bff8a, 2, 9, 2);
        crystalLight.position.set(0, LID_TOP + 0.4, 0);
        scene.add(crystalLight);

        /* ---------- Ruined plinths ---------- */

        const columns = [
            [-5.2, -3.6, 3.6, true], [-2.4, -6.2, 5.2, true], [2.6, -6.4, 2.2, false],
            [5.6, -3.4, 4.4, true], [-6.6, 0.6, 1.6, false], [6.8, 0.9, 2.9, false], [0.2, -8.4, 6.0, true]
        ];
        columns.forEach(([x, z, h, capital]) => {
            mesh(roughen(new T.BoxGeometry(1.25, 0.36, 1.25, 4, 1, 4), 0.03, 3), M.stone, x, 0.18, z);
            const shaft = mesh(roughen(new T.CylinderGeometry(0.42, 0.47, h, 14, 8), 0.03, 2.6), M.stone, x, 0.36 + h / 2, z);
            shaft.rotation.y = rand() * 6;
            if (capital) mesh(roughen(new T.BoxGeometry(1.1, 0.3, 1.1, 4, 1, 4), 0.03, 3), M.stone, x, 0.36 + h + 0.15, z);
            else {
                for (let i = 0; i < 3; i++) {
                    const s = 0.18 + rand() * 0.22;
                    const chunk = mesh(new T.DodecahedronGeometry(s, 0), M.stone, x + (rand() - 0.5) * 2, s * 0.6, z + (rand() - 0.5) * 2);
                    chunk.rotation.set(rand() * 3, rand() * 3, rand() * 3);
                }
            }
            // Vine coiling up the shaft
            const pts = [];
            const turns = 1.5 + rand() * 1.5, phase = rand() * 6;
            for (let t = 0; t <= 1; t += 0.05) {
                const a = phase + t * turns * Math.PI * 2;
                pts.push(new V3(x + Math.cos(a) * 0.5, 0.3 + t * h * 0.9, z + Math.sin(a) * 0.5));
            }
            mesh(new T.TubeGeometry(new T.CatmullRomCurve3(pts), 60, 0.028, 5), M.vine, 0, 0, 0, false);
        });

        // One toppled column across the clearing's edge
        const fallen = mesh(roughen(new T.CylinderGeometry(0.42, 0.45, 3.4, 14, 6), 0.03, 2.6), M.stone, -4.3, 0.38, 2.1);
        fallen.rotation.set(0, 0.5, Math.PI / 2);

        /* ---------- Towering canopy ---------- */

        const trees = [];
        for (let i = 0; i < 18; i++) {
            // Behind and to the sides; leave the camera's corridor open
            const a = -2.25 + (i / 17) * 4.5 + (rand() - 0.5) * 0.2;
            const r = 10 + rand() * 9;
            trees.push([Math.sin(a) * r, -Math.cos(a) * r, 0.55 + rand() * 0.6]);
        }
        trees.push([-7.4, 4.6, 0.75], [8.2, 3.8, 0.9]); // framing trunks near the lens
        const leafGeo = new T.IcosahedronGeometry(1, 1);
        const trunkCount = trees.length;
        trees.forEach(([x, z, rad]) => {
            const h = 26;
            const trunk = mesh(roughen(new T.CylinderGeometry(rad * 0.7, rad * 1.1, h, 10, 10), 0.08, 0.9), M.bark, x, h / 2, z, false);
            trunk.rotation.y = rand() * 6;
            mesh(new T.ConeGeometry(rad * 2.1, 1.6, 10, 1, true), M.bark, x, 0.8, z, false);
            // Buttress roots
            for (let r = 0; r < 4; r++) {
                const a = r * 1.57 + rand();
                const root = mesh(new T.BoxGeometry(0.12, 1.4, rad * 2.4), M.bark, x + Math.cos(a) * rad * 0.9, 0.5, z + Math.sin(a) * rad * 0.9, false);
                root.rotation.set(0.45, -a + Math.PI / 2, 0);
            }
        });
        instanced(leafGeo, M.leaf, trunkCount * 4, (d, i) => {
            const [x, z] = trees[Math.floor(i / 4)];
            const s = 2.6 + rand() * 2.4;
            d.position.set(x + (rand() - 0.5) * 6, 11 + rand() * 7, z + (rand() - 0.5) * 6);
            d.scale.set(s, s * 0.55, s);
            d.rotation.set(rand(), rand() * 6, rand());
        });

        // Hanging lianas
        for (let i = 0; i < (small ? 8 : 16); i++) {
            const a = -2 + rand() * 4, r = 5.5 + rand() * 6;
            const x = Math.sin(a) * r, z = -Math.cos(a) * r;
            const drop = 4 + rand() * 6;
            const curve = new T.CatmullRomCurve3([
                new V3(x, 16, z),
                new V3(x + (rand() - 0.5), 16 - drop * 0.5, z + (rand() - 0.5)),
                new V3(x + (rand() - 0.5) * 1.5, 16 - drop, z + (rand() - 0.5) * 1.5)
            ]);
            mesh(new T.TubeGeometry(curve, 20, 0.035, 4), M.vine, 0, 0, 0, false);
        }

        // Ferns: clumps of fronds leaning outward
        const frondGeo = new T.PlaneGeometry(0.55, 1.2);
        frondGeo.translate(0, 0.6, 0);
        const clumps = [];
        for (let i = 0; i < (small ? 34 : 70); i++) {
            const a = rand() * Math.PI * 2, r = 3.6 + rand() * 11;
            const x = Math.cos(a) * r, z = Math.sin(a) * r;
            if (z > 2.2 && Math.abs(x) < 3.2) continue; // keep the foreground clear
            clumps.push([x, z, 0.7 + rand() * 1.1]);
        }
        instanced(frondGeo, M.fern, clumps.length * 6, (d, i) => {
            const [x, z, s] = clumps[Math.floor(i / 6)];
            d.position.set(x, 0, z);
            d.rotation.set(-(0.55 + rand() * 0.55), (i % 6) * 1.047 + rand() * 0.4, 0, 'YXZ');
            d.scale.setScalar(s * (0.8 + rand() * 0.4));
        });

        /* ---------- God rays ---------- */

        const RAY_VS = `
            varying vec2 vUv;
            varying float vFacing;
            void main() {
                vUv = uv;
                vec4 mv = modelViewMatrix * vec4(position, 1.0);
                vFacing = abs(dot(normalize(normalMatrix * normal), normalize(-mv.xyz)));
                gl_Position = projectionMatrix * mv;
            }`;
        const RAY_FS = `
            uniform float uTime, uStrength, uSeed, uFoot;
            uniform vec3 uColor;
            varying vec2 vUv;
            varying float vFacing;
            void main() {
                float along = smoothstep(0.0, uFoot, vUv.y) * smoothstep(1.0, 0.55, vUv.y);
                float core = pow(vFacing, 2.4);
                float streaks = 0.6 + 0.4 * sin(vUv.x * 37.0 + uSeed * 9.0 + sin(vUv.x * 11.0 + uTime * 0.17) * 2.0);
                float sway = 0.72 + 0.28 * sin(uTime * 0.31 + uSeed * 4.0) * sin(uTime * 0.19 + uSeed);
                gl_FragColor = vec4(uColor * core * along * streaks * sway * uStrength, 1.0);
            }`;

        function rayMaterial(color, strength, seed, foot) {
            return new T.ShaderMaterial({
                uniforms: {
                    uTime, uColor: { value: new T.Color(color) },
                    uStrength: { value: strength }, uSeed: { value: seed }, uFoot: { value: foot }
                },
                vertexShader: RAY_VS, fragmentShader: RAY_FS,
                transparent: true, depthWrite: false, blending: T.AdditiveBlending, side: T.DoubleSide
            });
        }

        const Y_AXIS = new V3(0, 1, 0);
        [[0.4, 0.2, 1.9, 0.34], [-3.4, -1.6, 1.1, 0.24], [3.1, -2.8, 1.3, 0.22], [-1.2, -5, 0.9, 0.2], [5.2, 0.4, 1.0, 0.18]]
            .forEach(([x, z, r, s], i) => {
                const len = 24;
                const g = new T.CylinderGeometry(r * 0.45, r, len, 32, 1, true);
                g.translate(0, len / 2, 0);
                const m = new T.Mesh(g, rayMaterial(0x8fb0d8, s, i * 1.7, 0.28));
                m.position.set(x, 0, z);
                m.quaternion.setFromUnitVectors(Y_AXIS, MOON_DIR);
                m.renderOrder = 2;
                scene.add(m);
            });

        // The surge beam from the crystal (dark until surge)
        const beamGeo = new T.CylinderGeometry(0.9, 0.12, 14, 32, 1, true);
        beamGeo.translate(0, 7, 0);
        const beamMat = rayMaterial(0x44ff99, 0, 0.3, 0.02);
        const beam = new T.Mesh(beamGeo, beamMat);
        beam.position.y = LID_TOP;
        beam.renderOrder = 3;
        scene.add(beam);

        /* ---------- Ground fog ---------- */

        const FOG_VS = `
            varying vec3 vWorld;
            void main() {
                vec4 w = modelMatrix * vec4(position, 1.0);
                vWorld = w.xyz;
                gl_Position = projectionMatrix * viewMatrix * w;
            }`;
        const FOG_FS = `
            uniform float uTime, uOpacity, uGlow;
            uniform vec2 uDrift;
            uniform vec3 uColor;
            varying vec3 vWorld;
            float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
            float noise(vec2 p) {
                vec2 i = floor(p), f = fract(p);
                vec2 u = f * f * (3.0 - 2.0 * f);
                return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
            }
            float fbm(vec2 p) {
                float s = 0.0, a = 0.5;
                for (int i = 0; i < 5; i++) { s += a * noise(p); p = p * 2.03 + vec2(1.7, 9.2); a *= 0.5; }
                return s;
            }
            void main() {
                vec2 p = vWorld.xz * 0.16 + uDrift * uTime;
                float n = fbm(p + fbm(p * 0.6 + uTime * 0.02) * 1.6);
                float d = length(vWorld.xz);
                float alpha = smoothstep(0.32, 0.85, n) * smoothstep(30.0, 7.0, d) * uOpacity;
                vec3 col = mix(uColor, vec3(0.12, 0.85, 0.45), smoothstep(4.0, 0.0, d) * uGlow);
                gl_FragColor = vec4(col, alpha);
            }`;
        const fogLayers = [[0.12, 0.42, [0.018, 0.006]], [0.45, 0.3, [-0.012, 0.01]], [0.9, 0.16, [0.008, -0.014]]].map(([y, op, drift]) => {
            const m = new T.Mesh(new T.PlaneGeometry(64, 64), new T.ShaderMaterial({
                uniforms: {
                    uTime, uOpacity: { value: op }, uGlow: { value: 0.2 },
                    uDrift: { value: new T.Vector2(...drift) }, uColor: { value: new T.Color(0x6f9b98) }
                },
                vertexShader: FOG_VS, fragmentShader: FOG_FS,
                transparent: true, depthWrite: false
            }));
            m.rotation.x = -Math.PI / 2;
            m.position.y = y;
            m.renderOrder = 1;
            scene.add(m);
            return m;
        });

        /* ---------- Spores & fireflies ---------- */

        const SWARM_VS = `
            attribute float aSeed;
            attribute float aScale;
            uniform float uTime, uPixelRatio, uSize, uSurge, uBlink;
            uniform vec3 uCenter;
            varying float vAlpha;
            void main() {
                vec3 p = position;
                float t = uTime * 0.22 + aSeed * 6.2831;
                p.x += sin(t * 1.3 + p.y * 0.7) * 0.6 + sin(t * 0.7 + aSeed * 13.0) * 0.3;
                p.y += sin(t * 0.9 + p.x * 0.5) * 0.35 + sin(t * 0.4 + aSeed * 7.0) * 0.25;
                p.z += cos(t * 1.1 + p.y * 0.6) * 0.6;
                p += (uCenter - p) * uSurge * (0.4 + 0.45 * fract(aSeed * 7.13));
                vec4 mv = modelViewMatrix * vec4(p, 1.0);
                gl_Position = projectionMatrix * mv;
                gl_PointSize = uSize * aScale * uPixelRatio / -mv.z;
                float twinkle = 0.65 + 0.35 * sin(uTime * (1.0 + aSeed * 2.0) + aSeed * 40.0);
                float blink = smoothstep(0.55, 1.0, sin(uTime * (0.5 + aSeed * 0.8) + aSeed * 50.0));
                vAlpha = mix(twinkle, 0.08 + blink, uBlink) * smoothstep(30.0, 6.0, -mv.z) * (1.0 + uSurge * 1.5);
            }`;
        const SWARM_FS = `
            uniform vec3 uColor;
            varying float vAlpha;
            void main() {
                float d = length(gl_PointCoord - 0.5);
                float a = pow(smoothstep(0.5, 0.0, d), 2.2) * vAlpha;
                gl_FragColor = vec4(uColor * (1.0 + a), a);
            }`;

        const swarmUniforms = [];
        function swarm(count, color, size, blink, place) {
            const pos = new Float32Array(count * 3);
            const seed = new Float32Array(count);
            const scl = new Float32Array(count);
            for (let i = 0; i < count; i++) {
                place(pos, i * 3);
                seed[i] = rand();
                scl[i] = 0.5 + rand();
            }
            const g = new T.BufferGeometry();
            g.setAttribute('position', new T.BufferAttribute(pos, 3));
            g.setAttribute('aSeed', new T.BufferAttribute(seed, 1));
            g.setAttribute('aScale', new T.BufferAttribute(scl, 1));
            const u = {
                uTime, uPixelRatio: { value: dpr }, uSize: { value: size }, uSurge: { value: 0 },
                uBlink: { value: blink }, uColor: { value: new T.Color(color) },
                uCenter: { value: new V3(0, LID_TOP + 0.15, 0) }
            };
            swarmUniforms.push(u);
            const pts = new T.Points(g, new T.ShaderMaterial({
                uniforms: u, vertexShader: SWARM_VS, fragmentShader: SWARM_FS,
                transparent: true, depthWrite: false, blending: T.AdditiveBlending
            }));
            pts.frustumCulled = false;
            pts.renderOrder = 4;
            scene.add(pts);
        }
        swarm(small ? 260 : 560, 0x3dff9a, 46, 0, (p, i) => {
            const r = 0.6 + Math.sqrt(rand()) * 12, a = rand() * Math.PI * 2;
            p[i] = Math.cos(a) * r; p[i + 1] = 0.2 + Math.pow(rand(), 1.6) * 7; p[i + 2] = Math.sin(a) * r;
        });
        swarm(small ? 40 : 80, 0xd8ff7a, 110, 1, (p, i) => {
            const r = 2.6 + rand() * 8, a = rand() * Math.PI * 2;
            p[i] = Math.cos(a) * r; p[i + 1] = 0.3 + rand() * 3.2; p[i + 2] = Math.sin(a) * r;
        });

        /* ======================================================================
           Camera rig: Lissajous idle drift, focus dolly, damped quaternion parallax
           ====================================================================== */

        const rig = {
            farPos: new V3(0, 3.2, 7.8), farLook: new V3(0, 1.3, 0),
            nearPos: new V3(0.25, 2.7, 4.9), nearLook: new V3(0, 1.55, 0)
        };
        const pos = new V3(), look = new V3();
        const lookM = new T.Matrix4(), qBase = new T.Quaternion(), qPar = new T.Quaternion(), qTarget = new T.Quaternion();
        const euler = new T.Euler(0, 0, 0, 'YXZ');
        const pointer = { x: 0, y: 0 }, ptr = { x: 0, y: 0 };
        let focus = 0, focusTarget = 0;
        let layoutDolly = 1;

        function onPointer(x, y) {
            pointer.x = Math.max(-1, Math.min(1, x));
            pointer.y = Math.max(-1, Math.min(1, y));
        }
        window.addEventListener('pointermove', (e) => {
            onPointer((e.clientX / window.innerWidth) * 2 - 1, (e.clientY / window.innerHeight) * 2 - 1);
        }, { passive: true });
        window.addEventListener('touchmove', (e) => {
            const t = e.touches[0];
            if (t) onPointer((t.clientX / window.innerWidth) * 2 - 1, (t.clientY / window.innerHeight) * 2 - 1);
        }, { passive: true });
        // Gyroscope where it needs no permission prompt (Android); iOS falls back to touch
        window.addEventListener('deviceorientation', (e) => {
            if (e.gamma == null || e.beta == null) return;
            onPointer(e.gamma / 30, (e.beta - 50) / 30);
        }, { passive: true });

        function damp(current, target, lambda, dt) {
            return current + (target - current) * (1 - Math.exp(-lambda * dt));
        }
        const ease = (x) => x * x * (3 - 2 * x);

        /* ---------- Resize & layout-aware framing ---------- */

        function resize() {
            const W = window.innerWidth, H = window.innerHeight;
            const aspect = W / H;
            renderer.setSize(W, H, false);
            camera.aspect = aspect;
            // Portrait screens widen the lens so the whole box stays in frame
            camera.fov = aspect < 1 ? 36 + Math.min(1, (1 - aspect) / 0.55) * 16 : 36;
            layoutDolly = aspect < 1 ? 1.05 : 1;

            // Slide the projection so the altar sits in the space the pass leaves free
            let offX = 0, offY = 0;
            if (W >= 960) offX = Math.min(300, W * 0.2);
            else offY = H * (aspect < 0.8 ? 0.24 : 0.16);
            camera.setViewOffset(W, H, offX, offY, W, H);
            camera.updateProjectionMatrix();
            swarmUniforms.forEach((u) => { u.uPixelRatio.value = renderer.getPixelRatio(); });
        }
        window.addEventListener('resize', resize);
        resize();

        /* ---------- Loop ---------- */

        const drift = reduceMotion ? 0 : 1;
        let raf = 0, last = performance.now(), elapsed = 0, surgeT = -1, intro = reduceMotion ? 1 : 0;
        let slowFrames = 0, ready = false;
        const MIN_FRAME = 1 / 62; // cap high-refresh displays near 60 fps

        // Two-beat drum pulse: ba-DUM ... ba-DUM
        function drum(t) {
            const p = (t % 1.7) / 1.7;
            const g = (c, w) => Math.exp(-((p - c) * (p - c)) / w);
            return g(0.04, 0.0015) * 0.7 + g(0.17, 0.0018);
        }

        function frame(now) {
            raf = requestAnimationFrame(frame);
            let dt = (now - last) / 1000;
            if (dt < MIN_FRAME - 0.002) return;
            last = now;
            dt = Math.min(dt, 0.1);
            elapsed += reduceMotion ? dt * 0.3 : dt;
            uTime.value = elapsed;

            // Adaptive resolution: step down if we keep missing ~40 fps
            slowFrames = dt > 1 / 40 ? slowFrames + 1 : Math.max(0, slowFrames - 1);
            if (slowFrames > 90 && dpr > 1) {
                dpr = Math.max(1, dpr - 0.5);
                renderer.setPixelRatio(dpr);
                resize();
                slowFrames = 0;
            }

            // Intro: exposure rises out of darkness, then the crystal ignites
            if (intro < 1) {
                intro = Math.min(1, intro + dt / 2.6);
                renderer.toneMappingExposure = 0.05 + ease(intro) * 1.25;
            }
            const ignite = reduceMotion ? 1 : smoothstep(0.45, 1, intro);

            // Surge envelope: fast rise, long fall
            let s = 0;
            if (surgeT >= 0) {
                surgeT += dt;
                s = surgeT < 0.35 ? ease(surgeT / 0.35) : Math.max(0, 1 - (surgeT - 0.35) / 1.9);
                if (surgeT > 2.4) surgeT = -1;
            }
            shared.surge = s;
            const beat = reduceMotion ? 0.4 : drum(elapsed);
            const glow = (0.45 + beat * 0.55) * ignite;

            M.dome.emissiveIntensity = 0.45 + glow * 1.1 + s * 3;
            M.rune.emissiveIntensity = 0.08 + glow * 0.35 + s * 2.2;
            core.material.opacity = 0.35 + glow * 0.55 + s * 0.1;
            core.scale.setScalar(1 + beat * 0.12 * ignite + s * 0.4);
            crystalLight.intensity = 0.8 + glow * 3 + s * 9;
            halos.forEach((h, i) => {
                h.scale.setScalar(h.userData.base * (1 + beat * 0.15 + s * (i === 0 ? 1.4 : 0.9)));
                h.material.opacity = h.userData.opacity * (0.45 + glow * 1.1) + s * 0.25;
            });
            beamMat.uniforms.uStrength.value = s * 0.55;
            swarmUniforms.forEach((u) => { u.uSurge.value = s * 0.7; });
            fogLayers.forEach((f) => { f.material.uniforms.uGlow.value = 0.15 + glow * 0.25 + s * 0.6; });
            if (intro >= 1) renderer.toneMappingExposure = 1.3 + s * 0.3;

            // Camera
            focus = damp(focus, focusTarget, 2.4, dt);
            const f = ease(focus);
            pos.lerpVectors(rig.farPos, rig.nearPos, f).multiplyScalar(layoutDolly);
            look.lerpVectors(rig.farLook, rig.nearLook, f);
            pos.x += Math.sin(elapsed * 0.11) * 0.45 * drift;
            pos.y += Math.sin(elapsed * 0.17 + 1.3) * 0.14 * drift;
            pos.z += Math.sin(elapsed * 0.07 + 0.5) * 0.25 * drift;
            ptr.x = damp(ptr.x, pointer.x, 2.6, dt);
            ptr.y = damp(ptr.y, pointer.y, 2.6, dt);
            pos.x += ptr.x * 0.55 * drift;
            pos.y -= ptr.y * 0.22 * drift;
            if (s > 0 && !reduceMotion) {
                pos.x += (Math.random() - 0.5) * s * 0.03;
                pos.y += (Math.random() - 0.5) * s * 0.03;
            }
            camera.position.copy(pos);

            lookM.lookAt(pos, look, Y_AXIS);
            qBase.setFromRotationMatrix(lookM);
            euler.set(-ptr.y * 0.03 * drift, -ptr.x * 0.045 * drift, 0);
            qPar.setFromEuler(euler);
            qTarget.copy(qBase).multiply(qPar);
            if (!ready) camera.quaternion.copy(qTarget);
            camera.quaternion.slerp(qTarget, 1 - Math.exp(-5 * dt));

            renderer.render(scene, camera);

            if (!ready) {
                ready = true;
                body.classList.add('is-scene-ready');
            }
        }

        function start() {
            if (raf) return;
            last = performance.now();
            raf = requestAnimationFrame(frame);
        }
        function stop() {
            cancelAnimationFrame(raf);
            raf = 0;
        }
        doc.addEventListener('visibilitychange', () => (doc.hidden ? stop() : start()));
        canvas.addEventListener('webglcontextlost', (e) => {
            e.preventDefault();
            stop();
            body.classList.add('no-webgl');
        });
        start();

        return {
            setFocus(on) { focusTarget = on ? 1 : 0; },
            surge() { surgeT = 0; }
        };
    }

    boot();
})();
