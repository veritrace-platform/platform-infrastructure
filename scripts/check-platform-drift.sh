#!/usr/bin/env bash
# Reports differences in the shared Go platform packages of sibling service repositories.
# The packages are intentionally duplicated per service (polyrepo); this check keeps them in sync.
# Usage: scripts/check-platform-drift.sh [workspace-dir]   (default: parent of this repository)
set -euo pipefail

workspace="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
reference="core-business-service"
services=(telemetry-stream-service blockchain-relayer-service)
shared_dirs=(internal/platform internal/httpapi)

normalize() {
  # Strip service-specific identifiers so only real code differences remain.
  sed -E \
    -e 's#github.com/veritrace-platform/[a-z-]+#MODULE#g' \
    -e 's#(core|telemetry|relayer)-[a-z-]*service#SERVICE#g' \
    -e 's#veritrace_(core|telemetry|relayer)#veritrace_SERVICE#g' \
    -e 's#"(core|telemetry|relayer)"#"SUBSYSTEM"#g' \
    -e 's#:80[89][01]|:810[01]#:PORT#g' "$1"
}

status=0
for service in "${services[@]}"; do
  if [[ ! -d "$workspace/$service/internal/platform" ]]; then
    echo "skip  $service (no Go platform packages yet)"
    continue
  fi
  for dir in "${shared_dirs[@]}"; do
    while IFS= read -r file; do
      rel="${file#"$workspace/$reference/"}"
      other="$workspace/$service/$rel"
      if [[ ! -f "$other" ]]; then
        echo "MISSING $service/$rel"
        status=1
      elif ! diff -q <(normalize "$file") <(normalize "$other") >/dev/null; then
        echo "DRIFT   $service/$rel"
        diff -u <(normalize "$file") <(normalize "$other") | sed 's/^/        /' | head -20
        status=1
      fi
    done < <(find "$workspace/$reference/$dir" -name '*.go' | sort)
  done
done

if [[ $status -eq 0 ]]; then
  echo "shared platform packages are in sync"
fi
exit "$status"
