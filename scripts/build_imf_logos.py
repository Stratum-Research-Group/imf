#!/usr/bin/env python3
"""
Generate 7 distinct, precision IMF (Interaction Model Foundations) logos matching
the dimensions, typography, layout, and studio line-art aesthetic of dioptra_logo.jpg (1376x768).

Layout:
  [Left: Mathematical / Architectural Emblem] | IMF
                                                Stratum
                                                Research
                                                Group

Concepts:
  01 - Enneazetton 9D Polytope & Barycentric Simplex Lattice (Higher-Dimensional Polytope Landmark Connector)
  02 - Symmetric-Antisymmetric Lie-Algebraic Memory Split (SAVG Decomposition: Symmetric Kernel + Antisymmetric Commutator)
  03 - Directional Phase Inversion & Causal Wavefront (Reversal Curse Elimination: Forward vs Backward Phase)
  04 - Degen's Eight-Square Identity & Octonionic Fibration (Circuit Lower Bounds & Normed Algebra Memory)
  05 - Virtual Grid Torus & Continuous Crossing Flow (Continuous Crossing Bounds & $O(N)$ Context Scaling)
  06 - Decayotton 10D Decagonal Projection & Landmark Orbit (Decagonal Polytope Vertex System)
  07 - Hendecaxennon 11D Hyper-Foliation & Coordinate Bastion (11D Higher-Arity Simplex Coordinate Frame)
"""

import math
import os
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Canvas dimensions (exact match to dioptra_logo.jpg)
WIDTH = 1376
HEIGHT = 768
SCALE = 2  # 2x supersampling for ultra-crisp anti-aliasing
W_S = WIDTH * SCALE
H_S = HEIGHT * SCALE

# Typography & Layout anchors (in 1x coordinates, matching dioptra / metis standard)
DIVIDER_X = 631
DIVIDER_TOP = 185
DIVIDER_BOT = 582
DIVIDER_WIDTH = 11

TEXT_X = 688
TITLE_Y = 184  # Font size 178 puts cap-top at y=216
SUB_X = 690
SUB_Y1 = 354  # "Stratum"
SUB_Y2 = 429  # "Research"
SUB_Y3 = 504  # "Group"

EMBLEM_CX = 390
EMBLEM_CY = 384

FONT_CANDIDATES = [
    os.environ.get("IMF_FONT_PATH", ""),
    "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/Adwaita/AdwaitaSans-Regular.ttf",
]
FONT_PATH = next((p for p in FONT_CANDIDATES if p and os.path.exists(p)), None)


def _get_font(size: int):
    if FONT_PATH and os.path.exists(FONT_PATH):
        try:
            return ImageFont.truetype(FONT_PATH, size)
        except Exception:
            pass
    return ImageFont.load_default()


