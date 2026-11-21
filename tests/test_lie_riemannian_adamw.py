import torch
import pytest
from imf.lie_riemannian_adamw import LieRiemannianAdamW, cayley_transform

def test_cayley_transform_so_orthogonality():
    d = 16
    torch.manual_seed(42)
    # Generate random skew-symmetric matrix Omega = A - A^T
    A = torch.randn(d, d)
    Omega = A - A.t()
    
    # Compute Cayley transform: R = (I - 0.5 Omega) (I + 0.5 Omega)^-1
    R = cayley_transform(Omega)
    
    # Check orthogonality: R R^T = I
    I = torch.eye(d)
    recon = torch.matmul(R, R.t())
    diff = torch.norm(recon - I).item()
    assert diff < 1e-4, f"Orthogonality violation: norm diff = {diff}"
    
    # Check determinant = +1 (proper rotation SO(d))
    det = torch.linalg.det(R).item()
    assert abs(det - 1.0) < 1e-3, f"Determinant is not +1: det = {det}"

def test_lie_riemannian_adamw_step():
    torch.manual_seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # Parameter 1: SO(d) rotation matrix (square 2D)
    d = 8
    A = torch.randn(d, d, device=device)
    Q, _ = torch.linalg.qr(A) # Start on O(d)
    if torch.linalg.det(Q) < 0:
        Q[:, 0] = -Q[:, 0]  # Ensure det(Q) = +1 in SO(d)
    U = torch.nn.Parameter(Q.clone())
    
    # Parameter 2: General flat weight matrix (non-square or feedforward)
    W = torch.nn.Parameter(torch.randn(32, 16, device=device))
    
    optimizer = LieRiemannianAdamW(
        [
            {"params": [U], "is_rotator": True, "lr": 1e-2},
            {"params": [W], "is_rotator": False, "lr": 1e-3, "weight_decay": 0.01}
        ]
    )
    
    # Check initial orthogonality of U
    I = torch.eye(d, device=device)
    init_ortho = torch.norm(torch.matmul(U, U.t()) - I).item()
    assert init_ortho < 1e-4
    
    # Run 5 optimization steps with dummy loss
    for step in range(5):
        optimizer.zero_grad()
        loss = (U ** 2).sum() + (W ** 2).sum()
        loss.backward()
        optimizer.step()
        
        # Verify U remains strictly on the SO(d) manifold after every step!
        ortho_err = torch.norm(torch.matmul(U, U.t()) - I).item()
        assert ortho_err < 1e-4, f"Step {step}: Orthogonality drifted to {ortho_err}"
        det = torch.linalg.det(U).item()
        assert abs(det - 1.0) < 1e-3, f"Step {step}: Determinant drifted: {det}"
