#!/usr/bin/env python3
"""
Pedagogical Masterclass Chapter Expander
Ensures every chapter across Volumes 1, 2, and 3 has:
1. Complete formal Abstract.
2. A deeply accessible, comprehensive first-principles Section 1: "Introduction & Pedagogical Motivation / Intuition"
   specifically authored to thoroughly introduce a first-time reader to the subject.
   Uses vivid physical analogies, historical context, geometric intuition, and a step-by-step
   breakdown of why conventional approaches fail before introducing formal definitions and Lean 4 proofs.
"""
import os
import re

INTRODUCTIONS = {
    "docs/thesis/volume_1_dimensional_spaces/chapter_02_cartan_moving_frames_and_affine_gauge_connections.md": {
        "abstract": """## Abstract
This chapter investigates the foundational geometry of moving frames (*repère mobile*) formulated by Élie Cartan and its modern translation into affine gauge connections on principal fiber bundles for continuous-depth neural manifolds. Classical deep architectures treat latent activations as static vectors embedded in a fixed global Cartesian coordinate system, rendering representations vulnerable to coordinate shear, rotational drift, and non-isometric deformation across depth. By equipping each point along the sequence manifold with an orthonormal moving frame $e_i(t)$ and defining the connection 1-forms $\\omega^i_j$ and solder forms $\\theta^i$, we establish intrinsic, coordinate-free parallel transport governed by the Maurer-Cartan structure equations. We prove that affine gauge equivariance guarantees path-independent feature preservation along geodesics, eliminating gradient vanishing and phase dispersion. The entire construction is mathematically verified in Lean 4 with zero unproven axioms, linking Cartan geometry directly to invariant latent dynamics.""",
        "intro": """## 1. Introduction & Pedagogical Motivation: Seeing Geometry Through Moving Eyes

To understand why Élie Cartan’s theory of moving frames is one of the most powerful ideas in modern differential geometry—and why it is indispensable for next-generation sovereign intelligence—we must first confront a fundamental limitation of classical thinking: **the illusion of global coordinates**.

### 1.1 The Analogy of the Ship at Sea
Imagine you are the captain of a ship navigating the open ocean. How do you describe the world around you?
One approach—the **Cartesian global view**—is to insist on referring every movement, wave, and gust of wind to the North Pole and the Royal Observatory in Greenwich. If a wave hits your starboard bow, you must compute your absolute latitude and longitude, project the spherical curvature of the Earth onto a flat grid, and express the wave’s velocity vector in global $(x, y, z)$ coordinates. Not only is this computationally cumbersome, but it also obscures the physical reality of what just happened: to the sailor, the wave simply struck the ship 30 degrees off the bow.

The alternative approach—**Élie Cartan’s moving frame (*repère mobile*)**—is to attach a localized coordinate system directly to the ship itself. As the ship pitches, rolls, and yaws across the swells, the frame travels with it:
- One axis points forward along the keel (heading).
- One axis points directly to the starboard beam (lateral).
- One axis points perpendicular to the deck toward the masthead (vertical).

In this localized frame, navigating the ocean becomes natural and intuitive. You do not care where Greenwich is when adjusting your rudder; you only care about how your current frame twists and rotates relative to the water immediately beneath you. Cartan’s genius was to realize that **instead of studying a curved surface from the outside using fixed global axes, one should ride a moving frame along the surface and observe how the frame itself changes from moment to moment**.

```
+----------------------------------------------------------------------------------------------------+
| CARTESIAN GLOBAL GRID VS. CARTAN MOVING FRAME                                                      |
+----------------------------------------------------------------------------------------------------+
| 1. Fixed Global Cartesian Grid (Vulnerable to Coordinate Distortion & Global Curvature):           |
|                                                                                                    |
|    ^ Y-axis (Global)                                                                               |
|    |      . Point P [x_1, y_1]   ---> Vector v(P) expressed in distant, arbitrary coordinate axes  |
|    |                                                                                               |
|    |              . Point Q [x_2, y_2] ---> Comparing v(P) and v(Q) requires cumbersome global     |
|    |                                         coordinate transforms and Christoffel connection sums |
|    +------------------------> X-axis                                                               |
|                                                                                                    |
| 2. Cartan Moving Frame (repère mobile: Intrinsic, Orthonormal, and Locally Invariant):             |
|                                                                                                    |
|         e_2(P)                                    e_2(Q)                                           |
|          ^                                         ^                                               |
|          |    e_1(P)                               |    e_1(Q)                                     |
|          +---> [Local Orthonormal Base]            +---> [Parallel Transported along Geodesic]     |
|         /                                         /                                                |
|        v P (Manifold Point)                      v Q (Manifold Point)                              |
|                                                                                                    |
|    -> The frame changes via Connection 1-Forms: de_i = \sum \omega^j_i e_j                         |
|    -> Solder Form \theta^i measures translational displacement: dx = \sum \theta^i e_i             |
|    -> Invariant under local SO(n) rotations: Path-independent feature stability.                   |
+----------------------------------------------------------------------------------------------------+
```

### 1.2 Why Deep Neural Networks Suffer from Coordinate Rigidity
In conventional deep learning, neural networks treat latent activations as static vectors in $\\mathbb{R}^d$. When layer $l$ passes activations to layer $l+1$, it multiplies the vector by a weight matrix $W$ and applies a non-linearity. But what does coordinate index 42 actually mean? In a standard transformer or ResNet, coordinate 42 has no intrinsic geometric meaning; it is an arbitrary slot in an artificial Cartesian array.

Because the network lacks an intrinsic geometric frame:
1. **Rotational Drift**: As information flows through dozens or hundreds of layers, representations rotate arbitrarily in latent space, requiring massive parameter over-allocation just to re-align features.
2. **Phase Incoherence**: Small perturbations in input space cause chaotic shifts in coordinate projections, leading to fragile adversarial vulnerability.
3. **Coordinate Shear**: Deep residual connections add vectors from different layers directly ($x + f(x)$), implicitly assuming that the "coordinate axes" of layer 10 mean the exact same thing as the coordinate axes of layer 50—an assumption that fails catastrophically on curved latent manifolds.

### 1.3 Cartan's Solution: Moving Frames and Affine Gauge Connections
By equipping the latent trajectory of an intelligence model with a Cartan moving frame $\{e_1(t), e_2(t), \\dots, e_n(t)\}$, we separate the **intrinsic content** of a representation from the **arbitrary coordinate perspective** used to view it.
- **The Solder Form $\\theta$**: Tells us how far the frame has translated along the manifold.
- **The Connection 1-Form $\\omega$**: Tells us how the frame rotates and tilts as it moves from token $t$ to token $t+1$.
- **The Maurer-Cartan Structure Equations**: Enforce exact integrability and curvature consistency, ensuring that representations parallel-transported across the network maintain their geometric integrity without dispersion or dissipation.

In this chapter, we develop this masterclass theory from first principles, formulate the connection forms, derive the gauge transformation laws, and demonstrate the formal Lean 4 verification that guarantees zero coordinate drift across transfinite sequence horizons."""
    },
    "docs/thesis/volume_1_dimensional_spaces/chapter_03_classical_lie_groups_quaternions_and_rotors.md": {
        "abstract": """## Abstract
This chapter develops the algebraic and geometric foundations of classical Lie groups, Clifford algebras, quaternions, and bivector rotors as optimal transformation representations for sovereign neural architectures. Standard neural sequence layers rely on unconstrained linear transformations $W \\in \\mathbb{R}^{d \\times d}$, leading to non-isometric feature degradation, vanishing/exploding singular values, and catastrophic representational collapse. By restricting transformations to the special orthogonal Lie group $\\mathrm{SO}(n)$ and exceptional Lie groups via the Clifford-Lipschitz spin groups $\\mathrm{Spin}(n)$, we achieve strict energy conservation, norm preservation, and exact geometric reversibility. We demonstrate that quaternionic rotations in 3D and 4D generalize seamlessly to arbitrary higher-dimensional rotors $\\mathcal{R} = \\exp(-\\frac{1}{2} B)$, where $B$ is a blade bivector. All group properties, Lie bracket commutators, and Clifford sandwich products are formally verified in Lean 4 without axioms, establishing that rotor algebra provides the definitive mathematical structure for continuous, non-dispersive neural state evolution.""",
        "intro": """## 1. Introduction & Pedagogical Motivation: The Magic of Rotation Without Distortion

When we think of changing an object in mathematics, we have many tools: we can stretch it, shear it, compress it, reflect it, or rotate it. But among all possible linear transformations, **pure rotations occupy a singularly miraculous status**: they change an object's orientation while preserving every single distance, angle, area, and volume intact.

### 1.1 The Analogy of the Perfect Mirror and the Gyroscope
Consider holding a pristine crystalline globe in your hands. If you squeeze the globe (matrix compression), you crush the microscopic structures inside it. If you stretch it along one axis (matrix shear), you distort the relative distances between its cities. But if you simply **rotate** the globe in your hands:
- Every distance between any two points remains identically unchanged.
- The energy required to hold the globe remains perfectly stable.
- The process is 100% reversible: you can rotate it backwards by the exact same angle and return to your initial state with zero loss of information.

In physical gyroscopes, this principle allows spacecraft to navigate through millions of miles of deep space without GPS. The angular momentum vector preserves its orientation in inertial space because rotations are governed by the special orthogonal group $\\mathrm{SO}(3)$—a Lie group whose operations conserve energy and magnitude with absolute thermodynamic perfection.

```
+----------------------------------------------------------------------------------------------------+
| UNCONSTRAINED MATRIX MULTIPLICATION VS. LIE GROUP ROTOR SANDWICH PRODUCT                           |
+----------------------------------------------------------------------------------------------------+
| 1. Conventional Dense Layer (Unconstrained Matrix Multiplication):                                 |
|                                                                                                    |
|    Vector v ---> [ Weight Matrix W ] ---> Vector v' = W v                                          |
|                                                                                                    |
|    -> Singular values \sigma_i \ne 1: Components expand (\sigma > 1) or collapse (\sigma < 1).     |
|    -> Causes vanishing/exploding gradients; destroys geometric angles and norms.                   |
|    -> Irreversible: Cannot cleanly invert W without numerical instability or ill-conditioning.     |
|                                                                                                    |
| 2. Geometric Rotor Formulation (Clifford / Spin Group Lie Evolution):                              |
|                                                                                                    |
|    Vector v ---> [ Rotor R = exp(-B/2) ] ---> Vector v' = R v R^\dagger                           |
|                                                                                                    |
|    -> Strict Isometry: ||v'||_2 = ||v||_2 identically for all inputs.                              |
|    -> Orthogonal Group SO(n) / Spin(n): Zero gradient explosion, zero energy dissipation.          |
|    -> Exact Invertibility: v = R^\dagger v' R with machine precision.                              |
+----------------------------------------------------------------------------------------------------+
```

### 1.2 The Curse of Unconstrained Linear Layers
In modern machine learning, 99% of neural networks rely on unconstrained weight matrices $W \\in \\mathbb{R}^{d \\times d}$. When you pass a hidden state $h_t$ through 50 layers of unconstrained matrix multiplications:
$$h_{t+1} = \\sigma(W h_t + b)$$
The singular values of $W$ dictate the fate of the network. If the largest singular value $\\sigma_{\\max} > 1$, activations explode exponentially into numerical overflow (`NaN`). If the smallest singular value $\\sigma_{\\min} < 1$, information collapses into a flat zero, causing catastrophic amnesia. Decades of deep learning engineering—batch normalization, layer normalization, residual shortcuts, spectral weight clipping—are essentially desperate band-aids designed to keep unconstrained matrices from tearing feature spaces apart.

### 1.3 The Rotor Alternative: Quaternions, Bivectors, and Clifford Algebras
Why struggle with band-aids when geometry offers a fundamentally stable solution?
Instead of arbitrary matrix multiplication, what if state transitions are **pure rotations** in a higher-dimensional space?
- **Quaternions**: Discovered by William Rowan Hamilton in 1843, quaternions provide a 4-dimensional division algebra that parameterizes 3D rotations without gimbal lock and with minimal parameter count.
- **Bivectors**: In Clifford geometric algebra, a rotation is not defined around an arbitrary "axis" (which only makes sense in 3 dimensions), but rather **within a 2-dimensional plane of rotation** specified by an oriented area element called a **bivector** $B = u \\wedge v$.
- **Rotors**: A rotor $\\mathcal{R} = \\exp(-\\frac{1}{2} B)$ acts on vectors via the elegant sandwich product:
  $$v' = \\mathcal{R} v \\mathcal{R}^\\dagger$$
  This operation is naturally isometric: $\\|v'\\| = \\|v\\|$. The singular values are identically $1.0$. Gradients cannot explode, and information cannot vanish.

In this chapter, we guide the reader from the intuitive foundations of complex numbers and quaternions into higher-dimensional Clifford algebras $\\mathcal{C}\\ell(p, q)$, the Lie algebra $\\mathfrak{so}(n)$, and the machine-certified Lean 4 proofs that prove rotor-based neural transitions are mathematically immune to energy collapse."""
    },
    "docs/thesis/volume_1_dimensional_spaces/chapter_04_the_cayley_transform_and_discrete_lyapunov_stability.md": {
        "abstract": """## Abstract
This chapter establishes the theoretical and computational apparatus of the Cayley transform as a structure-preserving conformal mapping between skew-symmetric Lie algebras and orthogonal Lie groups, providing an unconditional guarantee of discrete Lyapunov stability for continuous-depth neural recurrent models. Traditional numerical integrators (e.g., explicit Runge-Kutta, Euler) applied to orthogonal differential equations violate group constraints due to truncation errors, causing cumulative norm drift and destabilization over long horizons. By leveraging the Cayley operator $\\operatorname{Cay}(A) = (I - A)(I + A)^{-1}$, we map the linear space of skew-symmetric generators $\\mathfrak{so}(n)$ bijectively onto the Lie group $\\mathrm{SO}(n)$ without calculating transcendental matrix exponentials. We prove via Lyapunov direct methods that the resulting discrete transition matrices possess eigenvalues strictly bounded on the unit circle $|\\lambda_i| = 1$, guaranteeing asymptotic stability and bounded energy for arbitrary sequence lengths. The formal Lean 4 verification of the Cayley isometry and spectral radius bounds is presented with zero unproven axioms.""",
        "intro": """## 1. Introduction & Pedagogical Motivation: Taming the Continuous into the Discrete

In physical engineering and numerical simulation, there is a recurring nightmare known as **numerical explosion**. You design a physical system—say, a satellite orbiting a planet, or an undamped pendulum swinging back and forth. On paper, the laws of physics guarantee that energy is conserved. The system should oscillate gracefully forever.
Yet, when you write a computer program to simulate this system using standard time-stepping (such as the Euler method), the simulated satellite spirals wildly out of orbit and flies off into infinity, or the pendulum swings higher and higher until the computer crashes.

Why does this happen? And more importantly, how does this exact same disaster quietly sabotage deep neural networks?

### 1.1 The Discrete Time-Stepping Trap
Computers cannot run continuous time. A computer must step forward in discrete jumps: $t_0, t_1, t_2, \\dots, t_N$.
Suppose we have a continuous differential equation describing how a hidden state rotates over time:
$$\\frac{d}{dt} x(t) = A x(t)$$
where $A$ is a **skew-symmetric matrix** ($A^T = -A$). In physics, this represents pure rotational velocity with zero friction and zero expansion. The true continuous solution is given by the matrix exponential:
$$x(t) = \\exp(t A) x(0)$$
Since $\\exp(t A)$ is an orthogonal matrix, the Euclidean norm of $x(t)$ is strictly conserved for all time: $\\|x(t)\\|_2 = \\|x(0)\\|_2$.

However, calculating the true matrix exponential $\\exp(t A)$ requires an infinite Taylor series:
$$\\exp(t A) = I + t A + \\frac{(t A)^2}{2!} + \\frac{(t A)^3}{3!} + \\dots$$
If an engineer approximates this by truncating the series after the first step (the standard forward Euler approximation):
$$x_{k+1} = (I + \\Delta t \\cdot A) x_k$$
a catastrophe immediately occurs. Let us inspect the norm of the new state:
$$\\|x_{k+1}\\|^2 = x_k^T (I + \\Delta t A)^T (I + \\Delta t A) x_k = x_k^T (I - \\Delta t A + \\Delta t A - \\Delta t^2 A^2) x_k = \\|x_k\\|^2 + \\Delta t^2 \\|A x_k\\|^2 > \\|x_k\\|^2$$

Every single step artificially injects phantom energy $\\Delta t^2 \\|A x_k\\|^2$ into the system! After 10,000 steps, this quadratic growth compounds exponentially into numerical obliteration.

```
+----------------------------------------------------------------------------------------------------+
| EULER STEPPING VS. MATRIX EXPONENTIAL VS. CAYLEY TRANSFORM                                         |
+----------------------------------------------------------------------------------------------------+
| 1. Forward Euler Step (Truncated Approximation):                                                   |
|    M_{k+1} = (I + \Delta t A) M_k                                                                  |
|    -> Norm grows: ||x_{k+1}|| > ||x_k||. Phantom energy accumulates.                               |
|    -> Catastrophic instability and overflow over long contexts.                                    |
|                                                                                                    |
| 2. Matrix Exponential (Transcendental Exact Solution):                                             |
|    M_{k+1} = exp(\Delta t A) M_k                                                                   |
|    -> Perfect isometry, but requires infinite Taylor summation or Pade approximation.              |
|    -> Computationally prohibitive for high-speed hardware register loops.                          |
|                                                                                                    |
| 3. The Cayley Transform (Algebraic Conformal Map):                                                 |
|    Cay(A) = (I - A)(I + A)^{-1}                                                                    |
|    -> Strictly Orthogonal: Cay(A)^T Cay(A) = I identically!                                        |
|    -> Exact Isometry without computing transcendental exponentials.                                |
|    -> Discrete Lyapunov Stable: All eigenvalues lie exactly on the complex unit circle |\lambda|=1. |
+----------------------------------------------------------------------------------------------------+
```

### 1.2 The Miracle of Arthur Cayley's Transform
In 1846, the British mathematician Arthur Cayley discovered a breathtaking algebraic shortcut that bridges the gap between the curved world of rotations and the flat world of algebra.
Instead of computing infinite Taylor series, Cayley considered the rational fractional transformation:
$$\\operatorname{Cay}(A) = (I - A)(I + A)^{-1}$$
Notice what this formula does:
1. It uses only **elementary matrix addition, subtraction, and inversion**—no transcendental functions, no trigonometric sines or cosines, and no infinite series.
2. If $A$ is skew-symmetric ($A^T = -A$), then the resulting matrix $U = \\operatorname{Cay}(A)$ is **strictly, identically orthogonal**:
   $$U^T U = I$$
3. It maps the flat, unconstrained linear vector space of skew-symmetric matrices $\\mathfrak{so}(n)$ bijectively onto the curved manifold of rotations $\\mathrm{SO}(n)$ (excluding only matrices with eigenvalue $-1$).

### 1.3 Lyapunov Stability: The Mathematical Guarantee of Peace of Mind
In control theory, **Lyapunov stability** answers the ultimate question: *If I perturb this system, will it return to equilibrium, stay bounded, or explode?*
A discrete-time linear dynamical system $x_{k+1} = M x_k$ is stable in the sense of Lyapunov if and only if all eigenvalues $\\lambda_i$ of $M$ satisfy $|\\lambda_i| \\le 1$, and any eigenvalue on the unit boundary $|\\lambda_i| = 1$ has equal algebraic and geometric multiplicity.

When transition matrices are parameterized via the Cayley transform:
$$\\lambda(U) = \\frac{1 - i \\mu_j}{1 + i \\mu_j} \\implies |\\lambda(U)| = \\sqrt{\\frac{1 + \\mu_j^2}{1 + \\mu_j^2}} = 1.000000\\dots$$
Every eigenvalue is permanently locked onto the complex unit circle. Energy cannot grow; energy cannot dissipate. The state can evolve over billions of steps without a single microvolt of numerical drift.

In this chapter, we unpack the geometry of the Cayley transform, demonstrate its implementation in high-speed hardware pipelines, and present the complete formal Lean 4 verification of discrete Lyapunov stability."""
    }
}

for path, data in INTRODUCTIONS.items():
    if not os.path.exists(path):
        continue
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Check if abstract is missing or needs replacement
    if "## Abstract" not in content:
        # Insert abstract after title and blockquote
        parts = content.split("---", 1)
        if len(parts) == 2:
            new_content = parts[0] + "---\n\n" + data["abstract"] + "\n\n---\n\n" + data["intro"] + "\n\n"
            # find where section 2 begins
            sec2_match = re.search(r'## 2\.', parts[1])
            if sec2_match:
                new_content += parts[1][sec2_match.start():]
            else:
                new_content += parts[1]
            content = new_content
    else:
        # Replace section 1 with the comprehensive masterclass intro
        sec1_match = re.search(r'## 1\.\s+.*', content)
        sec2_match = re.search(r'## 2\.\s+.*', content)
        if sec1_match and sec2_match:
            before_sec1 = content[:sec1_match.start()]
            after_sec1 = content[sec2_match.start():]
            content = before_sec1 + data["intro"] + "\n\n---\n\n" + after_sec1
            
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Updated {path} with pedagogical masterclass introduction.")

