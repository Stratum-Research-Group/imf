#!/usr/bin/env python3
"""
generate_bruhat_tits_building_3d.py
Generates docs/assets/bruhat_tits_building_3d.html:
Interactive 3D WebGL Bruhat-Tits Building & Polysimplicial Apartment Visualizer.
Features affine Weyl group tiling, branching apartments, and retraction mappings.
"""

import os

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>IMF Bruhat-Tits Building & Apartment Visualizer (3D)</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            padding: 0;
            background: #020409;
            color: #e6edf3;
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
            background: rgba(10, 15, 25, 0.88);
            border: 1px solid #1f293d;
            border-radius: 8px;
            padding: 18px 22px;
            max-width: 440px;
            backdrop-filter: blur(8px);
            box-shadow: 0 8px 32px rgba(0,0,0,0.6);
            pointer-events: auto;
        }
        h1 {
            margin: 0 0 8px 0;
            font-size: 19px;
            font-weight: 700;
            color: #00f2fe;
            letter-spacing: 0.5px;
        }
        .subtitle {
            font-size: 12px;
            color: #79c0ff;
            margin-bottom: 12px;
            line-height: 1.4;
        }
        .metric-row {
            display: flex;
            justify-content: space-between;
            margin: 6px 0;
            font-size: 13px;
            border-bottom: 1px dashed rgba(255,255,255,0.08);
            padding-bottom: 4px;
        }
        .metric-label {
            color: #8b949e;
        }
        .metric-value {
            font-family: monospace;
            font-weight: bold;
            color: #38ef7d;
        }
        .controls {
            margin-top: 14px;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        button {
            background: #16243b;
            color: #58a6ff;
            border: 1px solid #30363d;
            border-radius: 4px;
            padding: 6px 12px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s;
        }
        button:hover {
            background: #1f385c;
            color: #fff;
            border-color: #58a6ff;
        }
        #legend {
            position: absolute;
            bottom: 16px;
            right: 16px;
            background: rgba(10, 15, 25, 0.85);
            border: 1px solid #1f293d;
            border-radius: 6px;
            padding: 12px 16px;
            font-size: 12px;
            color: #8b949e;
            backdrop-filter: blur(6px);
        }
        .dot {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 6px;
        }
    </style>
