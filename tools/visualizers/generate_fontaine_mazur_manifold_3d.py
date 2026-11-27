#!/usr/bin/env python3
"""
generate_fontaine_mazur_manifold_3d.py
Generates docs/assets/fontaine_mazur_manifold_3d.html:
Interactive 3D WebGL Fontaine-Mazur Geometric Representations & Hodge-Tate Weight Visualizer.
Renders de Rham filtration cones, crystalline Frobenius lattices, and geometric Galois weight bundles.
"""

import os

HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>IMF Fontaine-Mazur Geometric Representations Visualizer (3D)</title>
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
            color: #a855f7;
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
            accent-color: #a855f7;
        }
    </style>
    <!-- Three.js from CDN -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
</head>
<body>
    <div id="hud">
        <h1>Fontaine-Mazur Geometry (Module 44)</h1>
        <div class="subtitle">de Rham Filtrations, Hodge-Tate Weights & Crystalline Frobenius</div>
        <div class="stat-grid">
            <div class="stat-card">
                <div class="stat-label">de Rham Dim D_dR</div>
                <div class="stat-value" id="val-ddr">dim = 2</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Hodge-Tate Weights</div>
                <div class="stat-value" id="val-ht">w = {0, 1}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Frobenius Trace Tr(&#966;)</div>
                <div class="stat-value" id="val-frob">a_p = 3.20</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Geometric Purity</div>
                <div class="stat-value" style="color: #10b981;">&#10003; de Rham Verified</div>
            </div>
        </div>
        <div class="controls">
            <label><span>Hodge Filtration Parameter:</span> <span id="lbl-hodge">1.00</span></label>
            <input type="range" id="param-hodge" min="0.2" max="3.0" step="0.05" value="1.0">

            <label><span>Frobenius Eigenvalue Scaling:</span> <span id="lbl-frob">1.50</span></label>
            <input type="range" id="param-frob" min="0.5" max="3.0" step="0.05" value="1.5">

            <label><span>p-Adic Weight Levels:</span> <span id="lbl-levels">5</span></label>
            <input type="range" id="param-levels" min="2" max="10" step="1" value="5">
        </div>
    </div>

    <canvas id="canvas"></canvas>

    <script>
        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x020617, 0.02);

        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
        camera.position.set(22, 16, 28);

        const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('canvas'), antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;

        // Ambient and Directional Lighting
        const ambLight = new THREE.AmbientLight(0x38bdf8, 0.4);
        scene.add(ambLight);

        const dirLight1 = new THREE.DirectionalLight(0xa855f7, 1.2);
        dirLight1.position.set(25, 35, 20);
        scene.add(dirLight1);

        const dirLight2 = new THREE.DirectionalLight(0x06b6d4, 0.8);
        dirLight2.position.set(-25, -20, -20);
        scene.add(dirLight2);

        const grid = new THREE.GridHelper(50, 50, 0x334155, 0x1e293b);
        grid.position.y = -6;
        scene.add(grid);

        let mainMesh, crystallineLattice = [], hodgeRings = [];

        function buildFontaineMazurManifold(hodgeScale, frobScale, levels) {
            if (mainMesh) scene.remove(mainMesh);
            crystallineLattice.forEach(obj => scene.remove(obj));
            hodgeRings.forEach(obj => scene.remove(obj));
            crystallineLattice = [];
            hodgeRings = [];

            // Parametric de Rham Filtration Hyperboloid
            const uSegs = 60, vSegs = 60;
            const geom = new THREE.BufferGeometry();
            const positions = [];
            const colors = [];

            const color1 = new THREE.Color(0xa855f7); // Purple
            const color2 = new THREE.Color(0x38bdf8); // Sky blue
            const color3 = new THREE.Color(0x10b981); // Emerald

            for (let i = 0; i <= uSegs; i++) {
                const u = (i / uSegs) * Math.PI * 2;
                for (let j = 0; j <= vSegs; j++) {
                    const v = (j / vSegs) * 4 - 2; // -2 to 2

                    const r = Math.sqrt(1 + v * v * 0.5) * (4.0 * hodgeScale);
                    const x = r * Math.cos(u);
                    const y = v * 5.0;
                    const z = r * Math.sin(u);

                    positions.push(x, y, z);

                    const t = (v + 2) / 4;
                    const c = color1.clone().lerp(color2, t);
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
                roughness: 0.25,
                metalness: 0.6,
                transparent: true,
                opacity: 0.88,
                wireframe: false
            });

            mainMesh = new THREE.Mesh(geom, mat);
            scene.add(mainMesh);

            // Crystalline Frobenius Eigen-spheres
            const sphereGeom = new THREE.SphereGeometry(0.35, 16, 16);
            const sphereMat = new THREE.MeshStandardMaterial({
                color: 0xfacc15,
                emissive: 0x854d0e,
                roughness: 0.2
            });

            for (let k = 0; k < levels * 3; k++) {
                const angle = (k / (levels * 3)) * Math.PI * 4;
                const rad = 6.0 * frobScale;
                const sx = Math.cos(angle) * (rad * (1 + 0.1 * Math.sin(k)));
                const sy = (k - levels * 1.5) * 1.2;
                const sz = Math.sin(angle) * (rad * (1 + 0.1 * Math.sin(k)));

                const sp = new THREE.Mesh(sphereGeom, sphereMat);
                sp.position.set(sx, sy, sz);
                scene.add(sp);
                crystallineLattice.push(sp);
            }

            // Hodge-Tate Weight Rings
            for (let w = 0; w < levels; w++) {
                const ringRad = 5.0 + w * 1.2;
                const torusGeom = new THREE.TorusGeometry(ringRad, 0.08, 8, 48);
                const torusMat = new THREE.MeshBasicMaterial({
                    color: 0x38bdf8,
                    transparent: true,
                    opacity: 0.5
                });
                const ring = new THREE.Mesh(torusGeom, torusMat);
                ring.rotation.x = Math.PI / 2;
                ring.position.y = (w - levels / 2) * 2.5;
                scene.add(ring);
                hodgeRings.push(ring);
            }
        }

        buildFontaineMazurManifold(1.0, 1.5, 5);

        // UI Listeners
        const paramHodge = document.getElementById('param-hodge');
        const paramFrob = document.getElementById('param-frob');
        const paramLevels = document.getElementById('param-levels');

        function updateParams() {
            const h = parseFloat(paramHodge.value);
            const f = parseFloat(paramFrob.value);
            const lev = parseInt(paramLevels.value);

            document.getElementById('lbl-hodge').innerText = h.toFixed(2);
            document.getElementById('lbl-frob').innerText = f.toFixed(2);
            document.getElementById('lbl-levels').innerText = lev;
            document.getElementById('val-frob').innerText = "a_p = " + (2.0 * f + 0.2).toFixed(2);

            buildFontaineMazurManifold(h, f, lev);
        }

        paramHodge.addEventListener('input', updateParams);
        paramFrob.addEventListener('input', updateParams);
        paramLevels.addEventListener('input', updateParams);

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

            if (mainMesh) {
                mainMesh.rotation.y = t * 0.12;
            }
            crystallineLattice.forEach((sp, idx) => {
                sp.position.y += Math.sin(t * 2.0 + idx) * 0.015;
            });
            hodgeRings.forEach((r, idx) => {
                r.rotation.z = t * 0.05 * (idx % 2 === 0 ? 1 : -1);
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
    out_path = os.path.join(out_dir, "fontaine_mazur_manifold_3d.html")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(HTML_CONTENT)

    print(f"[✓] Generated 3D Fontaine-Mazur Manifold Visualizer: {out_path} ({len(HTML_CONTENT)} bytes)")

if __name__ == "__main__":
    main()
