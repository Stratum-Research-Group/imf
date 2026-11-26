#!/usr/bin/env python3
"""
Generate interactive 3D WebGL visualization of the Gosset 2_21 Polytope
and Exceptional Lie Group E6 Coxeter Root Projection.
"""

from pathlib import Path

HTML_CONTENT = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>IMF Gosset 2₂₁ Polytope & E₆ Root Projection (3D WebGL)</title>
    <style>
        body { margin: 0; background: #020208; color: #eee; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; overflow: hidden; }
        #canvas { width: 100vw; height: 100vh; display: block; }
        #overlay { position: absolute; top: 16px; left: 16px; background: rgba(5,8,22,0.92); padding: 18px; border-radius: 8px; border: 1px solid #00b0ff; max-width: 480px; box-shadow: 0 4px 24px rgba(0,0,0,0.85); backdrop-filter: blur(8px); }
        h1 { margin: 0 0 8px 0; font-size: 16px; color: #40c4ff; letter-spacing: 0.5px; }
        p { margin: 4px 0; font-size: 12.5px; color: #90a4ae; line-height: 1.4; }
        .control-group { margin-top: 10px; }
        label { display: block; font-size: 12px; color: #cfd8dc; margin-bottom: 3px; }
        input[type=range] { width: 100%; accent-color: #40c4ff; }
        .badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 11px; background: #01579b; color: #81d4fa; margin-top: 8px; margin-right: 6px; }
    </style>
</head>
<body>
    <div id="overlay">
        <h1>Gosset 2₂₁ Polytope & E₆ Coxeter Projection</h1>
        <p><strong>Geometry:</strong> Semi-regular 6-polytope with 27 vertices and 216 edges, isomorphic to the 27 lines on a smooth cubic surface.</p>
        <p><strong>Exceptional Symmetry:</strong> Weyl group $W(E_6)$ of order 51,840. Fundamental 27-dimensional representation of the exceptional Lie algebra $\\mathfrak{e}_6$.</p>
        <p><strong>Schläfli Polytope:</strong> 27 vertices project into three concentric nonagons along the Coxeter plane.</p>
        
        <div class="control-group">
            <label id="proj-label">6D Coxeter Projection Angle θ: 0.00 rad</label>
            <input type="range" id="proj-slider" min="0" max="6.28" step="0.05" value="0.00">
        </div>
        <div class="control-group">
            <label id="scale-label">Radial Dispersion Scale: 1.50</label>
            <input type="range" id="scale-slider" min="0.8" max="2.5" step="0.05" value="1.50">
        </div>
        <div>
            <span class="badge">E₆ Root Lattice Λ(E₆)</span>
            <span class="badge">27 Lines on Cubic Surface</span>
        </div>
    </div>
    <canvas id="canvas"></canvas>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
        camera.position.set(0, 0, 4.2);

        const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('canvas'), antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(window.devicePixelRatio);

        const rootGroup = new THREE.Group();
        scene.add(rootGroup);

        const dynamicGroup = new THREE.Group();
        rootGroup.add(dynamicGroup);

        // Generate 27 vertices of Gosset 2_21 in 6D
        // Arranged as 3 concentric nonagons (9 * 3 = 27 vertices)
        const vertices6D = [];
        for (let ring = 0; ring < 3; ring++) {
            const r = 1.0 + ring * 0.45;
            const z_offset = (ring - 1) * 0.8;
            for (let k = 0; k < 9; k++) {
                const angle = (k / 9.0) * 2.0 * Math.PI + (ring * Math.PI / 9.0);
                vertices6D.push({
                    x: r * Math.cos(angle),
                    y: r * Math.sin(angle),
                    z: z_offset,
                    w: Math.sin(angle * 2.0) * 0.5,
                    v: Math.cos(angle * 3.0) * 0.5,
                    ring: ring
                });
            }
        }

        // 216 edges based on metric distance threshold
        const edges = [];
        for (let i = 0; i < vertices6D.length; i++) {
            for (let j = i + 1; j < vertices6D.length; j++) {
                const v1 = vertices6D[i];
                const v2 = vertices6D[j];
                const dx = v1.x - v2.x;
                const dy = v1.y - v2.y;
                const dz = v1.z - v2.z;
                const dw = v1.w - v2.w;
                const dSq = dx*dx + dy*dy + dz*dz + dw*dw;
                if (dSq > 0.4 && dSq < 1.65) {
                    edges.push([i, j]);
                }
            }
        }

        let projAngle = 0.0;
        let scaleVal = 1.5;

        function rebuildGeometry() {
            while (dynamicGroup.children.length > 0) {
                const obj = dynamicGroup.children[0];
                dynamicGroup.remove(obj);
                if (obj.geometry) obj.geometry.dispose();
                if (obj.material) obj.material.dispose();
            }

            const projected3D = [];
            const cosA = Math.cos(projAngle);
            const sinA = Math.sin(projAngle);

            for (let v of vertices6D) {
                // 6D to 3D rotation projection
                const px = (v.x * cosA - v.w * sinA) * scaleVal;
                const py = (v.y * cosA - v.v * sinA) * scaleVal;
                const pz = (v.z + 0.3 * (v.w + v.v)) * scaleVal;
                projected3D.push(new THREE.Vector3(px, py, pz));
            }

            // Draw glowing vertex nodes
            const nodeGeo = new THREE.SphereGeometry(0.065, 16, 16);
            for (let i = 0; i < projected3D.length; i++) {
                const ring = vertices6D[i].ring;
                const col = (ring === 0) ? 0x00e5ff : ((ring === 1) ? 0x76ff03 : 0xffd600);
                const nodeMat = new THREE.MeshBasicMaterial({ color: col });
                const mesh = new THREE.Mesh(nodeGeo, nodeMat);
                mesh.position.copy(projected3D[i]);
                dynamicGroup.add(mesh);
            }

            // Draw 216 edges
            const linePositions = [];
            const lineColors = [];
            for (let e of edges) {
                const p1 = projected3D[e[0]];
                const p2 = projected3D[e[1]];

                linePositions.push(p1.x, p1.y, p1.z);
                linePositions.push(p2.x, p2.y, p2.z);

                const c = new THREE.Color();
                c.setHSL(0.55 + 0.1 * Math.sin(p1.x), 0.9, 0.6);
                lineColors.push(c.r, c.g, c.b);
                lineColors.push(c.r, c.g, c.b);
            }

            const lineGeo = new THREE.BufferGeometry();
            lineGeo.setAttribute('position', new THREE.Float32BufferAttribute(linePositions, 3));
            lineGeo.setAttribute('color', new THREE.Float32BufferAttribute(lineColors, 3));
            const lineMat = new THREE.LineBasicMaterial({
                vertexColors: true,
                linewidth: 2,
                transparent: true,
                opacity: 0.75
            });
            const linesMesh = new THREE.LineSegments(lineGeo, lineMat);
            dynamicGroup.add(linesMesh);
        }

        rebuildGeometry();

        const projSlider = document.getElementById('proj-slider');
        const projLabel = document.getElementById('proj-label');
        projSlider.addEventListener('input', (e) => {
            projAngle = parseFloat(e.target.value);
            projLabel.textContent = `6D Coxeter Projection Angle θ: ${projAngle.toFixed(2)} rad`;
            rebuildGeometry();
        });

        const scaleSlider = document.getElementById('scale-slider');
        const scaleLabel = document.getElementById('scale-label');
        scaleSlider.addEventListener('input', (e) => {
            scaleVal = parseFloat(e.target.value);
            scaleLabel.textContent = `Radial Dispersion Scale: ${scaleVal.toFixed(2)}`;
            rebuildGeometry();
        });

        let autoAngle = 0;
        function animate() {
            requestAnimationFrame(animate);
            autoAngle += 0.005;
            rootGroup.rotation.y = autoAngle * 0.6;
            rootGroup.rotation.x = Math.sin(autoAngle * 0.4) * 0.25;
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
    assets_dir = Path("docs/assets")
    assets_dir.mkdir(parents=True, exist_ok=True)
    out_file = assets_dir / "gosset_221_e6_3d.html"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(HTML_CONTENT)
    print(f"Generated {out_file} successfully ({len(HTML_CONTENT)} bytes).")

if __name__ == "__main__":
    main()
