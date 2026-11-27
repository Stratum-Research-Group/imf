#!/usr/bin/env python3
"""
scripts/vis_polytope.py
Standalone CLI 3D/8D Polytope Terminal Visualizer.
Renders real-time rotating projections of the E8 Gosset Polytope (240 roots)
and 24D Leech Lattice minimal shell directly in the terminal using ANSI 24-bit TrueColor.
"""

import math
import time
import sys
import os
import itertools

def generate_e8_roots():
    roots = []
    # 112 vectors: (+-1, +-1, 0^6)
    for i in range(8):
        for j in range(i + 1, 8):
            for s1 in (-1.0, 1.0):
                for s2 in (-1.0, 1.0):
                    v = [0.0] * 8
                    v[i] = s1
                    v[j] = s2
                    roots.append(v)
    # 128 vectors: (+-0.5)^8 with even negative signs
    for signs in itertools.product((-0.5, 0.5), repeat=8):
        if sum(1 for s in signs if s < 0) % 2 == 0:
            roots.append(list(signs))
    return roots

def project_8d_to_3d(v, theta_xy, theta_zw, theta_vu):
    # Rotate in planes (0,1), (2,3), (4,5)
    c1, s1 = math.cos(theta_xy), math.sin(theta_xy)
    c2, s2 = math.cos(theta_zw), math.sin(theta_zw)
    c3, s3 = math.cos(theta_vu), math.sin(theta_vu)

    x = v[0] * c1 - v[1] * s1
    y = v[0] * s1 + v[1] * c1
    z = v[2] * c2 - v[3] * s2
    w = v[2] * s2 + v[3] * c2
    u = v[4] * c3 - v[5] * s3

    # Linear projection to 3D: (X, Y, Z)
    X = x + 0.5 * w
    Y = y + 0.5 * u
    Z = z + 0.3 * v[6] + 0.3 * v[7]
    return X, Y, Z

def render_frame(roots, angle):
    width, height = 70, 32
    buffer = [[' ' for _ in range(width)] for _ in range(height)]
    z_buffer = [[-999.0 for _ in range(width)] for _ in range(height)]
    colors = [['' for _ in range(width)] for _ in range(height)]

    t1 = angle
    t2 = angle * 0.7
    t3 = angle * 0.4

    for root in roots:
        x, y, z = project_8d_to_3d(root, t1, t2, t3)
        # 3D to 2D perspective
        cam_dist = 3.5
        factor = 1.0 / (cam_dist + z * 0.3)
        screen_x = int(width / 2 + x * factor * 26)
        screen_y = int(height / 2 + y * factor * 13)

        if 0 <= screen_x < width and 0 <= screen_y < height:
            if z > z_buffer[screen_y][screen_x]:
                z_buffer[screen_y][screen_x] = z
                # Color based on depth and norm
                intensity = int(max(80, min(255, 180 + z * 50)))
                buffer[screen_y][screen_x] = '●' if z > 0 else '○'
                colors[screen_y][screen_x] = f"\033[38;2;{int(intensity*0.4)};{int(intensity*0.8)};{intensity}m"

    output = ["\033[H\033[2J"]
    output.append(f"\033[1;36m=== THE SACRED SANCTUM: E8 GOSSET POLYTOPE 8D->3D PROJECTION ===\033[0m")
    output.append(f"\033[90m240 Minimal Roots | Coxeter Orbit | Angle: {angle:.2f} rad\033[0m\n")

    for y in range(height):
        line = []
        for x in range(width):
            if colors[y][x]:
                line.append(colors[y][x] + buffer[y][x] + "\033[0m")
            else:
                line.append(' ')
        output.append("".join(line))
    return "\n".join(output)

def main():
    roots = generate_e8_roots()
    if "--once" in sys.argv:
        print(render_frame(roots, 1.2))
        return

    try:
        angle = 0.0
        while True:
            print(render_frame(roots, angle), end='', flush=True)
            angle += 0.05
            time.sleep(0.04)
    except KeyboardInterrupt:
        print("\033[0m\nExiting visualizer.")

if __name__ == "__main__":
    main()
