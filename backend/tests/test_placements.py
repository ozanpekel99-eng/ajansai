from app.services import meta_ads_service as m


def test_positions_mix():
    out = m._positions(["instagram_feed", "facebook_story"])
    assert out == {"publisher_platforms": ["instagram", "facebook"], "instagram_positions": ["stream"], "facebook_positions": ["story"]}


def test_positions_default_instagram_only():
    assert m._positions(None)["publisher_platforms"] == ["instagram"]


def test_customized_creative_labels():
    pos = m._positions(["instagram_feed", "instagram_story", "facebook_feed"])
    body = m._customized_creative("1", "t", "Ad", "p", "ig", {"image_hash": "a"}, {"image_hash": "b"}, pos, "metin", "", "https://x.com", {"type": "LEARN_MORE"})
    spec = body["asset_feed_spec"]
    assert [i["hash"] for i in spec["images"]] == ["a", "b"]
    rules = spec["asset_customization_rules"]
    assert rules[0]["customization_spec"]["instagram_positions"] == ["story"]
    assert rules[1]["customization_spec"]["facebook_positions"] == ["feed"]
