from services.extractor.prompt_builder import build_extraction_prompt


def test_build_extraction_prompt_embeds_text() -> None:
    prompt = build_extraction_prompt("Recovered near Kyoto in 1993.")
    assert "<BEGIN_TEXT>" in prompt
    assert "Recovered near Kyoto in 1993." in prompt
    assert "Return only valid JSON." in prompt
