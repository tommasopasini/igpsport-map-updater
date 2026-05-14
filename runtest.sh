#!/bin/bash
# Wrapper around run.sh for BiNavi Air alignment investigation trials.
# Sets all runtime knobs in one place, writes a timestamped log under tmp/trials/,
# and (optionally) rebuilds only specific tiles by deleting their output files first.
#
# See INVESTIGATION.md for the current hypothesis and what each trial is testing.

set -u
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# =============================================================================
# EDIT ME PER TRIAL
# =============================================================================

# Short label for this trial. Becomes part of the log filename. No spaces.
TRIAL_LABEL="${TRIAL_LABEL:-h3b-stock-bbox}"

# Free-form notes recorded in the log header.
TRIAL_NOTES="${TRIAL_NOTES:-H3(b): --bounding-box inherits stock map bbox (10.360/12.500/45.655/47.110 for IT17). Writer 0.27.0, osmium pre-clip.}"

# Maps directory passed to run.sh. The IT17 sample lives in input/.
MAPS_DIR="${MAPS_DIR:-input}"

# Tiles to force-rebuild this trial (deleted from output/ before the run).
# Resume mode is on, so any other tile in output/ will be skipped.
# Use the canonical generated filename (no trailing underscore).
TRIAL_RM_TILES=(
    "output/IT17002605103CB27X01D01C.map"
)

# Pass --resume to run.sh (recommended: skips the 5 other tiles).
USE_RESUME="${USE_RESUME:-1}"

# Run header-dump comparison against the stock map after a successful build.
COMPARE_AFTER="${COMPARE_AFTER:-1}"
STOCK_MAP="${STOCK_MAP:-input/IT17002604203CB27X01D01C.map}"
GENERATED_MAP="${GENERATED_MAP:-output/IT17002605103CB27X01D01C.map}"

# =============================================================================
# Mapsforge / Java runtime knobs (exported to script.sh)
# =============================================================================

# auto | ram | hd
export MAP_WRITER_TYPE="${MAP_WRITER_TYPE:-auto}"

# Allow auto mode to fall back to hd writer if ram OOMs. Empty = disabled.
export MAP_ALLOW_HD_FALLBACK="${MAP_ALLOW_HD_FALLBACK:-}"

# Threads for mapfile-writer tile-write phase. Empty = auto.
# Note (from INVESTIGATION.md): only the write phase parallelises; read/clip
# are single-threaded, so threads > cores wastes nothing but also won't make
# the big single-thread phase faster.
export MAP_WRITER_THREADS="${MAP_WRITER_THREADS:-}"

# Java heap. Empty = auto (sized by script.sh from PBF size + RAM).
export JAVA_XMS="${JAVA_XMS:-}"
export JAVA_XMX="${JAVA_XMX:-}"

# Java tmpdir (script.sh defaults to ./tmp).
export JAVA_TMP_DIR="${JAVA_TMP_DIR:-$SCRIPT_DIR/tmp}"

# =============================================================================
# Logging setup
# =============================================================================

TS="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="$SCRIPT_DIR/tmp/trials"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/${TS}-${TRIAL_LABEL}.log"

# Write a structured header so old logs are self-describing.
{
    echo "===================================================================="
    echo "TRIAL:    $TRIAL_LABEL"
    echo "WHEN:     $(date -Is)"
    echo "HOST:     $(hostname)"
    echo "CWD:      $SCRIPT_DIR"
    echo "GIT HEAD: $(git rev-parse --short HEAD 2>/dev/null || echo n/a)"
    echo "GIT DIRTY:"
    git status --porcelain 2>/dev/null | sed 's/^/  /'
    echo "NOTES:    $TRIAL_NOTES"
    echo "--------------------------------------------------------------------"
    echo "MAPS_DIR:               $MAPS_DIR"
    echo "USE_RESUME:             $USE_RESUME"
    echo "MAP_WRITER_TYPE:        $MAP_WRITER_TYPE"
    echo "MAP_ALLOW_HD_FALLBACK:  $MAP_ALLOW_HD_FALLBACK"
    echo "MAP_WRITER_THREADS:     ${MAP_WRITER_THREADS:-auto}"
    echo "JAVA_XMS / JAVA_XMX:    ${JAVA_XMS:-auto} / ${JAVA_XMX:-auto}"
    echo "JAVA_TMP_DIR:           $JAVA_TMP_DIR"
    echo "TRIAL_RM_TILES:"
    for t in "${TRIAL_RM_TILES[@]}"; do echo "  $t"; done
    echo "===================================================================="
    echo
} | tee "$LOG_FILE"

# =============================================================================
# Pre-run: remove targeted tiles so resume mode rebuilds them
# =============================================================================

for tile in "${TRIAL_RM_TILES[@]}"; do
    if [ -f "$tile" ]; then
        echo "Removing $tile (force rebuild)" | tee -a "$LOG_FILE"
        rm -f "$tile"
    else
        echo "Skip remove (absent): $tile" | tee -a "$LOG_FILE"
    fi
done
echo | tee -a "$LOG_FILE"

# =============================================================================
# Run
# =============================================================================

run_args=("$MAPS_DIR")
[ "$USE_RESUME" = "1" ] && run_args+=(--resume)

start_epoch=$SECONDS
set +e
./run.sh "${run_args[@]}" 2>&1 | tee -a "$LOG_FILE"
run_status=${PIPESTATUS[0]}
set -e
duration=$(( SECONDS - start_epoch ))

{
    echo
    echo "--------------------------------------------------------------------"
    printf "EXIT:     %d\n" "$run_status"
    printf "DURATION: %dm%02ds\n" $((duration/60)) $((duration%60))
    echo "--------------------------------------------------------------------"
} | tee -a "$LOG_FILE"

# =============================================================================
# Post-run: header comparison
# =============================================================================

if [ "$COMPARE_AFTER" = "1" ] && [ "$run_status" -eq 0 ] \
        && [ -f "$STOCK_MAP" ] && [ -f "$GENERATED_MAP" ] \
        && [ -f "$SCRIPT_DIR/misc/dump_mapheader.py" ]; then
    {
        echo
        echo "===== HEADER COMPARE: $STOCK_MAP  vs  $GENERATED_MAP ====="
        python3 $SCRIPT_DIR/misc/dump_mapheader.py "$STOCK_MAP" "$GENERATED_MAP" || true
    } | tee -a "$LOG_FILE"
fi

echo
echo "Log written to: $LOG_FILE"
exit "$run_status"