def create_studio_background(w, h, seed=42):
    """Generate subtle studio paper off-white background with micro-grain noise."""
    rng = np.random.default_rng(seed)
    y_grad = np.linspace(231.8, 230.5, h)[:, None]
    x_grad = np.linspace(231.2, 230.8, w)[None, :]
    base_luma = (y_grad + x_grad) / 2.0

    bg = np.zeros((h, w, 3), dtype=np.float32)
    bg[:, :, 0] = base_luma
    bg[:, :, 1] = base_luma
    bg[:, :, 2] = base_luma - 1.2  # subtle warm paper undertone

    noise = rng.normal(0.0, 1.8, size=(h, w, 3))
    bg = np.clip(bg + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(bg)


def render_base_template(draw, scale=SCALE):
    """Render the vertical divider bar and standard text: IMF / Stratum Research Group."""
    # Divider line
    div_x = DIVIDER_X * scale
    div_w = DIVIDER_WIDTH * scale
    y0 = DIVIDER_TOP * scale
    y1 = DIVIDER_BOT * scale
    draw.rounded_rectangle([div_x - div_w // 2, y0, div_x + div_w // 2, y1], radius=scale, fill=(0, 0, 0, 255))

    # Fonts
    font_title = _get_font(int(178 * scale))
    font_sub = _get_font(int(76 * scale))

    # Text
    draw.text((int(TEXT_X * scale), int(TITLE_Y * scale)), "IMF", font=font_title, fill=(0, 0, 0, 255))
    draw.text((int(SUB_X * scale), int(SUB_Y1 * scale)), "Stratum", font=font_sub, fill=(0, 0, 0, 255))
    draw.text((int(SUB_X * scale), int(SUB_Y2 * scale)), "Research", font=font_sub, fill=(0, 0, 0, 255))
    draw.text((int(SUB_X * scale), int(SUB_Y3 * scale)), "Group", font=font_sub, fill=(0, 0, 0, 255))


# ---------------------------------------------------------------------------
# EMBLEM GENERATORS (Render at 2x scale directly onto transparent overlay)
# ---------------------------------------------------------------------------

def draw_concept_01_enneazetton_polytope(overlay, cx, cy, s):
    """Concept 01: Enneazetton 9D Polytope & Barycentric Simplex Lattice.
    9-vertex regular enneatopic projection with complete chord lattice and inner simplex focal ring.
    """
    draw = ImageDraw.Draw(overlay)
    n = 9
    r_outer = 155 * s
    r_inner = 80 * s
    
    # 9 Outer vertices
    pts_outer = []
    for i in range(n):
        ang = -math.pi / 2 + i * (2 * math.pi / n)
        pts_outer.append((cx + r_outer * math.cos(ang), cy + r_outer * math.sin(ang)))
        
    # 9 Inner harmonic vertices
    pts_inner = []
    for i in range(n):
        ang = -math.pi / 2 + (i + 0.5) * (2 * math.pi / n)
        pts_inner.append((cx + r_inner * math.cos(ang), cy + r_inner * math.sin(ang)))

    # Outer perimeter boundary
    for i in range(n):
        next_i = (i + 1) % n
        draw.line([pts_outer[i], pts_outer[next_i]], fill=(0, 0, 0, 255), width=int(8 * s))

    # Full pairwise chord lattice (stride 2, 3, 4)
    for stride, w in [(2, 5), (3, 4), (4, 3)]:
        for i in range(n):
            j = (i + stride) % n
            draw.line([pts_outer[i], pts_outer[j]], fill=(0, 0, 0, 255), width=int(w * s))

    # Internal simplex frame connecting to inner ring
    for i in range(n):
        draw.line([pts_outer[i], pts_inner[i]], fill=(0, 0, 0, 255), width=int(4 * s))
        next_in = (i + 1) % n
        draw.line([pts_inner[i], pts_inner[next_in]], fill=(0, 0, 0, 255), width=int(6 * s))

    # Central barycentric focal core
    r_core = 24 * s
    draw.ellipse([cx - r_core, cy - r_core, cx + r_core, cy + r_core], outline=(0, 0, 0, 255), width=int(7 * s))
    draw.ellipse([cx - 8 * s, cy - 8 * s, cx + 8 * s, cy + 8 * s], fill=(0, 0, 0, 255))

    # Vertex nodes
    for px, py in pts_outer:
        draw.ellipse([px - 9 * s, py - 9 * s, px + 9 * s, py + 9 * s], fill=(0, 0, 0, 255))
    for px, py in pts_inner:
        draw.ellipse([px - 6 * s, py - 6 * s, px + 6 * s, py + 6 * s], fill=(0, 0, 0, 255))


def draw_concept_02_savg_lie_algebraic_split(overlay, cx, cy, s):
    """Concept 02: Symmetric-Antisymmetric Lie-Algebraic Split (SAVG).
    Dual interwoven manifolds: Symmetric circular harmonic grid + Antisymmetric skew-symmetric hyperbolic lemniscate.
    """
    draw = ImageDraw.Draw(overlay)
    r_main = 150 * s

    # Outer metric coordinate ring
    draw.ellipse([cx - r_main, cy - r_main, cx + r_main, cy + r_main], outline=(0, 0, 0, 255), width=int(9 * s))

    # Symmetric Component: Concentric orthogonal coordinate circles & axis
    for r_sub in [105 * s, 60 * s]:
        draw.ellipse([cx - r_sub, cy - r_sub, cx + r_sub, cy + r_sub], outline=(0, 0, 0, 255), width=int(4 * s))
    
    # Coordinate axes
    draw.line([cx - r_main - 15 * s, cy, cx + r_main + 15 * s, cy], fill=(0, 0, 0, 255), width=int(5 * s))
    draw.line([cx, cy - r_main - 15 * s, cx, cy + r_main + 15 * s], fill=(0, 0, 0, 255), width=int(5 * s))

    # Antisymmetric Component: Skew-symmetric dual rotated lemniscate loops / commutator lobes
    # Parametric figure-8 / lemniscate rotated at 45 degrees
    lobes_a = []
    lobes_b = []
    steps = 180
    a = 135 * s
    for t_i in range(steps + 1):
        t = t_i * (2 * math.pi / steps)
        # Lemniscate of Bernoulli: x = a*cos(t)/(1+sin(t)^2), y = a*sin(t)*cos(t)/(1+sin(t)^2)
        denom = 1 + math.sin(t)**2
        lx = a * math.cos(t) / denom
        ly = a * math.sin(t) * math.cos(t) / denom
        # Rotate by +45 deg
        rx1 = (lx - ly) * math.sqrt(0.5)
        ry1 = (lx + ly) * math.sqrt(0.5)
        lobes_a.append((cx + rx1, cy + ry1))
        # Rotate by -45 deg (counter-phase)
        rx2 = (lx + ly) * math.sqrt(0.5)
        ry2 = (-lx + ly) * math.sqrt(0.5)
        lobes_b.append((cx + rx2, cy + ry2))

    for k in range(len(lobes_a) - 1):
        draw.line([lobes_a[k], lobes_a[k + 1]], fill=(0, 0, 0, 255), width=int(7 * s))
        draw.line([lobes_b[k], lobes_b[k + 1]], fill=(0, 0, 0, 255), width=int(5 * s))

    # Commutator central intersection singularity & anchor satellites
    r_core = 20 * s
    draw.ellipse([cx - r_core, cy - r_core, cx + r_core, cy + r_core], fill=(232, 232, 230, 255), outline=(0, 0, 0, 255), width=int(7 * s))
    draw.ellipse([cx - 8 * s, cy - 8 * s, cx + 8 * s, cy + 8 * s], fill=(0, 0, 0, 255))

    # Cardinal tick marks
    for ang in [0, math.pi/2, math.pi, 3*math.pi/2]:
        px = cx + (r_main + 15 * s) * math.cos(ang)
        py = cy + (r_main + 15 * s) * math.sin(ang)
        draw.ellipse([px - 6 * s, py - 6 * s, px + 6 * s, py + 6 * s], fill=(0, 0, 0, 255))


def draw_concept_03_directional_phase_inversion(overlay, cx, cy, s):
    """Concept 03: Directional Phase Inversion & Causal Wavefront.
    Resolves the Reversal Curse: Forward/backward phase interference pattern with directional wave crests and asymmetric focal point.
    """
    draw = ImageDraw.Draw(overlay)
    r_bound = 152 * s
    
    # Outer circular frame
    draw.ellipse([cx - r_bound, cy - r_bound, cx + r_bound, cy + r_bound], outline=(0, 0, 0, 255), width=int(9 * s))

    # Opposing logarithmic spiral wavefronts (Forward causal spiral vs Inverted anti-causal spiral)
    # Forward wave (clock-wise)
    steps = 200
    spiral_fwd = []
    spiral_rev = []
    for i in range(steps):
        theta = i * (4 * math.pi / steps)
        r = (18 * s) + (130 * s) * (i / steps)**1.1
        spiral_fwd.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
        spiral_rev.append((cx + r * math.cos(theta + math.pi), cy + r * math.sin(theta + math.pi)))

    for i in range(len(spiral_fwd) - 1):
        draw.line([spiral_fwd[i], spiral_fwd[i+1]], fill=(0, 0, 0, 255), width=int(7 * s))
        draw.line([spiral_rev[i], spiral_rev[i+1]], fill=(0, 0, 0, 255), width=int(7 * s))

    # Directional phase wavefront arcs (concentric shifted arcs)
    for r in [55 * s, 90 * s, 125 * s]:
        draw.arc([cx - r, cy - r, cx + r, cy + r], start=30, end=150, fill=(0, 0, 0, 255), width=int(5 * s))
        draw.arc([cx - r, cy - r, cx + r, cy + r], start=210, end=330, fill=(0, 0, 0, 255), width=int(5 * s))

    # Asymmetric directional axis with arrow indicators
    draw.line([cx - r_bound - 12 * s, cy, cx + r_bound + 12 * s, cy], fill=(0, 0, 0, 255), width=int(6 * s))
    # Right-pointing forward phase chevron
    arr_x = cx + r_bound - 15 * s
    draw.line([arr_x - 18 * s, cy - 18 * s, arr_x, cy], fill=(0, 0, 0, 255), width=int(7 * s))
    draw.line([arr_x - 18 * s, cy + 18 * s, arr_x, cy], fill=(0, 0, 0, 255), width=int(7 * s))

    # Center phase inversion core (dipole)
    draw.ellipse([cx - 28 * s, cy - 28 * s, cx + 28 * s, cy + 28 * s], fill=(232, 232, 230, 255), outline=(0, 0, 0, 255), width=int(6 * s))
    # Dipole nodes: one solid, one ring
    draw.ellipse([cx - 14 * s, cy - 8 * s, cx - 2 * s, cy + 4 * s], fill=(0, 0, 0, 255))
    draw.ellipse([cx + 2 * s, cy - 8 * s, cx + 14 * s, cy + 4 * s], outline=(0, 0, 0, 255), width=int(4 * s))


def draw_concept_04_degens_eight_square_algebra(overlay, cx, cy, s):
    """Concept 04: Degen's Eight-Square Identity & Octonionic Fibration.
    8-fold orthogonal symmetry: Two interlocking 4-squares (octagram) with internal fibration lines and norm invariance ring.
    """
    draw = ImageDraw.Draw(overlay)
    r_outer = 152 * s
    r_inner = 95 * s

    # Two concentric squares rotated by 45 degrees forming regular octagram {8/2}
    pts_sq1 = []
    pts_sq2 = []
    for i in range(4):
        ang1 = i * (math.pi / 2.0)
        ang2 = ang1 + (math.pi / 4.0)
        pts_sq1.append((cx + r_outer * math.cos(ang1), cy + r_outer * math.sin(ang1)))
        pts_sq2.append((cx + r_outer * math.cos(ang2), cy + r_outer * math.sin(ang2)))

    # Outer enclosing norm boundary circle
    draw.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer], outline=(0, 0, 0, 255), width=int(6 * s))

    # Draw the two interlocking squares
    for i in range(4):
        next_i = (i + 1) % 4
        draw.line([pts_sq1[i], pts_sq1[next_i]], fill=(0, 0, 0, 255), width=int(8 * s))
        draw.line([pts_sq2[i], pts_sq2[next_i]], fill=(0, 0, 0, 255), width=int(8 * s))

    # Octonionic Fibration: Connect all 8 outer vertices to opposite vertices (8-dimensional coordinate axes)
    all_pts = []
    for i in range(4):
        all_pts.append(pts_sq1[i])
        all_pts.append(pts_sq2[i])
    # Sort by angle
    all_pts.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))

    for i in range(4):
        opp_i = i + 4
        draw.line([all_pts[i], all_pts[opp_i]], fill=(0, 0, 0, 255), width=int(4 * s))

    # Intermediate octave ring
    draw.ellipse([cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner], outline=(0, 0, 0, 255), width=int(7 * s))

    # 8 Internal invariant nodes on the octave ring
    for i in range(8):
        ang = i * (2 * math.pi / 8)
        px = cx + r_inner * math.cos(ang)
        py = cy + r_inner * math.sin(ang)
        draw.ellipse([px - 8 * s, py - 8 * s, px + 8 * s, py + 8 * s], fill=(0, 0, 0, 255))

    # Central normed nucleus
    r_core = 26 * s
    draw.ellipse([cx - r_core, cy - r_core, cx + r_core, cy + r_core], fill=(232, 232, 230, 255), outline=(0, 0, 0, 255), width=int(8 * s))
    draw.ellipse([cx - 10 * s, cy - 10 * s, cx + 10 * s, cy + 10 * s], fill=(0, 0, 0, 255))

    # 8 Vertex spheres
    for px, py in all_pts:
        draw.ellipse([px - 10 * s, py - 10 * s, px + 10 * s, py + 10 * s], fill=(0, 0, 0, 255))


