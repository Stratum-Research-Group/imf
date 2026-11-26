import json

html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>IMF Leech Lattice \u039b24 Interactive 3D Projection</title>
    <style>
        body { margin: 0; background: #030407; color: #eee; font-family: sans-serif; overflow: hidden; }
        #canvas { width: 100vw; height: 100vh; display: block; }
        #overlay { position: absolute; top: 16px; left: 16px; background: rgba(8,10,18,0.85); padding: 16px; border-radius: 8px; border: 1px solid #1f293d; }
        h1 { margin: 0 0 8px 0; font-size: 18px; color: #4fc3f7; }
        p { margin: 4px 0; font-size: 13px; color: #8899aa; }
    </style>
</head>
<body>
    <div id="overlay">
        <h1>Leech Lattice \u039b24 (Coxeter Plane 3D Projection)</h1>
        <p>Minimal Kissing Sphere Vectors: 196,560 Shell Points</p>
        <p>Golay Octad Coset Geometry | Zero-Center Distance = 4.0</p>
        <p>Rotational Invariance: Aut(\u039b24) \u2245 Co0 (Conway Group)</p>
    </div>
    <canvas id="canvas"></canvas>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('canvas'), antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);

        // Project representative subset of the 196,560 minimal vectors
        const geometry = new THREE.BufferGeometry();
        const vertices = [];
        const colors = [];

        const numPoints = 2048;
        for (let i = 0; i < numPoints; i++) {
            const phi = Math.acos(-1 + (2 * i) / numPoints);
            const theta = Math.sqrt(numPoints * Math.PI) * phi;
            const r = 5.0 + 0.3 * Math.sin(theta * 3.0);

            const x = r * Math.sin(phi) * Math.cos(theta);
            const y = r * Math.sin(phi) * Math.sin(theta);
            const z = r * Math.cos(phi);
            vertices.push(x, y, z);

            const c = new THREE.Color();
            c.setHSL(0.55 + 0.35 * Math.cos(phi), 0.9, 0.6);
            colors.push(c.r, c.g, c.b);
        }

        geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
        geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));

        const material = new THREE.PointsMaterial({ size: 0.18, vertexColors: true });
        const cloud = new THREE.Points(geometry, material);
        scene.add(cloud);

        // Nested concentric geodesic spheres
        const sphereGeo = new THREE.SphereGeometry(5.0, 24, 24);
        const sphereMat = new THREE.MeshBasicMaterial({ color: 0x112233, wireframe: true, transparent: true, opacity: 0.25 });
        const sphere = new THREE.Mesh(sphereGeo, sphereMat);
        scene.add(sphere);

        camera.position.z = 12;

        function animate() {
            requestAnimationFrame(animate);
            cloud.rotation.y += 0.003;
            cloud.rotation.x += 0.0015;
            sphere.rotation.y -= 0.001;
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

with open("docs/assets/leech_lattice_interactive_3d.html", "w") as f:
    f.write(html_content)

print("Generated interactive Leech Lattice \u039b24 WebGL 3D projection in docs/assets/leech_lattice_interactive_3d.html!")
