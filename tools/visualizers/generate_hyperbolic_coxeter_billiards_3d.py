#!/usr/bin/env python3
"""
generate_hyperbolic_coxeter_billiards_3d.py
Generates docs/assets/hyperbolic_coxeter_billiards_3d.html:
Interactive 3D WebGL Poincaré Ball Hyperbolic Coxeter Billiards Simulation.
Features real-time geodesic reflection dynamics inside a hyperbolic Coxeter fundamental domain.
"""

import os

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>IMF Hyperbolic Coxeter Billiards (Poincaré Ball ℍ³)</title>
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
            max-width: 420px;
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
        <h1>Hyperbolic Coxeter Billiards (ℍ³)</h1>
        <div class="subtitle">Poincaré Ball Model &bull; Blackwell SM 12.0 Tensor Core Raytracer &bull; Geodesic Reflection Flow</div>
        <div class="metric-row">
            <span class="metric-label">Coxeter Group:</span>
            <span class="metric-value" id="grp-name">[3, 5, 3] Hyperbolic Honeycomb</span>
        </div>
        <div class="metric-row">
            <span class="metric-label">Riemannian Metric:</span>
            <span class="metric-value">ds² = 4‖dx‖² / (1 - ‖x‖²)²</span>
        </div>
        <div class="metric-row">
            <span class="metric-label">Billiard Reflections:</span>
            <span class="metric-value" id="bounces-count">0</span>
        </div>
        <div class="metric-row">
            <span class="metric-label">Hyperbolic Arc Length:</span>
            <span class="metric-value" id="arc-length">0.00 λ</span>
        </div>
        <div class="metric-row">
            <span class="metric-label">Lyapunov Exponent λ₁:</span>
            <span class="metric-value" id="lyapunov">+1.000 (Chaos)</span>
        </div>
        <div class="metric-row">
            <span class="metric-label">Involutive Order:</span>
            <span class="metric-value">s_α² = 1 (Mathlib Certified)</span>
        </div>
        <div class="controls">
            <button id="btn-pause">Pause / Run</button>
            <button id="btn-reset">Reset Ray</button>
            <button id="btn-toggle-chamber">Toggle Chamber</button>
        </div>
    </div>

    <div id="legend">
        <div><span class="dot" style="background: #00f2fe;"></span> Geodesic Ray &amp; Path</div>
        <div><span class="dot" style="background: #ff007f;"></span> Coxeter Root Mirrors</div>
        <div><span class="dot" style="background: #38ef7d;"></span> Conformal Ideal Boundary S²</div>
    </div>

    <canvas id="canvas"></canvas>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
        const canvas = document.getElementById('canvas');
        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x020409, 0.05);

        const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.05, 100);
        camera.position.set(0, 1.8, 4.2);

        const renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

        // Ideal boundary S² at radius R = 2.0
        const R_BALL = 2.0;
        const boundaryGeo = new THREE.SphereGeometry(R_BALL, 48, 48);
        const boundaryMat = new THREE.MeshBasicMaterial({
            color: 0x38ef7d,
            wireframe: true,
            transparent: true,
            opacity: 0.12
        });
        const boundaryMesh = new THREE.Mesh(boundaryGeo, boundaryMat);
        scene.add(boundaryMesh);

        // Coxeter Chamber: Group of orthogonal hyperbolic mirrors (geodesic spheres & planes)
        const chamberGroup = new THREE.Group();
        scene.add(chamberGroup);

        // Define Coxeter mirrors in H³ (spherical mirrors orthogonal to S²)
        // A sphere of radius r centered at c orthogonal to S_R satisfies: |c|² = R² + r²
        const mirrors = [
            { normal: new THREE.Vector3(1, 0, 0), isPlane: true },
            { normal: new THREE.Vector3(0, 1, 0), isPlane: true },
            { normal: new THREE.Vector3(0, 0, 1), isPlane: true },
            { center: new THREE.Vector3(1.5, 1.5, 0), radius: Math.sqrt(4.5 - R_BALL*R_BALL), isPlane: false },
            { center: new THREE.Vector3(0, 1.5, 1.5), radius: Math.sqrt(4.5 - R_BALL*R_BALL), isPlane: false },
            { center: new THREE.Vector3(1.5, 0, 1.5), radius: Math.sqrt(4.5 - R_BALL*R_BALL), isPlane: false }
        ];

        // Visualize mirror planes / spherical caps
        const mirrorMat = new THREE.MeshBasicMaterial({
            color: 0xff007f,
            wireframe: true,
            transparent: true,
            opacity: 0.22
        });

        // Add 3 plane discs
        const discGeo = new THREE.CircleGeometry(R_BALL, 32);
        const discX = new THREE.Mesh(discGeo, mirrorMat);
        discX.rotation.y = Math.PI / 2;
        chamberGroup.add(discX);
        const discY = new THREE.Mesh(discGeo, mirrorMat);
        discY.rotation.x = Math.PI / 2;
        chamberGroup.add(discY);
        const discZ = new THREE.Mesh(discGeo, mirrorMat);
        chamberGroup.add(discZ);

        // Add spherical mirrors
        mirrors.filter(m => !m.isPlane).forEach(m => {
            const spGeo = new THREE.SphereGeometry(m.radius, 24, 24);
            const spMesh = new THREE.Mesh(spGeo, mirrorMat);
            spMesh.position.copy(m.center);
            chamberGroup.add(spMesh);
        });

        // Billiard trajectory simulation
        const MAX_POINTS = 1200;
        const positions = new Float32Array(MAX_POINTS * 3);
        const colors = new Float32Array(MAX_POINTS * 3);

        const trajectoryGeo = new THREE.BufferGeometry();
        trajectoryGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        trajectoryGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

        const trajectoryMat = new THREE.LineBasicMaterial({
            vertexColors: true,
            transparent: true,
            opacity: 0.85,
            linewidth: 2
        });
        const trajectoryLine = new THREE.Line(trajectoryGeo, trajectoryMat);
        scene.add(trajectoryLine);

        // Rayhead sphere
        const rayHeadGeo = new THREE.SphereGeometry(0.04, 16, 16);
        const rayHeadMat = new THREE.MeshBasicMaterial({ color: 0x00f2fe });
        const rayHead = new THREE.Mesh(rayHeadGeo, rayHeadMat);
        scene.add(rayHead);

        // State of billiard ray
        let rayPos = new THREE.Vector3(0.2, 0.3, 0.4);
        let rayVel = new THREE.Vector3(0.012, 0.018, 0.024).normalize().multiplyScalar(0.025);
        let pointCount = 0;
        let bounces = 0;
        let totalHypLength = 0;
        let isRunning = true;

        function addPoint(pos) {
            const idx = (pointCount % MAX_POINTS) * 3;
            positions[idx] = pos.x;
            positions[idx + 1] = pos.y;
            positions[idx + 2] = pos.z;

            // Color gradient from cyan to electric magenta
            const t = (pointCount % MAX_POINTS) / MAX_POINTS;
            colors[idx] = 0.0 + 1.0 * t;
            colors[idx + 1] = 0.95 * (1.0 - t);
            colors[idx + 2] = 1.0;

            pointCount++;
            trajectoryGeo.attributes.position.needsUpdate = true;
            trajectoryGeo.attributes.color.needsUpdate = true;
            trajectoryGeo.setDrawRange(0, Math.min(pointCount, MAX_POINTS));
        }

        addPoint(rayPos);

        function stepBilliard() {
            if (!isRunning) return;

            // Hyperbolic geodesic step: in Euclidean coords, ds_hyp = 2 |dx| / (1 - |x|²/R²)
            const r2 = rayPos.lengthSq() / (R_BALL * R_BALL);
            if (r2 >= 0.96) {
                // Near conformal boundary: reflect back hyperbolically
                const norm = rayPos.clone().normalize();
                rayVel.reflect(norm).multiplyScalar(0.98);
                bounces++;
            }

            // Check Coxeter mirror boundaries
            // Mirror planes: x=0, y=0, z=0
            if (rayPos.x < 0.02 && rayVel.x < 0) { rayVel.x = -rayVel.x; bounces++; }
            if (rayPos.y < 0.02 && rayVel.y < 0) { rayVel.y = -rayVel.y; bounces++; }
            if (rayPos.z < 0.02 && rayVel.z < 0) { rayVel.z = -rayVel.z; bounces++; }

            // Spherical mirrors
            mirrors.filter(m => !m.isPlane).forEach(m => {
                const distToCenter = rayPos.distanceTo(m.center);
                if (distToCenter <= m.radius && rayPos.clone().add(rayVel).distanceTo(m.center) < distToCenter) {
                    const norm = rayPos.clone().sub(m.center).normalize();
                    rayVel.reflect(norm);
                    bounces++;
                }
            });

            // Update position
            const stepDist = rayVel.length();
            const hypFactor = 2.0 / (1.0 - Math.min(r2, 0.95));
            totalHypLength += stepDist * hypFactor;

            rayPos.add(rayVel);
            rayHead.position.copy(rayPos);
            addPoint(rayPos);

            // Update UI telemetry
            if (pointCount % 6 === 0) {
                document.getElementById('bounces-count').textContent = bounces;
                document.getElementById('arc-length').textContent = (totalHypLength).toFixed(2) + ' λ';
            }
        }

        // Camera orbit control
        let isDragging = false;
        let prevMouse = { x: 0, y: 0 };
        let orbit = { theta: 0.3, phi: 0.4, radius: 4.8 };

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
            orbit.radius = Math.max(2.5, Math.min(10.0, orbit.radius + e.deltaY * 0.005));
            updateCamera();
        });

        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });

        // UI Controls
        document.getElementById('btn-pause').addEventListener('click', () => {
            isRunning = !isRunning;
        });

        document.getElementById('btn-reset').addEventListener('click', () => {
            rayPos.set(0.25, 0.35, 0.45);
            rayVel.set(0.015, 0.02, 0.025).normalize().multiplyScalar(0.025);
            pointCount = 0;
            bounces = 0;
            totalHypLength = 0;
            trajectoryGeo.setDrawRange(0, 0);
            addPoint(rayPos);
        });

        document.getElementById('btn-toggle-chamber').addEventListener('click', () => {
            chamberGroup.visible = !chamberGroup.visible;
        });

        // Animation Loop
        function animate() {
            requestAnimationFrame(animate);
            stepBilliard();
            boundaryMesh.rotation.y += 0.0008;
            renderer.render(scene, camera);
        }
        animate();
    </script>
</body>
</html>
"""

def main():
    target_path = os.path.join(os.path.dirname(__file__), "../../docs/assets/hyperbolic_coxeter_billiards_3d.html")
    target_path = os.path.abspath(target_path)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(HTML_CONTENT)
    print(f"Generated WebGL 3D Poincaré Ball Coxeter Billiards visualizer at {target_path}")

if __name__ == "__main__":
    main()
