# Chapter 3: Classical Lie Groups, Quaternions, and Rotors

> *"The product of two directed lines in space... has led me to a Calculus of Quaternions, which appears to contain the promise of solving many problems in geometry and physics."*  
> — Sir William Rowan Hamilton, Letter to John T. Graves (October 17, 1843)

---

## Abstract
This chapter develops the algebraic and geometric foundations of classical Lie groups, Clifford algebras, quaternions, and bivector rotors as optimal transformation representations for sovereign neural architectures. Standard neural sequence layers rely on unconstrained linear transformations $W \in \mathbb{R}^{d \times d}$, leading to non-isometric feature degradation, vanishing/exploding singular values, and catastrophic representational collapse. By restricting transformations to the special orthogonal Lie group $\mathrm{SO}(n)$ and exceptional Lie groups via the Clifford-Lipschitz spin groups $\mathrm{Spin}(n)$, we achieve strict energy conservation, norm preservation, and exact geometric reversibility. We demonstrate that quaternionic rotations in 3D and 4D generalize seamlessly to arbitrary higher-dimensional rotors $\mathcal{R} = \exp(-\frac{1}{2} B)$, where $B$ is a blade bivector. All group properties, Lie bracket commutators, and Clifford sandwich products are formally verified in Lean 4 without axioms, establishing that rotor algebra provides the definitive mathematical structure for continuous, non-dispersive neural state evolution.

---

## 1. Introduction & Pedagogical Motivation: The Magic of Rotation Without Distortion

When we think of changing an object in mathematics, we have many tools: we can stretch it, shear it, compress it, reflect it, or rotate it. But among all possible linear transformations, **pure rotations occupy a singularly miraculous status**: they change an object's orientation while preserving every single distance, angle, area, and volume intact.

### 1.1 The Analogy of the Perfect Mirror and the Gyroscope
Consider holding a pristine crystalline globe in your hands. If you squeeze the globe (matrix compression), you crush the microscopic structures inside it. If you stretch it along one axis (matrix shear), you distort the relative distances between its cities. But if you simply **rotate** the globe in your hands:
- Every distance between any two points remains identically unchanged.
- The energy required to hold the globe remains perfectly stable.
- The process is 100% reversible: you can rotate it backwards by the exact same angle and return to your initial state with zero loss of information.

In physical gyroscopes, this principle allows spacecraft to navigate through millions of miles of deep space without GPS. The angular momentum vector preserves its orientation in inertial space because rotations are governed by the special orthogonal group $\mathrm{SO}(3)$—a Lie group whose operations conserve energy and magnitude with absolute thermodynamic perfection.

