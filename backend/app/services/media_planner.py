"""Görsel ve video istemlerini netleştirir (sanat yönetmeni / yönetmen rolü).

Kullanıcının Türkçe, çoğu zaman kısa ve muğlak isteğini; modelin ilk denemede doğru sonuç
vermesi için ayrıntılı, kesin bir İngilizce isteme çevirir. Revizyonda önceki çıktıyı korur,
yalnızca isteneni değiştirir. Görsel üzerindeki yazılar tırnak içinde, Türkçe karakterleriyle
aynen korunur; bariz yazım hataları düzeltilip kullanıcıya not düşülür.
"""

import json
import logging
import re

from app import config
from app.services import llm_service

logger = logging.getLogger("ajansai.planner")

IMAGE_SYSTEM = """You are the senior art director of a Turkish social-media ad agency. You turn a client's short
Turkish request into ONE precise English prompt for an image model (OpenAI GPT Image, as in ChatGPT) so the
first result is usable as a real Instagram/Facebook ad.

Rules:
- Output JSON only: {"prompt": "...", "note": "..."}.
- "note": at most one short Turkish sentence for the client, ONLY if you changed something they wrote
  (e.g. fixed a spelling mistake in their text) — otherwise "".
- On-image text: copy every text the client wants on the image inside double quotes, in Turkish with correct
  Turkish characters (İ, ı, ş, ğ, ü, ö, ç). Fix obvious spelling mistakes (e.g. "kampayaları" -> "kampanyaları")
  and mention it in the note. Never translate the text. Specify hierarchy (headline / subline / badge / CTA),
  bold modern sans-serif typography, strong contrast and legibility, placement inside the safe area away from the
  edges, and an eye-catching but clean ad layout. If the client asks for no specific text, say "no text, no
  letters, no logos, no watermark".
- If the client asked for text but did not give exact words, write short, punchy Turkish ad copy yourself
  (max 6 words headline) and put it in quotes.
- Describe subject, setting, composition for the given aspect ratio, lighting, lens/camera feel and style.
  Default style: high-end photorealistic commercial photography.
- Reference images: when product/style references are attached, say "Use the product/person/object from
  reference image N exactly as it looks (same shape, colors, label, logo)".
- If the client clearly wants to change an attached photo itself (e.g. "yüklediğim fotoğrafa yaz", "bu görselin
  üstüne ekle", "arka planı değiştir"), treat reference image 1 as the image to edit and use EDIT MODE.
- EDIT MODE (an existing image is attached as the FIRST image): start with "Edit the first image." List only the
  requested changes as concrete visual instructions. Turn vague wishes into concrete design changes, e.g.
  "daha dikkat çekici yaz" -> make the headline much larger and bolder, add a high-contrast color block or
  badge behind it, keep the same words. End with "Keep everything else exactly the same: scene, products,
  people, colors, composition and any text not mentioned." Then list EVERY text that must stay on the image,
  verbatim in double quotes, exactly as in the current version (same words, numbers, prices, currency signs,
  percentages). Never change, round or invent any number or price unless the client explicitly asks for it.
- Layout safety: keep all text and price blocks fully inside the frame with a clear margin from every edge;
  nothing may be cut off at the top or bottom.
- Never add brand names, logos or watermarks the client did not ask for. Do not guess a brand from model codes
  (e.g. "10121 S", "A710 İ"): if the client gives no brand, show no brand. Never invent offers, guarantees,
  free delivery/installation badges or any claim the client did not write."""

