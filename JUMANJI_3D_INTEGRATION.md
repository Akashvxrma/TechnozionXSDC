# Jumanji 3D World — Integration Guide

The WebGL layer lives in two files and hooks into the existing templates without changing their game logic.

| File | Role |
| --- | --- |
| `DAY 1/www/static/js/jumanji_3d_engine.js` | `Jumanji3DWorld` engine plus the `RelicTokens` and `FieldRig` modules |
| `DAY 1/www/static/css/jumanji_3d.css` | Canvas layer, hub slot, token cards, terminal chassis, CSS fallback |
| `DAY 1/www/static/js/jumanji_fx.js` | Adds `JX.audio.graph()` (shared Web Audio bus) and `JX.sfx.stamp()` |

Three.js r149 is loaded from jsdelivr (`three@0.149.0/build/three.min.js`), the last line of releases that still ships a non-module build. No `.gltf` or image assets are used: all geometry and textures are procedural.

## Adding it to a template

In `<head>`, after the design system stylesheet:

```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/jumanji_3d.css') }}">
<script src="https://cdn.jsdelivr.net/npm/three@0.149.0/build/three.min.js" defer></script>
<script src="{{ url_for('static', filename='js/jumanji_3d_engine.js') }}" defer></script>
```

Pick a world on `<body>`:

```html
<body class="scene hub" data-world="hub">        <!-- board box, dome, god-rays -->
<body class="l1 scene"  data-world="ambient">    <!-- spores + mist only -->
```

The engine prepends `<canvas id="jumanji-3d-canvas">` to `<body>`: fixed, `z-index: 0`, `pointer-events: none`. Every existing screen, terminal and form paints above it, and nothing receives fewer clicks or keystrokes.

`jumanji_fx.js` must load before the engine. Every template already loads it synchronously, and the engine is `defer`, so the order holds.

## Hooks per page

**Hub** — the `.emblem` element becomes the board's slot. The engine pins the camera to it (scroll-aware via `setViewOffset`) and makes it a keyboard-operable button that opens and closes the lid. Links marked `data-deploy` play a camera move before navigating:

```html
<a href="{{ url_for('level2') }}" class="btn btn--gold btn--block" data-deploy="board">Enter the jungle</a>
<a href="{{ url_for('level3') }}" class="btn btn--gold btn--block" data-deploy="emerald">Access the mainframe</a>
```

`board` cranes overhead; `emerald` dives into the jaguar eye. Modifier-clicks (new tab) are left alone, navigation runs on a timer so a stalled frame can't trap the player, and reduced-motion users navigate immediately.

**Level 2** — one slot per avatar card, after the image:

```html
<span class="relic-token" data-token="{{ id }}" aria-hidden="true"></span>
```

`data-token` is one of `bravestone`, `ruby`, `finbar`, `oberon`, `seaplane`. Cards that already contain `.seal` start stamped. When a flag is solved, `stampSeal()` calls `JX3D.stamp(avatarId)`; the stamp waits until the card is back on screen.

**Any terminal** — every `.bezel` containing a `.crt-glass` gets the field-rig chassis automatically: a CRT shader canvas over xterm (glow and shade only, text untouched), a Link LED, a Glow knob and a Screen switch (both remembered in `localStorage`). The Gauntlet also gets a Curse LED, because it has `#curse-banner`.

Socket handlers report link state and traffic:

```js
socket.on('pty-output', data => { term.write(data.output); window.JX3D && JX3D.signal('telemetry'); });
socket.on('connect',    () => window.JX3D && JX3D.signal('link', true));
socket.on('disconnect', () => window.JX3D && JX3D.signal('link', false));
```

Curses need no hook: the engine watches `body.is-cursed` (already toggled by the Gauntlet's `curse-alert` handler) and turns spores, mist, CRT glass and the Curse LED red.

## API

```js
JX3D.setMode('resting' | 'boardOpen' | 'terminalFocus');
JX3D.toggleBoard(true);
JX3D.deploy('/level3', 'emerald');
JX3D.stamp('ruby');
JX3D.signal('link', false);
```

## Performance and fallbacks

- **Tiers:** high (god-rays, soft shadows, 4× MSAA, 480 spores), mid (rays, no shadows), low (direct render, 220 spores). The tier comes from `deviceMemory` and `hardwareConcurrency`.
- **Resolution:** the pixel ratio starts at `min(devicePixelRatio, 2)` and steps down 0.25 at a time if frames run over ~22 ms; god-rays drop out at the bottom of that range.
- **Ambient pages** render at half rate, so terminals keep the GPU.
- **Background tabs:** the loop stops on `visibilitychange`.
- **No WebGL:** `<html>` gets `.jx3d-fallback`. The hub keeps its SVG emblem with a CSS 3D pointer tilt, token slots hide, and the terminal chassis still mounts (CSS-only, no shader).
- **`prefers-reduced-motion`:** no intro, parallax, tilt, flicker or stamp animation; the board starts open.

## Audio

Spatial voices route through `JX`'s master bus, so they respect `JX.sfx.enabled`. Nothing plays before the first pointer or key press.

- Heartbeat thump at 68 BPM, panned from the emerald and muffled while the lid is closed.
- Stone scrape and landing thud for each lid wing, panned left and right.
- Stamp thud on Level 2.