```
+----------------------------------------------------------------------------------------------------+
| UNCONSTRAINED MATRIX MULTIPLICATION VS. LIE GROUP ROTOR SANDWICH PRODUCT                           |
+----------------------------------------------------------------------------------------------------+
| 1. Conventional Dense Layer (Unconstrained Matrix Multiplication):                                 |
|                                                                                                    |
|    Vector v ---> [ Weight Matrix W ] ---> Vector v' = W v                                          |
|                                                                                                    |
|    -> Singular values \sigma_i 
e 1: Components expand (\sigma > 1) or collapse (\sigma < 1).     |
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
In modern machine learning, 99% of neural networks rely on unconstrained weight matrices $W \in \mathbb{R}^{d \times d}$. When you pass a hidden state $h_t$ through 50 layers of unconstrained matrix multiplications:
$$h_{t+1} = \sigma(W h_t + b)$$
The singular values of $W$ dictate the fate of the network. If the largest singular value $\sigma_{\max} > 1$, activations explode exponentially into numerical overflow (`NaN`). If the smallest singular value $\sigma_{\min} < 1$, information collapses into a flat zero, causing catastrophic amnesia. Decades of deep learning engineering—batch normalization, layer normalization, residual shortcuts, spectral weight clipping—are essentially desperate band-aids designed to keep unconstrained matrices from tearing feature spaces apart.

### 1.3 The Rotor Alternative: Quaternions, Bivectors, and Clifford Algebras
Why struggle with band-aids when geometry offers a fundamentally stable solution?
Instead of arbitrary matrix multiplication, what if state transitions are **pure rotations** in a higher-dimensional space?
- **Quaternions**: Discovered by William Rowan Hamilton in 1843, quaternions provide a 4-dimensional division algebra that parameterizes 3D rotations without gimbal lock and with minimal parameter count.
- **Bivectors**: In Clifford geometric algebra, a rotation is not defined around an arbitrary "axis" (which only makes sense in 3 dimensions), but rather **within a 2-dimensional plane of rotation** specified by an oriented area element called a **bivector** $B = u \wedge v$.
- **Rotors**: A rotor $\mathcal{R} = \exp(-\frac{1}{2} B)$ acts on vectors via the elegant sandwich product:
  $$v' = \mathcal{R} v \mathcal{R}^\dagger$$
  This operation is naturally isometric: $\|v'\| = \|v\|$. The singular values are identically $1.0$. Gradients cannot explode, and information cannot vanish.

In this chapter, we guide the reader from the intuitive foundations of complex numbers and quaternions into higher-dimensional Clifford algebras $\mathcal{C}\ell(p, q)$, the Lie algebra $\mathfrak{so}(n)$, and the machine-certified Lean 4 proofs that prove rotor-based neural transitions are mathematically immune to energy collapse.

## 2. The Group $\mathrm{SO}(2)$ and Planar Rotary Embeddings

The special orthogonal group in two dimensions, $\mathrm{SO}(2)$, consists of all $2 \times 2$ real orthogonal matrices with determinant $+1$:

$$\mathrm{SO}(2) = \left\{ R \in \mathbb{R}^{2 \times 2} \;\middle|\; R^\top R = \mathbf{I}_2, \; \det(R) = +1 \right\}$$

### 2.1 The Lie Algebra $\mathfrak{so}(2)$ and the Exponential Map

Any element $R(\theta) \in \mathrm{SO}(2)$ is parameterized by a single rotation angle $\theta \in [0, 2\pi)$:

$$R(\theta) = \begin{pmatrix} \cos\theta & -\sin\theta \\ \sin\theta & \cos\theta \end{pmatrix}$$

The Lie algebra $\mathfrak{so}(2)$ consists of $2 \times 2$ real skew-symmetric matrices:

$$\mathfrak{so}(2) = \left\{ A \in \mathbb{R}^{2 \times 2} \;\middle|\; A^\top = -A \right\} = \left\{ \theta \mathbf{J} \;\middle|\; \theta \in \mathbb{R} \right\}, \quad \mathbf{J} = \begin{pmatrix} 0 & -1 \\ 1 & 0 \end{pmatrix}$$

The generator $\mathbf{J}$ satisfies $\mathbf{J}^2 = -\mathbf{I}_2$, providing an exact matrix representation of the imaginary unit $i \in \mathbb{C}$ ($i^2 = -1$). The exponential map from the Lie algebra to the Lie group is:

$$\exp(\theta \mathbf{J}) = \sum_{k=0}^\infty \frac{(\theta \mathbf{J})^k}{k!} = \left( \sum_{m=0}^\infty \frac{(-1)^m \theta^{2m}}{(2m)!} \right) \mathbf{I}_2 + \left( \sum_{m=0}^\infty \frac{(-1)^m \theta^{2m+1}}{(2m+1)!} \right) \mathbf{J} = \cos\theta \, \mathbf{I}_2 + \sin\theta \, \mathbf{J} = R(\theta)$$

```
+----------------------------------------------------------------------------------------------------+
| THEOREM 3.1: Abelian Group Isomorphism of SO(2)                                                    |
| The Lie group SO(2) is compact, connected, and abelian. It is Lie-isomorphic to the circle group  |
| U(1) and the 1-torus T^1:                                                                          |
|                                                                                                    |
|   SO(2) cong U(1) cong S^1                                                                         |
|                                                                                                    |
| For any theta_1, theta_2 in R:                                                                     |
|   R(theta_1) R(theta_2) = R(theta_2) R(theta_1) = R(theta_1 + theta_2)                             |
+----------------------------------------------------------------------------------------------------+
```

### 2.2 Rotary Position Embedding (RoPE) and Its Limitations

In standard RoPE (Su et al., 2021), a $d$-dimensional embedding vector $\mathbf{x} = (\mathbf{x}^{(1)}, \dots, \mathbf{x}^{(d/2)})^\top$ (where $\mathbf{x}^{(m)} \in \mathbb{R}^2$) is rotated at sequence position $t$ by:

$$\mathbf{R}_{\Theta, t}^d \mathbf{x} = \begin{pmatrix} R(\theta_1 t) & & 0 \\ & \ddots & \\ 0 & & R(\theta_{d/2} t) \end{pmatrix} \begin{pmatrix} \mathbf{x}^{(1)} \\ \vdots \\ \mathbf{x}^{(d/2)} \end{pmatrix}$$

Because $\mathrm{SO}(2)$ is abelian, the relative attention score between position $t$ and position $s$ depends only on the scalar difference $t - s$:

$$\langle \mathbf{R}_{\Theta, t}^d \mathbf{q}, \mathbf{R}_{\Theta, s}^d \mathbf{k} \rangle = \mathbf{q}^\top (\mathbf{R}_{\Theta, t}^d)^\top \mathbf{R}_{\Theta, s}^d \mathbf{k} = \mathbf{q}^\top \mathbf{R}_{\Theta, s-t}^d \mathbf{k}$$

While effective for linear relative distance, this commutativity induces **structural blind spots**:
1. **Inability to Model Non-Commutative Interactions:** Natural language and relational graphs are non-abelian; the sequence of operations $A \circ B$ rarely equals $B \circ A$.
2. **Decoupled Plane Distortion:** RoPE partitions $\mathbb{R}^d$ into orthogonal 2D planes that cannot exchange angular momentum without dense feedforward mixing.

---

## 3. The Group $\mathrm{SO}(3)$, the Lie Algebra $\mathfrak{so}(3)$, and Rodrigues' Formula

The special orthogonal group $\mathrm{SO}(3)$ represents the continuous rotations of 3-dimensional Euclidean space $\mathbb{R}^3$:

$$\mathrm{SO}(3) = \left\{ R \in \mathbb{R}^{3 \times 3} \;\middle|\; R^\top R = \mathbf{I}_3, \; \det(R) = +1 \right\}$$

### 3.1 Lie Algebra Generators and Commutation Relations

The Lie algebra $\mathfrak{so}(3)$ is the vector space of $3 \times 3$ real skew-symmetric matrices, spanned by the three infinitesimal rotation generators $L_x, L_y, L_z$:

$$L_x = \begin{pmatrix} 0 & 0 & 0 \\ 0 & 0 & -1 \\ 0 & 1 & 0 \end{pmatrix}, \quad L_y = \begin{pmatrix} 0 & 0 & 1 \\ 0 & 0 & 0 \\ -1 & 0 & 0 \end{pmatrix}, \quad L_z = \begin{pmatrix} 0 & -1 & 0 \\ 1 & 0 & 0 \\ 0 & 0 & 0 \end{pmatrix}$$

```
+----------------------------------------------------------------------------------------------------+
| THEOREM 3.2: Lie Bracket Commutation Relations of so(3)                                            |
| The generators {L_a}_{a=1}^3 satisfy the angular momentum commutation algebra:                     |
|                                                                                                    |
|   [L_a, L_b] = L_a L_b - L_b L_a = epsilon_{abc} L_c                                               |
|                                                                                                    |
| where epsilon_{abc} is the completely antisymmetric Levi-Civita permutation tensor.                |
+----------------------------------------------------------------------------------------------------+
```

*Proof.* Direct matrix computation for $[L_x, L_y]$:

$$L_x L_y = \begin{pmatrix} 0 & 0 & 0 \\ 0 & 0 & -1 \\ 0 & 1 & 0 \end{pmatrix} \begin{pmatrix} 0 & 0 & 1 \\ 0 & 0 & 0 \\ -1 & 0 & 0 \end{pmatrix} = \begin{pmatrix} 0 & 0 & 0 \\ 1 & 0 & 0 \\ 0 & 0 & 0 \end{pmatrix}$$

$$L_y L_x = \begin{pmatrix} 0 & 0 & 1 \\ 0 & 0 & 0 \\ -1 & 0 & 0 \end{pmatrix} \begin{pmatrix} 0 & 0 & 0 \\ 0 & 0 & -1 \\ 0 & 1 & 0 \end{pmatrix} = \begin{pmatrix} 0 & 1 & 0 \\ 0 & 0 & 0 \\ 0 & 0 & 0 \end{pmatrix}$$

$$[L_x, L_y] = L_x L_y - L_y L_x = \begin{pmatrix} 0 & -1 & 0 \\ 1 & 0 & 0 \\ 0 & 0 & 0 \end{pmatrix} = L_z$$

Cyclic permutation over $(x, y, z)$ completes the proof: $[L_y, L_z] = L_x$ and $[L_z, L_x] = L_y$. $\blacksquare$

### 3.2 Rodrigues' Rotation Formula

Any 3D rotation can be parameterized by an axis of rotation $\mathbf{n} = (n_x, n_y, n_z)^\top$ ($\|\mathbf{n}\|_2 = 1$) and an angle $\theta \in [0, \pi]$. Let $\mathbf{K} = \mathbf{n} \cdot \mathbf{L} = n_x L_x + n_y L_y + n_z L_z \in \mathfrak{so}(3)$:

$$\mathbf{K} = \begin{pmatrix} 0 & -n_z & n_y \\ n_z & 0 & -n_x \\ -n_y & n_x & 0 \end{pmatrix}$$

The matrix $\mathbf{K}$ implements the vector cross product: $\mathbf{K} \mathbf{v} = \mathbf{n} \times \mathbf{v}$.

```
+----------------------------------------------------------------------------------------------------+
| THEOREM 3.3: Rodrigues' Rotation Formula                                                           |
| The matrix exponential exp(theta K) in SO(3) evaluates in closed form to:                          |
|                                                                                                    |
|   exp(theta K) = I_3 + sin theta , K + (1 - cos theta) , K^2                                       |
+----------------------------------------------------------------------------------------------------+
```

*Proof.* By direct multiplication, for any unit vector $\mathbf{n}$:

$$\mathbf{K}^2 \mathbf{v} = \mathbf{n} \times (\mathbf{n} \times \mathbf{v}) = (\mathbf{n} \cdot \mathbf{v})\mathbf{n} - (\mathbf{n} \cdot \mathbf{n})\mathbf{v} = \mathbf{n}\mathbf{n}^\top \mathbf{v} - \mathbf{v} \implies \mathbf{K}^2 = \mathbf{n}\mathbf{n}^\top - \mathbf{I}_3$$

$$\mathbf{K}^3 = \mathbf{K}(\mathbf{n}\mathbf{n}^\top - \mathbf{I}_3) = (\mathbf{K}\mathbf{n})\mathbf{n}^\top - \mathbf{K} = \mathbf{0} - \mathbf{K} = -\mathbf{K}$$

Thus, higher powers satisfy the cyclic relations: $\mathbf{K}^{2m+1} = (-1)^m \mathbf{K}$ and $\mathbf{K}^{2m+2} = (-1)^m \mathbf{K}^2$ for $m \ge 0$. Expanding the matrix exponential:

$$\exp(\theta \mathbf{K}) = \sum_{k=0}^\infty \frac{\theta^k \mathbf{K}^k}{k!} = \mathbf{I}_3 + \left( \sum_{m=0}^\infty \frac{(-1)^m \theta^{2m+1}}{(2m+1)!} \right) \mathbf{K} + \left( \sum_{m=0}^\infty \frac{(-1)^m \theta^{2m+2}}{(2m+2)!} \right) \mathbf{K}^2$$

Recognizing the Taylor series for $\sin\theta$ and $1 - \cos\theta$:

$$\exp(\theta \mathbf{K}) = \mathbf{I}_3 + \sin\theta \, \mathbf{K} + (1 - \cos\theta) \, \mathbf{K}^2$$

$\blacksquare$

---

## 4. The Double Cover $\mathrm{SU}(2)$ and Quaternions $\mathbb{H}$

While $\mathrm{SO}(3)$ represents rotations, it suffers from a topological deficit: the manifold of $\mathrm{SO}(3)$ is homeomorphic to real projective space $\mathbb{R}P^3$, which is non-simply connected ($\pi_1(\mathrm{SO}(3)) \cong \mathbb{Z}_2$). This manifests practically as **gimbal lock** and topological phase discontinuities during gradient descent.

To achieve smooth, global optimization, we lift $\mathrm{SO}(3)$ to its universal covering group: the special unitary group $\mathrm{SU}(2)$, isomorphic to the unit quaternions $\operatorname{Sp}(1)$.

```
   Unit Quaternions Sp(1) ~= S^3 (Simply Connected 3-Sphere)
               |
               |  2:1 Covering Map pi(q) = pi(-q)
               v
   SO(3) ~= RP^3 (Projective 3-Space, pi_1 = Z_2)
