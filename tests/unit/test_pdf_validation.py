from types import SimpleNamespace

from importlib import import_module

forms = import_module("app.routers.forms")


def test_pdf_validation_branches(monkeypatch, tmp_path):
    path = tmp_path / "resume.pdf"
    path.write_bytes(b"pdf")
    assert forms._validate_pdf(str(path), "resume.txt")[0] is False

    monkeypatch.setattr(
        forms,
        "PdfReader",
        lambda _path: SimpleNamespace(is_encrypted=True, pages=[1], trailer={}),
    )
    assert forms._validate_pdf(str(path), "resume.pdf")[0] is False

    monkeypatch.setattr(
        forms,
        "PdfReader",
        lambda _path: SimpleNamespace(is_encrypted=False, pages=[], trailer={}),
    )
    assert forms._validate_pdf(str(path), "resume.pdf")[0] is False

    for root in ({"nested": [{"/JS": "bad"}]}, {"nested": {"/EmbeddedFile": "bad"}}):
        monkeypatch.setattr(
            forms,
            "PdfReader",
            lambda _path, root=root: SimpleNamespace(
                is_encrypted=False, pages=[1], trailer={"/Root": root}
            ),
        )
        assert forms._validate_pdf(str(path), "resume.pdf")[0] is False

    monkeypatch.setattr(forms, "PdfReader", lambda _path: (_ for _ in ()).throw(ValueError("bad")))
    valid, error = forms._validate_pdf(str(path), "resume.pdf")
    assert valid is False
    assert error.startswith("Invalid PDF")