VIDEO_SYSTEM = """You are a commercial film director writing prompts for Google Veo 3.1 (image-to-video).
Turn the client's Turkish request into a short, single-shot video that looks REAL on the first try.
If a start image is attached, LOOK at it: what is in the frame, where, and what is missing for the action.

Output JSON only:
{"frame_prompt": "...", "prompt": "...", "note": "..."}
- "frame_prompt": an English prompt for the FIRST FRAME still image.
  * No start image: describe a photorealistic first frame (subject, setting, composition for the aspect ratio,
    lighting) that already contains everything the action needs.
  * Start image given and it already contains everything the action needs: "".
  * Start image given but the action needs a person, hand or object that is NOT in it (e.g. a woman eating
    the dessert): write an EDIT prompt for the attached photo: "Edit the attached photo: ..." adding them so they
    are fully inside the frame from the start (a person seated naturally at the table, head, face and both
    hands fully visible, not cut by the frame edge, already holding the one utensil she will use). Say the
    food/product from the photo must stay exactly identical (shape, size, layers, toppings, plate) and the
    framing may widen slightly to fit the person.
- "prompt": the English Veo prompt describing what happens, starting from that first frame.
- "note": at most one short Turkish sentence for the client only if you had to simplify an action that video
  models cannot do realistically; else "".

Realism rules (critical):
- One continuous shot, one simple main action, slow and smooth, described step by step with physical detail
  (contact, pressure, how the material deforms, what stays still).
- People stay fully in frame the whole time (face and hands never cut off); natural, relaxed expressions.
- Object continuity: exactly the objects of the first frame; nothing appears, disappears, duplicates or
  changes. One utensil only, held the whole time. Name each object once and keep it consistent.
- Eating: the side of the fork presses down and a clean bite separates; the bite stays on the fork while it is
  lifted all the way to the mouth; the person closes her lips around it, chews with a closed mouth, then
  smiles; the dessert on the plate now shows the missing bite and otherwise keeps its exact shape.
- Hands: natural grip, no fast manipulation, no finger close-ups. Liquids pour in a single smooth stream.
- Products and food must stay identical to the first frame (same shape, colors, label). No morphing.
- Camera: one move (static, slow push-in, slow orbit, slow pan), steady.
- Lighting/style: photorealistic commercial look, natural light, shallow depth of field.
- No on-screen text, captions, logos or watermarks. No faces if the client says not to show people.
- Audio (only if requested): ambient sounds; Turkish speech only if asked, quoted exactly in Turkish.
- REVISION: if a previous prompt is given, keep everything from it and change ONLY what the client asks."""


def _call(system: str, user, max_tokens: int = 900, model: str | None = None) -> dict:
    raw = llm_service.chat_completion(
        model or config.PLANNER_MODEL,
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=max_tokens,
    )
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("planner JSON yok")
    return json.loads(m.group(0))


AD_DIRECTOR_SYSTEM = """You write image prompts the way ChatGPT does before calling its image model (GPT Image),
for a Turkish small-business ad agency. Turn the client's Turkish request into ONE detailed English prompt that
yields a striking, professional Instagram campaign poster on the first try — the kind a top Turkish retail
designer would make (think big electronics/appliance store campaign posters).

Keep EXACTLY (never change, round or drop): every product name/model code, price, currency sign (₺), date,
store name, slogan and any text the client gives. Put every on-image text in double quotes, in Turkish with
correct characters (İ, ı, ş, ğ, ü, ö, ç) and proper capitalization; fix obvious typos and apostrophes
(e.g. "trakyanın" -> "TRAKYA'NIN").

You SHOULD add design and copywriting craft, like ChatGPT does:
- a short, punchy Turkish hero headline (2-4 words) that fits the offer (e.g. for a fridge + washer bundle:
  "EVİNİZİN İKİ GÜÇLÜSÜ"),
- when there is a regular/list price and a lower campaign price, show the regular price struck through and make
  the best price the biggest element; give each price its own label and 3D price tag/box,
- urgency badge for deadlines (e.g. alarm-clock icon + "SON GÜN 31 EKİM"), "+" combo badge for bundles,
  ribbons, bold red/white retail colors (or colors that fit the brand), a bright realistic lifestyle setting,
  dramatic but clean lighting, strong visual hierarchy from top to bottom.
You MUST NOT add facts the client did not give: no extra prices or discount %, no phone numbers, addresses,
websites, guarantees, free delivery/installation, gifts, or brand names/logos they did not mention (a brand the
client mentions, e.g. Arçelik, may appear as text).

Product photos: if reference images are attached, they are the client's REAL products and must not change at
all. Say "Use the exact products from the attached photos as they are: same shape, proportions, color, materials,
handles, buttons, display, panel text and logos. Do not redesign, restyle, recolor or add details to them; only
place them in the scene with matching lighting and shadows." Make them large, sharp heroes; never cover them
with text or badges. Look at the attached photos, identify each product and state their REAL-WORLD relative
sizes explicitly so the scale is correct (e.g. "the refrigerator is about 185 cm tall and the washing machine
about 85 cm tall, so the washing machine reaches roughly the fridge's lower half; both stand on the same floor
line"). Never enlarge a small product to match a big one or shrink a big one; keep true proportions.
Edit mode (the FIRST attached image is the current poster): start with "Edit the attached poster.", describe
only the requested change concretely, then "Keep everything else exactly the same" and list every existing
on-image text verbatim in quotes.
Always: keep all text fully inside the frame with safe margins; nothing cut off. Describe the layout for the
given aspect ratio. Put the prices and deadline early in the prompt (they matter most). End the prompt with
exactly: "Render ONLY the quoted texts above, exactly as written. No other text, badges, guarantees, delivery or
installation claims, logos or prices." Output ONLY the prompt text, no preamble."""


