#!/usr/bin/env python3
"""Measured launch latency + isometry check for csrc/fused_blackwell_lie_rolling_kv.cu -> benchmark_results/lie_kv.json"""
import ctypes, json, os, torch
root=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lib=ctypes.CDLL(os.path.join(root,"csrc","libfused_blackwell_lie_rolling_kv.so"))
lib.launch_fused_blackwell_lie_rolling_kv.argtypes=[ctypes.c_void_p]*6+[ctypes.c_int]*3+[ctypes.c_void_p]
lib.launch_fused_blackwell_lie_rolling_kv.restype=ctypes.c_int
d=32; res=[]
for B,H in [(1,1),(1,32),(8,32)]:
    q=torch.randn(B,H,1,d,device="cuda");k=torch.randn_like(q);v=torch.randn_like(q)
    U=torch.stack([torch.linalg.qr(torch.randn(d,d,device="cuda"))[0] for _ in range(H)]).contiguous()
    M=torch.zeros(B,H,d,d,device="cuda");y=torch.empty_like(q)
    run=lambda: lib.launch_fused_blackwell_lie_rolling_kv(q.data_ptr(),k.data_ptr(),v.data_ptr(),U.data_ptr(),M.data_ptr(),y.data_ptr(),B,H,d,None)
    for _ in range(200): assert run()==0
    torch.cuda.synchronize(); a=torch.cuda.Event(enable_timing=True); b=torch.cuda.Event(enable_timing=True); N=5000
    a.record(); [run() for _ in range(N)]; b.record(); torch.cuda.synchronize()
    res.append(dict(batch=B,heads=H,head_dim=d,us_per_launch=round(a.elapsed_time(b)/N*1000,2)))
U=torch.linalg.qr(torch.randn(d,d,device="cuda"))[0].unsqueeze(0).contiguous()
M=torch.randn(1,1,d,d,device="cuda"); z=torch.zeros(1,1,1,d,device="cuda"); y=torch.empty_like(z); n0=M.norm().item()
for _ in range(1000): lib.launch_fused_blackwell_lie_rolling_kv(z.data_ptr(),z.data_ptr(),z.data_ptr(),U.data_ptr(),M.data_ptr(),y.data_ptr(),1,1,d,None)
torch.cuda.synchronize()
out=dict(gpu=torch.cuda.get_device_name(0),launch_latency=res,frobenius_before=n0,frobenius_after_1000_steps=M.norm().item())
os.makedirs(os.path.join(root,"benchmark_results"),exist_ok=True)
json.dump(out,open(os.path.join(root,"benchmark_results","lie_kv.json"),"w"),indent=2); print(json.dumps(out,indent=2))
