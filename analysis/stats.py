"""Statistical tests and models used by the analysis. Pure functions: DataFrames in, results out.

Why these methods:
- Scores are not normally distributed and have outliers, so the tests use ranks (Spearman,
  Kruskal-Wallis) instead of means. Ranks only care about order: 9.3 beats 9.1 the same
  way 6.0 beats 5.8.
- With thousands of titles, almost every test comes out "significant". So every test also
  reports an effect size: how much of the variation in score ranks the factor explains.
- Many tests run at once, so p-values are adjusted with Benjamini-Hochberg.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import KFold, cross_val_score
from statsmodels.stats.multitest import multipletests

SEED = 42
BOOTSTRAP_SAMPLES = 1000

# Fields measured after an anime airs. They must never be used to explain score (D-007).
OUTCOMES = frozenset({"score", "scored_by", "members", "favorites", "rank", "popularity"})


def effect_size_label(effect: float) -> str:
    """Name an effect size (share of rank variation explained) with common rule-of-thumb cutoffs."""
    if effect < 0.01:
        return "negligible"
    if effect < 0.06:
        return "small"
    if effect < 0.14:
        return "medium"
    return "large"


def spearman_test(x: pd.Series, y: pd.Series) -> dict[str, float]:
    """Spearman rank correlation of x and y, ignoring rows where either is missing.

    rho squared is the effect size: the share of variation in y's ranks that x's ranks explain.
    """
    pairs = pd.DataFrame({"x": x, "y": y}).dropna()
    rho, p_value = stats.spearmanr(pairs["x"], pairs["y"])
    return {
        "n": len(pairs),
        "statistic": float(rho),
        "effect_size": float(rho**2),
        "p_value": float(p_value),
    }


def bootstrap_median_ci(
    values: np.ndarray, rng: np.random.Generator, samples: int = BOOTSTRAP_SAMPLES
) -> tuple[float, float]:
    """95% confidence interval for the median, by resampling the values with replacement.

    Each resample is a "what if we had drawn a slightly different set of titles". The middle
    95% of the resampled medians is the interval.
    """
    resamples = rng.choice(values, size=(samples, len(values)), replace=True)
    medians = np.median(resamples, axis=1)
    low, high = np.percentile(medians, [2.5, 97.5])
    return float(low), float(high)


def group_medians(
    df: pd.DataFrame, group_col: str, rng: np.random.Generator, target: str = "score"
) -> pd.DataFrame:
    """One row per group: n, median target, and the median's bootstrap 95% interval."""
    rows = []
    for group, values in df.groupby(group_col, sort=True)[target]:
        low, high = bootstrap_median_ci(values.to_numpy(), rng)
        rows.append(
            {
                "group": group,
                "n": len(values),
                "median": float(values.median()),
                "ci_low": low,
                "ci_high": high,
            }
        )
    return pd.DataFrame(rows).sort_values("median", ascending=False, ignore_index=True)


def kruskal_test(df: pd.DataFrame, group_col: str, target: str = "score") -> dict[str, float]:
    """Kruskal-Wallis test: do the groups' score distributions differ?

    The effect size is epsilon squared, H / (n - 1): the share of variation in score ranks
    explained by which group a title is in. It is on the same 0-to-1 scale as rho squared.
    """
    samples = [values.to_numpy() for _, values in df.groupby(group_col)[target]]
    h, p_value = stats.kruskal(*samples)
    n = sum(len(s) for s in samples)
    return {
        "n": n,
        "statistic": float(h),
        "effect_size": float(h / (n - 1)),
        "p_value": float(p_value),
    }


def adjust_pvalues(p_values: pd.Series) -> pd.Series:
    """Benjamini-Hochberg adjustment: controls the share of false positives among the hits.

    Run 50 tests at p < 0.05 and about 2 or 3 come out "significant" by luck alone. The
    adjusted p-values account for how many tests ran together.
    """
    _, adjusted, _, _ = multipletests(p_values.to_numpy(), method="fdr_bh")
    return pd.Series(adjusted, index=p_values.index)


def check_no_outcomes(columns: list[str]) -> None:
    """Fail loudly if an outcome field (or a column built from one) is about to be a predictor."""
    # "type=TV" is built from type; "log1p(members)" would be built from members.
    bases = {c: c.split("=")[0].removeprefix("log1p(").removesuffix(")") for c in columns}
    leaked = [c for c, base in bases.items() if base in OUTCOMES]
    if leaked:
        raise ValueError(f"Outcome fields cannot be predictors: {leaked}")


def design_matrix(
    df: pd.DataFrame, numeric: list[str], categorical: list[str], indicators: list[str]
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Turn factors into the all-numbers table a regression needs.

    Each categorical column becomes one 0/1 column per category, except its most common
    category. That one is the reference: every other category's coefficient is read as
    "compared with the reference". Dropping it is required, because the columns of a
    category would otherwise always add up to 1 and the model could not be solved.
    Returns the matrix and the reference category of each categorical column.
    """
    check_no_outcomes(numeric + categorical + indicators)
    parts = [df[numeric].astype(float), df[indicators].astype(float)]
    references: dict[str, str] = {}
    for col in categorical:
        reference = df[col].value_counts().idxmax()
        references[col] = str(reference)
        dummies = pd.get_dummies(df[col], prefix=col, prefix_sep="=", dtype=float)
        parts.append(dummies.drop(columns=f"{col}={reference}"))
    return pd.concat(parts, axis=1), references


def fit_ols(x: pd.DataFrame, y: pd.Series) -> tuple[pd.DataFrame, dict[str, float]]:
    """Ordinary least squares with HC3 robust standard errors.

    HC3 standard errors stay honest when the spread of scores differs between groups (it
    does: movies vary more than TV series), which plain standard errors assume away.
    """
    model = sm.OLS(y.astype(float), sm.add_constant(x)).fit(cov_type="HC3")
    ci = model.conf_int()
    coefficients = pd.DataFrame(
        {
            "term": model.params.index,
            "coef": model.params.to_numpy(),
            "std_err": model.bse.to_numpy(),
            "ci_low": ci[0].to_numpy(),
            "ci_high": ci[1].to_numpy(),
            "p_value": model.pvalues.to_numpy(),
        }
    )
    fit = {"n": int(model.nobs), "r2": float(model.rsquared), "adj_r2": float(model.rsquared_adj)}
    return coefficients, fit


def cross_validated_r2(x: pd.DataFrame, y: pd.Series, folds: int = 5) -> dict[str, float]:
    """R squared on held-out data, for the model and for always predicting the mean.

    In-sample R squared flatters a model. Here the data is split into 5 parts; the model
    learns from 4 and is scored on the 5th, five times. The baseline shows what "no
    information at all" scores, which is about 0.
    """
    splitter = KFold(n_splits=folds, shuffle=True, random_state=SEED)
    model = cross_val_score(LinearRegression(), x, y, cv=splitter, scoring="r2")
    baseline = cross_val_score(DummyRegressor(), x, y, cv=splitter, scoring="r2")
    return {
        "model_r2": float(model.mean()),
        "model_r2_std": float(model.std()),
        "baseline_r2": float(baseline.mean()),
    }
