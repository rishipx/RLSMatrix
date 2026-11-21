#!/usr/bin/env bash
# Runs one RLSMatrix campaign for the GitHub Action and publishes the report.
# Inputs arrive as INPUT_* environment variables, never interpolated into code.
set -uo pipefail

: "${INPUT_BOOTSTRAP:?bootstrap is required}"
: "${INPUT_MANIFEST:?manifest is required}"

report="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/rlsmatrix-report.md"
rm -f "$report"

args=(
  run
  --bootstrap "$INPUT_BOOTSTRAP"
  --manifest "$INPUT_MANIFEST"
  --operators "${INPUT_OPERATORS:-core}"
  --workers "${INPUT_WORKERS:-4}"
  --format markdown
  --output "$report"
  --quiet
)
[ -n "${INPUT_MIN_SCORE:-}" ] && args+=(--min-score "$INPUT_MIN_SCORE")
[ "${INPUT_EXCLUDE_EQUIVALENT:-false}" = "true" ] && args+=(--exclude-equivalent)
[ "${INPUT_ALLOW_ERRORS:-false}" = "true" ] && args+=(--allow-errors)

rlsmatrix "${args[@]}"
code=$?

if [ -f "$report" ]; then
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    cat "$report" >> "$GITHUB_STEP_SUMMARY"
  else
    cat "$report"
  fi
  score="$(sed -n 's/^\*\*Mutation score: \([0-9.]*\)%\*\*.*/\1/p' "$report" | head -n 1)"
  if [ -n "$score" ] && [ -n "${GITHUB_OUTPUT:-}" ]; then
    echo "score=$score" >> "$GITHUB_OUTPUT"
  fi
fi

exit "$code"
