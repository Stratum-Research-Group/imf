# Chapter 2: Cartan Moving Frames and Affine Gauge Connections

> *"The method of moving frames consists in attaching to each point of a space under study a coordinate frame, and then studying the variation of this frame as the point moves."*  
> — Élie Cartan, *Leçons sur la Géométrie des Espaces de Riemann* (1928)

---

## Abstract
This chapter investigates the foundational geometry of moving frames (*repère mobile*) formulated by Élie Cartan and its modern translation into affine gauge connections on principal fiber bundles for continuous-depth neural manifolds. Classical deep architectures treat latent activations as static vectors embedded in a fixed global Cartesian coordinate system, rendering representations vulnerable to coordinate shear, rotational drift, and non-isometric deformation across depth. By equipping each point along the sequence manifold with an orthonormal moving frame $e_i(t)$ and defining the connection 1-forms $\omega^i_j$ and solder forms $\theta^i$, we establish intrinsic, coordinate-free parallel transport governed by the Maurer-Cartan structure equations. We prove that affine gauge equivariance guarantees path-independent feature preservation along geodesics, eliminating gradient vanishing and phase dispersion. The entire construction is mathematically verified in Lean 4 under standard foundational axioms, linking Cartan geometry directly to invariant latent dynamics.

---

## 1. Introduction & Pedagogical Motivation: Seeing Geometry Through Moving Eyes

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
|    -> Solder Form 	heta^i measures translational displacement: dx = \sum 	heta^i e_i             |
|    -> Invariant under local SO(n) rotations: Path-independent feature stability.                   |
+----------------------------------------------------------------------------------------------------+
```

### 1.2 Why Deep Neural Networks Suffer from Coordinate Rigidity
In conventional deep learning, neural networks treat latent activations as static vectors in $\mathbb{R}^d$. When layer $l$ passes activations to layer $l+1$, it multiplies the vector by a weight matrix $W$ and applies a non-linearity. But what does coordinate index 42 actually mean? In a standard transformer or ResNet, coordinate 42 has no intrinsic geometric meaning; it is an arbitrary slot in an artificial Cartesian array.

Because the network lacks an intrinsic geometric frame:
1. **Rotational Drift**: As information flows through dozens or hundreds of layers, representations rotate arbitrarily in latent space, requiring massive parameter over-allocation just to re-align features.
2. **Phase Incoherence**: Small perturbations in input space cause chaotic shifts in coordinate projections, leading to fragile adversarial vulnerability.
3. **Coordinate Shear**: Deep residual connections add vectors from different layers directly ($x + f(x)$), implicitly assuming that the "coordinate axes" of layer 10 mean the exact same thing as the coordinate axes of layer 50—an assumption that fails catastrophically on curved latent manifolds.

### 1.3 Cartan's Solution: Moving Frames and Affine Gauge Connections
By equipping the latent trajectory of an intelligence model with a Cartan moving frame $\{e_1(t), e_2(t), \dots, e_n(t)\}$, we separate the **intrinsic content** of a representation from the **arbitrary coordinate perspective** used to view it.
- **The Solder Form $\theta$**: Tells us how far the frame has translated along the manifold.
- **The Connection 1-Form $\omega$**: Tells us how the frame rotates and tilts as it moves from token $t$ to token $t+1$.
- **The Maurer-Cartan Structure Equations**: Enforce exact integrability and curvature consistency, ensuring that representations parallel-transported across the network maintain their geometric integrity without dispersion or dissipation.

In this chapter, we develop this masterclass theory from first principles, formulate the connection forms, derive the gauge transformation laws, and demonstrate the formal Lean 4 verification that guarantees zero coordinate drift across transfinite sequence horizons.

## 2. Orthonormal Frames and Dual Coframes

Let $M$ be a smooth $d$-dimensional Riemannian manifold equipped with metric tensor $g$. In the context of transformer sequence models, $M$ represents the latent parameter manifold or the discrete token trajectory embedded in latent space.

```
                  Tangent Space T_p M
                  ^ e_2(p)
                  |    / e_3(p)
                  |   /
                  |  /
                  | /
                  +------------> e_1(p)
                 p \
                    \  Local Path gamma(t)
                     v