```

### 4.1 Hamilton's Quaternion Algebra $\mathbb{H}$

```
+----------------------------------------------------------------------------------------------------+
| DEFINITION 3.1: The Algebra of Quaternions H                                                       |
| The quaternions H form a 4-dimensional associative, non-commutative normed division algebra over R |
| spanned by {1, i, j, k} satisfying Hamilton's fundamental identities:                              |
|                                                                                                    |
|   i^2 = j^2 = k^2 = i j k = -1                                                                     |
|                                                                                                    |
| and cyclic anticommutative relations:                                                              |
|   i j = k,   j i = -k,   j k = i,   k j = -i,   k i = j,   i k = -j                                |
+----------------------------------------------------------------------------------------------------+
```

A quaternion $q \in \mathbb{H}$ is written:

$$q = q_0 + q_1 \mathbf{i} + q_2 \mathbf{j} + q_3 \mathbf{k} = (q_0, \mathbf{v}), \quad q_0 \in \mathbb{R}, \; \mathbf{v} \in \mathbb{R}^3$$

The quaternion conjugate, norm, and inverse are:

$$q^* = q_0 - q_1 \mathbf{i} - q_2 \mathbf{j} - q_3 \mathbf{k} = (q_0, -\mathbf{v})$$

$$\|q\|^2 = q q^* = q^* q = q_0^2 + q_1^2 + q_2^2 + q_3^2$$

$$q^{-1} = \frac{q^*}{\|q\|^2} \quad (q \ne 0)$$

For unit quaternions ($\|q\| = 1$), the set forms the Lie group $\operatorname{Sp}(1) \cong S^3$.

### 4.2 Isomorphism $\mathrm{SU}(2) \cong \operatorname{Sp}(1)$

The group $\mathrm{SU}(2)$ consists of $2 \times 2$ unitary matrices with unit determinant:

$$\mathrm{SU}(2) = \left\{ U \in \mathbb{C}^{2 \times 2} \;\middle|\; U^\dagger U = \mathbf{I}_2, \; \det(U) = +1 \right\} = \left\{ \begin{pmatrix} \alpha & \beta \\ -\beta^* & \alpha^* \end{pmatrix} \;\middle|\; |\alpha|^2 + |\beta|^2 = 1 \right\}$$

Setting $\alpha = q_0 + i q_3$ and $\beta = q_2 + i q_1$, we map unit quaternions directly to $\mathrm{SU}(2)$ matrices:

$$U(q) = q_0 \mathbf{I}_2 + q_1 (i \sigma_x) + q_2 (i \sigma_y) + q_3 (i \sigma_z) = \begin{pmatrix} q_0 + i q_3 & q_2 + i q_1 \\ -q_2 + i q_1 & q_0 - i q_3 \end{pmatrix}$$

where $\sigma_x, \sigma_y, \sigma_z$ are the standard Hermitian **Pauli spin matrices**:

$$\sigma_x = \begin{pmatrix} 0 & 1 \\ 1 & 0 \end{pmatrix}, \quad \sigma_y = \begin{pmatrix} 0 & -i \\ i & 0 \end{pmatrix}, \quad \sigma_z = \begin{pmatrix} 1 & 0 \\ 0 & -1 \end{pmatrix}$$

### 4.3 The Double Covering Homomorphism $\pi : \mathrm{SU}(2) \to \mathrm{SO}(3)$

Let $\mathbf{v} = (x, y, z)^\top \in \mathbb{R}^3$ be identified with a purely imaginary quaternion $p = 0 + x\mathbf{i} + y\mathbf{j} + z\mathbf{k} \in \operatorname{Im}(\mathbb{H})$.

```
+----------------------------------------------------------------------------------------------------+
| THEOREM 3.4: Quaternion Rotation Action                                                            |
| For any unit quaternion q in Sp(1), the conjugation map:                                           |
|                                                                                                    |
|   Phi_q(p) = q p q^*                                                                               |
|                                                                                                    |
| maps Im(H) to Im(H) isometrically and preserves orientation, defining a 3D rotation R(q) in SO(3). |
| The homomorphism pi : Sp(1) -> SO(3) defined by pi(q) = R(q) is a surjective 2-to-1 Lie group     |
| covering map with kernel ker(pi) = {+1, -1}.                                                       |
+----------------------------------------------------------------------------------------------------+
```

*Proof.*
1. **Imaginary Preservation:**  
   $$(q p q^*)^* = (q^*)^* p^* q^* = q (-p) q^* = -(q p q^*)$$
   Since $(q p q^*)^* = -(q p q^*)$, $\operatorname{Re}(q p q^*) = 0$, so $q p q^* \in \operatorname{Im}(\mathbb{H})$.
2. **Norm Preservation:**  
   $$\|q p q^*\| = \|q\| \|p\| \|q^*\| = 1 \cdot \|p\| \cdot 1 = \|p\|$$
   The map is a linear isometry on $\mathbb{R}^3$, hence an orthogonal transformation in $\mathrm{O}(3)$. Since $\operatorname{Sp}(1) \cong S^3$ is connected, the image must lie in the connected component of the identity, $\mathrm{SO}(3)$.
3. **Double Covering Kernel:**  
   $R(q) = \mathbf{I}_3 \iff q p q^* = p$ for all $p \in \operatorname{Im}(\mathbb{H}) \iff q p = p q$.  
   The only quaternions commuting with all imaginary quaternions are the real scalars: $q \in \mathbb{R} \cap \operatorname{Sp}(1) = \{+1, -1\}$.  
   Therefore, $\ker(\pi) = \{+1, -1\}$, and $\pi(q) = \pi(-q)$. $\blacksquare$

For a rotation by angle $\theta$ around unit axis $\mathbf{n}$:

$$q = \cos\left(\frac{\theta}{2}\right) + \sin\left(\frac{\theta}{2}\right) (n_x \mathbf{i} + n_y \mathbf{j} + n_z \mathbf{k})$$

The half-angle $\theta / 2$ demonstrates the **spinor nature** of $\mathrm{SU}(2)$: a full $2\pi$ rotation in $\mathbb{R}^3$ sends $q \mapsto -q$; a $4\pi$ rotation is required to return to the identity $+1$.

---

## 5. Four-Dimensional Rotations: The $\mathrm{SO}(4)$ Isoclinic Factorization

In four dimensions, rotations exhibit rich algebraic structure not present in 3D: any rotation in $\mathbb{R}^4$ can be decomposed into two independent, commuting 2D plane rotations.

```
       SO(4) Lie Algebra so(4)  (dim = 6)
                  |
     +------------+------------+
     |                         |
     v                         v
  so(4)_+ ~= su(2)_L        so(4)_- ~= su(2)_R
  Self-Dual Bivectors       Anti-Self-Dual Bivectors
  Left Isoclinic            Right Isoclinic
