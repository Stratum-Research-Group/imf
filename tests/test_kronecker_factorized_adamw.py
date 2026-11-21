import torch
import pytest
from imf.kronecker_factorized_adamw import KroneckerFactorizedAdamW

def test_kronecker_factorized_adamw_memory_and_step():
    torch.manual_seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Linear layer with 2048 x 8192 parameters (~16.7M params)
    d1, d2 = 512, 1024
    w = torch.nn.Parameter(torch.randn(d1, d2, device=device))
    b = torch.nn.Parameter(torch.zeros(d1, device=device))

    opt = KroneckerFactorizedAdamW([w, b], lr=1e-3)

    # 1. Forward & Backward
    x = torch.randn(8, d2, device=device)
    loss = (torch.matmul(x, w.t()) + b).sum()
    loss.backward()

    opt.step()

    # 2. Verify state memory: row + col vectors instead of full matrix!
    state_w = opt.state[w]
    assert state_w["is_factorized"] is True
    # exp_avg_sq_row has size d1, exp_avg_sq_col has size d2
    row_bytes = state_w["exp_avg_sq_row"].numel() * 4
    col_bytes = state_w["exp_avg_sq_col"].numel() * 4
    factorized_bytes = row_bytes + col_bytes
    full_matrix_bytes = (d1 * d2) * 4

    reduction_factor = full_matrix_bytes / factorized_bytes
    print(f"Memory reduction factor for second moment: {reduction_factor:.1f}x")
    assert reduction_factor > 300.0, f"Expected >300x reduction, got {reduction_factor}"

    # 3. Check stability across 5 steps
    for step in range(5):
        opt.zero_grad()
        loss = (torch.matmul(x, w.t()) + b).sum()
        loss.backward()
        opt.step()
        assert not torch.isnan(loss)
        assert not torch.isnan(w).any()
