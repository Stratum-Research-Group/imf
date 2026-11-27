#!/usr/bin/env python3
"""
scripts/verify_dual_push_sync.py
Verifies commit parity and branch alignment between 'origin' (GitLab) and 'github' (GitHub).
Certifies lockstep synchronization across both remotes.
"""

import subprocess
import sys

def get_remote_head(remote):
    cmd = ["git", "ls-remote", remote, "refs/heads/main"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and res.stdout.strip():
        return res.stdout.split()[0]
    return None

def verify_sync():
    print("[*] Verifying dual-remote commit parity...")
    local_head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    gitlab_head = get_remote_head("origin")
    github_head = get_remote_head("github")

    print(f"  • Local HEAD:  {local_head}")
    print(f"  • GitLab HEAD: {gitlab_head}")
    print(f"  • GitHub HEAD: {github_head}")

    if local_head == gitlab_head == github_head:
        print("\n[✓] Dual-Push Parity Certified: 100% in lockstep across both remotes.")
        return 0
    else:
        print("\n[!] Discrepancy detected between remotes.")
        return 1

if __name__ == '__main__':
    sys.exit(verify_sync())
