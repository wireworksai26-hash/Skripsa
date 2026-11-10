"""Uji statistik lanjutan untuk data penelitian pengguna: korelasi, regresi, chi-square, normalitas, reliabilitas.

Semuanya dihitung langsung dengan numpy/scipy; tidak ada LLM, sehingga angka tidak mungkin dikarang. Setiap uji
mengembalikan tabel siap masuk Bab IV, kalimat pelaporan gaya APA, dan interpretasi singkat.
"""

import math

import numpy as np
from scipy import stats as sps

KINDS = ("correlation", "regression", "chi_square", "normality", "reliability")

L10N = {
    "id": {
        "sig": "signifikan", "nsig": "tidak signifikan", "var": "Variabel", "coef": "Koefisien", "const": "Konstanta", "item": "Butir",
        "alpha_del": "Alpha jika dihapus", "rtot": "Korelasi butir-total", "total": "Total",
    },
    "en": {
        "sig": "significant", "nsig": "not significant", "var": "Variable", "coef": "Coefficient", "const": "Constant", "item": "Item",
        "alpha_del": "Alpha if deleted", "rtot": "Corrected item-total r", "total": "Total",
    },
}


def _f(x: float, nd: int = 2, lang: str = "id") -> str:
    s = f"{x:.{nd}f}"
    return s if lang == "en" else s.replace(".", ",")


def _p(p: float, lang: str = "id") -> str:
    if p < 0.001:
        return "p < .001" if lang == "en" else "p < 0,001"
    return "p = " + _f(p, 3, lang)


def _numeric(values: list) -> np.ndarray:
    arr = np.array([float(v) for v in values], dtype=float)
    if not np.all(np.isfinite(arr)):
        raise ValueError("Data memuat nilai non-angka")
    return arr


def _pairs(cols: dict[str, list], names: list[str]) -> tuple[list[np.ndarray], int]:
    """Buang baris yang kosong pada kolom mana pun (listwise deletion)."""
    n = min(len(cols[nm]) for nm in names)
    keep = [i for i in range(n) if all(cols[nm][i] is not None and str(cols[nm][i]).strip() != "" for nm in names)]
    return [_numeric([cols[nm][i] for i in keep]) for nm in names], len(keep)


def correlation(cols: dict[str, list], a: str, b: str, alpha: float = 0.05, lang: str = "id") -> dict:
    (x, y), n = _pairs(cols, [a, b])
    if n < 3:
        raise ValueError("Korelasi butuh minimal 3 pasang data")
    if np.std(x) == 0 or np.std(y) == 0:
        raise ValueError("Salah satu variabel tidak bervariasi (semua nilai sama)")
    r, p = sps.pearsonr(x, y)
    rho, p_s = sps.spearmanr(x, y)
    strength = abs(r)
    word = ("sangat lemah", "lemah", "sedang", "kuat", "sangat kuat")[min(4, int(strength / 0.2))] if lang == "id" else ("very weak", "weak", "moderate", "strong", "very strong")[min(4, int(strength / 0.2))]
    direction = ("positif" if r > 0 else "negatif") if lang == "id" else ("positive" if r > 0 else "negative")
    sig = p < alpha
    report = f"r({n - 2}) = {_f(r, 2, lang)}, {_p(p, lang)}"
    if lang == "en":
        interp = f"There is a {word} {direction} correlation between {a} and {b}, {report}, which is {L10N['en']['sig' if sig else 'nsig']} at alpha = {alpha}. Spearman's rho = {_f(rho, 2, lang)} ({_p(p_s, lang)})."
    else:
        interp = f"Terdapat korelasi {direction} yang {word} antara {a} dan {b}, {report}, {L10N['id']['sig' if sig else 'nsig']} pada taraf {_f(alpha, 2)}. Korelasi Spearman rho = {_f(rho, 2)} ({_p(p_s)})."
    cols_ = ["Pearson r", "p", "Spearman rho", "p (Spearman)", "n"]
    return {
        "kind": "correlation", "report": report, "interpretation": interp, "significant": bool(sig),
        "tables": [{"title": f"{'Correlation' if lang == 'en' else 'Korelasi'} {a} – {b}", "columns": cols_, "rows": [[_f(r, 3, lang), _f(p, 3, lang), _f(rho, 3, lang), _f(p_s, 3, lang), str(n)]], "note": "Pearson r; Spearman rho"}],
    }


