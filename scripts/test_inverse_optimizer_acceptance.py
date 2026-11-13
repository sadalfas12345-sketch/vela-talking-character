"""Regression tests for monotone inverse-force update acceptance."""
from pathlib import Path
import importlib.util

module_path = Path(__file__).with_name("optimize_reference_forces.py")
spec = importlib.util.spec_from_file_location("inverse_optimizer", module_path)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def check(condition, message):
    if not condition:
        raise AssertionError(message)


baseline = {
    "imageObjective": 1.0,
    "forceBalance": 0.1,
    "finite": True,
    "orientationReversals": 12,
    "collapses": 0,
}

ok, reason = module.candidate_is_acceptable(baseline, {**baseline, "imageObjective": 1.1})
check(not ok and reason == "image_objective_not_improved", "deteriorating objective must be rejected")

ok, reason = module.candidate_is_acceptable(baseline, {**baseline, "imageObjective": 0.9, "orientationReversals": 13})
check(not ok and reason == "orientation_reversals_increased", "geometry regression must be rejected")

ok, reason = module.candidate_is_acceptable(baseline, {**baseline, "imageObjective": 0.9, "forceBalance": 0.2})
check(not ok and reason == "force_balance_worsened", "force-balance regression must be rejected")

ok, reason = module.candidate_is_acceptable(baseline, {**baseline, "imageObjective": 0.9})
check(ok and reason == "accepted", "genuinely improving candidate should be accepted")

alpha_zero = {"alpha": 0.0, "error": 1.0, "imageObjective": 1.0, "forceBalance": 0.1, "finite": True, "orientationReversals": 12, "collapses": 0}
worse = {"alpha": 1.0, "error": 1.1, "imageObjective": 1.1, "forceBalance": 0.2, "finite": True, "orientationReversals": 13, "collapses": 0}
chosen, reasons = module.choose_accepted_candidate(baseline, [alpha_zero, worse])
check(chosen["alpha"] == 0.0 and reasons, "alpha zero must remain when every tested update is worse")

print("inverse optimizer acceptance tests: PASS")
