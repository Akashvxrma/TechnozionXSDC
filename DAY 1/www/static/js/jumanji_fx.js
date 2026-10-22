/* ==========================================================================
   JUMANJI EXPEDITION NOIR — audio & micro-interactions
   Exposes window.JX:
     JX.sfx      Web Audio synth: key, chirp, transmit, success, warn, fail, curse, unlock
     JX.drums    ambient drum loop manager with automatic playback and autoplay unlock
     JX.toast    in-page notice, replaces alert()
     JX.copy     clipboard with inline "Copied" state on the button
     JX.typeInto types a command into the PTY one key at a time
     JX.surface  makes text rise out of the orb smoke
     JX.countdown mm:ss ticker
   ========================================================================== */
(function () {
    'use strict';

    const store = {
        get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
        set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* storage blocked */ } }
    };

    /* ---------- Web Audio synth ---------- */

    let ctx = null;
    let master = null;

    function audio() {
        if (!ctx) {
            const AC = window.AudioContext || window.webkitAudioContext;
            if (!AC) return null;
            ctx = new AC();
            master = ctx.createGain();
            master.gain.value = 0.5;
            master.connect(ctx.destination);
        }
        if (ctx.state === 'suspended') ctx.resume();
        return ctx;
    }

    // One enveloped oscillator voice
    function tone(freq, start, dur, type = 'sine', vol = 0.08, glideTo = null) {
        const c = audio();
        if (!c) return;
        const t = c.currentTime + start;
        const osc = c.createOscillator();
        const g = c.createGain();
        osc.type = type;
        osc.frequency.setValueAtTime(freq, t);
        if (glideTo) osc.frequency.exponentialRampToValueAtTime(glideTo, t + dur);
        g.gain.setValueAtTime(0.0001, t);
        g.gain.exponentialRampToValueAtTime(vol, t + 0.01);
        g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
        osc.connect(g).connect(master);
        osc.start(t);
        osc.stop(t + dur + 0.02);
    }

    // Filtered noise burst (keys, stone grind)
    function noise(start, dur, vol = 0.05, freq = 2000, q = 1, sweepTo = null) {
        const c = audio();
        if (!c) return;
        const t = c.currentTime + start;
        const len = Math.max(1, Math.floor(c.sampleRate * dur));
        const buf = c.createBuffer(1, len, c.sampleRate);
        const data = buf.getChannelData(0);
        for (let i = 0; i < len; i++) data[i] = Math.random() * 2 - 1;
        const src = c.createBufferSource();
        src.buffer = buf;
        const filt = c.createBiquadFilter();
        filt.type = 'bandpass';
        filt.frequency.setValueAtTime(freq, t);
        if (sweepTo) filt.frequency.exponentialRampToValueAtTime(sweepTo, t + dur);
        filt.Q.value = q;
        const g = c.createGain();
        g.gain.setValueAtTime(vol, t);
        g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
        src.connect(filt).connect(g).connect(master);
        src.start(t);
    }

    const sfx = {
        enabled: store.get('jx-sfx') !== 'off',

        // Generic chirp, kept for drop-in compatibility with the old playChirp()
        chirp(freq = 600, dur = 0.05, type = 'sine', vol = 0.08) {
            if (sfx.enabled) tone(freq, 0, dur, type, vol);
        },
        // Tactile terminal key: a tiny clack
        key() {
            if (!sfx.enabled) return;
            noise(0, 0.025, 0.035, 3200 + Math.random() * 900, 4);
            tone(1800 + Math.random() * 300, 0, 0.012, 'square', 0.006);
        },
        // Relic seal leaving the altar: rising pentatonic run
        transmit() {
            if (!sfx.enabled) return;
            [392, 440, 523, 587, 659].forEach((f, i) => tone(f, i * 0.06, 0.18, 'triangle', 0.06));
            noise(0, 0.35, 0.02, 600, 0.7, 4000);
        },
        // Relic secured: bell chord
        success() {
            if (!sfx.enabled) return;
            [523, 659, 784, 1046].forEach((f, i) => tone(f, i * 0.03, 0.9, 'sine', 0.07));
            tone(1568, 0.12, 0.6, 'triangle', 0.03);
        },
        // Split-key / partial: two hollow knocks
        warn() {
            if (!sfx.enabled) return;
            tone(330, 0, 0.14, 'triangle', 0.08);
            tone(262, 0.16, 0.2, 'triangle', 0.08);
        },
        // Rejected seal
        fail() {
            if (!sfx.enabled) return;
            tone(220, 0, 0.35, 'sawtooth', 0.05, 110);
        },
        // Curse: low detuned rumble with tremolo
        curse() {
            if (!sfx.enabled) return;
            const c = audio();
            if (!c) return;
            const t = c.currentTime;
            const g = c.createGain();
            g.gain.setValueAtTime(0.0001, t);
            g.gain.exponentialRampToValueAtTime(0.09, t + 0.08);
            g.gain.exponentialRampToValueAtTime(0.0001, t + 1.6);
            const lfo = c.createOscillator();
            const lfoGain = c.createGain();
            lfo.frequency.value = 7;
            lfoGain.gain.value = 0.04;
            lfo.connect(lfoGain).connect(g.gain);
            [55, 58.3, 82.4].forEach(f => {
                const o = c.createOscillator();
                o.type = 'sawtooth';
                o.frequency.setValueAtTime(f, t);
                o.frequency.exponentialRampToValueAtTime(f * 0.7, t + 1.6);
                o.connect(g);
                o.start(t);
                o.stop(t + 1.7);
            });
            const lp = c.createBiquadFilter();
            lp.type = 'lowpass';
            lp.frequency.value = 500;
            g.connect(lp).connect(master);
            lfo.start(t);
            lfo.stop(t + 1.7);
        },
        // Stone padlock grinding open, then a chime
        unlock() {
            if (!sfx.enabled) return;
            noise(0, 0.5, 0.08, 180, 0.8, 900);
            noise(0.45, 0.12, 0.06, 2600, 6);
            tone(784, 0.55, 0.7, 'sine', 0.06);
            tone(1175, 0.62, 0.7, 'sine', 0.04);
        }
    };

    /* ---------- Ambient drums ---------- */

    const drums = {
        audio: null,
        button: null,
        playing: false,
        fadeTimer: null,
        unlocked: false,

        // Play audio element with robust auto-unlock for modern browser autoplay policies
        play(audioEl, targetVol = 0.55) {
            if (audioEl) drums.audio = audioEl;
            if (!drums.audio) return;
            drums.audio.loop = true;

            const executePlay = () => {
                drums.audio.volume = targetVol;
                const p = drums.audio.play();
                if (p !== undefined) {
                    p.then(() => {
                        drums.playing = true;
                        drums.unlocked = true;
                    }).catch(() => {
                        // Browser autoplay policy blocked unmuted audio; attach one-time user gesture listeners
                        if (!drums.unlocked) {
                            const unlock = () => {
                                if (!drums.audio) return;
                                drums.audio.volume = targetVol;
                                drums.audio.play().then(() => {
                                    drums.playing = true;
                                    drums.unlocked = true;
                                }).catch(() => {});
                            };
                            window.addEventListener('pointerdown', unlock, { once: true });
                            window.addEventListener('keydown', unlock, { once: true });
                            window.addEventListener('click', unlock, { once: true });
                        }
                    });
                }
            };
            executePlay();
        },

        start(targetVol = 0.55) {
            if (!drums.audio) return;
            drums.play(drums.audio, targetVol);
        },

        pause() {
            if (drums.audio) {
                drums.audio.pause();
                drums.playing = false;
            }
        },

        resume(targetVol = 0.55) {
            if (drums.audio) {
                drums.play(drums.audio, targetVol);
            }
        },

        stop() {
            if (!drums.audio) return;
            drums.playing = false;
            drums.audio.pause();
            drums.audio.currentTime = 0;
        },

        fadeTo(target, ms, done) {
            if (!drums.audio) return;
            const a = drums.audio;
            clearInterval(drums.fadeTimer);
            const steps = 20;
            const from = a.volume;
            let i = 0;
            drums.fadeTimer = setInterval(() => {
                i++;
                a.volume = Math.min(1, Math.max(0, from + (target - from) * (i / steps)));
                if (i >= steps) {
                    clearInterval(drums.fadeTimer);
                    if (done) done();
                }
            }, ms / steps);
        },

        // Backwards compatibility helpers
        bind(button, audioEl) {
            if (audioEl) drums.audio = audioEl;
            if (button) drums.button = button;
        },
        toggle() { drums.playing ? drums.pause() : drums.start(); },
        render() {}
    };

    /* ---------- Toast ---------- */

    function toast(message, kind = 'ok', ms = 3200) {
        let stack = document.querySelector('.toast-stack');
        if (!stack) {
            stack = document.createElement('div');
            stack.className = 'toast-stack';
            stack.setAttribute('role', 'status');
            stack.setAttribute('aria-live', 'polite');
            document.body.appendChild(stack);
        }
        const el = document.createElement('div');
        el.className = 'toast' + (kind === 'warn' ? ' toast--warn' : kind === 'curse' ? ' toast--curse' : '');
        el.textContent = message;
        stack.appendChild(el);
        setTimeout(() => {
            el.classList.add('is-leaving');
            setTimeout(() => el.remove(), 320);
        }, ms);
    }

    /* ---------- Clipboard ---------- */

    function fallbackCopy(text) {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        let ok = false;
        try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
        ta.remove();
        return ok;
    }

    async function copy(text, button) {
        if (!text) return false;
        let ok = false;
        try {
            await navigator.clipboard.writeText(text);
            ok = true;
        } catch (e) {
            ok = fallbackCopy(text);
        }
        if (ok) sfx.chirp(880, 0.05, 'triangle');
        if (button) {
            const original = button.dataset.label || button.textContent;
            button.dataset.label = original;
            button.textContent = ok ? 'Copied' : 'Copy failed';
            button.classList.toggle('is-copied', ok);
            clearTimeout(button._jxTimer);
            button._jxTimer = setTimeout(() => {
                button.textContent = original;
                button.classList.remove('is-copied');
            }, 1400);
        }
        return ok;
    }

    /* ---------- Typewriter into PTY ---------- */

    // emit(ch) sends one chunk to the PTY. Resolves when the whole string is sent.
    function typeInto(emit, text, delay = 38) {
        return new Promise(resolve => {
            let i = 0;
            (function next() {
                if (i >= text.length) return resolve();
                const ch = text[i++];
                emit(ch);
                if (ch !== '\r') sfx.key();
                setTimeout(next, delay + Math.random() * 30);
            })();
        });
    }

    /* ---------- Orb text ---------- */

    function surface(el, text, className = 'surfacing') {
        if (!el) return;
        if (typeof text === 'string') el.textContent = text;
        el.classList.remove(className);
        void el.offsetWidth;
        el.classList.add(className);
    }

    /* ---------- Countdown ---------- */

    function fmt(sec) {
        const s = Math.max(0, sec);
        const m = Math.floor(s / 60);
        return String(m).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');
    }

    // targets: elements that show mm:ss. Adds .is-low under `low` seconds.
    function countdown(seconds, targets, { low = 300, onDone } = {}) {
        let remaining = Math.max(0, parseInt(seconds, 10) || 0);
        const els = targets.filter(Boolean);
        function render() {
            els.forEach(el => {
                el.textContent = fmt(remaining);
                el.classList.toggle('is-low', remaining <= low);
            });
        }
        render();
        const id = setInterval(() => {
            remaining--;
            if (remaining <= 0) {
                remaining = 0;
                render();
                clearInterval(id);
                if (onDone) onDone();
                return;
            }
            render();
        }, 1000);
        return { stop: () => clearInterval(id), get remaining() { return remaining; } };
    }

    window.JX = { sfx, drums, toast, copy, typeInto, surface, countdown, store };
})();