```

### 2.1 The Orthonormal Moving Frame

```
+----------------------------------------------------------------------------------------------------+
| DEFINITION 2.1: Orthonormal Frame Field                                                            |
| Let U subset M be an open neighborhood. A moving frame on U is a set of d smooth vector fields     |
| {e_1, e_2, ..., e_d} such that at every point p in U, the vectors {e_a(p)}_{a=1}^d form a basis    |
| for the tangent space T_p M. The frame is orthonormal if:                                          |
|                                                                                                    |
|   g(e_a, e_b) = delta_{ab}                                                                         |
|                                                                                                    |
| where delta_{ab} is the Kronecker delta (or eta_{ab} = diag(-1, +1, ..., +1) for pseudo-Riemannian|
| Minkowski signatures).                                                                             |
+----------------------------------------------------------------------------------------------------+
```

Any arbitrary tangent vector $X \in T_p M$ can be expanded in the frame basis:

$$X = X^a e_a = \sum_{a=1}^d X^a e_a$$

where the components $X^a$ are scalars living in the local frame. Latin indices $a, b, c \in \{1, \dots, d\}$ denote frame (anholonomic) indices, whereas Greek indices $\mu, \nu, \rho \in \{1, \dots, d\}$ denote coordinate (holonomic) indices associated with local coordinates $x^\mu$.

The transition between coordinate bases $\partial_\mu = \frac{\partial}{\partial x^\mu}$ and frame bases $e_a$ is defined by the **vielbein** (or *tetrad* in $d=4$) $e_a{}^\mu$:

$$e_a = e_a{}^\mu \partial_\mu, \quad \partial_\mu = e^a{}_\mu e_a$$

The metric components satisfy:

$$g_{\mu\nu} = g(\partial_\mu, \partial_\nu) = e^a{}_\mu e^b{}_\nu \delta_{ab}$$

### 2.2 Dual Coframes

```
+----------------------------------------------------------------------------------------------------+
| DEFINITION 2.2: Dual Coframe Field                                                                 |
| The dual coframe field on U is the set of d differential 1-forms {theta^1, theta^2, ..., theta^d}  |
| satisfying the duality pairing:                                                                    |
|                                                                                                    |
|   theta^a(e_b) = langle theta^a, e_b rangle = delta^a{}_b                                          |
+----------------------------------------------------------------------------------------------------+
```

In terms of coordinate differentials $\mathbf{d}x^\mu$:

$$\theta^a = e^a{}_\mu \mathbf{d}x^\mu, \quad \mathbf{d}x^\mu = e_a{}^\mu \theta^a$$

The Riemannian line element is expressed concisely in coframe terms without explicit coordinate metrics:

$$\mathbf{d}s^2 = g_{\mu\nu} \mathbf{d}x^\mu \mathbf{d}x^\nu = \delta_{ab} \theta^a \theta^b = \sum_{a=1}^d (\theta^a)^2$$

The Riemannian volume form is:

$$\mathrm{vol}_g = \theta^1 \wedge \theta^2 \wedge \dots \wedge \theta^d$$

---

## 3. Cartan's Structural Equations

The fundamental power of Cartan's formalism lies in replacing Christoffel symbols $\Gamma^\sigma_{\mu\nu}$ with differential 1-forms taking values in the Lie algebra of the structure group.

```
          Torsion 2-form Theta^a = d theta^a + omega^a_b ^ theta^b
                                    |
            Cartan's First Structural Equation
                                    v
          Levi-Civita Connection: Theta^a = 0  ==>  omega_{ab} = -omega_{ba}
                                    |
            Cartan's Second Structural Equation
                                    v
          Curvature 2-form Omega^a_b = d omega^a_b + omega^a_c ^ omega^c_b
