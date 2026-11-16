"""색인할 글(embed_text)을 만든다. 구성 방식은 평가로 고른다 (eval/rag)."""

MODES = ("body", "name_cat_body")


def build_embed_text(
    name: str, category: str, intro: str | None, tag: str | None, mode: str
) -> str:
    body = " ".join((intro or "").split())
    if tag:
        body = f"{body} 태그: {tag}".strip()
    if mode == "body":
        return body
    if mode == "name_cat_body":
        return f"{name} ({category}). {body}"
    raise ValueError(f"모르는 구성: {mode}")