</head>
<body>
    <div id="hud">
        <h1>Bruhat-Tits Building ℬ(SL₃, ℚₚ)</h1>
        <div class="subtitle">Polysimplicial Apartment Complex &bull; Affine Coxeter System Ã₂ &bull; Non-Archimedean Retractions</div>
        <div class="metric-row">
            <span class="metric-label">Affine Weyl Group:</span>
            <span class="metric-value">Ã₂ ≅ W(A₂) ⋉ ℤ²</span>
        </div>
        <div class="metric-row">
            <span class="metric-label">Apartment Geometry:</span>
            <span class="metric-value">Triangular Simplicial Tesselation</span>
        </div>
        <div class="metric-row">
            <span class="metric-label">Residue Field Degree:</span>
            <span class="metric-value" id="val-degree">p = 3 (Branching = 4)</span>
        </div>
        <div class="metric-row">
            <span class="metric-label">Current Chamber ID:</span>
            <span class="metric-value" id="chamber-id">Δ₀ (Base Alcove)</span>
        </div>
        <div class="metric-row">
            <span class="metric-label">Curvature Bound:</span>
            <span class="metric-value">CAT(0) Non-Positive</span>
        </div>
        <div class="metric-row">
            <span class="metric-label">Affine Isometry Invariant:</span>
            <span class="metric-value">‖s_{α,c}(x) - s_{α,c}(y)‖ = ‖x - y‖ (Mathlib 30)</span>
        </div>
        <div class="controls">
            <button id="btn-toggle-apartments">Toggle Branching</button>
            <button id="btn-toggle-walk">Pause / Step Walk</button>
            <button id="btn-retract">Trigger Retraction</button>
            <button id="btn-reset">Reset Camera</button>
        </div>
    </div>

    <div id="legend">
        <div><span class="dot" style="background: #00f2fe;"></span> Base Apartment A₀</div>
        <div><span class="dot" style="background: #ff007f;"></span> Branching Apartments A₁, A₂, A₃</div>
        <div><span class="dot" style="background: #38ef7d;"></span> Active Geodesic Token Ray</div>
        <div><span class="dot" style="background: #ffcc00;"></span> Affine Reflection Walls</div>
    </div>

    <canvas id="canvas"></canvas>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
        const canvas = document.getElementById('canvas');
        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x020409, 0.04);

        const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 100);
        camera.position.set(0, 3.2, 5.8);

        const renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

        // Group container for all apartments
        const buildingGroup = new THREE.Group();
        scene.add(buildingGroup);

        // Function to create an affine triangular apartment (A2 affine Weyl tiling)
        function createApartment(colorHex, opacityVal, yOffset, rotAngle) {
            const apt = new THREE.Group();
            const R = 3.5;
            const step = 0.8;
            const h = step * Math.sqrt(3) / 2;

            // Generate triangular mesh grid
            const vertices = [];
            const colors = [];
            const baseColor = new THREE.Color(colorHex);

            for (let q = -4; q <= 4; q++) {
                for (let r = -4; r <= 4; r++) {
                    const x = (q + r * 0.5) * step;
                    const z = (r * h);
                    if (x*x + z*z > R*R) continue;

                    // Triangle 1
                    vertices.push(x, 0, z);
                    vertices.push(x + step, 0, z);
                    vertices.push(x + step*0.5, 0, z + h);

                    // Triangle 2
                    vertices.push(x + step, 0, z);
                    vertices.push(x + step*1.5, 0, z + h);
                    vertices.push(x + step*0.5, 0, z + h);

                    for (let k = 0; k < 6; k++) {
                        colors.push(baseColor.r, baseColor.g, baseColor.b);
                    }
                }
            }

            const geo = new THREE.BufferGeometry();
            geo.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
            geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));

            const mat = new THREE.MeshBasicMaterial({
                vertexColors: true,
                wireframe: true,
                transparent: true,
                opacity: opacityVal
            });
            const mesh = new THREE.Mesh(geo, mat);
            apt.add(mesh);

            // Add affine root hyperplane walls
            const wallMat = new THREE.LineBasicMaterial({ color: 0xffcc00, transparent: true, opacity: 0.35 });
            for (let i = -3; i <= 3; i++) {
                const wallGeo = new THREE.BufferGeometry().setFromPoints([
                    new THREE.Vector3(-3.0, 0, i * h),
                    new THREE.Vector3(3.0, 0, i * h)
                ]);
                apt.add(new THREE.Line(wallGeo, wallMat));
            }

            apt.position.y = yOffset;
            apt.rotation.x = rotAngle;
            return apt;
        }

        // Base apartment A0
        const baseApartment = createApartment(0x00f2fe, 0.45, 0, 0);
        buildingGroup.add(baseApartment);

        // Branching apartments (A1, A2, A3) folding out along walls
        const branchGroup = new THREE.Group();
        const branchA1 = createApartment(0xff007f, 0.30, 0, Math.PI / 4);
        const branchA2 = createApartment(0xff007f, 0.30, 0, -Math.PI / 4);
        const branchA3 = createApartment(0xff007f, 0.25, 0, Math.PI / 2.5);
        branchGroup.add(branchA1);
        branchGroup.add(branchA2);
        branchGroup.add(branchA3);
        buildingGroup.add(branchGroup);

        // Trajectory ray traversing chambers
        const MAX_RAY_POINTS = 600;
        const rayPosArray = new Float32Array(MAX_RAY_POINTS * 3);
        const rayGeo = new THREE.BufferGeometry();
        rayGeo.setAttribute('position', new THREE.BufferAttribute(rayPosArray, 3));
        const rayMat = new THREE.LineBasicMaterial({ color: 0x38ef7d, linewidth: 2 });
        const rayLine = new THREE.Line(rayGeo, rayMat);
        scene.add(rayLine);

        const walkerHeadGeo = new THREE.SphereGeometry(0.06, 16, 16);
        const walkerHeadMat = new THREE.MeshBasicMaterial({ color: 0x38ef7d });
        const walkerHead = new THREE.Mesh(walkerHeadGeo, walkerHeadMat);
        scene.add(walkerHead);

        let walkPos = new THREE.Vector3(0.1, 0, 0.1);
        let walkVel = new THREE.Vector3(0.015, 0.005, 0.012);
        let rayCount = 0;
        let isWalking = true;
        let chamberIndex = 0;

        function addRayPoint(p) {
            const idx = (rayCount % MAX_RAY_POINTS) * 3;
            rayPosArray[idx] = p.x;
            rayPosArray[idx + 1] = p.y;
            rayPosArray[idx + 2] = p.z;
            rayCount++;
            rayGeo.attributes.position.needsUpdate = true;
            rayGeo.setDrawRange(0, Math.min(rayCount, MAX_RAY_POINTS));
        }

        addRayPoint(walkPos);

        function stepBuildingWalk() {
            if (!isWalking) return;

            walkPos.add(walkVel);

            // Reflection at apartment boundary (affine walls)
            if (walkPos.x > 2.8 || walkPos.x < -2.8) { walkVel.x = -walkVel.x; chamberIndex++; }
            if (walkPos.z > 2.8 || walkPos.z < -2.8) { walkVel.z = -walkVel.z; chamberIndex++; }
            if (walkPos.y > 1.2 || walkPos.y < -1.2) { walkVel.y = -walkVel.y; chamberIndex++; }

            walkerHead.position.copy(walkPos);
            addRayPoint(walkPos);

            if (rayCount % 12 === 0) {
                document.getElementById('chamber-id').textContent = 'Δ_' + chamberIndex + ' (Apartment A_' + (chamberIndex % 4) + ')';
            }
        }

        // Camera orbit control
        let isDragging = false;
        let prevMouse = { x: 0, y: 0 };
        let orbit = { theta: 0.4, phi: 0.5, radius: 6.5 };

        function updateCamera() {
            camera.position.x = orbit.radius * Math.sin(orbit.phi) * Math.sin(orbit.theta);
            camera.position.y = orbit.radius * Math.cos(orbit.phi);
            camera.position.z = orbit.radius * Math.sin(orbit.phi) * Math.cos(orbit.theta);
            camera.lookAt(0, 0, 0);
        }
        updateCamera();

        window.addEventListener('mousedown', e => {
            if (e.target.tagName === 'BUTTON') return;
            isDragging = true;
            prevMouse = { x: e.clientX, y: e.clientY };
        });

        window.addEventListener('mousemove', e => {
            if (!isDragging) return;
            const dx = e.clientX - prevMouse.x;
            const dy = e.clientY - prevMouse.y;
            orbit.theta -= dx * 0.008;
            orbit.phi = Math.max(0.1, Math.min(Math.PI - 0.1, orbit.phi - dy * 0.008));
            prevMouse = { x: e.clientX, y: e.clientY };
            updateCamera();
        });

        window.addEventListener('mouseup', () => isDragging = false);
        window.addEventListener('wheel', e => {
            orbit.radius = Math.max(2.0, Math.min(15.0, orbit.radius + e.deltaY * 0.005));
            updateCamera();
        });

        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });

        // UI Controls
        document.getElementById('btn-toggle-apartments').addEventListener('click', () => {
            branchGroup.visible = !branchGroup.visible;
        });

        document.getElementById('btn-toggle-walk').addEventListener('click', () => {
            isWalking = !isWalking;
        });

        document.getElementById('btn-retract').addEventListener('click', () => {
            // Retract ray and branching apartments flat into base apartment A0
            walkPos.y = 0;
            walkVel.y = 0;
            walkerHead.position.copy(walkPos);
            branchA1.rotation.x = 0;
            branchA2.rotation.x = 0;
            branchA3.rotation.x = 0;
            document.getElementById('chamber-id').textContent = 'Retracted into A₀ (Base)';
        });

        document.getElementById('btn-reset').addEventListener('click', () => {
            orbit = { theta: 0.4, phi: 0.5, radius: 6.5 };
            updateCamera();
            branchA1.rotation.x = Math.PI / 4;
            branchA2.rotation.x = -Math.PI / 4;
            branchA3.rotation.x = Math.PI / 2.5;
            branchGroup.visible = true;
        });

        // Animation Loop
        function animate() {
            requestAnimationFrame(animate);
            stepBuildingWalk();
            buildingGroup.rotation.y += 0.0006;
            renderer.render(scene, camera);
        }
        animate();
    </script>
</body>
</html>
"""

def main():
    target_path = os.path.join(os.path.dirname(__file__), "../../docs/assets/bruhat_tits_building_3d.html")
    target_path = os.path.abspath(target_path)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(HTML_CONTENT)
    print(f"Generated WebGL 3D Bruhat-Tits Building visualizer at {target_path}")

if __name__ == "__main__":
    main()