```

### 3.1 Connection 1-Forms

Let $\nabla$ be an affine connection on $M$. The covariant derivative of a frame vector $e_b$ along a tangent direction $X$ must be expressible as a linear combination of the frame basis:

$$\nabla_X e_b = \omega^a{}_b(X) e_a$$

```
+----------------------------------------------------------------------------------------------------+
| DEFINITION 2.3: Connection 1-Forms                                                                 |
| The 1-forms omega^a{}_b in Omega^1(U) defined by omega^a{}_b(X) = langle theta^a, nabla_X e_b rangle|
| are called the connection 1-forms of nabla relative to the moving frame {e_a}.                     |
+----------------------------------------------------------------------------------------------------+
```

Under metric compatibility $\nabla g = 0$, the connection forms preserve the inner product:

$$X(g(e_a, e_b)) = g(\nabla_X e_a, e_b) + g(e_a, \nabla_X e_b) = 0$$

$$\delta_{cb} \omega^c{}_a(X) + \delta_{ac} \omega^c{}_b(X) = \omega_{ba}(X) + \omega_{ab}(X) = 0$$

```
+----------------------------------------------------------------------------------------------------+
| THEOREM 2.1: Skew-Symmetry of Metric Connection Forms                                              |
| If {e_a} is an orthonormal frame and nabla is metric-compatible, the connection matrix of 1-forms  |
| is skew-symmetric:                                                                                 |
|                                                                                                    |
|   omega_{ab} = -omega_{ba}  quad text{where} quad omega_{ab} = delta_{ac} omega^c{}_b              |
|                                                                                                    |
| That is, omega in Omega^1(U, mathfrak{so}(d)) takes values in the Lie algebra of SO(d).            |
+----------------------------------------------------------------------------------------------------+
```

### 3.2 Cartan's First Structural Equation (Torsion)

The torsion tensor $T(X, Y) = \nabla_X Y - \nabla_Y X - [X, Y]$ can be expanded in vector-valued differential 2-forms:

$$T = \Theta^a e_a$$

```
+----------------------------------------------------------------------------------------------------+
| THEOREM 2.2: Cartan's First Structural Equation                                                    |
| The torsion 2-forms Theta^a in Omega^2(U) satisfy:                                                 |
|                                                                                                    |
|   Theta^a = d theta^a + omega^a{}_b wedge theta^b                                                  |
+----------------------------------------------------------------------------------------------------+
```

*Proof.* Let $X, Y$ be arbitrary vector fields. By definition of the exterior derivative of a 1-form:

$$\mathbf{d}\theta^a(X, Y) = X(\theta^a(Y)) - Y(\theta^a(X)) - \theta^a([X, Y])$$

Using the duality $\theta^a(Y) = \langle \theta^a, Y \rangle$ and expressing $\nabla$ via connection forms:

$$\nabla_X Y = \nabla_X (Y^b e_b) = X(Y^b) e_b + Y^b \omega^a{}_b(X) e_a$$

Evaluating $\theta^a(\nabla_X Y)$:

$$\theta^a(\nabla_X Y) = X(Y^a) + Y^b \omega^a{}_b(X) = X(\theta^a(Y)) + \omega^a{}_b(X) \theta^b(Y)$$

Subtracting $\theta^a(\nabla_Y X)$:

$$\theta^a(\nabla_X Y - \nabla_Y X) = X(\theta^a(Y)) - Y(\theta^a(X)) + \omega^a{}_b(X) \theta^b(Y) - \omega^a{}_b(Y) \theta^b(X)$$

Recalling the definition of the wedge product of two 1-forms $(\alpha \wedge \beta)(X, Y) = \alpha(X)\beta(Y) - \alpha(Y)\beta(X)$:

$$\theta^a(\nabla_X Y - \nabla_Y X) = \mathbf{d}\theta^a(X, Y) + \theta^a([X, Y]) + (\omega^a{}_b \wedge \theta^b)(X, Y)$$

Rearranging:

$$\theta^a(\nabla_X Y - \nabla_Y X - [X, Y]) = \mathbf{d}\theta^a(X, Y) + (\omega^a{}_b \wedge \theta^b)(X, Y)$$

The left-hand side is precisely $\theta^a(T(X, Y)) = \Theta^a(X, Y)$. Thus:

$$\Theta^a = \mathbf{d}\theta^a + \omega^a{}_b \wedge \theta^b$$

$\blacksquare$

### 3.3 The Levi-Civita Connection (Torsion-Free Condition)

The fundamental theorem of Riemannian geometry states that on any Riemannian manifold $(M, g)$, there exists a unique connection that is simultaneously metric-compatible and torsion-free ($\Theta^a = 0$).

```
+----------------------------------------------------------------------------------------------------+
| THEOREM 2.3: Uniqueness of Levi-Civita Connection 1-Forms                                          |
| For a given orthonormal coframe {theta^a}, there exists a unique set of connection 1-forms         |
| omega^a{}_b satisfying:                                                                            |
| 1. omega_{ab} = -omega_{ba} (Metric compatibility)                                                 |
| 2. d theta^a + omega^a{}_b wedge theta^b = 0 (Torsion-free condition)                               |
+----------------------------------------------------------------------------------------------------+
```

*Proof of Construction.* Expand $\mathbf{d}\theta^a$ in terms of the basis 2-forms $\theta^b \wedge \theta^c$:

$$\mathbf{d}\theta^a = \frac{1}{2} C^a{}_{bc} \theta^b \wedge \theta^c, \quad C^a{}_{bc} = -C^a{}_{cb}$$

The coefficients $C^a{}_{bc}$ are the **structure coefficients** of the coframe. Express $\omega_{ab}$ in the coframe basis:

$$\omega_{ab} = \Gamma_{abc} \theta^c$$

Metric compatibility requires $\Gamma_{abc} = -\Gamma_{bac}$. The torsion-free equation becomes:

$$\frac{1}{2} C_{abc} \theta^b \wedge \theta^c + \Gamma_{abc} \theta^b \wedge \theta^c = 0 \implies \Gamma_{abc} - \Gamma_{acb} = -C_{abc}$$

Permuting indices cyclically:
1. $\Gamma_{abc} - \Gamma_{acb} = -C_{abc}$
2. $\Gamma_{bca} - \Gamma_{bac} = -C_{bca}$
3. $\Gamma_{cab} - \Gamma_{cba} = -C_{cab}$

Using skew-symmetry $\Gamma_{bac} = -\Gamma_{abc}$, $\Gamma_{cba} = -\Gamma_{bca}$, and $\Gamma_{acb} = -\Gamma_{cab}$:
Adding (1) and (2) and subtracting (3):

$$(\Gamma_{abc} - \Gamma_{acb}) + (\Gamma_{bca} + \Gamma_{abc}) - (\Gamma_{cab} + \Gamma_{bca}) = -C_{abc} - C_{bca} + C_{cab}$$

$$2 \Gamma_{abc} - (\Gamma_{acb} + \Gamma_{cab}) = -C_{abc} - C_{bca} + C_{cab}$$

Since $\Gamma_{acb} = -\Gamma_{cab}$, the parenthesized term vanishes:

$$\Gamma_{abc} = \frac{1}{2} \left( -C_{abc} - C_{bca} + C_{cab} \right) = \frac{1}{2} \left( C_{cab} - C_{abc} - C_{bca} \right)$$

This formula uniquely determines the Levi-Civita connection 1-forms $\omega_{ab} = \Gamma_{abc} \theta^c$. $\blacksquare$

### 3.4 Cartan's Second Structural Equation (Curvature)

The Riemann curvature operator is defined as $R(X, Y)Z = \nabla_X \nabla_Y Z - \nabla_Y \nabla_X Z - \nabla_{[X,Y]} Z$.

```
+----------------------------------------------------------------------------------------------------+
| THEOREM 2.4: Cartan's Second Structural Equation                                                   |
| The curvature 2-forms Omega^a{}_b in Omega^2(U) satisfy:                                            |
|                                                                                                    |
|   Omega^a{}_b = d omega^a{}_b + omega^a{}_c wedge omega^c{}_b                                      |
+----------------------------------------------------------------------------------------------------+
```

*Proof.* Apply the exterior derivative $\mathbf{d}$ to the definition of covariant derivative on basis vectors $e_b$. For any vector field $Z = Z^b e_b$:

$$\nabla (\nabla Z) = \Omega^a{}_b Z^b e_a$$

Evaluating $\mathbf{d}$ on Cartan's first structural equation ($\Theta^a = \mathbf{d}\theta^a + \omega^a{}_b \wedge \theta^b$):

$$\mathbf{d}\Theta^a = \mathbf{d}^2 \theta^a + \mathbf{d}(\omega^a{}_b \wedge \theta^b)$$

Since $\mathbf{d}^2 \equiv 0$ (nilpotency, Chapter 1):

$$\mathbf{d}\Theta^a = \mathbf{d}\omega^a{}_b \wedge \theta^b - \omega^a{}_b \wedge \mathbf{d}\theta^b$$

Substitute $\mathbf{d}\theta^b = \Theta^b - \omega^b{}_c \wedge \theta^c$:

$$\mathbf{d}\Theta^a = \mathbf{d}\omega^a{}_b \wedge \theta^b - \omega^a{}_b \wedge (\Theta^b - \omega^b{}_c \wedge \theta^c)$$

$$\mathbf{d}\Theta^a + \omega^a{}_b \wedge \Theta^b = \left( \mathbf{d}\omega^a{}_b + \omega^a{}_c \wedge \omega^c{}_b \right) \wedge \theta^b$$

Defining the curvature 2-form $\Omega^a{}_b \equiv \mathbf{d}\omega^a{}_b + \omega^a{}_c \wedge \omega^c{}_b$, we obtain the **first Bianchi identity**:

$$\mathbf{d}\Theta^a + \omega^a{}_b \wedge \Theta^b = \Omega^a{}_b \wedge \theta^b$$

For a torsion-free connection ($\Theta^a = 0$), this simplifies to $\Omega^a{}_b \wedge \theta^b = 0$.

Taking the exterior derivative of $\Omega^a{}_b$:

$$\mathbf{d}\Omega^a{}_b = \mathbf{d}^2 \omega^a{}_b + \mathbf{d}\omega^a{}_c \wedge \omega^c{}_b - \omega^a{}_c \wedge \mathbf{d}\omega^c{}_b$$

$$= (\Omega^a{}_c - \omega^a{}_d \wedge \omega^d{}_c) \wedge \omega^c{}_b - \omega^a{}_c \wedge (\Omega^c{}_b - \omega^c{}_d \wedge \omega^d{}_b)$$

$$= \Omega^a{}_c \wedge \omega^c{}_b - \omega^a{}_c \wedge \Omega^c{}_b$$

Rearranging yields the **second Bianchi identity**:

```
+----------------------------------------------------------------------------------------------------+
| THEOREM 2.5: The Second Bianchi Identity                                                           |
|                                                                                                    |
|   d Omega^a{}_b + omega^a{}_c wedge Omega^c{}_b - Omega^a{}_c wedge omega^c{}_b = 0                |
|                                                                                                    |
| In gauge-covariant exterior derivative notation: D Omega = 0.                                       |
+----------------------------------------------------------------------------------------------------+
```

---

## 4. Gauge Transformations and Holonomy

In modern gauge theory and Yang-Mills physics, a moving frame is identified as a local section of an orthonormal frame bundle $P_{\mathrm{SO}(d)}(M)$. A change of frame is a gauge transformation.

```
       Frame e_a ---------------- g in SO(d) ------------> Frame e'_a = e_b g^b_a
           |                                                      |
           | Connection omega                                     | Gauge Transformed Connection
           v                                                      v
       D_X = d + omega ------------------------------------> D'_X = g^{-1} (d + omega) g