def draw_concept_05_virtual_grid_torus(overlay, cx, cy, s):
    """Concept 05: Virtual Grid Torus & Continuous Crossing Flow.
    Representing continuous crossing bounds and $O(N)$ linear memory scaling: An orthogonal toroidal grid manifold in isometric axonometry.
    """
    draw = ImageDraw.Draw(overlay)
    r_torus = 148 * s
    r_tube = 62 * s

    # Outer and inner toroidal boundary ellipses
    draw.ellipse([cx - r_torus, cy - (r_torus * 0.72), cx + r_torus, cy + (r_torus * 0.72)], outline=(0, 0, 0, 255), width=int(8 * s))
    draw.ellipse([cx - (r_torus - r_tube), cy - ((r_torus - r_tube) * 0.65), cx + (r_torus - r_tube), cy + ((r_torus - r_tube) * 0.65)], outline=(0, 0, 0, 255), width=int(7 * s))

    # Poloidal cross-sectional ellipses (ribs)
    num_ribs = 12
    for i in range(num_ribs):
        ang = i * (2 * math.pi / num_ribs)
        # Center of the tube ring at this angle
        rc = (r_torus - r_tube / 2)
        rx = cx + rc * math.cos(ang)
        ry = cy + (rc * 0.72) * math.sin(ang)
        
        # Tilt and radius of poloidal section
        w_rib = 24 * s
        h_rib = 46 * s
        # Draw inclined ellipse
        draw.ellipse([rx - w_rib, ry - h_rib, rx + w_rib, ry + h_rib], outline=(0, 0, 0, 255), width=int(4 * s))

    # Continuous crossing helical flow lines (streamlines wrapping around the torus)
    steps = 300
    flow1 = []
    flow2 = []
    for k in range(steps + 1):
        t = k * (2 * math.pi / steps)
        # Toroidal coordinates: phi = t, theta = 5*t
        phi = t
        theta = 4 * t
        R = (r_torus - r_tube / 2)
        r = r_tube / 2
        
        px1 = (R + r * math.cos(theta)) * math.cos(phi)
        py1 = (R + r * math.cos(theta)) * math.sin(phi) * 0.72 + r * math.sin(theta) * 0.4
        flow1.append((cx + px1, cy + py1))

        px2 = (R + r * math.cos(theta + math.pi)) * math.cos(phi)
        py2 = (R + r * math.cos(theta + math.pi)) * math.sin(phi) * 0.72 + r * math.sin(theta + math.pi) * 0.4
        flow2.append((cx + px2, cy + py2))

    for k in range(len(flow1) - 1):
        draw.line([flow1[k], flow1[k+1]], fill=(0, 0, 0, 255), width=int(5 * s))
        draw.line([flow2[k], flow2[k+1]], fill=(0, 0, 0, 255), width=int(5 * s))

    # Central aperture core
    draw.ellipse([cx - 16 * s, cy - 12 * s, cx + 16 * s, cy + 12 * s], fill=(0, 0, 0, 255))


