#!/usr/bin/env python3
"""
Generate interactive 3D WebGL visualization of the Gosset 3_21 Polytope
and Exceptional Lie Group E7 Miniscule Representation (56 Vertices, 756 Edges).
"""

from pathlib import Path
import json
import itertools
import math

HTML_CONTENT = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>IMF Gosset 3₂₁ Polytope & E₇ Miniscule Representation (3D WebGL)</title>
    <style>
        body { margin: 0; background: #010206; color: #eee; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; overflow: hidden; }
        #canvas { width: 100vw; height: 100vh; display: block; }
        #overlay { position: absolute; top: 16px; left: 16px; background: rgba(4,6,18,0.92); padding: 18px; border-radius: 8px; border: 1px solid #7c4dff; max-width: 480px; box-shadow: 0 4px 24px rgba(0,0,0,0.85); backdrop-filter: blur(8px); }
        h1 { margin: 0 0 8px 0; font-size: 16px; color: #b388ff; letter-spacing: 0.5px; }
        p { margin: 4px 0; font-size: 12.5px; color: #b0bec5; line-height: 1.4; }
        .control-group { margin-top: 10px; }
        label { display: block; font-size: 12px; color: #cfd8dc; margin-bottom: 3px; }
        input[type=range] { width: 100%; accent-color: #b388ff; }
        .badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 11px; background: #311b92; color: #d1c4e9; margin-top: 8px; margin-right: 6px; }
    </style>
</head>
<body>
    <div id="overlay">
        <h1>Gosset 3₂₁ Polytope & E₇ Miniscule Representation</h1>
        <p><strong>Geometry:</strong> Semi-regular 7-polytope with 56 vertices and 756 edges. Facets: 576 6-simplices and 126 6-orthoplexes (cross-polytopes).</p>
        <p><strong>Exceptional Symmetry:</strong> Weyl group $W(E_7)$ of order 2,903,040. The 56 vertices correspond to the weights of the miniscule 56-dimensional fundamental representation of $\\mathfrak{e}_7$.</p>
        <p><strong>Coxeter Projection:</strong> Vertices project into concentric double-heptagons along the 18-gonal Coxeter plane of $E_7$.</p>
        
        <div class="control-group">
            <label id="proj-label">7D Phase Rotation Angle θ: 0.00 rad</label>
            <input type="range" id="proj-slider" min="0" max="6.28" step="0.05" value="0.00">
        </div>
        <div class="control-group">
            <label id="scale-label">Radial Dispersion Scale: 1.60</label>
            <input type="range" id="scale-slider" min="0.8" max="2.5" step="0.05" value="1.60">
        </div>
        <div>
            <span class="badge">E₇ Root Lattice Λ(E₇)</span>
            <span class="badge">56 Miniscule Weights</span>
            <span class="badge">756 Edges</span>
        </div>
    </div>
    <canvas id="canvas"></canvas>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
        camera.position.set(0, 0, 4.5);

        const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('canvas'), antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(window.devicePixelRatio);

        const rootGroup = new THREE.Group();
        scene.add(rootGroup);

        // Generate 56 vertices of 3_21 polytope in 8D with sum = 0
        // Standard realization in R^8:
        // Type A: Permutations of (1, 1, -1/3, -1/3, -1/3, -1/3, -1/3, -1/3) -> 28 vertices
        // Type B: Permutations of (-1, -1, 1/3, 1/3, 1/3, 1/3, 1/3, 1/3) -> 28 vertices
        // Total = 56 vertices.
        const raw_vertices_8d = [];
        
        // 28 vertices from choosing 2 coordinates as +1 and 6 as -1/3 (sum = 2 - 2 = 0)
        for (let i = 0; i < 8; i++) {
            for (let j = i + 1; j < 8; j++) {
                const v = new Array(8).fill(-1.0 / 3.0);
                v[i] = 1.0;
                v[j] = 1.0;
                raw_vertices_8d.push(v);
            }
        }
        // 28 vertices from choosing 2 coordinates as -1 and 6 as +1/3 (sum = -2 + 2 = 0)
        for (let i = 0; i < 8; i++) {
            for (let j = i + 1; j < 8; j++) {
                const v = new Array(8).fill(1.0 / 3.0);
                v[i] = -1.0;
                v[j] = -1.0;
                raw_vertices_8d.push(v);
            }
        }

        // Compute 756 edges: pairs with squared Euclidean distance ≈ 32/9 ≈ 3.555
        const edges = [];
        for (let a = 0; a < 56; a++) {
            for (let b = a + 1; b < 56; b++) {
                let distSq = 0;
                for (let d = 0; d < 8; d++) {
                    const diff = raw_vertices_8d[a][d] - raw_vertices_8d[b][d];
                    distSq += diff * diff;
                }
                if (Math.abs(distSq - 3.5555555) < 0.1) {
                    edges.push([a, b]);
                }
            }
        }

        let currentTheta = 0.0;
        let currentScale = 1.60;

        function project8Dto3D(v, theta, scale) {
            // Coxeter-like harmonic projection from 8D to 3D
            const x = (v[0] * Math.cos(theta) + v[1] * Math.sin(theta) +
                       v[2] * Math.cos(theta + 1.25) + v[3] * Math.sin(theta + 1.25));
            const y = (v[4] * Math.cos(theta + 2.5) + v[5] * Math.sin(theta + 2.5) +
                       v[6] * Math.cos(theta + 3.75) + v[7] * Math.sin(theta + 3.75));
            const z = (v[0] * Math.sin(theta * 1.5) + v[3] * Math.cos(theta * 1.5) +
                       v[5] * Math.sin(theta * 2.1) + v[7] * Math.cos(theta * 2.1));
            return new THREE.Vector3(x * scale * 0.7, y * scale * 0.7, z * scale * 0.7);
        }

        // Create vertex visual meshes
        const vertexSpheres = [];
        const sphereGeo = new THREE.SphereGeometry(0.045, 16, 16);
        const sphereMatA = new THREE.MeshBasicMaterial({ color: 0xb388ff });
        const sphereMatB = new THREE.MeshBasicMaterial({ color: 0x00e5ff });

        for (let i = 0; i < 56; i++) {
            const sphere = new THREE.Mesh(sphereGeo, i < 28 ? sphereMatA : sphereMatB);
            rootGroup.add(sphere);
            vertexSpheres.push(sphere);
        }

        // Create edges geometry
        const lineGeo = new THREE.BufferGeometry();
        const linePositions = new Float32Array(edges.length * 6);
        lineGeo.setAttribute('position', new THREE.BufferAttribute(linePositions, 3));
        const lineMat = new THREE.LineBasicMaterial({
            color: 0x7c4dff,
            transparent: true,
            opacity: 0.35,
            blending: THREE.AdditiveBlending
        });
        const lineMesh = new THREE.LineSegments(lineGeo, lineMat);
        rootGroup.add(lineMesh);

        function updateGeometry() {
            const projected = raw_vertices_8d.map(v => project8Dto3D(v, currentTheta, currentScale));
            for (let i = 0; i < 56; i++) {
                vertexSpheres[i].position.copy(projected[i]);
            }
            const posAttr = lineGeo.attributes.position;
            let idx = 0;
            for (let k = 0; k < edges.length; k++) {
                const [i, j] = edges[k];
                posAttr.array[idx++] = projected[i].x;
                posAttr.array[idx++] = projected[i].y;
                posAttr.array[idx++] = projected[i].z;
                posAttr.array[idx++] = projected[j].x;
                posAttr.array[idx++] = projected[j].y;
                posAttr.array[idx++] = projected[j].z;
            }
            posAttr.needsUpdate = true;
        }

        updateGeometry();

        // UI Listeners
        const projSlider = document.getElementById('proj-slider');
        const scaleSlider = document.getElementById('scale-slider');
        const projLabel = document.getElementById('proj-label');
        const scaleLabel = document.getElementById('scale-label');

        projSlider.addEventListener('input', (e) => {
            currentTheta = parseFloat(e.target.value);
            projLabel.textContent = `7D Phase Rotation Angle θ: ${currentTheta.toFixed(2)} rad`;
            updateGeometry();
        });

        scaleSlider.addEventListener('input', (e) => {
            currentScale = parseFloat(e.target.value);
            scaleLabel.textContent = `Radial Dispersion Scale: ${currentScale.toFixed(2)}`;
            updateGeometry();
        });

        // Animation Loop
        let clock = 0;
        function animate() {
            requestAnimationFrame(animate);
            clock += 0.005;
            rootGroup.rotation.y += 0.003;
            rootGroup.rotation.x = Math.sin(clock * 0.5) * 0.2;
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
    out_dir = Path("docs/assets")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "gosset_321_e7_3d.html"
    out_file.write_text(HTML_CONTENT, encoding="utf-8")
    print(f"Successfully generated Gosset 3_21 E7 WebGL 3D visualizer at {out_file}")

if __name__ == "__main__":
    main()