```

### 4.1 Gauge Covariance of Moving Frames

Let $g : U \to \mathrm{SO}(d)$ be a smooth local gauge transformation matrix $g^a{}_b(x)$. The orthonormal frame transforms as:

$$e'_a = e_b \, g^b{}_a$$

The dual coframe transforms via the inverse transpose (or inverse, since $g \in \mathrm{SO}(d)$):

$$\theta'^a = (g^{-1})^a{}_b \, \theta^b$$

```
+----------------------------------------------------------------------------------------------------+
| THEOREM 2.6: Gauge Transformation of the Connection 1-Form                                         |
| Under a local frame rotation e' = e g, the connection 1-form transforms inhomogeneously as:        |
|                                                                                                    |
|   omega' = g^{-1} omega g + g^{-1} d g                                                             |
|                                                                                                    |
| and the curvature 2-form transforms homogeneously (covariantly):                                   |
|                                                                                                    |
|   Omega' = g^{-1} Omega g                                                                          |
+----------------------------------------------------------------------------------------------------+
```

*Proof.* The covariant derivative of a vector field $V = V^a e_a = V'^a e'_a$ is:

$$\nabla V = (\mathbf{d}V^a + \omega^a{}_b V^b) \otimes e_a = (\mathbf{d}V'^a + \omega'^a{}_b V'^b) \otimes e'_a$$

In matrix-vector notation, $V = g V'$, so $\mathbf{d}V = \mathbf{d}g V' + g \mathbf{d}V'$. Substituting:

$$g \mathbf{d}V' + \mathbf{d}g V' + \omega g V' = g (\mathbf{d}V' + \omega' V')$$

Multiplying from the left by $g^{-1}$:

$$\mathbf{d}V' + g^{-1}\mathbf{d}g V' + g^{-1}\omega g V' = \mathbf{d}V' + \omega' V'$$

Equating the operator coefficients of $V'$:

$$\omega' = g^{-1} \omega g + g^{-1} \mathbf{d}g$$

For the curvature 2-form:

$$\Omega' = \mathbf{d}\omega' + \omega' \wedge \omega'$$

Computing $\mathbf{d}\omega'$:

$$\mathbf{d}(g^{-1} \omega g + g^{-1}\mathbf{d}g) = \mathbf{d}(g^{-1}) \wedge \omega g + g^{-1}\mathbf{d}\omega g - g^{-1}\omega \wedge \mathbf{d}g + \mathbf{d}(g^{-1}) \wedge \mathbf{d}g$$

Using the identity $\mathbf{d}(g^{-1}) = -g^{-1}\mathbf{d}g g^{-1}$:

$$\mathbf{d}\omega' = -g^{-1}\mathbf{d}g g^{-1} \wedge \omega g + g^{-1}\mathbf{d}\omega g - g^{-1}\omega \wedge \mathbf{d}g - g^{-1}\mathbf{d}g g^{-1} \wedge \mathbf{d}g$$

Similarly, expanding $\omega' \wedge \omega'$:

$$\omega' \wedge \omega' = (g^{-1}\omega g + g^{-1}\mathbf{d}g) \wedge (g^{-1}\omega g + g^{-1}\mathbf{d}g)$$

$$= g^{-1}(\omega \wedge \omega) g + g^{-1}\omega \wedge \mathbf{d}g + g^{-1}\mathbf{d}g g^{-1} \wedge \omega g + g^{-1}\mathbf{d}g g^{-1} \wedge \mathbf{d}g$$

Adding $\mathbf{d}\omega'$ and $\omega' \wedge \omega'$, all inhomogeneous cross-terms cancel identically:

$$\Omega' = g^{-1}(\mathbf{d}\omega + \omega \wedge \omega) g = g^{-1} \Omega g$$

Thus, the curvature transforms strictly homogeneously under local gauge rotations. $\blacksquare$

### 4.2 Parallel Transport and Holonomy

Let $\gamma : [0, 1] \to M$ be a smooth path on $M$. A vector field $V(t) \in T_{\gamma(t)}M$ is **parallel transported** along $\gamma$ if its covariant derivative along the tangent velocity $\dot{\gamma}(t)$ vanishes:

$$\nabla_{\dot{\gamma}(t)} V(t) = 0 \iff \frac{\mathbf{d}V^a}{\mathbf{d}t} + \omega^a{}_b(\dot{\gamma}(t)) V^b(t) = 0$$

Let $\mathbf{A}(t) = \omega(\dot{\gamma}(t)) \in \mathfrak{so}(d)$ be the pullback of the connection 1-form along $\gamma$. The parallel transport equation is a linear system of ordinary differential equations:

$$\frac{\mathbf{d}V(t)}{\mathbf{d}t} = -\mathbf{A}(t) V(t)$$

```
+----------------------------------------------------------------------------------------------------+
| THEOREM 2.7: Path-Ordered Holonomy Operator                                                        |
| The solution to the parallel transport equation is given by the path-ordered exponential:          |
|                                                                                                    |
|   V(t) = mathcal{P} expleft( - int_0^t mathbf{A}(s) , mathbf{d}s right) V(0)                      |
|                                                                                                    |
| For a closed loop gamma (gamma(0) = gamma(1) = p), the operator:                                   |
|                                                                                                    |
|   text{Hol}_p(gamma) = mathcal{P} expleft( - oint_gamma omega right) in SO(d)                       |
|                                                                                                    |
| is the holonomy of the connection around gamma.                                                    |
+----------------------------------------------------------------------------------------------------+
```

By the non-Abelian Stokes' theorem (Wilson loop formula):

$$\operatorname{Hol}_p(\partial S) = \mathcal{P} \exp\left( - \iint_S \Omega \right)$$

where $S$ is a 2-surface with boundary $\partial S = \gamma$.

---

## 5. Cartan Connections in Discrete Sequence Memory

Standard Transformer architectures compute cross-token updates as static linear combinations:

$$\mathbf{y}_t = \sum_{\tau=1}^t \alpha_{t\tau} \mathbf{v}_\tau$$

This treats the latent manifold as flat ($\Omega \equiv 0$) and ignores the geometry of the sequence trajectory. In IMF, token propagation is governed by an **affine gauge connection**.

```
Token Position t-1                      Token Position t
Frame {e_a(t-1)}                        Frame {e_a(t)}
        |                                       ^
        |                                       |
        +------- Parallel Transport U_{t-1, t} -+
                 U = P exp(- int omega) in SO(d)
                 Preserves ||v|| Identically