def regression(cols: dict[str, list], y: str, xs: list[str], alpha: float = 0.05, lang: str = "id") -> dict:
    if not xs or y in xs:
        raise ValueError("Pilih satu variabel terikat (Y) dan minimal satu variabel bebas (X) yang berbeda")
    arrays, n = _pairs(cols, [y] + xs)
    k = len(xs)
    if n <= k + 2:
        raise ValueError(f"Data terlalu sedikit untuk {k} prediktor (butuh lebih dari {k + 2} baris lengkap)")
    yv = arrays[0]
    X = np.column_stack([np.ones(n)] + arrays[1:])
    if np.linalg.matrix_rank(X) < X.shape[1]:
        raise ValueError("Variabel bebas saling bergantung sempurna (multikolinearitas) atau tidak bervariasi")
    beta, *_ = np.linalg.lstsq(X, yv, rcond=None)
    resid = yv - X @ beta
    df_res = n - k - 1
    sse = float(resid @ resid)
    sst = float(((yv - yv.mean()) ** 2).sum())
    if sst == 0:
        raise ValueError("Variabel terikat tidak bervariasi")
    r2 = 1 - sse / sst
    adj = 1 - (1 - r2) * (n - 1) / df_res
    mse = sse / df_res
    cov = mse * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    tvals = beta / se
    pvals = 2 * sps.t.sf(np.abs(tvals), df_res)
    fstat = (r2 / k) / ((1 - r2) / df_res) if r2 < 1 else float("inf")
    fp = float(sps.f.sf(fstat, k, df_res)) if math.isfinite(fstat) else 0.0
    t = L10N[lang]
    names = [t["const"]] + xs
    rows = [[nm, _f(b, 3, lang), _f(s, 3, lang), _f(tv, 2, lang), _f(pv, 3, lang)] for nm, b, s, tv, pv in zip(names, beta, se, tvals, pvals)]
    report = f"F({k}, {df_res}) = {_f(fstat, 2, lang)}, {_p(fp, lang)}, R² = {_f(r2, 3, lang)}"
    sig_pred = [nm for nm, pv in zip(xs, pvals[1:]) if pv < alpha]
    if lang == "en":
        interp = (
            f"The model {'significantly' if fp < alpha else 'did not significantly'} predict {y}, {report} (adjusted R² = {_f(adj, 3, lang)}). "
            + (f"Significant predictors: {', '.join(sig_pred)}." if sig_pred else "No individual predictor was significant.")
        )
    else:
        interp = (
            f"Model {'secara signifikan' if fp < alpha else 'tidak secara signifikan'} memprediksi {y}, {report} (R² terkoreksi = {_f(adj, 3)}). "
            + (f"Prediktor yang signifikan: {', '.join(sig_pred)}." if sig_pred else "Tidak ada prediktor yang signifikan secara individual.")
        )
    return {
        "kind": "regression", "report": report, "interpretation": interp, "significant": bool(fp < alpha),
        "tables": [
            {"title": f"{'Regression coefficients' if lang == 'en' else 'Koefisien regresi'} ({y})", "columns": [t["var"], "B", "SE", "t", "p"], "rows": rows, "note": f"n = {n}; R² = {_f(r2, 3, lang)}; adj. R² = {_f(adj, 3, lang)}; F({k}, {df_res}) = {_f(fstat, 2, lang)}, {_p(fp, lang)}"},
        ],
    }


