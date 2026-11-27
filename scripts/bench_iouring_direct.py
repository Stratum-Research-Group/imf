#!/usr/bin/env python3
"""Real io_uring direct-read benchmark (replaces the stub numbers). Writes JSON to benchmark_results/."""
import ctypes, json, os, sys, platform, subprocess, time

class Cfg(ctypes.Structure):
    _fields_=[("path",ctypes.c_char_p),("block_size",ctypes.c_uint64),("num_blocks",ctypes.c_uint32),
              ("queue_depth",ctypes.c_uint32),("passes",ctypes.c_uint32),("want_direct",ctypes.c_uint32),
              ("want_fixed",ctypes.c_uint32),("want_sqpoll",ctypes.c_uint32),("remove_file",ctypes.c_uint32)]
class St(ctypes.Structure):
    _fields_=[("bytes_read",ctypes.c_uint64),("elapsed_ns",ctypes.c_uint64),("blocks_verified",ctypes.c_uint64),
              ("blocks_corrupt",ctypes.c_uint64),("direct_active",ctypes.c_uint32),("fixed_active",ctypes.c_uint32),
              ("sqpoll_active",ctypes.c_uint32),("status",ctypes.c_uint32),("err",ctypes.c_int32)]

def main():
    root=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lib=ctypes.CDLL(os.path.join(root,"bin","libfused_iouring_weight_streamer.so"))
    lib.run_iouring_direct_read_benchmark.argtypes=[ctypes.POINTER(Cfg),ctypes.POINTER(St)]
    lib.run_iouring_direct_read_benchmark.restype=ctypes.c_int
    tmp=os.path.join(root,".bench_iouring.tmp")
    results=[]
    for direct,fixed,sq,qd in [(0,0,0,8),(1,0,0,1),(1,0,0,8),(1,1,0,8),(1,1,1,8),(1,1,1,32)]:
        c=Cfg(tmp.encode(),1<<20,4096,qd,1,direct,fixed,sq,1); s=St()
        rc=lib.run_iouring_direct_read_benchmark(ctypes.byref(c),ctypes.byref(s))
        gbps=(s.bytes_read/ (s.elapsed_ns/1e9))/1e9 if s.elapsed_ns else 0
        r=dict(req_direct=direct,req_fixed=fixed,req_sqpoll=sq,qd=qd,rc=rc,err=s.err,status=s.status,
               direct_active=s.direct_active,fixed_active=s.fixed_active,sqpoll_active=s.sqpoll_active,
               bytes=s.bytes_read,seconds=round(s.elapsed_ns/1e9,4),GB_per_s=round(gbps,3),
               verified=s.blocks_verified,corrupt=s.blocks_corrupt)
        results.append(r); print(r)
    out=dict(kernel=platform.release(),cpu=platform.processor(),block_bytes=1<<20,blocks=4096,
             note="Pattern file written, fsync'd, posix_fadvise(DONTNEED) before read. GB/s=1e9 B/s.",results=results)
    os.makedirs(os.path.join(root,"benchmark_results"),exist_ok=True)
    json.dump(out,open(os.path.join(root,"benchmark_results","iouring_direct_read.json"),"w"),indent=2)
if __name__=="__main__": main()