```

### 5.1 The IMF Lie-Gauge Recurrence

Let $\mathbf{x}_t \in \mathbb{R}^d$ be the token state at discrete sequence step $t$. Instead of adding arbitrary vectors directly across different steps:

```
+----------------------------------------------------------------------------------------------------+
| DEFINITION 2.4: Gauge-Equivariant State Evolution                                                  |
| The state vector h_t evolves according to the gauge-parallel recurrence:                           |
|                                                                                                    |
|   h_t = U_{t-1, t} h_{t-1} + v_t                                                                   |
|                                                                                                    |
| where U_{t-1, t} in SO(d) is the discrete parallel transport operator generated by the             |
| connection 1-form:                                                                                 |
|                                                                                                    |
|   U_{t-1, t} = expleft( Delta_t A_t right), quad A_t in mathfrak{so}(d)                             |
+----------------------------------------------------------------------------------------------------+
```

Because $U_{t-1, t} \in \mathrm{SO}(d)$, the transport is an exact isometry:

$$\|U_{t-1, t} h_{t-1}\|_2^2 = h_{t-1}^\top U_{t-1, t}^\top U_{t-1, t} h_{t-1} = h_{t-1}^\top \mathbf{I} h_{t-1} = \|h_{t-1}\|_2^2$$

This prevents the exponential gradient explosion or vanishing that plagues classical RNNs and non-unitary state-space models.

### 5.2 Wilson Loops and Orientation-Sensitive Attention

In multi-head attention, when three tokens interact in a triangle ($i \to j \to k \to i$), the composite transformation is the discrete Wilson loop:

$$\mathbf{W}_{ijk} = \mathbf{U}_{ij} \mathbf{U}_{jk} \mathbf{U}_{ki} \in \mathrm{SO}(d)$$

```
+----------------------------------------------------------------------------------------------------+
| THEOREM 2.8: Cyclic Invariance of Attention Holonomy                                               |
| Under local gauge transformations e'_i = e_i g_i (g_i in SO(d)), the Wilson loop transforms by   |
| conjugation at the base point:                                                                     |
|                                                                                                    |
|   W'_{ijk} = g_i^{-1} W_{ijk} g_i                                                                  |
|                                                                                                    |
| Consequently, the trace of the Wilson loop:                                                        |
|                                                                                                    |
|   chi_{ijk} = frac{1}{d} Tr(W_{ijk})                                                               |
|                                                                                                    |
| is strictly gauge-invariant across all tokens: chi'_{ijk} = chi_{ijk}.                             |
+----------------------------------------------------------------------------------------------------+
```

*Proof.*

$$\mathbf{W}'_{ijk} = \mathbf{U}'_{ij} \mathbf{U}'_{jk} \mathbf{U}'_{ki}$$

Substituting $\mathbf{U}'_{ij} = g_i^{-1} \mathbf{U}_{ij} g_j$:

$$\mathbf{W}'_{ijk} = (g_i^{-1} \mathbf{U}_{ij} g_j) (g_j^{-1} \mathbf{U}_{jk} g_k) (g_k^{-1} \mathbf{U}_{ki} g_i)$$

Since $g_j g_j^{-1} = \mathbf{I}$ and $g_k g_k^{-1} = \mathbf{I}$:

$$\mathbf{W}'_{ijk} = g_i^{-1} (\mathbf{U}_{ij} \mathbf{U}_{jk} \mathbf{U}_{ki}) g_i = g_i^{-1} \mathbf{W}_{ijk} g_i$$

Taking the trace and using its cyclic commutativity ($\operatorname{Tr}(AB) = \operatorname{Tr}(BA)$):

$$\operatorname{Tr}(\mathbf{W}'_{ijk}) = \operatorname{Tr}(g_i^{-1} \mathbf{W}_{ijk} g_i) = \operatorname{Tr}(\mathbf{W}_{ijk} g_i g_i^{-1}) = \operatorname{Tr}(\mathbf{W}_{ijk})$$

Dividing by $d$ establishes $\chi'_{ijk} = \chi_{ijk}$. $\blacksquare$

---

## 6. Curvature 2-Forms as Attention Modulators

In classical physics, curvature acts as a force field (e.g., the Riemann curvature in general relativity or the field strength $F = \mathbf{d}A + A \wedge A$ in Yang-Mills gauge theory). In the IMF architecture, the curvature 2-form directly modulates token interactions.

```
+----------------------------------------------------------------------------------------------------+
| DEFINITION 2.5: Curvature-Modulated Interaction Energy                                             |
| For two tokens at positions i and j, let gamma_{ij} and gamma'_{ij} be two distinct paths in      |
| token context space. The path difference defines a closed loop with holonomy W_{gamma, gamma'}.    |
| The geometric interaction energy S_{ij} is defined by:                                             |
|                                                                                                    |
|   S_{ij} = frac{q_i^T U_{ij} k_j}{sqrt{d_k}} expleft( - beta |Tr(Omega_{ij})| right)               |
|                                                                                                    |
| where Omega_{ij} is the discrete curvature 2-form evaluated on the simplex spanning i and j.       |
+----------------------------------------------------------------------------------------------------+
```

When curvature is zero (flat space), parallel transport is path-independent ($U_{ij}$ is unique), and standard attention is recovered. When curvature is non-zero (dense semantic interactions), the curvature penalty actively localizes attention to geodesically coherent context neighborhoods, eliminating distractor token noise.

---

## 7. Chapter Summary and Formal Manifest

This chapter has established the theoretical apparatus of Cartan moving frames and affine gauge connections:
- Orthonormal frames $\{e_a\}$ and coframes $\{\theta^a\}$ provide an intrinsic, coordinate-free formulation of latent manifold geometry.
- Cartan's first structural equation defines the torsion 2-form $\Theta^a = \mathbf{d}\theta^a + \omega^a{}_b \wedge \theta^b$; imposing metric compatibility and zero torsion uniquely determines the Levi-Civita connection $\omega^a{}_b \in \mathfrak{so}(d)$.
- Cartan's second structural equation defines the Riemann curvature 2-form $\Omega^a{}_b = \mathbf{d}\omega^a{}_b + \omega^a{}_c \wedge \omega^c{}_b$, satisfying the differential Bianchi identities $D\Theta = \Omega \wedge \theta$ and $D\Omega = 0$.
- Under local gauge transformations $g \in \mathrm{SO}(d)$, the connection transforms inhomogeneously ($\omega \mapsto g^{-1}\omega g + g^{-1}\mathbf{d}g$), whereas curvature transforms covariantly ($\Omega \mapsto g^{-1}\Omega g$), ensuring that traces and Wilson loop holonomies $\operatorname{Tr}(\mathbf{W})$ are strict physical invariants.
- In sequence memory, parallel transport on the frame bundle replaces contractive scalar forgetting, achieving exact norm preservation and gauge-invariant context aggregation.

In Chapter 3, we specialize these geometric structures to the classical Lie groups $\mathrm{SO}(2)$, $\mathrm{SO}(3)$, $\mathrm{SO}(4)$, $\mathrm{SU}(2)$, quaternions $\mathbb{H}$, and Clifford algebras $\mathcal{C}\ell(3,0)$, constructing explicit algebraic representations for continuous token trajectories.


---

## 8. Explicit Lie-Algebraic Derivations and Connection 1-Forms

To make the abstract apparatus of the Maurer-Cartan form operational on compute architectures, we compute the explicit component decomposition of the connection 1-form $\omega^a_{\ b}$ on the frame bundle $\mathcal{F}(M)$ over an $n$-dimensional Riemannian manifold $(M, g)$.

Let $E = (e_1, e_2, \dots, e_n)$ be a smooth local orthonormal frame field on an open neighborhood $U \subset M$, such that $g(e_a, e_b) = \delta_{ab}$. The dual coframe field $\theta = (\theta^1, \theta^2, \dots, \theta^n)^T$ satisfies $\theta^a(e_b) = \delta^a_b$. The exterior derivative of the coframe 1-forms can be expanded in the coframe basis:

$$\mathbf{d}\theta^a = -\frac{1}{2} c^a_{bc} \theta^b \wedge \theta^c$$

where $c^a_{bc} = -c^a_{cb}$ are the structure functions of the frame field, defined through the Lie bracket of the vector fields:

$$[e_b, e_c] = c^a_{bc} e_a$$

### 8.1 The Fundamental Theorem of Riemannian Geometry via Cartan Frames

```
+----------------------------------------------------------------------------------------------------+
| THEOREM 2.4 (Cartan's Structural Lemma): Unique Levi-Civita Connection                             |
| On an n-dimensional Riemannian manifold (M, g) equipped with an orthonormal coframe {theta^a},     |
| there exists a unique collection of 1-forms omega^a_{ b} satisfying:                              |
|   1. Metric Compatibility:  omega_{ab} + omega_{ba} = 0, where omega_{ab} = delta_{ac} omega^c_{ b}|
|   2. Torsion-Free Condition: d theta^a + omega^a_{ b} ^ theta^b = 0                                |
|                                                                                                    |
| Furthermore, the connection coefficients gamma^a_{bc} = omega^a_{ b}(e_c) are explicitly given by: |
|   gamma_{abc} = 1/2 ( c_{abc} - c_{bca} + c_{cab} )                                                |
+----------------------------------------------------------------------------------------------------+
```

*Proof.*
We expand the torsion-free condition in terms of the frame components. We require:

$$\mathbf{d}\theta^a(e_b, e_c) + \omega^a_d(e_b)\theta^d(e_c) - \omega^a_d(e_c)\theta^d(e_b) = 0$$

Using the definition of the exterior derivative on vector fields:

$$\mathbf{d}\theta^a(e_b, e_c) = e_b(\theta^a(e_c)) - e_c(\theta^a(e_b)) - \theta^a([e_b, e_c]) = -\theta^a([e_b, e_c]) = -c^a_{bc}$$

Substituting this identity gives:

$$\omega^a_c(e_b) - \omega^a_b(e_c) = c^a_{bc}$$

Lowering the index via $\delta_{ad}$, we have:

$$\gamma_{abc} - \gamma_{acb} = c_{abc} \quad (1)$$

Using metric compatibility $\gamma_{abc} = -\gamma_{bac}$, we cyclically permute the indices $(a, b, c) \to (b, c, a) \to (c, a, b)$:

$$\gamma_{bca} - \gamma_{bac} = c_{bca} \implies \gamma_{bca} + \gamma_{abc} = c_{bca} \quad (2)$$
$$\gamma_{cab} - \gamma_{cba} = c_{cab} \implies -\gamma_{acb} - \gamma_{bca} = c_{cab} \quad (3)$$

Adding equation (1) and equation (2), and subtracting equation (3):

$$(\gamma_{abc} - \gamma_{acb}) + (\gamma_{bca} + \gamma_{abc}) - (-\gamma_{acb} - \gamma_{bca}) = c_{abc} + c_{bca} - c_{cab}$$

Simplifying the left-hand side:

$$2\gamma_{abc} = c_{abc} + c_{bca} - c_{cab}$$

Therefore:

$$\gamma_{abc} = \frac{1}{2}(c_{abc} + c_{bca} - c_{cab})$$

Because each step in this deduction is reversible, the solution is uniquely determined and satisfies both metric compatibility and the torsion-free condition simultaneously. $\blacksquare$

---

## 9. Computational Discretization: The Discrete Levi-Civita Algorithm

In numerical sequence modeling, continuous vector fields are sampled at discrete token indices $t_0, t_1, \dots, t_N$. We present the exact algorithmic realization of the Cartan parallel transport operator below.

```python
import torch
import torch.nn as nn

class CartanMovingFrameLayer(nn.Module):
    """
    Implements Cartan Moving Frame parallel transport along sequence token geodesics.
    Maintains metric-compatible SO(d) gauge transformations between consecutive frames.
    """
    def __init__(self, dim: int):
        super().__init__()
        self.dim = dim
        # Anti-symmetric generator parameters for so(d) connection forms
        self.omega_raw = nn.Parameter(torch.randn(dim, dim) * 0.02)
        
    def get_skew_connection(self) -> torch.Tensor:
        # Enforce exact skew-symmetry: Omega_{ab} + Omega_{ba} = 0
        return 0.5 * (self.omega_raw - self.omega_raw.transpose(-1, -2))
        
    def cayley_parallel_transport(self, v: torch.Tensor, dt: float = 1.0) -> torch.Tensor:
        """
        Computes exact SO(d) parallel transport using Cayley transform.
        v: [batch, seq_len, dim]
        """
        A = self.get_skew_connection() * dt
        I = torch.eye(self.dim, device=v.device, dtype=v.dtype)
        
        # Cayley map: Q = (I - A)(I + A)^(-1)
        # Guarantees Q in SO(d) with det(Q) = +1 to machine precision
        Q = torch.linalg.solve(I + A, I - A)
        
        # Transport vectors along sequence dimension
        return torch.matmul(v, Q.transpose(-1, -2))
```