def draw_concept_06_decayotton_decagonal_orbit(overlay, cx, cy, s):
    """Concept 06: Decayotton 10D Decagonal Projection & Landmark Orbit.
    10-dimensional regular polytope projection with dual nested decagonal shells and concentric landmark orbits.
    """
    draw = ImageDraw.Draw(overlay)
    n = 10
    r_outer = 155 * s
    r_mid = 110 * s
    r_inner = 65 * s

    pts_outer = []
    pts_mid = []
    pts_inner = []
    for i in range(n):
        ang = -math.pi / 2 + i * (2 * math.pi / n)
        pts_outer.append((cx + r_outer * math.cos(ang), cy + r_outer * math.sin(ang)))
        pts_mid.append((cx + r_mid * math.cos(ang + math.pi / n), cy + r_mid * math.sin(ang + math.pi / n)))
        pts_inner.append((cx + r_inner * math.cos(ang), cy + r_inner * math.sin(ang)))

    # Outer decagon perimeter
    for i in range(n):
        next_i = (i + 1) % n
        draw.line([pts_outer[i], pts_outer[next_i]], fill=(0, 0, 0, 255), width=int(8 * s))

    # Middle decagon
    for i in range(n):
        next_i = (i + 1) % n
        draw.line([pts_mid[i], pts_mid[next_i]], fill=(0, 0, 0, 255), width=int(6 * s))

    # Inner decagon
    for i in range(n):
        next_i = (i + 1) % n
        draw.line([pts_inner[i], pts_inner[next_i]], fill=(0, 0, 0, 255), width=int(5 * s))

    # Polytope radial connector trusses between outer, mid, and inner
    for i in range(n):
        next_i = (i + 1) % n
        draw.line([pts_outer[i], pts_mid[i]], fill=(0, 0, 0, 255), width=int(4 * s))
        draw.line([pts_outer[next_i], pts_mid[i]], fill=(0, 0, 0, 255), width=int(4 * s))
        draw.line([pts_mid[i], pts_inner[i]], fill=(0, 0, 0, 255), width=int(4 * s))
        draw.line([pts_mid[i], pts_inner[next_i]], fill=(0, 0, 0, 255), width=int(4 * s))

    # 10D Decagonal star chords (stride 3)
    for i in range(n):
        j = (i + 3) % n
        draw.line([pts_outer[i], pts_outer[j]], fill=(0, 0, 0, 255), width=int(3 * s))

    # Central nucleus
    r_core = 22 * s
    draw.ellipse([cx - r_core, cy - r_core, cx + r_core, cy + r_core], fill=(232, 232, 230, 255), outline=(0, 0, 0, 255), width=int(7 * s))
    draw.ellipse([cx - 8 * s, cy - 8 * s, cx + 8 * s, cy + 8 * s], fill=(0, 0, 0, 255))

    # Landmark nodes
    for px, py in pts_outer:
        draw.ellipse([px - 9 * s, py - 9 * s, px + 9 * s, py + 9 * s], fill=(0, 0, 0, 255))
    for px, py in pts_mid:
        draw.ellipse([px - 6 * s, py - 6 * s, px + 6 * s, py + 6 * s], fill=(0, 0, 0, 255))


