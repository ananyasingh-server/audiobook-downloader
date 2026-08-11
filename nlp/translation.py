from deep_translator import GoogleTranslator


def translate_text(text, target_language="hi"):
    """
    Translate English text into the selected language.

    Currently supported:
    hi = Hindi
    """

    if not text or not text.strip():
        return ""

    if target_language == "hi":
        try:
            translator = GoogleTranslator(
                source="en",
                target="hi"
            )

            return translator.translate(text)

        except Exception as e:
            raise RuntimeError(
                f"Hindi translation failed: {e}"
            )

    return text