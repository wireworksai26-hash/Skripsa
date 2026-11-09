import math

import pytest

from app.services import stats


def close(a, b, tol=1e-3):
    return abs(a - b) <= tol


def test_t_pvalues_against_known_values():
    assert close(stats.t_two_sided_p(2.228139, 10), 0.05, 1e-4)  # nilai kritis t(10) dua sisi
    assert close(stats.t_two_sided_p(2.0, 10), 0.0734, 1e-3)
    assert close(stats.t_two_sided_p(2.0, 8), 0.0805, 1e-3)
    assert close(stats.t_two_sided_p(0.0, 5), 1.0, 1e-9)
    assert close(stats.t_two_sided_p(12.706205, 1), 0.05, 1e-4)  # df=1 (Cauchy)
    assert stats.t_two_sided_p(40, 30) < 1e-20


def test_f_pvalues_against_known_values():
    assert close(stats.f_upper_p(3.354131, 2, 27), 0.05, 1e-4)  # nilai kritis F(2,27)
    assert close(stats.f_upper_p(4.0, 1, 10), stats.t_two_sided_p(2.0, 10), 1e-9), "F(1,n) = t^2"
    assert close(stats.f_upper_p(3.0, 2, 6), 0.1250, 1e-3)
    assert stats.f_upper_p(0.0, 2, 6) == 1.0


def test_describe_sample_sd_and_median():
    d = stats.describe([2, 4, 4, 4, 5, 5, 7, 9])
    assert d["n"] == 8 and close(d["mean"], 5.0, 1e-9)
    assert close(d["sd"], math.sqrt(32 / 7), 1e-9), "SD sampel (n-1), bukan populasi"
    assert d["median"] == 4.5 and d["min"] == 2 and d["max"] == 9


def test_welch_matches_hand_calculation():
    r = stats.welch_t([1, 2, 3, 4, 5], [3, 4, 5, 6, 7])
    assert close(r["statistic"], -2.0, 1e-9) and close(r["df"], 8.0, 1e-9)
    assert close(r["p"], 0.0805, 1e-3) and close(r["mean_diff"], -2.0, 1e-9)


def test_welch_unequal_variance_df_is_fractional():
    r = stats.welch_t([10, 11, 12, 13, 14, 15], [10, 20, 30])
    assert 2 < r["df"] < 7 and 0 <= r["p"] <= 1


def test_paired_t():
    r = stats.paired_t([1, 2, 3, 4], [2, 3, 3, 6])
    assert close(abs(r["statistic"]), 2.449, 1e-3) and r["df"] == 3
    assert close(r["p"], 0.0917, 1e-3)
    with pytest.raises(ValueError, match="jumlah data yang sama"):
        stats.paired_t([1, 2], [1, 2, 3])


def test_anova_hand_calculation():
    r = stats.one_way_anova([[1, 2, 3], [2, 3, 4], [3, 4, 5]])
    assert close(r["statistic"], 3.0, 1e-9) and (r["df"], r["df2"]) == (2, 6)
    assert close(r["p"], 0.1250, 1e-3) and close(r["effect_size"], 0.5, 1e-9)


def test_zero_variance_is_reported_not_crashed():
    with pytest.raises(ValueError, match="SD = 0"):
        stats.welch_t([5, 5, 5], [5, 5, 5])
    with pytest.raises(ValueError, match="SSW = 0"):
        stats.one_way_anova([[1, 1], [2, 2], [3, 3]])


def test_analyze_two_groups_reports_in_indonesian():
    out = stats.analyze({"Kontrol": [60, 62, 65, 61, 63], "Eksperimen": [75, 78, 72, 80, 77]})
    assert out["test"]["test"] == "welch_t" and out["test"]["significant"] is True
    assert out["test"]["report"].startswith("t(") and "p < 0,001" in out["test"]["report"] or "p = 0," in out["test"]["report"]
    assert "terdapat perbedaan rerata yang signifikan" in out["interpretation"]
    assert [d["group"] for d in out["descriptives"]] == ["Kontrol", "Eksperimen"]


def test_analyze_three_groups_uses_anova_and_nonsignificant_wording():
    out = stats.analyze({"A": [1, 2, 3], "B": [2, 3, 4], "C": [3, 4, 5]})
    assert out["test"]["test"] == "anova" and out["test"]["significant"] is False
    assert "tidak terdapat perbedaan" in out["interpretation"]
    assert out["test"]["report"].startswith("F(2, 6) = 3,00")


def test_analyze_paired_flag_and_edge_cases():
    out = stats.analyze({"Pre": [50, 55, 60, 65], "Post": [58, 60, 70, 75]}, paired=True)
    assert out["test"]["test"] == "paired_t"
    solo = stats.analyze({"Saja": [1, 2, 3]})
    assert solo["test"] is None and "deskriptif" in solo["interpretation"]
    with pytest.raises(ValueError, match="minimal 2 data"):
        stats.analyze({"A": [1], "B": [1, 2]})
    with pytest.raises(ValueError, match="tidak ada data"):
        stats.analyze({"A": []})
    ignored = stats.analyze({"A": [1, 2, float("nan"), 3], "B": [2, 3, 4]})
    assert ignored["descriptives"][0]["n"] == 3, "NaN dibuang"