def draw_concept_07_hendecaxennon_coordinate_frame(overlay, cx, cy, s):
    """Concept 07: Hendecaxennon 11D Hyper-Foliation & Coordinate Bastion.
    11-simplex higher-arity polytope coordinate frame with chiral metric foliation and hyper-dimensional geodesic axes.
    """
    draw = ImageDraw.Draw(overlay)
    n = 11
    r_outer = 155 * s
    r_in = 75 * s

    pts_outer = []
    for i in range(n):
        ang = -math.pi / 2 + i * (2 * math.pi / n)
        pts_outer.append((cx + r_outer * math.cos(ang), cy + r_outer * math.sin(ang)))

    # Outer 11-gon boundary
    for i in range(n):
        next_i = (i + 1) % n
        draw.line([pts_outer[i], pts_outer[next_i]], fill=(0, 0, 0, 255), width=int(8 * s))

    # Complete 11-simplex star lattice chords (chiral strides 2, 4, 5)
    for stride, w in [(2, 5), (4, 4), (5, 3)]:
        for i in range(n):
            j = (i + stride) % n
            draw.line([pts_outer[i], pts_outer[j]], fill=(0, 0, 0, 255), width=int(w * s))

    # Concentric metric foliation circles
    for r in [115 * s, 80 * s, 45 * s]:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(0, 0, 0, 255), width=int(4 * s))

    # 11 Coordinate radial axes emanating from core
    for px, py in pts_outer:
        draw.line([cx, cy, px, py], fill=(0, 0, 0, 255), width=int(3 * s))

    # Central 11-dimensional singularity core
    r_core = 26 * s
    draw.ellipse([cx - r_core, cy - r_core, cx + r_core, cy + r_core], fill=(232, 232, 230, 255), outline=(0, 0, 0, 255), width=int(8 * s))
    draw.ellipse([cx - 10 * s, cy - 10 * s, cx + 10 * s, cy + 10 * s], fill=(0, 0, 0, 255))

    # 11 Landmark vertices
    for px, py in pts_outer:
        draw.ellipse([px - 9 * s, py - 9 * s, px + 9 * s, py + 9 * s], fill=(0, 0, 0, 255))


