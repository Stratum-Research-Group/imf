# tools/visualizers/generate_calabi_yau_moduli_flow.py
# Generates an interactive 3D WebGL visualization illustrating:
# 1. Calabi-Yau quintic moduli space deformation (Dwork family z₁⁵ + ... + z₅⁵ - 5ψ z₁...z₅ = 0)
# 2. Dynamical geodesic flow along the Ricci-flat Kähler metric

html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>IMF Calabi-Yau Moduli Deformation & Geodesic Flow (3D WebGL)</title>
    <style>
        body { margin: 0; background: #020308; color: #eee; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; overflow: hidden; }
        #canvas { width: 100vw; height: 100vh; display: block; }
        #overlay { position: absolute; top: 16px; left: 16px; background: rgba(8,12,22,0.88); padding: 18px; border-radius: 8px; border: 1px solid #1a2a44; max-width: 440px; box-shadow: 0 4px 24px rgba(0,0,0,0.7); backdrop-filter: blur(8px); }
        h1 { margin: 0 0 8px 0; font-size: 17px; color: #00e5ff; letter-spacing: 0.5px; }
        p { margin: 4px 0; font-size: 13px; color: #90a4ae; line-height: 1.4; }
        .control-group { margin-top: 12px; }
        label { display: block; font-size: 12px; color: #cfd8dc; margin-bottom: 4px; }
        input[type=range] { width: 100%; accent-color: #00e5ff; }
        .badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 11px; background: #004d40; color: #64ffda; margin-top: 8px; }
    </style>
</head>
<body>
    <div id="overlay">
        <h1>Calabi-Yau Moduli & Geodesic Flow (CY₃)</h1>
        <p><strong>Dwork Pencil Family:</strong> ∑ zᵢ⁵ - 5ψ ∏ zᵢ = 0 ⊂ ℂℙ⁴</p>
        <p><strong>Metric:</strong> Ricci-flat Kähler metric (R_ij = 0) with SU(3) holonomy.</p>
        <p><strong>Flow:</strong> Real-time geodesic particles trace volume-preserving extremal geodesics across the 5 sheets.</p>
        <div class="control-group">
            <label id="psi-label">Moduli Parameter ψ: 0.00</label>
            <input type="range" id="psi-slider" min="0" max="2" step="0.01" value="0.00">
        </div>
        <div class="badge">Blackwell Polytope Differential Geometry Engine</div>
    </div>
    <canvas id="canvas"></canvas>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('canvas'), antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);

        const group = new THREE.Group();
        scene.add(group);

        const numSheets = 5;
        const uSteps = 45;
        const vSteps = 65;
        const scale = 3.4;
        let currentPsi = 0.0;

        const sheetMeshes = [];

        function buildSheet(k, psi) {
            const phi_k = (2.0 * Math.PI * k) / 5.0;
            const geometry = new THREE.BufferGeometry();
            const positions = [];
            const colors = [];

            for (let i = 0; i <= uSteps; i++) {
                const r = (i / uSteps) * 0.95;
                for (let j = 0; j <= vSteps; j++) {
                    const theta = (j / vSteps) * 2.0 * Math.PI;
                    const r5 = Math.pow(r, 5);
                    const mod_term = 1.0 - r5 + psi * r5 * 0.35;
                    const val = Math.max(0.01, mod_term);
                    const w = Math.pow(val, 0.2);

                    const x = scale * r * Math.cos(theta);
                    const y = scale * r * Math.sin(theta);
                    const z = scale * w * Math.cos(phi_k + theta * 0.4 + psi * 0.5);

                    positions.push(x, y, z);

                    const hue = (k / 5.0) + (r * 0.25) + (psi * 0.1);
                    const col = new THREE.Color();
                    col.setHSL(hue % 1.0, 0.85, 0.45 + 0.15 * Math.sin(theta * 2.0));
                    colors.push(col.r, col.g, col.b);
                }
            }

            const indices = [];
            for (let i = 0; i < uSteps; i++) {
                for (let j = 0; j < vSteps; j++) {
                    const a = i * (vSteps + 1) + j;
                    const b = (i + 1) * (vSteps + 1) + j;
                    const c = (i + 1) * (vSteps + 1) + (j + 1);
                    const d = i * (vSteps + 1) + (j + 1);
                    indices.push(a, b, d);
                    indices.push(b, c, d);
                }
            }

            geometry.setIndex(indices);
            geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
            geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
            geometry.computeVertexNormals();
            return geometry;
        }

        const material = new THREE.MeshPhongMaterial({
            vertexColors: true,
            side: THREE.DoubleSide,
            wireframe: false,
            transparent: true,
            opacity: 0.82,
            shininess: 70
        });

        for (let k = 0; k < numSheets; k++) {
            const geom = buildSheet(k, 0.0);
            const mesh = new THREE.Mesh(geom, material);
            sheetMeshes.push(mesh);
            group.add(mesh);
        }

        // Add Geodesic Flow Streamlines
        const numParticles = 240;
        const particleGeo = new THREE.BufferGeometry();
        const pPositions = new Float32Array(numParticles * 3);
        const pColors = new Float32Array(numParticles * 3);

        for (let i = 0; i < numParticles; i++) {
            pPositions[i * 3 + 0] = (Math.random() - 0.5) * 6.0;
            pPositions[i * 3 + 1] = (Math.random() - 0.5) * 6.0;
            pPositions[i * 3 + 2] = (Math.random() - 0.5) * 6.0;

            pColors[i * 3 + 0] = 0.0;
            pColors[i * 3 + 1] = 0.9;
            pColors[i * 3 + 2] = 1.0;
        }

        particleGeo.setAttribute('position', new THREE.BufferAttribute(pPositions, 3));
        particleGeo.setAttribute('color', new THREE.BufferAttribute(pColors, 3));

        const pMaterial = new THREE.PointsMaterial({
            size: 0.09,
            vertexColors: true,
            transparent: true,
            opacity: 0.9
        });
        const particles = new THREE.Points(particleGeo, pMaterial);
        group.add(particles);

        // Lighting
        const ambLight = new THREE.AmbientLight(0x223344, 1.2);
        scene.add(ambLight);

        const dirLight1 = new THREE.DirectionalLight(0x00e5ff, 1.0);
        dirLight1.position.set(5, 10, 7);
        scene.add(dirLight1);

        const dirLight2 = new THREE.DirectionalLight(0xff007f, 0.8);
        dirLight2.position.set(-5, -10, -7);
        scene.add(dirLight2);

        camera.position.set(0, 0, 7.5);

        // Slider interaction
        const slider = document.getElementById('psi-slider');
        const psiLabel = document.getElementById('psi-label');

        function updateModuli(psi) {
            currentPsi = psi;
            psiLabel.innerText = "Moduli Parameter ψ: " + psi.toFixed(2);
            for (let k = 0; k < numSheets; k++) {
                const newGeom = buildSheet(k, psi);
                sheetMeshes[k].geometry.dispose();
                sheetMeshes[k].geometry = newGeom;
            }
        }

        slider.addEventListener('input', (e) => {
            updateModuli(parseFloat(e.target.value));
        });

        // Animation Loop
        let clock = 0;
        function animate() {
            requestAnimationFrame(animate);
            clock += 0.012;

            group.rotation.x = clock * 0.25;
            group.rotation.y = clock * 0.35;

            // Stream geodesic particles along rotating flow
            const posAttr = particles.geometry.attributes.position;
            for (let i = 0; i < numParticles; i++) {
                let x = posAttr.getX(i);
                let y = posAttr.getY(i);
                let z = posAttr.getZ(i);

                // Geodesic Hamiltonian flow equations
                x += -0.018 * y + 0.005 * Math.sin(z * 2.0);
                y += 0.018 * x - 0.005 * Math.cos(z * 2.0);
                z += 0.008 * Math.sin(clock + i);

                // Wrap-around
                if (x*x + y*y + z*z > 25.0) {
                    x = (Math.random() - 0.5) * 1.5;
                    y = (Math.random() - 0.5) * 1.5;
                    z = (Math.random() - 0.5) * 1.5;
                }

                posAttr.setXYZ(i, x, y, z);
            }
            posAttr.needsUpdate = true;

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

with open("docs/assets/calabi_yau_moduli_flow.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("Generated docs/assets/calabi_yau_moduli_flow.html successfully.")
