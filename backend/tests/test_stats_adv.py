import math

import numpy as np
import pytest
from scipy import stats as sps

from app.services import stats_adv as sa

rng = np.random.default_rng(7)
X1 = rng.normal(50, 10, 40)
X2 = rng.normal(20, 5, 40)
Y = 5 + 0.8 * X1 - 0.5 * X2 + rng.normal(0, 3, 40)
COLS = {"x1": list(X1), "x2": list(X2), "y": list(Y)}


def test_correlation_matches_scipy():
    r = sa.correlation(COLS, "x1", "y")
    ref_r, ref_p = sps.pearsonr(X1, Y)
    row = r["tables"][0]["rows"][0]
    assert row[0] == f"{ref_r:.3f}".replace(".", ",") and r["significant"] is True
    assert any(w in r["interpretation"] for w in ("kuat", "sedang"))
    assert r["report"].startswith(f"r(38) = {ref_r:.2f}".replace(".", ","))


def test_regression_matches_ols_and_reports_model_fit():
    r = sa.regression(COLS, "y", ["x1", "x2"])
    X = np.column_stack([np.ones(40), X1, X2])
    beta = np.linalg.lstsq(X, Y, rcond=None)[0]
    rows = {row[0]: row for row in r["tables"][0]["rows"]}
    assert rows["x1"][1] == f"{beta[1]:.3f}".replace(".", ",") and rows["x2"][1] == f"{beta[2]:.3f}".replace(".", ",")
    assert float(rows["x1"][4].replace(",", ".")) < 0.001 and "Prediktor yang signifikan: x1, x2" in r["interpretation"]
    assert r["report"].startswith("F(2, 37)") and r["significant"] is True


def test_regression_rejects_collinear_and_tiny_data():
    cols = {"a": [1, 2, 3, 4, 5, 6], "b": [2, 4, 6, 8, 10, 12], "y": [1, 3, 2, 5, 4, 6]}
    with pytest.raises(ValueError, match="multikolinearitas"):
        sa.regression(cols, "y", ["a", "b"])
    with pytest.raises(ValueError, match="terlalu sedikit"):
        sa.regression({"a": [1, 2, 3], "y": [1, 2, 4]}, "y", ["a"])


def test_chi_square_matches_scipy_and_cramers_v():
    a = ["L"] * 30 + ["P"] * 70
    b = ["ya"] * 10 + ["tidak"] * 20 + ["ya"] * 30 + ["tidak"] * 40
    r = sa.chi_square({"gender": a, "lulus": b}, "gender", "lulus")
    chi2, p, dof, _ = sps.chi2_contingency(np.array([[20, 10], [40, 30]]), correction=False)
    assert f"χ²(1, N = 100) = {chi2:.2f}".replace(".", ",") in r["report"]
    assert r["tables"][0]["rows"][-1][-1] == "100"
    with pytest.raises(ValueError, match="dua kategori"):
        sa.chi_square({"a": ["x", "y"] * 5, "b": ["p"] * 10}, "a", "b")


def test_normality_distinguishes_normal_from_skewed():
    normal = sa.normality({"v": list(rng.normal(0, 1, 80))}, "v")
    skew = sa.normality({"v": list(rng.exponential(1, 80))}, "v")
    assert normal["significant"] is False and "berdistribusi normal" in normal["interpretation"]
    assert skew["significant"] is True and "tidak berdistribusi normal" in skew["interpretation"]


def test_reliability_matches_formula():
    items = rng.integers(1, 6, size=(30, 4)).astype(float)
    items[:, 1] = items[:, 0] + rng.integers(-1, 2, 30)  # butir berkorelasi
    cols = {f"q{i + 1}": list(items[:, i]) for i in range(4)}
    r = sa.reliability(cols, ["q1", "q2", "q3", "q4"])
    k = 4
    alpha = k / (k - 1) * (1 - items.var(axis=0, ddof=1).sum() / items.sum(axis=1).var(ddof=1))
    assert f"{alpha:.3f}".replace(".", ",") in r["report"]
    assert len(r["tables"][0]["rows"]) == 4
    with pytest.raises(ValueError, match="minimal 2"):
        sa.reliability(cols, ["q1"])