# Concept Registry
CONCEPTS = [
    {
        "id": "imf_logo_01_enneazetton_polytope",
        "title": "Enneazetton 9D Polytope & Barycentric Simplex Lattice",
        "desc": "9-vertex higher-dimensional polytope projection with pairwise chord lattice and inner barycentric simplex frame (IMF Landmark Connector).",
        "draw_fn": draw_concept_01_enneazetton_polytope,
    },
    {
        "id": "imf_logo_02_savg_lie_split",
        "title": "Symmetric-Antisymmetric Lie-Algebraic Split (SAVG)",
        "desc": "Dual interwoven manifolds: Symmetric harmonic coordinate grid + Antisymmetric skew-symmetric commutator lemniscate (Lie-Algebraic Memory).",
        "draw_fn": draw_concept_02_savg_lie_algebraic_split,
    },
    {
        "id": "imf_logo_03_directional_phase_inversion",
        "title": "Directional Phase Inversion & Causal Wavefront",
        "desc": "Opposing spiral wavefronts and directional phase chevron eliminating backward associative hallucination and the Reversal Curse.",
        "draw_fn": draw_concept_03_directional_phase_inversion,
    },
    {
        "id": "imf_logo_04_degens_eight_square",
        "title": "Degen's Eight-Square Identity & Octonionic Fibration",
        "desc": "8-fold orthogonal octagram symmetry with coordinate fibration and central normed invariant core (Lean 4 circuit lower bounds).",
        "draw_fn": draw_concept_04_degens_eight_square_algebra,
    },
    {
        "id": "imf_logo_05_virtual_grid_torus",
        "title": "Virtual Grid Torus & Continuous Crossing Flow",
        "desc": "Axonometric toroidal manifold with continuous helical streamlines and poloidal coordinate sections ($O(N)$ linear memory scaling).",
        "draw_fn": draw_concept_05_virtual_grid_torus,
    },
    {
        "id": "imf_logo_06_decayotton_decagonal_orbit",
        "title": "Decayotton 10D Decagonal Projection & Landmark Orbit",
        "desc": "10-dimensional regular polytope projection with nested decagonal shells, radial trusses, and orbit landmarks.",
        "draw_fn": draw_concept_06_decayotton_decagonal_orbit,
    },
    {
        "id": "imf_logo_07_hendecaxennon_coordinate_frame",
        "title": "Hendecaxennon 11D Hyper-Foliation & Coordinate Bastion",
        "desc": "11-simplex higher-arity polytope coordinate frame with complete chiral chords and metric foliation rings.",
        "draw_fn": draw_concept_07_hendecaxennon_coordinate_frame,
    },
]