def chi_square(cols: dict[str, list], a: str, b: str, alpha: float = 0.05, lang: str = "id") -> dict:
    n = min(len(cols[a]), len(cols[b]))
    pairs = [(str(cols[a][i]).strip(), str(cols[b][i]).strip()) for i in range(n) if str(cols[a][i]).strip() and str(cols[b][i]).strip()]
    ra = sorted({p[0] for p in pairs})
    rb = sorted({p[1] for p in pairs})
    if len(ra) < 2 or len(rb) < 2:
        raise ValueError("Chi-square butuh minimal dua kategori pada tiap variabel")
    if len(ra) > 10 or len(rb) > 10:
        raise ValueError("Maksimal 10 kategori per variabel")
    table = np.zeros((len(ra), len(rb)), dtype=int)
    for u, v in pairs:
        table[ra.index(u), rb.index(v)] += 1
    chi2, p, dof, expected = sps.chi2_contingency(table, correction=False)
    total = int(table.sum())
    v_cramer = math.sqrt(chi2 / (total * (min(table.shape) - 1)))
    low = float((expected < 5).mean())
    sig = p < alpha
    report = f"χ²({dof}, N = {total}) = {_f(chi2, 2, lang)}, {_p(p, lang)}, Cramér's V = {_f(v_cramer, 2, lang)}"
    note_low = (f" {round(low * 100)}% sel memiliki frekuensi harapan < 5; hasil perlu ditafsirkan hati-hati." if lang == "id" else f" {round(low * 100)}% of cells have expected counts < 5; interpret with caution.") if low > 0.2 else ""
    if lang == "en":
        interp = f"The association between {a} and {b} is {L10N['en']['sig' if sig else 'nsig']}, {report}.{note_low}"
    else:
        interp = f"Hubungan antara {a} dan {b} {L10N['id']['sig' if sig else 'nsig']}, {report}.{note_low}"
    rows = [[ra[i]] + [str(int(table[i, j])) for j in range(len(rb))] + [str(int(table[i].sum()))] for i in range(len(ra))]
    rows.append([L10N[lang]["total"]] + [str(int(table[:, j].sum())) for j in range(len(rb))] + [str(total)])
    return {
        "kind": "chi_square", "report": report, "interpretation": interp, "significant": bool(sig),
        "tables": [{"title": f"{'Crosstab' if lang == 'en' else 'Tabulasi silang'} {a} × {b}", "columns": [f"{a} \\ {b}"] + rb + [L10N[lang]["total"]], "rows": rows, "note": report}],
    }


def normality(cols: dict[str, list], name: str, alpha: float = 0.05, lang: str = "id") -> dict:
    (x,), n = _pairs(cols, [name])
    if n < 3:
        raise ValueError("Uji normalitas butuh minimal 3 data")
    if n > 5000:
        raise ValueError("Uji Shapiro-Wilk dibatasi 5000 data")
    if np.std(x) == 0:
        raise ValueError("Semua nilai sama; normalitas tidak dapat diuji")
    w, p = sps.shapiro(x)
    ok = p >= alpha
    report = f"W = {_f(w, 3, lang)}, {_p(p, lang)}"
    if lang == "en":
        interp = f"Shapiro-Wilk test indicates that {name} is {'approximately normally distributed' if ok else 'not normally distributed'}, {report} (alpha = {alpha}, n = {n})."
    else:
        interp = f"Uji Shapiro-Wilk menunjukkan data {name} {'berdistribusi normal' if ok else 'tidak berdistribusi normal'}, {report} (taraf {_f(alpha, 2)}, n = {n})."
    return {
        "kind": "normality", "report": report, "interpretation": interp, "significant": bool(not ok),
        "tables": [{"title": f"{'Normality test' if lang == 'en' else 'Uji normalitas'} ({name})", "columns": ["Shapiro-Wilk W", "p", "n", "Skewness", "Kurtosis"], "rows": [[_f(w, 3, lang), _f(p, 3, lang), str(n), _f(float(sps.skew(x)), 2, lang), _f(float(sps.kurtosis(x)), 2, lang)]], "note": "H0: data berdistribusi normal" if lang == "id" else "H0: data are normally distributed"}],
    }


