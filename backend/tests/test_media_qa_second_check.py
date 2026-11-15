"""Yeniden üretilen görsel de denetlenir; iki görselden kusuru az olan seçilir (eşitlikte ilki)."""

from app.services import gateway_media, media_qa


def _setup(monkeypatch, verdicts):
    calls, checked = [], []
    monkeypatch.setattr(gateway_media, "generate_image",
                        lambda p, a, r=None, q="standard": calls.append(p) or (b"img%d" % len(calls), "image/png"))
    it = iter(verdicts)

    def fake_check(data, req, urls=None):
        checked.append(data)
        return next(it)

    monkeypatch.setattr(media_qa, "check_image", fake_check)
    return calls, checked


def test_second_image_is_checked_and_used_when_better(monkeypatch):
    calls, checked = _setup(monkeypatch, [["price missing", "text cut off"], ["text cut off"]])
    data, mime = media_qa.generate_checked("P", "4:5", None, "istek")
    assert data == b"img2" and mime == "image/png"
    assert checked == [b"img1", b"img2"] and len(calls) == 2


def test_first_image_kept_when_retry_is_worse(monkeypatch):
    calls, checked = _setup(monkeypatch, [["price missing"], ["garbled text", "extra finger"]])
    data, _ = media_qa.generate_checked("P", "4:5", None, "istek")
    assert data == b"img1" and checked == [b"img1", b"img2"]


def test_first_image_kept_on_tie(monkeypatch):
    _setup(monkeypatch, [["price missing"], ["date wrong"]])
    data, _ = media_qa.generate_checked("P", "4:5", None, "istek")
    assert data == b"img1"


def test_retry_clean_wins(monkeypatch):
    _setup(monkeypatch, [["price missing"], []])
    data, _ = media_qa.generate_checked("P", "4:5", None, "istek")
    assert data == b"img2"


def test_retry_generation_error_keeps_first_without_second_check(monkeypatch):
    checked = []
    seq = iter([(b"img1", "image/png")])

    def gen(p, a, r=None, q="standard"):
        try:
            return next(seq)
        except StopIteration:
            raise gateway_media.MediaError("kota")

    monkeypatch.setattr(gateway_media, "generate_image", gen)
    monkeypatch.setattr(media_qa, "check_image", lambda data, req, urls=None: checked.append(data) or ["x"])
    data, _ = media_qa.generate_checked("P", "4:5", None, "istek")
    assert data == b"img1" and checked == [b"img1"]


def test_product_urls_passed_to_both_checks(monkeypatch):
    seen = []
    monkeypatch.setattr(gateway_media, "generate_image", lambda p, a, r=None, q="standard": (b"i", "image/png"))
    verdicts = iter([["a"], []])
    monkeypatch.setattr(media_qa, "check_image", lambda data, req, urls=None: seen.append((req, urls)) or next(verdicts))
    media_qa.generate_checked("P", "4:5", ["r"], "istek", ["u1"])
    assert seen == [("istek", ["u1"]), ("istek", ["u1"])]