def main():
    repo_root = Path(__file__).resolve().parent.parent
    imf_assets = repo_root / "assets" / "logos"
    imf_assets.mkdir(parents=True, exist_ok=True)
    branding_dir = repo_root.parent.parent / "z.branding"

    print(f"[*] Building 7 precision IMF logos at {WIDTH}x{HEIGHT} (2x supersampled to {W_S}x{H_S})...")

    # Base studio background with micro-grain noise matching dioptra_logo.jpg
    base_bg = create_studio_background(WIDTH, HEIGHT, seed=2026)

    for i, c in enumerate(CONCEPTS):
        print(f"[{i+1}/7] Rendering {c['id']}: {c['title']}...")

        # 1. Create 2x transparent overlay
        overlay = Image.new("RGBA", (W_S, H_S), (0, 0, 0, 0))

        # 2. Render Left Emblem
        c["draw_fn"](overlay, EMBLEM_CX * SCALE, EMBLEM_CY * SCALE, SCALE)

        # 3. Render layout template (Divider + Typography: IMF / Stratum Research Group)
        draw_overlay = ImageDraw.Draw(overlay)
        render_base_template(draw_overlay, scale=SCALE)

        # 4. Downsample overlay with Lanczos anti-aliasing
        overlay_1x = overlay.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)

        # 5. Composite onto studio paper background
        composite = base_bg.copy()
        composite.paste(overlay_1x, (0, 0), overlay_1x)

        # 6. Save outputs: high-quality JPEG and lossless PNG
        jpg_path = imf_assets / f"{c['id']}.jpg"
        png_path = imf_assets / f"{c['id']}.png"
        composite.save(jpg_path, quality=98, subsampling=0)
        composite.save(png_path)

        # Also copy primary variant to /assets/imf_logo.jpg for default repo presentation
        if i == 0:
            default_jpg = repo_root / "assets" / "imf_logo.jpg"
            default_png = repo_root / "assets" / "imf_logo.png"
            composite.save(default_jpg, quality=98, subsampling=0)
            composite.save(default_png)
            print(f"      -> Created default primary logo: {default_jpg}")

        # Also copy to z.branding if available
        if branding_dir.is_dir():
            import shutil
            shutil.copy(jpg_path, branding_dir / jpg_path.name)
            shutil.copy(png_path, branding_dir / png_path.name)

        print(f"      -> Saved {jpg_path} and {png_path}")

    print("[+] All 7 IMF logos created successfully!")


if __name__ == "__main__":
    main()
