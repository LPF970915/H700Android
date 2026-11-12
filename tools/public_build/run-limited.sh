#!/bin/bash
# Apply the project's resource limits on any systemd/cgroup-v2 Linux host.
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
    [[ $# -gt 0 ]] || { echo 'Usage: run-limited.sh command [args...]' >&2; exit 2; }
    if [[ $EUID == 0 ]]; then
        : "${ROC_BUILD_USER:?When invoking as root, set ROC_BUILD_USER to the unprivileged builder}"
        build_uid=$(id -u "$ROC_BUILD_USER")
        build_gid=$(id -g "$ROC_BUILD_USER")
        prefix=()
    else
        build_uid=$(id -u)
        build_gid=$(id -g)
        prefix=(sudo -n)
    fi
    [[ "$build_uid" != 0 ]] || { echo 'Build user must not be root' >&2; exit 2; }
    exec "${prefix[@]}" systemd-run --quiet --wait --pipe --collect \
        --unit="roc-public-$(date +%Y%m%d-%H%M%S)-$$" \
        --uid="$build_uid" --gid="$build_gid" \
        -p CPUQuota=100% -p AllowedCPUs=0,1 -p MemoryMax=6G \
        -p MemorySwapMax=512M -p Nice=19 -p IOSchedulingClass=idle \
        -p RuntimeMaxSec=3h -p KillMode=control-group \
        /usr/bin/taskset -c 0,1 /usr/bin/nice -n 19 /bin/bash "$(realpath "$0")" --inside "$@"
fi
shift
exec 9>/tmp/h700-android10-low-pressure.lock
flock -n 9 || { echo 'Another H700 build or packaging task is active' >&2; exit 2; }
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 GOMAXPROCS=1
export GOGC=10 JAVA_TOOL_OPTIONS=-Xmx2048m NINJA_ARGS=-j1 MAKEFLAGS=-j1
exec "$@"
