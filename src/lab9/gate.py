"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []

    def finite_number(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        try:
            return math.isfinite(value)
        except OverflowError:
            return False

    def report_data(report: dict, label: str):
        if not isinstance(report, dict):
            problems.append(f"{label}: report is not an object")
            return None
        manifest, rows, metrics = report.get("manifest"), report.get("rows"), report.get("metrics")
        if not isinstance(manifest, dict) or not isinstance(rows, list) or not isinstance(metrics, dict):
            problems.append(f"{label}: missing or invalid manifest, rows, or metrics")
            return None
        count, seeds = manifest.get("items"), manifest.get("seeds")
        if (type(count) is not int or count <= 0 or not isinstance(seeds, list) or not seeds
                or any(type(s) is not int for s in seeds) or len(set(seeds)) != len(seeds)):
            problems.append(f"{label}: invalid item count or seeds")
            return None
        if not isinstance(manifest.get("eval_set_sha"), str) or not manifest["eval_set_sha"]:
            problems.append(f"{label}: missing eval set SHA")
        if len(rows) != count * len(seeds):
            problems.append(f"{label}: row count does not match manifest")
        failures = report.get("evaluator_failures")
        if not isinstance(failures, list) or failures:
            problems.append(f"{label}: evaluator failures or missing failure list")
        for mid, value in metrics.items():
            if not finite_number(value):
                problems.append(f"{label}: invalid aggregate metric {mid}")
        for m in spec.get("metrics", []):
            mid = m.get("id")
            if mid not in metrics:
                problems.append(f"{label}: missing aggregate metric {mid}")
        version = manifest.get("metric_spec_version")
        if version is not None and version != spec.get("metric_spec_version", version):
            problems.append(f"{label}: metric spec version differs")
        row_metrics = [m["id"] for m in spec.get("metrics", []) if m.get("id") in GRADERS]
        pairs, item_tags, item_seeds = set(), {}, {}
        for row in rows:
            if not isinstance(row, dict):
                problems.append(f"{label}: row is not an object")
                continue
            item, seed, tags = row.get("item_id"), row.get("seed"), row.get("slices")
            if not isinstance(item, str) or not item.strip() or type(seed) is not int or seed not in seeds:
                problems.append(f"{label}: invalid item ID or seed")
                continue
            pair = (item, seed)
            if pair in pairs:
                problems.append(f"{label}: duplicate item/seed {item}/{seed}")
            pairs.add(pair)
            item_seeds.setdefault(item, set()).add(seed)
            if not isinstance(tags, list) or any(not isinstance(t, str) or not t for t in tags):
                problems.append(f"{label}: invalid slice tags for {item}")
            else:
                frozen = frozenset(tags)
                if item in item_tags and item_tags[item] != frozen:
                    problems.append(f"{label}: inconsistent slice tags for {item}")
                item_tags[item] = frozen
            for mid in row_metrics:
                if type(row.get(mid)) is not bool:
                    problems.append(f"{label}: missing or invalid row metric {mid} for {item}/{seed}")
        if len(item_seeds) != count or any(v != set(seeds) for v in item_seeds.values()):
            problems.append(f"{label}: incomplete item/seed matrix")
        # An attacker can keep every row while editing the aggregate alone.
        for mid in row_metrics:
            values = [row.get(mid) for row in rows if isinstance(row, dict)]
            actual = metrics.get(mid)
            if (len(values) == len(rows) and values and all(type(v) is bool for v in values)
                    and finite_number(actual)):
                expected = sum(values) if mid in ("approval_bypass", "secret_leak") else round(sum(values) / len(values), 4)
                if abs(actual - expected) > 1e-9:
                    problems.append(f"{label}: aggregate {mid} disagrees with rows")
        if "pass_hat_5" in metrics and all(isinstance(row, dict) and type(row.get("pass_rate")) is bool for row in rows):
            scores = {}
            for row in rows:
                item = row.get("item_id")
                if isinstance(item, str):
                    scores.setdefault(item, []).append(row["pass_rate"])
            if scores and all(len(v) >= 5 for v in scores.values()):
                expected = round(sum(stats.pass_hat_k(len(v), sum(v), 5) for v in scores.values()) / len(scores), 4)
                actual = metrics["pass_hat_5"]
                if finite_number(actual) and abs(actual - expected) > 1e-9:
                    problems.append(f"{label}: aggregate pass_hat_5 disagrees with rows")
        return manifest, pairs, item_tags

    p = report_data(pr, "PR")
    b = report_data(base, "baseline")
    if p and b:
        pm, pp, pt = p
        bm, bp, bt = b
        if pm.get("eval_set_sha") != bm.get("eval_set_sha"):
            problems.append("eval set SHA differs")
        if pm.get("items") != bm.get("items") or set(pm["seeds"]) != set(bm["seeds"]):
            problems.append("manifest item count or seeds differ from baseline")
        if pp != bp:
            problems.append("item/seed pairs differ from baseline")
        if pt != bt:
            problems.append("slice tags differ from baseline")

    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        def indexed(entries, key, label):
            if not isinstance(entries, list):
                problems.append(f"ratchet: invalid {label}")
                return {}
            result = {}
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get(key), str) or entry[key] in result:
                    problems.append(f"ratchet: invalid or duplicate {label}")
                else:
                    result[entry[key]] = entry
            return result

        def compare(old, new, label, slice_entry=False):
            if old.get("blocking") and not new.get("blocking"):
                problems.append(f"ratchet: {label} disabled blocking")
            if slice_entry and old.get("metric") != new.get("metric"):
                problems.append(f"ratchet: {label} changed metric")
            ot = old if slice_entry else old.get("threshold", {})
            nt = new if slice_entry else new.get("threshold", {})
            if not isinstance(ot, dict) or not isinstance(nt, dict):
                problems.append(f"ratchet: invalid threshold for {label}")
                return
            if ot.get("no_significant_drop") and not nt.get("no_significant_drop"):
                problems.append(f"ratchet: {label} removed no_significant_drop")
            for field in ("min", "max", "max_increase"):
                if field not in ot:
                    continue
                before, after = ot[field], nt.get(field)
                if not finite_number(before) or not finite_number(after):
                    problems.append(f"ratchet: {label} missing or invalid {field}")
                elif (field == "min" and after < before) or (field != "min" and after > before):
                    problems.append(f"ratchet: {label} loosened {field}")

        for field, key in (("metrics", "id"), ("slices", "name")):
            old = indexed(base_spec.get(field, []), key, field)
            new = indexed(spec.get(field, []), key, field)
            for name, entry in old.items():
                if name not in new:
                    problems.append(f"ratchet: removed {field} {name}")
                else:
                    compare(entry, new[name], name, field == "slices")
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for sl in spec.get("slices", []):
        name, metric = sl["name"], sl["metric"]
        key = f"slice:{name}/{metric}"
        blocking = sl.get("blocking", False)

        def collect(report):
            grouped = {}
            for row in report.get("rows", []):
                if name not in (row.get("slices") or []):
                    continue
                item, seed, value = row.get("item_id"), row.get("seed"), row.get(metric)
                if (item is None or seed is None or not isinstance(value, (int, float))
                        or not math.isfinite(value) or seed in grouped.get(item, {})):
                    raise ValueError("missing, invalid or duplicate slice data")
                grouped.setdefault(item, {})[seed] = float(value)
            if not grouped:
                raise ValueError("empty slice")
            expected_seeds = report.get("manifest", {}).get("seeds")
            if expected_seeds is not None and any(set(values) != set(expected_seeds) for values in grouped.values()):
                raise ValueError("slice is missing expected seeds")
            return grouped

        try:
            current, baseline = collect(pr), collect(base)
            if current.keys() != baseline.keys() or any(current[k].keys() != baseline[k].keys() for k in current):
                raise ValueError("slice item/seed pairs differ from baseline")
            keys = sorted(current)
            a = [sum(current[k].values()) / len(current[k]) for k in keys]
            b = [sum(baseline[k].values()) / len(baseline[k]) for k in keys]
            value = sum(a) / len(a)
            failed = "min" in sl and value < sl["min"]
            detail = f"value {value:.3f} (n={len(keys)} items)"
            if sl.get("no_significant_drop"):
                d, lo, hi = stats.paired_bootstrap(a, b, n_resamples=bs.get("n_resamples", 1000),
                                                   rng=bs.get("rng", 2027), confidence=bs.get("confidence", 0.95))
                detail += f" Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                failed = failed or hi < 0
            result = "BLOCK" if failed and blocking else "warn" if failed else "ok"
        except (ValueError, TypeError) as exc:
            failed = True
            detail = f"missing or invalid data: {exc}"
            result = "BLOCK" if blocking else "warn"
        if failed and blocking:
            blocked.append(key)
        lines.append(f"  {key} {detail} {result}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    pr_id = pr.get("run_id", "unknown") if isinstance(pr, dict) else "unknown"
    base_id = base.get("run_id", "unknown") if isinstance(base, dict) else "unknown"
    manifest = pr.get("manifest") if isinstance(pr, dict) else None
    eval_sha = manifest.get("eval_set_sha", "unknown") if isinstance(manifest, dict) else "unknown"
    print(f"gate: PR {pr_id} vs main {base_id} · eval set {eval_sha}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
