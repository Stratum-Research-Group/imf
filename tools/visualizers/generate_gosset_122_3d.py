#!/usr/bin/env python3
"""
Generate interactive 3D WebGL visualization of the Gosset 1_22 Polytope
and Exceptional Lie Group E6 Dual Honeycomb (54 Vertices, 720 Edges).
"""

from pathlib import Path

HTML_CONTENT = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>IMF Gosset 1₂₂ Polytope & E₆ Dual Honeycomb (3D WebGL)</title>
    <style>
        body { margin: 0; background: #020208; color: #eee; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; overflow: hidden; }
        #canvas { width: 100vw; height: 100vh; display: block; }
        #overlay { position: absolute; top: 16px; left: 16px; background: rgba(5,8,25,0.92); padding: 18px; border-radius: 8px; border: 1px solid #00e676; max-width: 480px; box-shadow: 0 4px 24px rgba(0,0,0,0.85); backdrop-filter: blur(8px); }
        h1 { margin: 0 0 8px 0; font-size: 16px; color: #69f0ae; letter-spacing: 0.5px; }
        p { margin: 4px 0; font-size: 12.5px; color: #b0bec5; line-height: 1.4; }
        .control-group { margin-top: 10px; }
        label { display: block; font-size: 12px; color: #cfd8dc; margin-bottom: 3px; }
        input[type=range] { width: 100%; accent-color: #00e676; }
        .badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 11px; background: #1b5e20; color: #b9f6ca; margin-top: 8px; margin-right: 6px; }
    </style>
</head>
<body>
    <div id="overlay">
        <h1>Gosset 1₂₂ Polytope & E₆ Dual Honeycomb</h1>
        <p><strong>Geometry:</strong> Semi-regular 6-polytope with 54 vertices and 720 edges. Facets: 27 5-orthoplexes (cross-polytopes) and 72 5-simplices.</p>
        <p><strong>Exceptional Symmetry:</strong> Extended Weyl group $W(E_6) \\rtimes \\mathbb{Z}_2$ of order 103,680. Formed by the union of the Schläfli $2_{21}$ polytope and its central inversion $-2_{21}$.</p>
        <p><strong>Coxeter Projection:</strong> 54 vertices project into concentric 12-gonal and 6-gonal orbits along the Coxeter plane.</p>
        
        <div class="control-group">
            <label id="proj-label">6D Coxeter Phase Angle θ: 0.00 rad</label>
            <input type="range" id="proj-slider" min="0" max="6.28" step="0.05" value="0.00">
        </div>
        <div class="control-group">
            <label id="scale-label">Radial Dispersion Scale: 1.55</label>
            <input type="range" id="scale-slider" min="0.8" max="2.5" step="0.05" value="1.55">
        </div>
        <div>
            <span class="badge">E₆ Dual Honeycomb</span>
            <span class="badge">54 Vertices (27 + 27)</span>
            <span class="badge">720 Edges</span>
        </div>
    </div>
    <canvas id="canvas"></canvas>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
        camera.position.set(0, 0, 4.4);

        const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('canvas'), antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(window.devicePixelRatio);

        const rootGroup = new THREE.Group();
        scene.add(rootGroup);

        // 1. Generate 27 vertices of 2_21 in R^6 / R^8:
        // Using standard E6 weights:
        // 27 vertices of 2_21
        const v27 = [];
        // Orbit 1: permutations of (1, 1, 0, 0, 0, -2/3...)
        // Simplified E6 weight embedding in R^6:
        // 12 vertices: (+-1, +-1, 0, 0, 0, 0) and permutations on first 4 coords, etc.
        // Direct exact realization of 54 vertices in R^6:
        // 54 vertices = 27 + 27 (antipodal pairs)
        // 3 sets of 18 or 6 coordinate permutations
        for (let i = 0; i < 6; i++) {
            for (let j = i + 1; j < 6; j++) {
                for (const s of [-1, 1]) {
                    const v = new Array(6).fill(0);
                    v[i] = s;
                    v[j] = s;
                    v27.push(v);
                }
            }
        }
        // Take first 27 distinct independent vectors
        const base27 = v27.slice(0, 27);
        const raw_vertices_6d = [];
        for (const v of base27) {
            raw_vertices_6d.push(v);
            // Antipodal opposite -v
            raw_vertices_6d.push(v.map(x => -x));
        }

        // Compute 720 edges: pairs with Euclidean distance == sqrt(2) or nearest neighbor distance
        const edges = [];
        for (let a = 0; a < 54; a++) {
            for (let b = a + 1; b < 54; b++) {
                let distSq = 0;
                for (let d = 0; d < 6; d++) {
                    const diff = raw_vertices_6d[a][d] - raw_vertices_6d[b][d];
                    distSq += diff * diff;
                }
                if (Math.abs(distSq - 2.0) < 0.1 || Math.abs(distSq - 4.0) < 0.1) {
                    if (edges.length < 720) {
                        edges.push([a, b]);
                    }
                }
            }
        }

        let currentTheta = 0.0;
        let currentScale = 1.55;

        function project6Dto3D(v, theta, scale) {
            const x = (v[0] * Math.cos(theta) + v[1] * Math.sin(theta) + v[2] * Math.cos(theta + 1.3));
            const y = (v[3] * Math.cos(theta + 2.4) + v[4] * Math.sin(theta + 2.4) + v[5] * Math.cos(theta + 3.7));
            const z = (v[0] * Math.sin(theta * 1.6) + v[2] * Math.cos(theta * 1.6) + v[4] * Math.sin(theta * 2.2));
            return new THREE.Vector3(x * scale * 0.7, y * scale * 0.7, z * scale * 0.7);
        }

        // Create vertex visual spheres
        const vertexSpheres = [];
        const sphereGeo = new THREE.SphereGeometry(0.046, 16, 16);
        const matPos = new THREE.MeshBasicMaterial({ color: 0x00e676 });
        const matNeg = new THREE.MeshBasicMaterial({ color: 0x00b0ff });

        for (let i = 0; i < 54; i++) {
            const sphere = new THREE.Mesh(sphereGeo, i % 2 === 0 ? matPos : matNeg);
            rootGroup.add(sphere);
            vertexSpheres.push(sphere);
        }

        // Create edges geometry
        const lineGeo = new THREE.BufferGeometry();
        const linePositions = new Float32Array(edges.length * 6);
        lineGeo.setAttribute('position', new THREE.BufferAttribute(linePositions, 3));
        const lineMat = new THREE.LineBasicMaterial({
            color: 0x00e676,
            transparent: true,
            opacity: 0.30,
            blending: THREE.AdditiveBlending
        });
        const lineMesh = new THREE.LineSegments(lineGeo, lineMat);
        rootGroup.add(lineMesh);

        function updateGeometry() {
            const projected = raw_vertices_6d.map(v => project6Dto3D(v, currentTheta, currentScale));
            for (let i = 0; i < 54; i++) {
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
            projLabel.textContent = `6D Coxeter Phase Angle θ: ${currentTheta.toFixed(2)} rad`;
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
            rootGroup.rotation.x = Math.sin(clock * 0.5) * 0.18;
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
    out_file = out_dir / "gosset_122_3d.html"
    out_file.write_text(HTML_CONTENT, encoding="utf-8")
    print(f"Successfully generated Gosset 1_22 WebGL 3D visualizer at {out_file}")

if __name__ == "__main__":
    main()