```

```
+----------------------------------------------------------------------------------------------------+
| THEOREM 3.5: Exceptional Lie Algebra Isomorphism of so(4)                                          |
| The 6-dimensional Lie algebra so(4) splits into the direct sum of two commuting copies of su(2):   |
|                                                                                                    |
|   so(4) cong su(2)_L oplus su(2)_R                                                                 |
|                                                                                                    |
| Correspondingly, the universal covering group is Spin(4) cong SU(2)_L times SU(2)_R, and:          |
|                                                                                                    |
|   SO(4) cong (SU(2)_L times SU(2)_R) / { (+1, +1), (-1, -1) }                                      |
+----------------------------------------------------------------------------------------------------+
```

### 5.1 Quaternionic Representation of $\mathrm{SO}(4)$

Identify $\mathbb{R}^4$ with the algebra of quaternions $\mathbb{H}$ via $x = x_0 + x_1 \mathbf{i} + x_2 \mathbf{j} + x_3 \mathbf{k}$.

```
+----------------------------------------------------------------------------------------------------+
| THEOREM 3.6: Cayley's SO(4) Quaternionic Action                                                    |
| Every proper four-dimensional rotation R in SO(4) can be uniquely represented (up to sign) as a   |
| pair of unit quaternions (q_L, q_R) in Sp(1) times Sp(1) acting on x in H by:                     |
|                                                                                                    |
|   R(x) = q_L , x , q_R^*                                                                           |
+----------------------------------------------------------------------------------------------------+
```

- When $q_R = 1$, $R(x) = q_L x$ is a **left-isoclinic rotation**.
- When $q_L = 1$, $R(x) = x q_R^*$ is a **right-isoclinic rotation**.
- Every general 4D rotation is the composition of a left-isoclinic and a right-isoclinic rotation:
  $$R = R_L(q_L) \circ R_R(q_R) = R_R(q_R) \circ R_L(q_L)$$

### 5.2 Self-Dual and Anti-Self-Dual Splitting

In the language of differential forms and exterior calculus (Chapter 1), the space of 2-forms $\bigwedge^2(\mathbb{R}^4) \cong \mathfrak{so}(4)$ is 6-dimensional. Under the Hodge star operator $\star_2$:

$$\star_2^2 = (-1)^{2(4-2)} \operatorname{id} = +1 \implies \text{Eigenvalues are } \lambda = \pm 1$$

$$\bigwedge\nolimits^2(\mathbb{R}^4) = \bigwedge\nolimits^2_+(\mathbb{R}^4) \oplus \bigwedge\nolimits^2_-(\mathbb{R}^4)$$

- **Self-Dual Subspace $\bigwedge^2_+$ ($\star \omega = +\omega$):** Corresponds to left-isoclinic Lie algebra $\mathfrak{su}(2)_L$. Basis:
  $$\omega_1^+ = \mathbf{d}x^0 \wedge \mathbf{d}x^1 + \mathbf{d}x^2 \wedge \mathbf{d}x^3, \quad \omega_2^+ = \mathbf{d}x^0 \wedge \mathbf{d}x^2 + \mathbf{d}x^3 \wedge \mathbf{d}x^1, \quad \omega_3^+ = \mathbf{d}x^0 \wedge \mathbf{d}x^3 + \mathbf{d}x^1 \wedge \mathbf{d}x^2$$
- **Anti-Self-Dual Subspace $\bigwedge^2_-$ ($\star \eta = -\eta$):** Corresponds to right-isoclinic Lie algebra $\mathfrak{su}(2)_R$. Basis:
  $$\omega_1^- = \mathbf{d}x^0 \wedge \mathbf{d}x^1 - \mathbf{d}x^2 \wedge \mathbf{d}x^3, \quad \omega_2^- = \mathbf{d}x^0 \wedge \mathbf{d}x^2 - \mathbf{d}x^3 \wedge \mathbf{d}x^1, \quad \omega_3^- = \mathbf{d}x^0 \wedge \mathbf{d}x^3 - \mathbf{d}x^1 \wedge \mathbf{d}x^2$$

As proven in `lean_pilot/Pilot/HodgeStarDuality.lean`, these two subspaces are strictly orthogonal under any Hodge-isometry inner product. In the IMF architecture, this enables independent left/right chiral token projections without mutual interference.

---

## 6. Clifford Geometric Algebras $\mathcal{C}\ell(3,0)$ and $\mathcal{C}\ell(0,3)$

Clifford algebras unify scalars, vectors, bivectors, and pseudoscalars into a single associative graded algebra via the **geometric product**.

```
+----------------------------------------------------------------------------------------------------+
| DEFINITION 3.2: Clifford Geometric Algebra                                                         |
| The Clifford algebra Cl(p, q) over R^{p,q} is the associative unital algebra generated by an      |
| orthonormal basis {e_1, ..., e_{p+q}} satisfying:                                                  |
|                                                                                                    |
|   e_i e_j + e_j e_i = 2 g_{ij}                                                                     |
|                                                                                                    |
| where g_{ii} = +1 for 1 <= i <= p, and g_{ii} = -1 for p+1 <= i <= p+q, with e_i e_j = -e_j e_i    |
| for i != j.                                                                                        |
+----------------------------------------------------------------------------------------------------+
```

The geometric product of two 1-vectors $\mathbf{u}, \mathbf{v}$ decomposes into a symmetric scalar inner product and an antisymmetric bivector outer product:

$$\mathbf{u} \mathbf{v} = \mathbf{u} \cdot \mathbf{v} + \mathbf{u} \wedge \mathbf{v}$$

```
+----------------------------------------------------------------------------------------------------+
| TABLE 3.1: Graded Structure of Cl(3,0) (Dimension = 2^3 = 8)                                      |
+-------+---------------+--------------------+-----------+-------------------------------------------+
| Grade | Name          | Basis Elements     | Dimension | Geometric Role                            |
+-------+---------------+--------------------+-----------+-------------------------------------------+
| 0     | Scalar        | 1                  | 1         | Magnitude, scalar distance                |
| 1     | Vector        | e_1, e_2, e_3      | 3         | Directed displacement, token vector       |
| 2     | Bivector      | e_12, e_23, e_31   | 3         | Oriented plane of rotation, Lie algebra   |
| 3     | Pseudoscalar  | I = e_1 e_2 e_3    | 1         | Oriented volume, spatial chirality        |
+-------+---------------+--------------------+-----------+-------------------------------------------+
```

### 6.1 Rotors in $\mathcal{C}\ell(3,0)$

A **rotor** $R$ is an even-grade element ($R \in \mathcal{C}\ell^+(3,0)$) satisfying $R R^\dagger = 1$, where $\dagger$ is the Clifford reversion operator:

$$R = \exp\left( -\frac{B}{2} \right) = \cos\left(\frac{\theta}{2}\right) - \sin\left(\frac{\theta}{2}\right) \hat{B}$$

where $B = \theta \hat{B}$ is a simple bivector representing the plane of rotation ($\hat{B}^2 = -1$).

The rotor acts on an arbitrary vector $\mathbf{v}$ via the **sandwich product**:

$$\mathbf{v}' = R \, \mathbf{v} \, R^\dagger$$

```
+----------------------------------------------------------------------------------------------------+
| THEOREM 3.7: Equivalence of Even Clifford Subalgebra and Quaternions                               |
| The even subalgebra Cl^+(3,0) of Cl(3,0) is algebra-isomorphic to Hamilton's quaternions H:        |
|                                                                                                    |
|   Cl^+(3,0) cong H                                                                                 |
|                                                                                                    |
| under the identification:                                                                          |
|   i <---> -e_23 = -e_2 e_3,    j <---> -e_31 = -e_3 e_1,    k <---> -e_12 = -e_1 e_2              |
+----------------------------------------------------------------------------------------------------+
```

*Proof.* Verify the quaternion relations for the bivector generators:

$$(-e_2 e_3)^2 = (-e_2 e_3)(-e_2 e_3) = e_2 e_3 e_2 e_3 = -e_2 e_2 e_3 e_3 = -(+1)(+1) = -1$$

$$(-e_2 e_3)(-e_3 e_1) = e_2 e_3 e_3 e_1 = e_2 (+1) e_1 = e_2 e_1 = -e_1 e_2$$

This matches the quaternion product $\mathbf{i} \mathbf{j} = \mathbf{k} \leftrightarrow -e_1 e_2$. Thus $\mathcal{C}\ell^+(3,0) \cong \mathbb{H}$. $\blacksquare$

---

## 7. Continuous Spherical Linear Interpolation (SLERP) on $S^3$

In autoregressive token generation, intermediate semantic states between discrete token positions $t$ and $t+1$ require smooth, constant-speed geodesic trajectory interpolation. Linear interpolation in Euclidean space ($\mathbf{q}(t) = (1-t)\mathbf{q}_0 + t\mathbf{q}_1$) fails catastrophically: it departs from the unit sphere ($||\mathbf{q}(t)|| < 1$), inducing norm decay and angular deceleration.

The exact geodesic on the Riemannian sphere $S^3 \subset \mathbb{H}$ is given by **Spherical Linear Interpolation (SLERP)** (Shoemake, 1985).

```
                      q_1 (Token t+1)
                     /
                    / Geodesic Arc gamma(t) on S^3
                   /  Constant Angular Velocity omega
                  v
       q_0 (Token t) --------> Ambient Space (Linear cut chords fail!)
