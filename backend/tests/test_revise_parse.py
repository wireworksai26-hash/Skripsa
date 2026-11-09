import json

from app.services.agents import reviser
from tests.test_revise_history import ORIGINAL, _fmt, _setup


def test_parse_response_variants():
    body, ch = reviser.parse_response("Naskah baru. (Nur, 2021)\n###PERUBAHAN###\n- Tambah A\n* Tambah B\n")
    assert body == "Naskah baru. (Nur, 2021)" and ch == ["Tambah A", "Tambah B"]
    assert reviser.parse_response("```\nIsi\n###PERUBAHAN###\n- x\n```")[0] == "Isi"
    assert reviser.parse_response(json.dumps({"content": "Isi json", "changes": ["c"]})) == ("Isi json", ["c"])
    assert reviser.parse_response("Tanpa pemisah sama sekali") == ("Tanpa pemisah sama sekali", [])


def test_long_section_gets_larger_token_budget(client, auth, monkeypatch):
    headers = auth["headers"]
    tid = _setup(client, headers)
    long_text = ORIGINAL + " " + " ".join(["Kalimat tambahan yang panjang sekali untuk menguji anggaran token."] * 120)
    client.patch(f"/theses/{tid}/sections/1.1", headers=headers, json={"content_markdown": long_text})
    budgets = []

    async def fake(messages, tier="heavy", temperature=0.4, max_tokens=1600, only=None):
        budgets.append(max_tokens)
        return _fmt({"content": long_text + " Tambahan baru. (Nur, 2021)", "changes": ["x"]}), "fake"

    monkeypatch.setattr(reviser, "llm_chat_ex", fake)
    assert client.post(f"/theses/{tid}/sections/1.1/revise", headers=headers, json={"feedback": ["x"]}).status_code == 200
    assert budgets[0] > 3000
