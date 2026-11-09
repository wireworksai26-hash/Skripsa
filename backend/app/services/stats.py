"""Statistik deskriptif dan uji beda rerata untuk Bab IV (tanpa scipy).

p-value dihitung dari fungsi beta tak lengkap terregularisasi (Numerical Recipes, deret pecahan berlanjut):
  - uji t dua sisi  : p = I_{df/(df+t^2)}(df/2, 1/2)
  - ANOVA (F, ekor atas): p = I_{d2/(d2+d1*F)}(d2/2, d1/2)
"""

import math

_EPS = 3e-14
_TINY = 1e-300


def _betacf(a: float, b: float, x: float) -> float:
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = _TINY if abs(d) < _TINY else d
    d = 1.0 / d
    h = d
    for m in range(1, 500):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = _TINY if abs(d) < _TINY else d
        c = 1.0 + aa / c
        c = _TINY if abs(c) < _TINY else c
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = _TINY if abs(d) < _TINY else d
        c = 1.0 + aa / c
        c = _TINY if abs(c) < _TINY else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _EPS:
            break
    return h


def betai(a: float, b: float, x: float) -> float:
    """Fungsi beta tak lengkap terregularisasi I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_front = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    front = math.exp(ln_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_two_sided_p(t: float, df: float) -> float:
    if df <= 0:
        raise ValueError("derajat bebas harus positif")
    return min(1.0, max(0.0, betai(df / 2.0, 0.5, df / (df + t * t))))


def f_upper_p(f: float, d1: float, d2: float) -> float:
    if f <= 0:
        return 1.0
    return min(1.0, max(0.0, betai(d2 / 2.0, d1 / 2.0, d2 / (d2 + d1 * f))))


def describe(values: list[float]) -> dict:
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1) if n > 1 else 0.0
    sd = math.sqrt(var)
    ordered = sorted(values)
    mid = n // 2
    median = ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2
    return {
        "n": n,
        "mean": mean,
        "sd": sd,
        "se": sd / math.sqrt(n) if n else 0.0,
        "min": ordered[0],
        "max": ordered[-1],
        "median": median,
    }


def welch_t(a: list[float], b: list[float]) -> dict:
    da, db = describe(a), describe(b)
    va, vb = da["sd"] ** 2 / da["n"], db["sd"] ** 2 / db["n"]
    if va + vb == 0:
        raise ValueError("kedua kelompok tidak bervariasi (SD = 0); uji t tidak dapat dihitung")
    se = math.sqrt(va + vb)
    t = (da["mean"] - db["mean"]) / se
    df = (va + vb) ** 2 / ((va**2) / (da["n"] - 1) + (vb**2) / (db["n"] - 1))
    pooled = math.sqrt(((da["n"] - 1) * da["sd"] ** 2 + (db["n"] - 1) * db["sd"] ** 2) / (da["n"] + db["n"] - 2))
    return {
        "test": "welch_t",
        "name": "Uji t independen (Welch)",
        "statistic": t,
        "df": df,
        "p": t_two_sided_p(t, df),
        "mean_diff": da["mean"] - db["mean"],
        "effect_size": (da["mean"] - db["mean"]) / pooled if pooled > 0 else None,
        "effect_name": "d Cohen",
    }


def paired_t(a: list[float], b: list[float]) -> dict:
    if len(a) != len(b):
        raise ValueError("uji t berpasangan butuh jumlah data yang sama pada kedua kelompok")
    diffs = [x - y for x, y in zip(a, b)]
    d = describe(diffs)
    if d["sd"] == 0:
        raise ValueError("selisih berpasangan tidak bervariasi (SD = 0); uji t tidak dapat dihitung")
    t = d["mean"] / (d["sd"] / math.sqrt(d["n"]))
    df = d["n"] - 1
    return {
        "test": "paired_t",
        "name": "Uji t berpasangan",
        "statistic": t,
        "df": df,
        "p": t_two_sided_p(t, df),
        "mean_diff": d["mean"],
        "effect_size": d["mean"] / d["sd"],
        "effect_name": "d Cohen (selisih)",
    }


def one_way_anova(groups: list[list[float]]) -> dict:
    k = len(groups)
    n_total = sum(len(g) for g in groups)
    grand = sum(sum(g) for g in groups) / n_total
    ssb = sum(len(g) * (sum(g) / len(g) - grand) ** 2 for g in groups)
    ssw = sum(sum((v - sum(g) / len(g)) ** 2 for v in g) for g in groups)
    d1, d2 = k - 1, n_total - k
    if ssw == 0:
        raise ValueError("semua kelompok tidak bervariasi di dalam kelompok (SSW = 0); ANOVA tidak dapat dihitung")
    f = (ssb / d1) / (ssw / d2)
    return {
        "test": "anova",
        "name": "ANOVA satu arah",
        "statistic": f,
        "df": d1,
        "df2": d2,
        "p": f_upper_p(f, d1, d2),
        "effect_size": ssb / (ssb + ssw),
        "effect_name": "eta kuadrat",
    }


def _fmt(x: float, nd: int = 2) -> str:
    return f"{x:.{nd}f}".replace(".", ",")


def _fmt_p(p: float) -> str:
    return "p < 0,001" if p < 0.001 else f"p = {_fmt(p, 3)}"


def analyze(groups: dict[str, list[float]], paired: bool = False, alpha: float = 0.05) -> dict:
    clean = {
        name: [float(v) for v in vals if v is not None and math.isfinite(float(v))]
        for name, vals in groups.items()
    }
    clean = {k: v for k, v in clean.items() if v}
    if not clean:
        raise ValueError("tidak ada data numerik")
    desc = {name: describe(vals) for name, vals in clean.items()}
    result: dict = {"descriptives": [{"group": n, **d} for n, d in desc.items()], "alpha": alpha, "test": None}

    names = list(clean)
    if len(names) < 2:
        result["interpretation"] = "Hanya satu kelompok, sehingga hanya statistik deskriptif yang dapat disajikan."
        return result
    small = [n for n in names if len(clean[n]) < 2]
    if small:
        raise ValueError(f"kelompok {', '.join(small)} hanya punya 1 data; uji butuh minimal 2 data per kelompok")

    if len(names) == 2:
        a, b = names
        t = paired_t(clean[a], clean[b]) if paired else welch_t(clean[a], clean[b])
        sig = t["p"] < alpha
        df = f"{_fmt(t['df'], 0)}" if paired or float(t["df"]).is_integer() else _fmt(t["df"], 1)
        report = f"t({df}) = {_fmt(t['statistic'])}, {_fmt_p(t['p'])}"
        da, db = desc[a], desc[b]
        t["report"] = report
        t["significant"] = sig
        result["test"] = t
        result["interpretation"] = (
            f"{t['name']} menunjukkan bahwa {'terdapat' if sig else 'tidak terdapat'} perbedaan rerata yang signifikan "
            f"antara {a} (M = {_fmt(da['mean'])}, SD = {_fmt(da['sd'])}) dan {b} (M = {_fmt(db['mean'])}, SD = {_fmt(db['sd'])}), "
            f"{report}, {t['effect_name']} = {_fmt(t['effect_size']) if t['effect_size'] is not None else '-'} "
            f"(taraf signifikansi {_fmt(alpha, 2)})."
        )
        return result

    t = one_way_anova([clean[n] for n in names])
    sig = t["p"] < alpha
    report = f"F({t['df']}, {t['df2']}) = {_fmt(t['statistic'])}, {_fmt_p(t['p'])}"
    t["report"] = report
    t["significant"] = sig
    result["test"] = t
    result["interpretation"] = (
        f"{t['name']} menunjukkan bahwa {'terdapat' if sig else 'tidak terdapat'} perbedaan rerata yang signifikan "
        f"di antara {len(names)} kelompok, {report}, eta kuadrat = {_fmt(t['effect_size'])} "
        f"(taraf signifikansi {_fmt(alpha, 2)})."
        + (" Disarankan uji lanjut (post hoc) untuk mengetahui pasangan kelompok yang berbeda." if sig else "")
    )
    return result
