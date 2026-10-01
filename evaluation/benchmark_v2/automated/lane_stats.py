"""Per-lane statistics: a Wilson interval, two exact one-sided sign tests, Holm's step-down and the decision rule.

Every constant of the decision rule is defined here and nowhere else. Standard library only. The name is not
`statistics` because that would shadow the standard library module.
"""

import math

# Two-sided 90% normal quantile (the 95th percentile of the standard normal distribution).
Z_90 = 1.6448536269514722
# Under the null a lane is a tie: the candidate wins half of the decisive documents.
NULL_PROPORTION = 0.5
# Smallest mean net preference, on the scale -1 to 1, that a recommendation needs.
MIN_EFFECT = 0.15
# Largest one-sided sign-test p-value, in the direction being claimed, that a recommendation accepts. At 0.05 no lane
# with fewer than five decisive documents can be decisive: the smallest p-value at n = 4 is 0.0625.
ALPHA_ONE_SIDED = 0.05


def _check_counts(wins, n):
    for name, value in (("wins", wins), ("n", n)):
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a nonnegative integer")
    if wins > n:
        raise ValueError("wins cannot exceed n")


def wilson_interval(wins, n):
    """Two-sided 90% Wilson score interval for `wins` successes out of `n` trials; [0, 1] when n is 0."""
    _check_counts(wins, n)
    if n == 0:
        return 0.0, 1.0
    p = wins / n
    z2 = Z_90 * Z_90
    scale = 1 + z2 / n
    center = (p + z2 / (2 * n)) / scale
    half = Z_90 * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / scale
    # At p of 0 or 1 one bound is exactly 0 or 1; rounding must not move it.
    lower = 0.0 if wins == 0 else max(0.0, center - half)
    upper = 1.0 if wins == n else min(1.0, center + half)
    return lower, upper


def sign_test_p_candidate(wins, n):
    """One-sided exact binomial p-value for the candidate: P(X >= wins) with X ~ Binomial(n, 0.5), the chance of at
    least `wins` out of `n` decisive documents when each is a fair coin. It is 1 when n is 0."""
    _check_counts(wins, n)
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def sign_test_p_baseline(wins, n):
    """One-sided exact binomial p-value for the baseline: P(X <= wins) with X ~ Binomial(n, 0.5), the chance of at
    most `wins` out of `n` decisive documents when each is a fair coin. It is 1 when n is 0."""
    _check_counts(wins, n)
    return sum(math.comb(n, k) for k in range(0, wins + 1)) / 2 ** n


def holm(p_values, alpha):
    """Holm-Bonferroni step-down. Returns, in input order, whether each hypothesis is rejected.

    Sort the p-values ascending; the i-th smallest (from 0) is rejected while it is at most alpha / (m - i), and the
    walk stops at the first one that is not. A caller that compares lanes together passes, for each lane, the p-value
    of the direction being claimed: `sign_test_p_candidate` for a claim that the candidate is better and
    `sign_test_p_baseline` for a claim that the baseline is better, never the other direction's value."""
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)) or not 0 < alpha <= 1:
        raise ValueError("alpha must be a number above 0 and at most 1")
    values = list(p_values)
    for p in values:
        if isinstance(p, bool) or not isinstance(p, (int, float)) or not 0 <= p <= 1:
            raise ValueError("each p-value must be a number from 0 to 1")
    rejected = [False] * len(values)
    for rank, index in enumerate(sorted(range(len(values)), key=values.__getitem__)):
        if values[index] > alpha / (len(values) - rank):
            break
        rejected[index] = True
    return rejected


def lane_statistics(values):
    """The statistics of one lane, from its per-document net preferences (each in [-1, 1], 0 for no preference)."""
    wins = sum(1 for value in values if value > 0)
    losses = sum(1 for value in values if value < 0)
    decisive = wins + losses
    lower, upper = wilson_interval(wins, decisive)
    return {"decisive": decisive, "wins": wins, "losses": losses,
            "proportion": wins / decisive if decisive else None,
            "wilson_lower": lower, "wilson_upper": upper,
            "mean": sum(values) / len(values) if values else None,
            "sign_test_p_candidate": sign_test_p_candidate(wins, decisive),
            "sign_test_p_baseline": sign_test_p_baseline(wins, decisive)}


def lane_decision(lower, upper, mean, p_candidate, p_baseline):
    """'candidate' when the interval lies above one half, the mean is at least MIN_EFFECT and the candidate sign-test
    p-value is at most ALPHA_ONE_SIDED; 'baseline' when the interval lies below one half, the mean is at most
    -MIN_EFFECT and the baseline sign-test p-value is at most ALPHA_ONE_SIDED; otherwise 'inconclusive'. Each
    direction reads only its own p-value."""
    if mean is None:
        return "inconclusive"
    if lower > NULL_PROPORTION and mean >= MIN_EFFECT and p_candidate <= ALPHA_ONE_SIDED:
        return "candidate"
    if upper < NULL_PROPORTION and mean <= -MIN_EFFECT and p_baseline <= ALPHA_ONE_SIDED:
        return "baseline"
    return "inconclusive"
