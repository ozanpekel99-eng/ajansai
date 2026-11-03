"""Video planlayıcı: kampanya görselindeki yazıların videoda sabit kalması kuralı."""
from app.services import media_planner


def test_video_system_keeps_campaign_text_fixed():
    s = media_planner.VIDEO_SYSTEM
    assert "Campaign graphic as first frame" in s
    assert "stay completely fixed" in s
    assert "do\n  not slide" in s or "not slide" in s
    # Eski çelişkili kural ("No on-screen text") yerine yalnızca yeni yazı eklenmesi yasak
    assert "Never ADD on-screen text" in s
    assert "- No on-screen text" not in s


def _fail(*a, **k):
    raise RuntimeError("LLM kapalı")


def test_fallback_with_start_frame_keeps_existing_text(monkeypatch):
    monkeypatch.setattr(media_planner.llm_service, "chat_completion", _fail)
    plan = media_planner.plan_video("Kampanya afişi canlansın", "9:16", 8, True, False)
    assert plan["frame_prompt"] == ""
    assert "Keep all existing text" in plan["prompt"]
    assert "exactly unchanged" in plan["prompt"]
    assert "no text" not in plan["prompt"].lower()


def test_fallback_without_start_frame_says_no_text(monkeypatch):
    monkeypatch.setattr(media_planner.llm_service, "chat_completion", _fail)
    plan = media_planner.plan_video("Kahve fincanından buhar yükselsin", "9:16", 8, False, False)
    assert plan["frame_prompt"].startswith("Photorealistic first frame")
    assert plan["prompt"].endswith("No text.")
    assert "Keep all existing text" not in plan["prompt"]
