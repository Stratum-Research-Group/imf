"""
Omni-100 Master Domain Synthesizer (IMF).
Integrates all 100 specialized expert domains:
- 64 Omni Domains: Quantum Maths, Chaos Theory, Game Theory, Cyber Security, Systems, Genomics, Logic, NLP.
- 32 Benchmark Domains: FineWeb-Edu, Python Algorithmic AST, Agentic Tool Calls, GSM8K, SWE-bench, ARC-AGI, Polyglot, MMLU-Pro.
- 4 Enterprise OS Domains: Windows Win32 Internals, Active Directory & PowerShell, macOS Darwin Mach/XPC, Apple Silicon ARM64.
"""

from typing import List, Tuple
import random

from imf.omni_64_multidomain_synthesizer import OMNI_64_EXPERT_DOMAINS, Omni64DomainSynthesizer
from imf.benchmark_master_synthesizer import BENCHMARK_32_ADDITIONAL_DOMAINS, BenchmarkMasterSynthesizer
from imf.os_enterprise_synthesizer import OSEnterpriseSynthesizer

ENTERPRISE_OS_DOMAINS: List[str] = [
    "os_windows_win32_internals",       # Win32 API, IOCP thread pools, security descriptors, NTDLL
    "os_windows_server_ad_powershell",  # Active Directory DS, Kerberos ticket triage, GPO, PowerShell DSC
    "os_macos_darwin_mach_xpc",         # Mach ports, task memory, Apple XPC services, libdispatch GCD
    "os_apple_silicon_arm64_abi",       # ARM64e PAC pointers, Mach-O fat binaries, Metal compute shaders
]

OMNI_100_MASTER_DOMAINS: List[str] = (
    OMNI_64_EXPERT_DOMAINS +
    BENCHMARK_32_ADDITIONAL_DOMAINS +
    ENTERPRISE_OS_DOMAINS
)

assert len(OMNI_100_MASTER_DOMAINS) == 100, f"Expected 100 domains, got {len(OMNI_100_MASTER_DOMAINS)}"


class Omni100MasterSynthesizer:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.omni64 = Omni64DomainSynthesizer(seed=seed)
        self.bench32 = BenchmarkMasterSynthesizer(seed=seed)
        self.os_ent = OSEnterpriseSynthesizer(seed=seed)

    def generate_corpus(self, num_samples: int = 1000) -> List[Tuple[str, str]]:
        corpus = []
        for _ in range(num_samples):
            r = self.rng.random()
            if r < 0.40:
                # 40% from 64-domain omni synthesizer
                sample = self.omni64.generate_corpus(1)[0]
                corpus.append(sample)
            elif r < 0.80:
                # 40% from 32-domain benchmark master (Edu, Agentic, Python AST, GSM8K, SWE-bench)
                sample = self.bench32.generate_corpus(1)[0]
                corpus.append(sample)
            else:
                # 20% from Enterprise OS (Windows, Active Directory, macOS XPC)
                sample = self.os_ent.generate_corpus(1)[0]
                corpus.append(sample)
        return corpus


if __name__ == "__main__":
    syn = Omni100MasterSynthesizer()
    samples = syn.generate_corpus(5)
    print(f"[*] Verified Omni-100 Master Synthesizer. Total domains: {len(OMNI_100_MASTER_DOMAINS)}")
    for txt, tag in samples:
        print(f"[{tag}] -> {txt[:100]}...\n")
