#!/usr/bin/env python3
"""
generate_serre_modularity_manifold_3d.py
Generates docs/assets/serre_modularity_manifold_3d.html:
Interactive 3D WebGL Serre's Modularity Conjecture & Hecke Cusp Form Visualizer.
Renders modular curve hyperbolic domains \Gamma_1(N) \ H, q-expansion Fourier spirals,
and Serre weight k(\rho) >= 2 cones.
"""

import os

HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>IMF Serre's Modularity Conjecture Visualizer (3D)</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            padding: 0;
            background: #020617;
            color: #f8fafc;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
            overflow: hidden;
        }
        #canvas {
            width: 100vw;
            height: 100vh;
            display: block;
        }
        #hud {
            position: absolute;
            top: 16px;
            left: 16px;
            background: rgba(15, 23, 42, 0.90);
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 18px 22px;
            max-width: 480px;
            backdrop-filter: blur(8px);
            box-shadow: 0 8px 32px rgba(0,0,0,0.6);
            pointer-events: auto;
        }
        h1 {
            margin: 0 0 8px 0;
            font-size: 19px;
            font-weight: 700;
            color: #f59e0b;
            letter-spacing: 0.5px;
        }
        .subtitle {
            font-size: 13px;
            color: #94a3b8;
            margin-bottom: 12px;
            line-height: 1.4;
        }
        .stat-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
            margin-bottom: 14px;
        }
        .stat-card {
            background: rgba(30, 41, 59, 0.6);
            border: 1px solid #334155;
            padding: 8px 12px;
            border-radius: 6px;
        }
        .stat-label {
            font-size: 11px;
            color: #64748b;
            text-transform: uppercase;
        }
        .stat-value {
            font-size: 14px;
            font-weight: 600;
            color: #f1f5f9;
        }
        .controls {
            margin-top: 12px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        label {
            font-size: 12px;
            color: #cbd5e1;
            display: flex;
            justify-content: space-between;
        }
        input[type=range] {
            width: 100%;
            accent-color: #f59e0b;
        }
    </style>
    <!-- Three.js from CDN -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
</head>
<body>
    <div id="hud">
        <h1>Serre's Modularity Conjecture (Module 45)</h1>
        <div class="subtitle">Odd Galois Representations, Artin Conductors & Hecke Eigenforms</div>
        <div class="stat-grid">
            <div class="stat-card">
                <div class="stat-label">Conjugation det &#961;(c)</div>
                <div class="stat-value" id="val-det">-1 (Odd)</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Serre Weight k(&#961;)</div>
                <div class="stat-value" id="val-weight">k = 2</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Artin Conductor N(&#961;)</div>
                <div class="stat-value" id="val-level">N = 18</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Modularity Status</div>
                <div class="stat-value" style="color: #10b981;">Khare-Wintenberger &#10003;</div>
            </div>
        </div>
        <div class="controls">
            <label><span>Serre Weight k:</span> <span id="lbl-weight">2</span></label>
            <input type="range" id="param-weight" min="2" max="12" step="1" value="2">

            <label><span>Artin Conductor Scale N:</span> <span id="lbl-level">18</span></label>
            <input type="range" id="param-level" min="1" max="50" step="1" value="18">

            <label><span>Fourier q-Harmonics:</span> <span id="lbl-harmonics">6</span></label>
            <input type="range" id="param-harmonics" min="3" max="16" step="1" value="6">
        </div>
    </div>

    <canvas id="canvas"></canvas>

    <script>
        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x020617, 0.02);

        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
        camera.position.set(20, 18, 30);

        const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('canvas'), antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;

        // Ambient & Directional Lighting
        const ambLight = new THREE.AmbientLight(0x38bdf8, 0.4);
        scene.add(ambLight);

        const dirLight1 = new THREE.DirectionalLight(0xf59e0b, 1.3);
        dirLight1.position.set(25, 35, 20);
        scene.add(dirLight1);

        const dirLight2 = new THREE.DirectionalLight(0xec4899, 0.8);
        dirLight2.position.set(-25, -20, -20);
        scene.add(dirLight2);

        const grid = new THREE.GridHelper(50, 50, 0x334155, 0x1e293b);
        grid.position.y = -6;
        scene.add(grid);

        let modularMesh, qSpirals = [], cuspCones = [];

        function buildSerreModularityManifold(weight, level, harmonics) {
            if (modularMesh) scene.remove(modularMesh);
            qSpirals.forEach(s => scene.remove(s));
            cuspCones.forEach(c => scene.remove(c));
            qSpirals = [];
            cuspCones = [];

            // Parametric Modular Hyperbolic Tessellation Surface:
            // z = (y / (x^2 + y^2)) modulated by Hecke Fourier coefficients
            const uSegs = 60, vSegs = 60;
            const geom = new THREE.BufferGeometry();
            const positions = [];
            const colors = [];

            const color1 = new THREE.Color(0xf59e0b); // Amber
            const color2 = new THREE.Color(0xef4444); // Red
            const color3 = new THREE.Color(0x3b82f6); // Blue

            for (let i = 0; i <= uSegs; i++) {
                const u = (i / uSegs) * 4 - 2; // -2 to 2
                for (let j = 0; j <= vSegs; j++) {
                    const v = (j / vSegs) * 3 + 0.4; // 0.4 to 3.4 (upper half plane)

                    const r2 = u * u + v * v;
                    const x = u * 5.0;
                    const heckeWave = Math.sin(u * harmonics) * Math.exp(-v * (weight * 0.2));
                    const y = (Math.log(v) * 2.5 + heckeWave * 2.0);
                    const z = (v - 1.5) * 5.0;

                    positions.push(x, y, z);

                    const t = (y + 4) / 8;
                    const c = color1.clone().lerp(color2, Math.max(0, Math.min(1, t)));
                    colors.push(c.r, c.g, c.b);
                }
            }

            const indices = [];
            for (let i = 0; i < uSegs; i++) {
                for (let j = 0; j < vSegs; j++) {
                    const a = i * (vSegs + 1) + j;
                    const b = (i + 1) * (vSegs + 1) + j;
                    const c = (i + 1) * (vSegs + 1) + (j + 1);
                    const d = i * (vSegs + 1) + (j + 1);
                    indices.push(a, b, d);
                    indices.push(b, c, d);
                }
            }

            geom.setIndex(indices);
            geom.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
            geom.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
            geom.computeVertexNormals();

            const mat = new THREE.MeshStandardMaterial({
                vertexColors: true,
                side: THREE.DoubleSide,
                roughness: 0.3,
                metalness: 0.65,
                transparent: true,
                opacity: 0.90,
                wireframe: false
            });

            modularMesh = new THREE.Mesh(geom, mat);
            scene.add(modularMesh);

            // Fourier q-Expansion Spirals (q = e^{2\pi i \tau})
            for (let h = 1; h <= harmonics; h++) {
                const curvePts = [];
                const maxTurns = 3.0;
                for (let step = 0; step <= 80; step++) {
                    const t = (step / 80) * maxTurns * Math.PI * 2;
                    const rad = Math.exp(-step * 0.03 * (weight * 0.5)) * (8.0 + h * 0.5);
                    const sx = Math.cos(t * h * 0.5) * rad;
                    const sy = (step / 80) * 10 - 5;
                    const sz = Math.sin(t * h * 0.5) * rad;
                    curvePts.push(new THREE.Vector3(sx, sy, sz));
                }

                const curve = new THREE.CatmullRomCurve3(curvePts);
                const tubeGeom = new THREE.TubeGeometry(curve, 64, 0.1, 8, false);
                const tubeMat = new THREE.MeshStandardMaterial({
                    color: 0x38bdf8,
                    emissive: 0x0369a1,
                    roughness: 0.2
                });
                const tube = new THREE.Mesh(tubeGeom, tubeMat);
                scene.add(tube);
                qSpirals.push(tube);
            }

            // Serre Weight Cusp Cones at modular cusps
            const coneGeom = new THREE.ConeGeometry(2.0, 6.0, 16);
            const coneMat = new THREE.MeshStandardMaterial({
                color: 0x10b981,
                wireframe: true,
                transparent: true,
                opacity: 0.7
            });

            const topCusp = new THREE.Mesh(coneGeom, coneMat);
            topCusp.position.set(0, 6, 0);
            scene.add(topCusp);
            cuspCones.push(topCusp);
        }

        buildSerreModularityManifold(2, 18, 6);

        // UI Listeners
        const paramWeight = document.getElementById('param-weight');
        const paramLevel = document.getElementById('param-level');
        const paramHarmonics = document.getElementById('param-harmonics');

        function updateParams() {
            const w = parseInt(paramWeight.value);
            const l = parseInt(paramLevel.value);
            const h = parseInt(paramHarmonics.value);

            document.getElementById('lbl-weight').innerText = w;
            document.getElementById('lbl-level').innerText = l;
            document.getElementById('lbl-harmonics').innerText = h;

            document.getElementById('val-weight').innerText = "k = " + w;
            document.getElementById('val-level').innerText = "N = " + l;

            buildSerreModularityManifold(w, l, h);
        }

        paramWeight.addEventListener('input', updateParams);
        paramLevel.addEventListener('input', updateParams);
        paramHarmonics.addEventListener('input', updateParams);

        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });

        // Animation Loop
        let clock = new THREE.Clock();
        function animate() {
            requestAnimationFrame(animate);
            const t = clock.getElapsedTime();

            if (modularMesh) {
                modularMesh.rotation.y = t * 0.1;
            }
            qSpirals.forEach((s, idx) => {
                s.rotation.y = -t * 0.15 * (idx % 2 === 0 ? 1 : -1);
            });
            cuspCones.forEach(c => {
                c.rotation.y = t * 0.25;
            });

            controls.update();
            renderer.render(scene, camera);
        }
        animate();
    </script>
</body>
</html>
"""

def main():
    out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "assets")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "serre_modularity_manifold_3d.html")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(HTML_CONTENT)

    print(f"[✓] Generated 3D Serre Modularity Manifold Visualizer: {out_path} ({len(HTML_CONTENT)} bytes)")

if __name__ == "__main__":
    main()