```

```
+----------------------------------------------------------------------------------------------------+
| THEOREM 3.8: Spherical Linear Interpolation (SLERP)                                                |
| Let q_0, q_1 in S^3 be two unit quaternions with inner product cos Omega = langle q_0, q_1 rangle.  |
| The shortest geodesic path gamma(t) : [0, 1] -> S^3 connecting q_0 to q_1 is:                      |
|                                                                                                    |
|   text{SLERP}(q_0, q_1; t) = frac{sin((1 - t)Omega)}{sin Omega} q_0 + frac{sin(t Omega)}{sin Omega} q_1|
+----------------------------------------------------------------------------------------------------+
```

*Proof.* The geodesic curve $\gamma(t)$ on a Riemannian unit sphere satisfies the great-circle equation:

$$\ddot{\gamma}(t) + \|\dot{\gamma}(t)\|^2 \gamma(t) = 0$$

Let $\Omega$ be the angular distance between $q_0$ and $q_1$, where $\cos\Omega = q_0 \cdot q_1$. The curve $\gamma(t)$ lies in the 2D plane spanned by $q_0$ and the orthogonal unit tangent vector $q_\perp$:

$$q_\perp = \frac{q_1 - (q_0 \cdot q_1) q_0}{\|q_1 - (q_0 \cdot q_1) q_0\|} = \frac{q_1 - q_0 \cos\Omega}{\sin\Omega}$$

For constant angular velocity, the geodesic is:

$$\gamma(t) = q_0 \cos(t\Omega) + q_\perp \sin(t\Omega)$$

Substituting $q_\perp$:

$$\gamma(t) = q_0 \cos(t\Omega) + \left( \frac{q_1 - q_0 \cos\Omega}{\sin\Omega} \right) \sin(t\Omega)$$

$$= q_0 \left( \cos(t\Omega) - \frac{\cos\Omega \sin(t\Omega)}{\sin\Omega} \right) + q_1 \left( \frac{\sin(t\Omega)}{\sin\Omega} \right)$$

$$= q_0 \left( \frac{\sin\Omega \cos(t\Omega) - \cos\Omega \sin(t\Omega)}{\sin\Omega} \right) + q_1 \frac{\sin(t\Omega)}{\sin\Omega}$$

Using the sine difference angle identity $\sin(\Omega - t\Omega) = \sin((1-t)\Omega)$:

$$\gamma(t) = \frac{\sin((1-t)\Omega)}{\sin\Omega} q_0 + \frac{\sin(t\Omega)}{\sin\Omega} q_1$$

$\blacksquare$

```
+----------------------------------------------------------------------------------------------------+
| THEOREM 3.9: Constant Geodesic Velocity of SLERP                                                   |
| The tangent velocity along the SLERP trajectory has constant Euclidean norm:                       |
|                                                                                                    |
|   ||dot{gamma}(t)||_2 = Omega                                                                      |
|                                                                                                    |
| and the covariant acceleration vanishes identically: nabla_{dot{gamma}} dot{gamma} = 0.           |
+----------------------------------------------------------------------------------------------------+
```

### 7.1 Double Cover Antipodal Metric Alignment

Because $q$ and $-q$ represent the identical physical rotation in $\mathrm{SO}(3)$, the shortest geodesic between two rotation states must select the closer antipodal branch:

$$\text{If } \langle q_0, q_1 \rangle < 0 \implies q_1 \leftarrow -q_1, \quad \cos\Omega \leftarrow -\cos\Omega$$

This prevents the trajectory from traversing the long arc ($> 180^\circ$) of the 3-sphere.

---

## 8. Continuous-Time Geodesic Token Trajectory Infilling

In the IMF Omni-Block, speculative decoding and sub-token infilling are formulated as geodesic flows on $\operatorname{Sp}(1)$.

```
+----------------------------------------------------------------------------------------------------+
| ALGORITHM 3.1: Speculative Sub-Token Lie Geodesic Infilling                                        |
| Input: Coarse token orientations Q_{t}, Q_{t+1} in Sp(1); sub-step parameter tau in (0, 1)        |
| Output: High-fidelity infilled intermediate representation h(t + tau) in R^d                        |
|                                                                                                    |
| 1. Compute cosine distance: c = langle Q_t, Q_{t+1} rangle                                         |
| 2. Antipodal alignment:                                                                            |
|      if c < 0:                                                                                     |
|          Q_{t+1} = -Q_{t+1}                                                                        |
|          c = -c                                                                                    |
| 3. If c > 0.9995 (nearly collinear, avoid division by zero):                                      |
|      Q(tau) = (1 - tau) Q_t + tau Q_{t+1}                                                          |
|      Q(tau) = Q(tau) / ||Q(tau)||                                                                  |
|    Else:                                                                                           |
|      Omega = arccos(c)                                                                             |
|      Q(tau) = (sin((1 - tau) Omega) / sin Omega) Q_t + (sin(tau Omega) / sin Omega) Q_{t+1}        |
| 4. Transform latent token feature v_0 via sandwich rotor product:                                  |
|      h(t + tau) = Q(tau) * v_0 * Q(tau)^*                                                          |
+----------------------------------------------------------------------------------------------------+
```

This ensures that intermediate sub-tokens maintain exact isometric energy conservation, preserving memory stability across speculative rollouts.

---

## 9. Chapter Summary and Formal Manifest

This chapter has established the algebraic and geometric foundations of classical Lie groups in low dimensions ($d \le 4$):
- $\mathrm{SO}(2) \cong \mathrm{U}(1)$ provides planar phase dynamics but is fundamentally constrained by its abelian commutativity.
- $\mathrm{SO}(3)$ models spatial 3D rotations, generated by $\mathfrak{so}(3)$ with commutation relation $[L_a, L_b] = \epsilon_{abc} L_c$, leading to Rodrigues' closed-form rotation formula.
- $\mathrm{SU}(2) \cong \operatorname{Sp}(1)$ provides the simply-connected double cover of $\mathrm{SO}(3)$, eliminating gimbal lock and non-contractible topological defects via Hamilton's quaternion algebra $\mathbb{H}$.
- $\mathrm{SO}(4)$ factorizes into two commuting copies of $\mathrm{SU}(2)$, mapping directly to self-dual and anti-self-dual bivectors in exterior calculus and enabling chiral token splitting.
- Clifford Geometric Algebra $\mathcal{C}\ell(3,0)$ unifies vectors, bivectors, and rotors into a coordinate-free framework where the even subalgebra $\mathcal{C}\ell^+(3,0)$ is isomorphic to $\mathbb{H}$.
- Spherical Linear Interpolation (SLERP) on $S^3$ provides the unique constant-speed geodesic trajectory connecting discrete token rotations, forming the algorithmic engine for continuous speculative reasoning in IMF.

In Chapter 4, we examine the rational **Cayley transform** and discrete Lyapunov stability, replacing transcendental matrix exponentials with exact, energy-conserving rational approximations.


---

## 8. Exceptional Subgroup Inclusions: Spin(7), G2, and Clifford Geometric Algebras

To establish the bridge between 3D/4D spatial rotations and the higher-dimensional exceptional manifolds treated in Volume II, we detail the algebraic embedding of the classical groups into Clifford geometric algebras $\mathcal{C}\ell(p, q)$.

### 8.1 The Even Clifford Subalgebra $\mathcal{C}\ell^+(3, 0) \cong \mathbb{H}$
In the geometric algebra $\mathcal{C}\ell(3, 0)$ generated by orthonormal basis vectors $e_1, e_2, e_3$ satisfying $e_i e_j + e_j e_i = 2\delta_{ij}$, the bivectors span a 3-dimensional subspace:

$$B_1 = e_2 e_3, \quad B_2 = e_3 e_1, \quad B_3 = e_1 e_2$$

Computing their pairwise geometric products reveals the exact Hamilton quaternionic relations:

$$B_1^2 = e_2 e_3 e_2 e_3 = -e_2 e_2 e_3 e_3 = -1$$
$$B_2^2 = -1, \quad B_3^2 = -1$$
$$B_1 B_2 = (e_2 e_3)(e_3 e_1) = e_2 e_1 = -B_3$$

Thus, the map identifying $B_1 \mapsto -i, B_2 \mapsto -j, B_3 \mapsto -k$ is an algebra isomorphism:

$$\mathcal{C}\ell^+(3, 0) \cong \mathbb{H}$$

```
+----------------------------------------------------------------------------------------------------+
| THEOREM 3.4: Universal Spinor Representation of Rotations                                          |
| Let u in R^3 be any spatial vector, and let R in Spin(3) be a unit rotor given by:                 |
|   R = cos(theta/2) - B sin(theta/2)                                                                |
| where B = e_1 e_2 is the unit plane bivector of rotation. Then the sandwich operator:             |
|   u' = R u R~                                                                                      |
| implements a strict spatial rotation of u through angle theta in the plane B, where R~ is the     |
| Clifford grade-reversal involution.                                                                |
+----------------------------------------------------------------------------------------------------+
```

*Proof.*
Decompose the vector $u = u_\parallel + u_\perp$, where $u_\parallel$ lies in the plane $B$ and $u_\perp$ is orthogonal to $B$.
For the parallel component:
$$B u_\parallel = -u_\parallel B$$
Since $u_\parallel$ anticommutes with $B$:
$$R u_\parallel = (\cos(\theta/2) - B\sin(\theta/2)) u_\parallel = u_\parallel (\cos(\theta/2) + B\sin(\theta/2)) = u_\parallel \tilde{R}$$
Multiplying on the right by $\tilde{R}$:
$$u'_\parallel = R u_\parallel \tilde{R} = u_\parallel \tilde{R}^2 = u_\parallel (\cos(\theta) + B\sin(\theta))$$
which is Euler's rotation formula in geometric algebra.
For the perpendicular component:
$$B u_\perp = u_\perp B$$
Since $u_\perp$ commutes with $B$:
$$R u_\perp = u_\perp R$$
Multiplying on the right by $\tilde{R}$:
$$u'_\perp = R u_\perp \tilde{R} = u_\perp R \tilde{R} = u_\perp$$
The orthogonal component is strictly invariant. Therefore, the sandwich map $R u \tilde{R}$ rotates the plane component by $\theta$ while preserving the normal axis, proving it is an exact element of $\mathrm{SO}(3)$. $\blacksquare$
