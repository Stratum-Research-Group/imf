# tools/visualizers/generate_calabi_yau_interactive_3d.py
import json

html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>IMF Calabi-Yau Quintic Threefold Cross-Section (3D WebGL)</title>
    <style>
        body { margin: 0; background: #020306; color: #eee; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; overflow: hidden; }
        #canvas { width: 100vw; height: 100vh; display: block; }
        #overlay { position: absolute; top: 16px; left: 16px; background: rgba(6,10,18,0.85); padding: 18px; border-radius: 8px; border: 1px solid #1a283e; max-width: 440px; box-shadow: 0 4px 20px rgba(0,0,0,0.6); }
        h1 { margin: 0 0 8px 0; font-size: 18px; color: #ff007f; letter-spacing: 0.5px; }
        p { margin: 4px 0; font-size: 13px; color: #90a4ae; line-height: 1.4; }
        .badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 11px; background: #4a148c; color: #ea80fc; margin-top: 6px; }
    </style>
</head>
<body>
    <div id="overlay">
        <h1>Calabi-Yau Quintic Threefold Slice (CY₃)</h1>
        <p><strong>Fermat Hypersurface:</strong> z₁⁵ + z₂⁵ + z₃⁵ + z₄⁵ + z₅⁵ = 0 ⊂ ℂℙ⁴</p>
        <p><strong>Geometric Metric:</strong> Ricci-flat Kähler Metric (R_ij = 0, SU(3) Holonomy)</p>
        <p><strong>Compactification:</strong> 2D real slice of the 6D internal manifold preserving N=1 supersymmetry and zero cosmological vacuum drift.</p>
        <div class="badge">Blackwell In-Register Polytope Geometry</div>
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

        // Generate 5-sheeted cross section of the quintic threefold
        const numSheets = 5;
        const uSteps = 40;
        const vSteps = 60;
        const scale = 3.2;

        for (let k = 0; k < numSheets; k++) {
            const phi_k = (2.0 * Math.PI * k) / 5.0;
            const geometry = new THREE.BufferGeometry();
            const positions = [];
            const colors = [];

            for (let i = 0; i <= uSteps; i++) {
                const r = (i / uSteps) * 0.96; // radius |z1| < 1
                for (let j = 0; j <= vSteps; j++) {
                    const theta = (j / vSteps) * 2.0 * Math.PI;

                    // z1 = r * exp(i * theta)
                    // z2 = exp(i * phi_k) * (1 - z1^5)^(1/5)
                    const z1_5_re = Math.pow(r, 5) * Math.cos(5 * theta);
                    const z1_5_im = Math.pow(r, 5) * Math.sin(5 * theta);

                    const one_minus_re = 1.0 - z1_5_re;
                    const one_minus_im = -z1_5_im;

                    const mag = Math.hypot(one_minus_re, one_minus_im);
                    const arg = Math.atan2(one_minus_im, one_minus_re);

                    const r2 = Math.pow(mag, 0.2);
                    const theta2 = (arg + phi_k) / 5.0;

                    // Real 3D projection: (Re(z1), Im(z1), Re(z2))
                    const x = r * Math.cos(theta) * scale;
                    const y = r * Math.sin(theta) * scale;
                    const z = r2 * Math.cos(theta2) * scale;

                    positions.push(x, y, z);

                    const color = new THREE.Color();
                    color.setHSL((k / 5.0) * 0.8 + 0.1, 0.9, 0.5 + 0.2 * (z / scale));
                    colors.push(color.r, color.g, color.b);
                }
            }

            // Create index triangles
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

            const material = new THREE.MeshPhongMaterial({
                vertexColors: true,
                side: THREE.DoubleSide,
                transparent: true,
                opacity: 0.72,
                wireframe: false,
                shininess: 90
            });

            const mesh = new THREE.Mesh(geometry, material);
            group.add(mesh);

            // Add wireframe overlay for topological ribs
            const wireMat = new THREE.MeshBasicMaterial({ color: 0xff007f, wireframe: true, transparent: true, opacity: 0.25 });
            const wireMesh = new THREE.Mesh(geometry, wireMat);
            group.add(wireMesh);
        }

        // Lighting
        const light1 = new THREE.DirectionalLight(0xffffff, 1.2);
        light1.position.set(5, 10, 7);
        scene.add(light1);

        const light2 = new THREE.DirectionalLight(0x00e5ff, 0.8);
        light2.position.set(-5, -10, -7);
        scene.add(light2);

        scene.add(new THREE.AmbientLight(0x221133));

        camera.position.set(0, 4, 9);
        camera.lookAt(0, 0, 0);

        let clock = new THREE.Clock();
        function animate() {
            requestAnimationFrame(animate);
            const t = clock.getElapsedTime() * 0.25;
            group.rotation.x = t * 0.4;
            group.rotation.y = t * 0.6;
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

with open("docs/assets/calabi_yau_interactive_3d.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("[✓] Successfully generated docs/assets/calabi_yau_interactive_3d.html")
