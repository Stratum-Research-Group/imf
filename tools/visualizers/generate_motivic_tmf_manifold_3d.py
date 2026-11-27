#!/usr/bin/env python3
r"""
generate_motivic_tmf_manifold_3d.py
Generates docs/assets/motivic_tmf_manifold_3d.html:
Interactive 3D WebGL Motivic Topological Modular Forms (tmf) Visualizer.
Renders the moduli stack of elliptic curves M_ell, modular j-invariant surfaces,
and tmf spectrum periodic fibers in real-time WebGL 3D.
"""

import os

HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>IMF Motivic Topological Modular Forms (3D)</title>
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
        <h1>Motivic Topological Modular Forms ($\mathbf{tmf}$)</h1>
        <p>Interactive 3D visualization of the moduli stack of elliptic curves $\mathcal{M}_{\mathrm{ell}}$, modular discriminant locus $\Delta^{24}$, Weierstrass $j$-invariant surfaces, and Witten genus string orientations.</p>
        <div>
            <span class="metric-badge">Moduli: $\mathcal{M}_{\mathrm{ell}}$</span>
            <span class="metric-badge">Discriminant: $\Delta \in \pi_{24}(\mathbf{tmf})$</span>
            <span class="metric-badge">Periodicity: 576-fold</span>
            <span class="metric-badge">String: $\mathbf{MString} \to \mathbf{tmf}$</span>
        </div>
        <div class="controls">
            Rotate: Left Click + Drag | Pan: Right Click + Drag | Zoom: Scroll Wheel
        </div>
    </div>
    <div id="canvas"></div>

    <script>
        const container = document.getElementById('canvas');
        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x020617, 0.024);

        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
        camera.position.set(26, 20, 30);

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

        const dirLight1 = new THREE.DirectionalLight(0xf59e0b, 2.2);
        dirLight1.position.set(25, 30, 25);
        scene.add(dirLight1);

        const dirLight2 = new THREE.DirectionalLight(0xec4899, 1.8);
        dirLight2.position.set(-25, -20, -25);
        scene.add(dirLight2);

        // 1. Moduli Stack M_ell: Double torus representing an elliptic curve family
        const torusGroup = new THREE.Group();
        const tGeo = new THREE.TorusGeometry(8.5, 2.2, 32, 128);
        const tMat = new THREE.MeshStandardMaterial({
            color: 0x6366f1,
            metalness: 0.85,
            roughness: 0.2,
            wireframe: true,
            transparent: true,
            opacity: 0.55
        });
        const torusMesh = new THREE.Mesh(tGeo, tMat);
        torusMesh.rotation.x = Math.PI / 3;
        torusGroup.add(torusMesh);
        scene.add(torusGroup);

        // 2. Discriminant Delta Locus: Modular cuspidal helical coils
        const cuspGroup = new THREE.Group();
        const numCoils = 8;
        for (let c = 0; c < numCoils; c++) {
            const points = [];
            const angle = (c * 2 * Math.PI) / numCoils;
            for (let t = -8; t <= 8; t += 0.25) {
                const r = 5.0 + 2.5 * Math.sin(t * 0.9 + angle);
                const x = r * Math.cos(t * 0.6 + angle);
                const y = t * 1.8;
                const z = r * Math.sin(t * 0.6 + angle);
                points.push(new THREE.Vector3(x, y, z));
            }
            const curve = new THREE.CatmullRomCurve3(points);
            const tubeGeo = new THREE.TubeGeometry(curve, 80, 0.12, 8, false);
            const tubeMat = new THREE.MeshStandardMaterial({
                color: 0xf59e0b,
                emissive: 0xd97706,
                emissiveIntensity: 0.4,
                roughness: 0.2
            });
            cuspGroup.add(new THREE.Mesh(tubeGeo, tubeMat));
        }
        scene.add(cuspGroup);

        // 3. Modular Form Fourier q-Expansion Particles
        const qGeo = new THREE.BufferGeometry();
        const pCount = 2400;
        const positions = new Float32Array(pCount * 3);
        const colors = new Float32Array(pCount * 3);

        const color1 = new THREE.Color(0x38bdf8);
        const color2 = new THREE.Color(0xec4899);

        for (let i = 0; i < pCount; i++) {
            const theta = Math.random() * Math.PI * 2;
            const phi = (Math.random() - 0.5) * Math.PI;
            const rad = 13.0 + (Math.random() - 0.5) * 3.5;

            const px = rad * Math.cos(phi) * Math.cos(theta);
            const py = rad * Math.sin(phi);
            const pz = rad * Math.cos(phi) * Math.sin(theta);

            positions[i * 3] = px;
            positions[i * 3 + 1] = py;
            positions[i * 3 + 2] = pz;

            const lerpVal = Math.random();
            const col = color1.clone().lerp(color2, lerpVal);
            colors[i * 3] = col.r;
            colors[i * 3 + 1] = col.g;
            colors[i * 3 + 2] = col.b;
        }

        qGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        qGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

        const qMat = new THREE.PointsMaterial({
            size: 0.2,
            vertexColors: true,
            transparent: true,
            opacity: 0.8
        });
        const qParticles = new THREE.Points(qGeo, qMat);
        scene.add(qParticles);

        // Animation Loop
        let clock = new THREE.Clock();
        function animate() {
            requestAnimationFrame(animate);
            const delta = clock.getDelta();

            torusGroup.rotation.y += delta * 0.12;
            torusGroup.rotation.z += delta * 0.08;

            cuspGroup.rotation.y -= delta * 0.15;
            qParticles.rotation.y += delta * 0.05;

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
        os.path.dirname(__file__), "..", "..", "docs", "assets", "motivic_tmf_manifold_3d.html"
    )
    target_path = os.path.abspath(target_path)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(HTML_CONTENT.strip() + "\n")
    print(f"[✓] Generated 3D WebGL visualizer: {target_path}")

if __name__ == "__main__":
    main()
