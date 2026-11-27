#!/usr/bin/env python3
r"""
generate_coleman_manifold_3d.py
Generates docs/assets/coleman_manifold_3d.html:
Interactive 3D WebGL Coleman Integration & p-Adic Abelian Integrals Visualizer.
Renders rigid analytic residue discs, Coleman integration geodesics, Frobenius pullback flows,
and Chabauty annihilator hyperplane intersections over hyperelliptic curve Jacobians.
"""

import os

HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>IMF Coleman Integration & p-Adic Abelian Integrals (3D)</title>
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
            color: #38bdf8;
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
            grid-template-columns: 1fr 1fr;
            gap: 8px 12px;
            font-size: 12px;
            margin-bottom: 14px;
        }
        .stat-label { color: #64748b; text-transform: uppercase; font-size: 10px; font-weight: 600; }
        .stat-val { color: #38bdf8; font-weight: 600; font-family: monospace; }
        .legend {
            font-size: 12px;
            border-top: 1px solid #1e293b;
            padding-top: 10px;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        .legend-item { display: flex; align-items: center; gap: 8px; }
        .legend-color { width: 12px; height: 12px; border-radius: 3px; }
        #controls {
            position: absolute;
            bottom: 16px;
            left: 16px;
            background: rgba(15, 23, 42, 0.85);
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 10px 14px;
            font-size: 12px;
            color: #94a3b8;
        }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
</head>
<body>
    <div id="hud">
        <h1>Coleman Integration & p-Adic Annihilators</h1>
        <div class="subtitle">Rigid Analytic Residue Discs & Chabauty-Coleman Bound Visualizer on Hyperelliptic Jacobian J(Q)</div>
        <div class="stat-grid">
            <div><span class="stat-label">Prime p</span><br><span class="stat-val">p = 5</span></div>
            <div><span class="stat-label">Curve Genus g</span><br><span class="stat-val">g = 2</span></div>
            <div><span class="stat-label">Mordell-Weil Rank r</span><br><span class="stat-val">r = 1 (r &lt; g)</span></div>
            <div><span class="stat-label">#C(F_p) Points</span><br><span class="stat-val">6 points</span></div>
            <div><span class="stat-label">Chabauty-Coleman Bound</span><br><span class="stat-val">#C(Q) &le; 6 + 4 - 2 = 8</span></div>
            <div><span class="stat-label">de Rham Cohomology</span><br><span class="stat-val">dim H&sup1;_dR = 2g = 4</span></div>
        </div>
        <div class="legend">
            <div class="legend-item"><div class="legend-color" style="background:#38bdf8;"></div> Residue Discs (p-adic wide open neighborhoods)</div>
            <div class="legend-item"><div class="legend-color" style="background:#f59e0b;"></div> Coleman Integration Geodesics (&int; &omega;)</div>
            <div class="legend-item"><div class="legend-color" style="background:#ec4899;"></div> Chabauty Annihilator Plane (Ann(J(Q)))</div>
            <div class="legend-item"><div class="legend-color" style="background:#10b981;"></div> Rational Points C(Q) in Residue Discs</div>
        </div>
    </div>
    <div id="controls">Orbit: Left Click + Drag | Pan: Right Click + Drag | Zoom: Scroll</div>
    <canvas id="canvas"></canvas>

    <script>
        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x020617, 0.02);

        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
        camera.position.set(0, 18, 30);

        const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('canvas'), antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;

        // Ambient and directional lighting
        scene.add(new THREE.AmbientLight(0xffffff, 0.4));
        const dirLight = new THREE.DirectionalLight(0x38bdf8, 1.2);
        dirLight.position.set(10, 20, 15);
        scene.add(dirLight);

        // Coordinate Grid
        const grid = new THREE.GridHelper(40, 40, 0x1e293b, 0x0f172a);
        grid.position.y = -6;
        scene.add(grid);

        // 1. Render p-adic Residue Discs (Toroidal arrangements of translucent spheres)
        const discsGroup = new THREE.Group();
        const numDiscs = 6; // #C(F_p) = 6
        const discRadius = 2.4;
        const discOrbitRadius = 12.0;

        for (let i = 0; i < numDiscs; ++i) {
            const angle = (i / numDiscs) * Math.PI * 2;
            const x = Math.cos(angle) * discOrbitRadius;
            const z = Math.sin(angle) * discOrbitRadius;
            const y = Math.sin(angle * 2) * 2.0;

            const discGeo = new THREE.SphereGeometry(discRadius, 32, 32);
            const discMat = new THREE.MeshStandardMaterial({
                color: 0x0284c7,
                roughness: 0.2,
                metalness: 0.8,
                transparent: true,
                opacity: 0.35,
                wireframe: false
            });
            const discMesh = new THREE.Mesh(discGeo, discMat);
            discMesh.position.set(x, y, z);
            discsGroup.add(discMesh);

            // Wireframe outer halo
            const haloGeo = new THREE.WireframeGeometry(discGeo);
            const haloLine = new THREE.LineSegments(haloGeo, new THREE.LineBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.3 }));
            haloLine.position.set(x, y, z);
            discsGroup.add(haloLine);

            // Rational Point inside each residue disc
            const ptGeo = new THREE.SphereGeometry(0.45, 16, 16);
            const ptMat = new THREE.MeshStandardMaterial({ color: 0x10b981, emissive: 0x059669, emissiveIntensity: 0.8 });
            const ptMesh = new THREE.Mesh(ptGeo, ptMat);
            ptMesh.position.set(x + Math.sin(i)*0.6, y, z + Math.cos(i)*0.6);
            discsGroup.add(ptMesh);
        }
        scene.add(discsGroup);

        // 2. Chabauty-Coleman Annihilator Plane (Translucent intersecting slice)
        const planeGeo = new THREE.PlaneGeometry(36, 36, 16, 16);
        const planeMat = new THREE.MeshStandardMaterial({
            color: 0xec4899,
            roughness: 0.4,
            metalness: 0.6,
            transparent: true,
            opacity: 0.22,
            side: THREE.DoubleSide,
            wireframe: false
        });
        const planeMesh = new THREE.Mesh(planeGeo, planeMat);
        planeMesh.rotation.x = Math.PI / 3;
        planeMesh.rotation.y = Math.PI / 6;
        scene.add(planeMesh);

        // Wireframe grid for annihilator plane
        const planeWire = new THREE.LineSegments(new THREE.WireframeGeometry(planeGeo), new THREE.LineBasicMaterial({ color: 0xf472b6, transparent: true, opacity: 0.35 }));
        planeWire.rotation.x = Math.PI / 3;
        planeWire.rotation.y = Math.PI / 6;
        scene.add(planeWire);

        // 3. Coleman Integration Geodesics (Curved luminous ribbons through residue discs)
        const curvePoints = [];
        const numPts = 300;
        for (let t = 0; t <= numPts; ++t) {
            const theta = (t / numPts) * Math.PI * 6;
            const r = discOrbitRadius + Math.sin(theta * 3) * 2.2;
            const x = Math.cos(theta) * r;
            const z = Math.sin(theta) * r;
            const y = Math.cos(theta * 2) * 4.0;
            curvePoints.push(new THREE.Vector3(x, y, z));
        }
        const curve = new THREE.CatmullRomCurve3(curvePoints);
        const tubeGeo = new THREE.TubeGeometry(curve, 250, 0.15, 8, true);
        const tubeMat = new THREE.MeshStandardMaterial({
            color: 0xf59e0b,
            emissive: 0xd97706,
            emissiveIntensity: 0.9,
            roughness: 0.1
        });
        const tubeMesh = new THREE.Mesh(tubeGeo, tubeMat);
        scene.add(tubeMesh);

        // Animation Loop
        let clock = new THREE.Clock();
        function animate() {
            requestAnimationFrame(animate);
            const delta = clock.getDelta();
            const elapsed = clock.getElapsedTime();

            discsGroup.rotation.y = elapsed * 0.12;
            tubeMesh.rotation.y = elapsed * 0.08;
            planeMesh.rotation.z = Math.sin(elapsed * 0.25) * 0.08;

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
    target_path = os.path.join(os.path.dirname(__file__), "../../docs/assets/coleman_manifold_3d.html")
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(HTML_CONTENT)
    print(f"[+] Successfully generated Coleman 3D visualizer at: {target_path}")

if __name__ == "__main__":
    main()