def reliability(cols: dict[str, list], items: list[str], lang: str = "id") -> dict:
    if len(items) < 2:
        raise ValueError("Reliabilitas butuh minimal 2 butir")
    arrays, n = _pairs(cols, items)
    if n < 3:
        raise ValueError("Reliabilitas butuh minimal 3 responden lengkap")
    M = np.column_stack(arrays)
    k = M.shape[1]
    if np.any(M.var(axis=0, ddof=1) == 0):
        raise ValueError("Ada butir yang semua jawabannya sama; hapus butir itu dari analisis")

    def alpha_of(mat: np.ndarray) -> float:
        kk = mat.shape[1]
        return float(kk / (kk - 1) * (1 - mat.var(axis=0, ddof=1).sum() / mat.sum(axis=1).var(ddof=1)))

    a = alpha_of(M)
    t = L10N[lang]
    rows = []
    for j, nm in enumerate(items):
        rest = np.delete(M, j, axis=1)
        rtot = float(np.corrcoef(M[:, j], rest.sum(axis=1))[0, 1])
        a_del = alpha_of(rest) if k > 2 else float("nan")
        rows.append([nm, _f(rtot, 3, lang), _f(a_del, 3, lang) if math.isfinite(a_del) else "-"])
    label = ("sangat baik", "baik", "dapat diterima", "dipertanyakan", "buruk")[0 if a >= 0.9 else 1 if a >= 0.8 else 2 if a >= 0.7 else 3 if a >= 0.6 else 4] if lang == "id" else ("excellent", "good", "acceptable", "questionable", "poor")[0 if a >= 0.9 else 1 if a >= 0.8 else 2 if a >= 0.7 else 3 if a >= 0.6 else 4]
    weak = [r[0] for r in rows if float(r[1].replace(",", ".")) < 0.3]
    report = f"Cronbach's α = {_f(a, 3, lang)} ({k} {'items' if lang == 'en' else 'butir'}, N = {n})"
    if lang == "en":
        interp = f"Internal consistency is {label}, {report}." + (f" Items with item-total r < .30: {', '.join(weak)}." if weak else "")
    else:
        interp = f"Konsistensi internal instrumen {label}, {report}." + (f" Butir dengan korelasi butir-total < 0,30: {', '.join(weak)}." if weak else "")
    return {
        "kind": "reliability", "report": report, "interpretation": interp, "significant": bool(a >= 0.7),
        "tables": [{"title": f"{'Reliability' if lang == 'en' else 'Reliabilitas'} (Cronbach's α = {_f(a, 3, lang)})", "columns": [t["item"], t["rtot"], t["alpha_del"]], "rows": rows, "note": report}],
    }


def run(kind: str, cols: dict[str, list], params: dict, alpha: float = 0.05, lang: str = "id") -> dict:
    lang = "en" if lang == "en" else "id"
    for c in [params.get("a"), params.get("b"), params.get("y"), *(params.get("xs") or []), *(params.get("items") or []), params.get("column")]:
        if c and c not in cols:
            raise ValueError(f"Kolom '{c}' tidak ada pada data")
    if kind == "correlation":
        return correlation(cols, params["a"], params["b"], alpha, lang)
    if kind == "regression":
        return regression(cols, params["y"], list(params.get("xs") or []), alpha, lang)
    if kind == "chi_square":
        return chi_square(cols, params["a"], params["b"], alpha, lang)
    if kind == "normality":
        return normality(cols, params["column"], alpha, lang)
    if kind == "reliability":
        return reliability(cols, list(params.get("items") or []), lang)
    raise ValueError("Jenis uji tidak dikenal")
