#!/usr/bin/env python3
r"""
generate_motivic_adams_novikov_manifold_3d.py
Generates docs/assets/motivic_adams_novikov_manifold_3d.html:
Interactive 3D WebGL Motivic Adams-Novikov Spectral Sequence Visualizer.
Renders the 3-graded spectral sequence lattice (s, t, w), differential vectors
d_r: E_r^{s, t, w} -> E_r^{s+r, t+r-1, w}, and stable homotopy convergence sheets.
"""

import os

HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>IMF Motivic Adams-Novikov Spectral Sequence (3D)</title>
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
            font-size: 1.15rem;
            margin: 0 0 8px 0;
            color: #38bdf8;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }
        p {
            font-size: 0.82rem;
            line-height: 1.45;
            color: #94a3b8;
            margin: 4px 0 12px 0;
        }
        .metric-badge {
            display: inline-block;
            background: #1e293b;
            border: 1px solid #475569;
            border-radius: 4px;
            padding: 3px 8px;
            margin-right: 6px;
            margin-bottom: 6px;
            font-size: 0.75rem;
            font-weight: 600;
            color: #38bdf8;
        }
        .controls {
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid #334155;
            font-size: 0.75rem;
            color: #64748b;
        }
    </style>
    <!-- Three.js from unpkg -->
    <script src="https://unpkg.com/three@0.160.0/build/three.min.js"></script>
    <script src="https://unpkg.com/three@0.160.0/examples/js/controls/OrbitControls.js"></script>
</head>
<body>
    <div id="hud">
        <h1>Motivic Adams-Novikov Spectral Sequence (MANSS)</h1>
        <p>Interactive 3D lattice representation of the $E_2$-page Ext groups $\operatorname{Ext}_{\mathbf{MGL}_{*,*}(\mathbf{MGL})}^{s, t, w}$, differential vector cascades $d_r: E_r^{s, t, w} \to E_r^{s+r, t+r-1, w}$, and $\pi_{*,*}(\mathbf{1})$ stable convergence sheets.</p>
        <div>
            <span class="metric-badge">Filtration: $s \ge 0$</span>
            <span class="metric-badge">Topological: $t \ge 0$</span>
            <span class="metric-badge">Weight: $w \in \mathbb{Z}$</span>
            <span class="metric-badge">Differentials: $d_r \circ d_r = 0$</span>
        </div>
        <div class="controls">
            Rotate: Left Click + Drag | Pan: Right Click + Drag | Zoom: Scroll Wheel
        </div>
    </div>
    <div id="canvas"></div>

    <script>
        const container = document.getElementById('canvas');
        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x020617, 0.022);

        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
        camera.position.set(28, 22, 32);

        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        container.appendChild(renderer.domElement);

        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;

        // Lighting
        const ambientLight = new THREE.AmbientLight(0x38bdf8, 0.85);
        scene.add(ambientLight);

        const dirLight1 = new THREE.DirectionalLight(0xa855f7, 2.2);
        dirLight1.position.set(25, 35, 25);
        scene.add(dirLight1);

        const dirLight2 = new THREE.DirectionalLight(0x06b6d4, 1.6);
        dirLight2.position.set(-25, -20, -25);
        scene.add(dirLight2);

        // 1. Spectral Sequence Lattice: 3D grid of nodes representing E_2^{s, t, w}
        const latticeGroup = new THREE.Group();
        const nodeGeo = new THREE.SphereGeometry(0.22, 12, 12);
        const nodeMat1 = new THREE.MeshStandardMaterial({ color: 0x38bdf8, metalness: 0.8, roughness: 0.2 });
        const nodeMat2 = new THREE.MeshStandardMaterial({ color: 0xf43f5e, metalness: 0.8, roughness: 0.2 });

        for (let s = 0; s < 8; s++) {
            for (let t = 0; t < 12; t++) {
                for (let w = 0; w < 4; w++) {
                    const mesh = new THREE.Mesh(nodeGeo, (s % 2 === 0) ? nodeMat1 : nodeMat2);
                    mesh.position.set((t - s) * 2.2 - 10, s * 2.5 - 8, w * 4.0 - 6);
                    latticeGroup.add(mesh);
                }
            }
        }
        scene.add(latticeGroup);

        // 2. Differential Vector Cascades: Arrows representing d_2: (s, t, w) -> (s+2, t+1, w)
        const arrowsGroup = new THREE.Group();
        for (let s = 0; s < 6; s += 2) {
            for (let t = 2; t < 10; t += 2) {
                for (let w = 0; w < 3; w++) {
                    const from = new THREE.Vector3((t - s) * 2.2 - 10, s * 2.5 - 8, w * 4.0 - 6);
                    const to = new THREE.Vector3((t + 1 - (s + 2)) * 2.2 - 10, (s + 2) * 2.5 - 8, w * 4.0 - 6);
                    const dir = new THREE.Vector3().subVectors(to, from);
                    const length = dir.length();
                    dir.normalize();
                    const arrow = new THREE.ArrowHelper(dir, from, length, 0x10b981, 0.6, 0.3);
                    arrowsGroup.add(arrow);
                }
            }
        }
        scene.add(arrowsGroup);

        // 3. Convergence Sheets: Semi-transparent planes representing E_infinity filtration
        const sheetsGroup = new THREE.Group();
        for (let w = 0; w < 4; w++) {
            const planeGeo = new THREE.PlaneGeometry(28, 20);
            const planeMat = new THREE.MeshBasicMaterial({
                color: (w % 2 === 0) ? 0x6366f1 : 0xec4899,
                side: THREE.DoubleSide,
                transparent: true,
                opacity: 0.15,
                wireframe: true
            });
            const plane = new THREE.Mesh(planeGeo, planeMat);
            plane.position.set(0, 0, w * 4.0 - 6);
            sheetsGroup.add(plane);
        }
        scene.add(sheetsGroup);

        // Animation Loop
        let clock = new THREE.Clock();
        function animate() {
            requestAnimationFrame(animate);
            const delta = clock.getDelta();

            latticeGroup.rotation.y += delta * 0.08;
            arrowsGroup.rotation.y += delta * 0.08;
            sheetsGroup.rotation.y += delta * 0.08;

            controls.update();
            renderer.render(scene, camera);
        }
        animate();

        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });
    </script>
</body>
</html>
"""

def main():
    target_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "docs", "assets", "motivic_adams_novikov_manifold_3d.html"
    )
    target_path = os.path.abspath(target_path)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(HTML_CONTENT.strip() + "\n")
    print(f"[✓] Generated 3D WebGL visualizer: {target_path}")

if __name__ == "__main__":
    main()