def test_english_labels():
    r = sa.regression(COLS, "y", ["x1"], lang="en")
    assert "Regression coefficients" in r["tables"][0]["title"] and "predict" in r["interpretation"] and "." in r["report"]


CSV = "skor;motivasi;kelas;q1;q2;q3\n" + "\n".join(
    f"{60 + i * 2};{3 + (i % 5) * 0.4:.1f};{'A' if i % 2 else 'B'};{1 + i % 5};{1 + (i + 1) % 5};{2 + i % 4}".replace(".", ",") for i in range(24)
)


def _thesis(client, h, suffix):
    return client.post("/theses", headers=h, json={"topic": "Pengaruh Motivasi terhadap Skor Belajar Siswa" + suffix, "method": "KUANTITATIF"}).json()["thesis_id"]


def test_endpoint_runs_tests_creates_tables_and_feeds_writer(client, auth):
    from app.core import db as core_db
    from app.models.models import Thesis
    from app.services.agents.context import results_data

    h = auth["headers"]
    tid = _thesis(client, h, " st")
    d = client.post(f"/theses/{tid}/data", headers=h, json={"title": "Kuesioner", "kind": "table", "content": CSV}).json()
    cols = client.get(f"/theses/{tid}/data/{d['data_id']}/columns", headers=h).json()
    assert {c["name"]: c["numeric"] for c in cols} == {"skor": True, "motivasi": True, "kelas": False, "q1": True, "q2": True, "q3": True}
    r = client.post(f"/theses/{tid}/data/{d['data_id']}/test", headers=h, json={"kind": "correlation", "a": "skor", "b": "motivasi"})
    assert r.status_code == 200, r.text
    assert r.json()["tables"][0]["title"].startswith("Korelasi")
    assert client.post(f"/theses/{tid}/data/{d['data_id']}/test", headers=h, json={"kind": "regression", "y": "skor", "xs": ["motivasi"]}).status_code == 200
    assert client.post(f"/theses/{tid}/data/{d['data_id']}/test", headers=h, json={"kind": "reliability", "items": ["q1", "q2", "q3"]}).status_code == 200
    rel = client.post(f"/theses/{tid}/data/{d['data_id']}/test", headers=h, json={"kind": "chi_square", "a": "kelas", "b": "q1"})
    assert rel.status_code == 200, rel.text
    full = client.get(f"/theses/{tid}", headers=h).json()
    assert len(full["tables"]) == 4
    assert client.get(f"/theses/{tid}/data", headers=h).json()[0]["analyzed"] is False, "uji tidak menandai data sebagai sudah diolah"
    db = core_db.SessionLocal()
    assert "UJI STATISTIK" in results_data(db.get(Thesis, tid))
    db.close()
    # hapus satu uji menghapus tabelnya
    assert client.delete(f"/theses/{tid}/data/{d['data_id']}/tests/0", headers=h).status_code == 204
    assert len(client.get(f"/theses/{tid}", headers=h).json()["tables"]) == 3
    # menghapus data menghapus semua tabel ujinya
    client.delete(f"/theses/{tid}/data/{d['data_id']}", headers=h)
    assert client.get(f"/theses/{tid}", headers=h).json()["tables"] == []


def test_endpoint_rejects_non_numeric_columns_and_unknown_columns(client, auth):
    h = auth["headers"]
    tid = _thesis(client, h, " st2")
    d = client.post(f"/theses/{tid}/data", headers=h, json={"title": "Data", "kind": "table", "content": CSV}).json()
    assert client.post(f"/theses/{tid}/data/{d['data_id']}/test", headers=h, json={"kind": "correlation", "a": "skor", "b": "kelas"}).status_code == 422
    assert client.post(f"/theses/{tid}/data/{d['data_id']}/test", headers=h, json={"kind": "normality", "column": "tidak-ada"}).status_code == 422
    txt = client.post(f"/theses/{tid}/data", headers=h, json={"title": "Wawancara", "kind": "text", "content": "teks wawancara panjang " * 10}).json()
    assert client.post(f"/theses/{tid}/data/{txt['data_id']}/test", headers=h, json={"kind": "normality", "column": "x"}).status_code == 422