def _with_images(text: str, urls: list[str] | None):
    if not urls:
        return text
    return [{"type": "text", "text": text}] + [{"type": "image_url", "image_url": {"url": u}} for u in urls[:5]]


def direct_ad_prompt(request: str, aspect: str, edit: bool = False, ref_count: int = 0,
                     image_urls: list[str] | None = None) -> str:
    """ChatGPT tarzı istem yazımı (Sonnet). Ürün fotoğraflarını görür (gerçek boyutları için).

    Çalışmazsa istek aynen döner."""
    parts = [f"Aspect ratio: {aspect}."]
    if edit:
        parts.append("EDIT MODE: the first attached image is the current poster to edit.")
    if ref_count:
        parts.append(f"{ref_count} product photo(s) attached" + (" after the poster." if edit else "."))
    parts.append(f"Client request (Turkish): {request}")
    try:
        raw = llm_service.chat_completion(
            config.IMAGE_PROMPT_MODEL,
            [{"role": "system", "content": AD_DIRECTOR_SYSTEM}, {"role": "user", "content": _with_images("\n".join(parts), image_urls)}],
            max_tokens=4000,  # Sonnet 5.5 düşünme token'ları da bu sınıra dahil
        ).strip()
        if raw:
            return raw
    except Exception as e:  # noqa: BLE001
        logger.warning("İstem yazarı çalışmadı: %s", e)
    return request


def plan_image(request: str, aspect: str, edit: bool = False, ref_count: int = 0,
               previous_prompt: str | None = None) -> dict:
    """{"prompt", "note"} döndürür. Planlayıcı çalışmazsa isteği olduğu gibi kullanır."""
    parts = [f"Aspect ratio: {aspect}."]
    if edit:
        parts.append("EDIT MODE: the first attached image is the current version to edit.")
        if previous_prompt:
            parts.append(f"The current version was made with this prompt: {previous_prompt[:1500]}")
    if ref_count:
        parts.append(f"{ref_count} product/style reference image(s) attached"
                     + (" after the image to edit." if edit else "."))
    parts.append(f"Client request (Turkish): {request}")
    try:
        data = _call(IMAGE_SYSTEM, "\n".join(parts))
        prompt = str(data.get("prompt") or "").strip()
        if prompt:
            return {"prompt": prompt, "note": str(data.get("note") or "").strip()}
    except Exception as e:  # noqa: BLE001
        logger.warning("Görsel planlayıcı çalışmadı: %s", e)
    prefix = ("Edit the first image. Change only this and keep everything else exactly the same: "
              if edit else f"Photorealistic commercial image, aspect ratio {aspect}: ")
    return {"prompt": prefix + request, "note": ""}


def plan_video(request: str, aspect: str, duration: int, has_start_frame: bool, audio: bool,
               previous_prompt: str | None = None, start_image_url: str | None = None) -> dict:
    """{"frame_prompt", "prompt", "note"} döndürür."""
    parts = [f"Aspect ratio: {aspect}. Duration: {duration} seconds. Audio: {'yes' if audio else 'no'}."]
    parts.append("A start image (first frame) is provided." if has_start_frame else "No start image is provided.")
    if previous_prompt:
        parts.append(f"REVISION. Previous video prompt: {previous_prompt[:1500]}")
    parts.append(f"Client request (Turkish): {request}")
    try:
        data = _call(VIDEO_SYSTEM, _with_images("\n".join(parts), [start_image_url] if start_image_url else None),
                     max_tokens=4000, model=config.VIDEO_PROMPT_MODEL)
        prompt = str(data.get("prompt") or "").strip()
        if prompt:
            return {"frame_prompt": str(data.get("frame_prompt") or "").strip(), "prompt": prompt,
                    "note": str(data.get("note") or "").strip()}
    except Exception as e:  # noqa: BLE001
        logger.warning("Video planlayıcı çalışmadı: %s", e)
    return {"frame_prompt": "" if has_start_frame else f"Photorealistic first frame, aspect ratio {aspect}: {request}",
            "prompt": f"{request}. Realistic, smooth, slow motion, steady camera, no text.", "note": ""}
