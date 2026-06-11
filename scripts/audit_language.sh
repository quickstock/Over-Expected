#!/bin/sh
# Banned-language audit over all site source + html.
# Causal/officiating-blame phrasings are banned; negations of "referee bias"
# (e.g. "does not prove referee bias") are explicitly allowed.
cd "$(dirname "$0")/../site" || exit 1

echo "== hard-banned phrases (must be empty) =="
grep -rinE "whistle favors|whistle-favors|robbed|bad whistle|officiating advantage|refs love|refs hate|ref bias" \
  src index.html public/data.json 2>/dev/null | grep -vE "does not prove|doesn't prove|cannot prove|not isolate"
HARD=$?

echo "== every mention of bias/ref/officiat (manual review) =="
grep -rinE "bias|referee|officiat" src index.html 2>/dev/null

if [ $HARD -eq 0 ]; then
  echo "AUDIT: FAIL (hard-banned phrase found)"
  exit 1
fi
echo "AUDIT: no hard-banned phrases"
