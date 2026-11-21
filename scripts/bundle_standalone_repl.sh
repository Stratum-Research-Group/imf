#!/usr/bin/env bash
# scripts/bundle_standalone_repl.sh
# Packages bin/imf_repl and runtime dependencies into a portable distribution bundle.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${ROOT_DIR}/dist/imf_repl_bundle"
rm -rf "${DIST_DIR}"
mkdir -p "${DIST_DIR}/bin" "${DIST_DIR}/lib" "${DIST_DIR}/checkpoints"

echo "=================================================================="
echo "  Bundling Standalone IMF C++ REPL Distribution"
echo "=================================================================="

# 1. Copy binary
cp "${ROOT_DIR}/bin/imf_repl" "${DIST_DIR}/bin/imf_repl"
chmod +x "${DIST_DIR}/bin/imf_repl"

# 2. Copy launcher script
cat << 'EOF' > "${DIST_DIR}/imf-repl"
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export LD_LIBRARY_PATH="${SCRIPT_DIR}/lib:${LD_LIBRARY_PATH:-}"
exec "${SCRIPT_DIR}/bin/imf_repl" "$@"
EOF
chmod +x "${DIST_DIR}/imf-repl"

# 3. Create tarball
tar -czf "${ROOT_DIR}/dist/imf_repl_linux_x86_64.tar.gz" -C "${ROOT_DIR}/dist" imf_repl_bundle
echo "[✓] Standalone C++ REPL Bundle created: ${ROOT_DIR}/dist/imf_repl_linux_x86_64.tar.gz"
