"""Guard: the per-unit target is never BR-scaled, and the target is never sourced
from basketball-reference season totals.

Failure modes this guards against:
  - Anyone resurrects fix_training_targets.py or fix_leaderboard_fta.py
  - Anyone multiplies the per-shot fta_from_shot by a per-player-season scale factor
  - Anyone sources actual_fta_from_fouls from basketball-reference season totals
  - Anyone adds a "BR" / "basketball_reference" import back to the pipeline

If any of these patterns appear in the source tree, this test FAILS the build.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent

FORBIDDEN_FILES = {
    "deprecated/fix_training_targets.py",
    "deprecated/fix_leaderboard_fta.py",
    "fix_training_targets.py",
    "fix_leaderboard_fta.py",
}

FORBIDDEN_IMPORTS = {
    "basketball_reference",
    "basketball-reference",
}

# Patterns that indicate per-player-season scaling of the per-unit target.
# These have to be re-introduced carefully, if ever — the test makes you
# delete the test instead of reintroducing the pattern.
FORBIDDEN_PATTERNS = [
    (r"actual_fta_from_fouls.*\*\s*scale", "per-player-season scale on actual_fta"),
    (r"pbp_fta.*/\s*actual_fta", "BR-scaling ratio"),
    (r"scale\s*=\s*.*actual_fta\s*/\s*pbp_fta", "BR-scaling ratio assignment"),
    (r"attempted_free_throws", "BR attempted_free_throws import"),
    (r"made_free_throws", "BR made_free_throws import"),
]


def test_no_br_scaling_scripts_present():
    """The corrupt scaling scripts must not exist anywhere in the repo."""
    for rel in FORBIDDEN_FILES:
        path = ROOT / rel
        assert not path.exists(), (
            f"Forbidden file re-introduced: {rel}. "
            f"BR-scaling the per-unit target is not allowed. "
            f"Delete this file."
        )


def test_no_basketball_reference_imports():
    """No code path imports from basketball-reference to source the target."""
    bad = []
    for py in ROOT.rglob("*.py"):
        # Skip this test file and the v2 backup (which preserves the abandoned attempt)
        rel = py.relative_to(ROOT).as_posix()
        if rel.startswith("tests/"):
            continue
        if rel.startswith("_v2_backup/"):
            continue
        if rel == "tests/test_no_br_scaling.py":
            continue
        text = py.read_text(errors="ignore")
        for bad_import in FORBIDDEN_IMPORTS:
            if bad_import in text:
                bad.append(f"{rel}: contains '{bad_import}'")
    assert not bad, "Forbidden BR references found:\n" + "\n".join(bad)


def test_no_per_player_season_scaling_patterns():
    """No code path scales the per-unit target by a per-player-season factor."""
    bad = []
    for py in ROOT.rglob("*.py"):
        rel = py.relative_to(ROOT).as_posix()
        if rel.startswith("tests/"):
            continue
        if rel.startswith("_v2_backup/"):
            continue
        if rel == "tests/test_no_br_scaling.py":
            continue
        text = py.read_text(errors="ignore")
        for pattern, label in FORBIDDEN_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                bad.append(f"{rel}: matches '{label}'")
    assert not bad, "Forbidden BR-scaling patterns found:\n" + "\n".join(bad)


def test_target_column_has_no_fractions():
    """The actual target column (player_season_xfta_poss.actual_fta_from_fouls)
    must be integer-valued when rebuilt under the possession model.

    The legacy v1 FGA-era table (player_season_xfta) is allowed to keep its
    BR-scaled fractional values for historical comparison, but new build paths
    must not write to it.
    """
    import sqlite3
    db = ROOT / "xfta.db"
    if not db.exists():
        return  # No db yet — nothing to check
    conn = sqlite3.connect(db)
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        if "player_season_xfta_poss" not in tables:
            return  # New table not built yet — nothing to check
        # Check that all values are integers
        non_int = conn.execute("""
            SELECT COUNT(*) FROM player_season_xfta_poss
            WHERE actual_fta_from_fouls != CAST(actual_fta_from_fouls AS INTEGER)
               OR actual_fta_from_fouls < 0
        """).fetchone()[0]
        assert non_int == 0, (
            f"player_season_xfta_poss.actual_fta_from_fouls has {non_int} "
            f"non-integer or negative values. Target must be a clean integer count."
        )
    finally:
        conn.close()
