import os
import json
from flask import Blueprint, session, request, redirect, url_for, g

i18n_bp = Blueprint("i18n", __name__)

SUPPORTED_LANGUAGES = {
    "en": {"name": "English", "native": "English", "flag": "🇺🇸", "dir": "ltr"},
    "es": {"name": "Spanish", "native": "Español", "flag": "🇪🇸", "dir": "ltr"},
    "fr": {"name": "French", "native": "Français", "flag": "🇫🇷", "dir": "ltr"},
    "de": {"name": "German", "native": "Deutsch", "flag": "🇩🇪", "dir": "ltr"},
    "ja": {"name": "Japanese", "native": "日本語", "flag": "🇯🇵", "dir": "ltr"},
    "ar": {"name": "Arabic", "native": "العربية", "flag": "🇸🇦", "dir": "rtl"},
    "si": {"name": "Sinhala", "native": "සිංහල", "flag": "🇱🇰", "dir": "ltr"},
}

_TRANSLATIONS = {}


def load_translations() -> dict:
    """Load all JSON translation files from app/translations directory."""
    global _TRANSLATIONS
    base_dir = os.path.dirname(__file__)
    trans_dir = os.path.join(base_dir, "translations")

    translations = {}
    if os.path.isdir(trans_dir):
        for fname in os.listdir(trans_dir):
            if fname.endswith(".json"):
                lang_code = fname[:-5]
                fpath = os.path.join(trans_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        translations[lang_code] = json.load(f)
                except Exception as exc:
                    print(f"Error loading translation for {lang_code}: {exc}")

    _TRANSLATIONS = translations
    return _TRANSLATIONS


def get_translation(key: str | None, **kwargs) -> str:
    """Retrieve translated text for key in current language (g.lang)."""
    if key is None:
        return ""
    lang = getattr(g, "lang", "en")
    if not _TRANSLATIONS:
        load_translations()

    str_key = str(key).strip()
    lang_catalog = _TRANSLATIONS.get(lang, {})

    # 1. Direct lookup
    text = lang_catalog.get(str_key)

    # 2. Case variations (Title, Lower, Upper, Snake to Title)
    if text is None:
        clean_variation = str_key.replace("_", " ").title()
        text = (
            lang_catalog.get(clean_variation)
            or lang_catalog.get(str_key.title())
            or lang_catalog.get(str_key.lower())
        )

    # 3. Fallback to English catalog
    if text is None:
        en_catalog = _TRANSLATIONS.get("en", {})
        clean_variation = str_key.replace("_", " ").title()
        text = (
            en_catalog.get(str_key)
            or en_catalog.get(clean_variation)
            or en_catalog.get(str_key.title())
            or en_catalog.get(str_key.lower())
            or str_key
        )

    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


# Alias functions for template and Python usage
_ = get_translation
t = get_translation


@i18n_bp.route("/set-lang/<lang_code>")
def set_language(lang_code: str):
    """Update session language and redirect back to previous page."""
    if lang_code in SUPPORTED_LANGUAGES:
        session["lang"] = lang_code

    # Safe redirect
    referrer = request.referrer
    if referrer and referrer.startswith(request.host_url):
        return redirect(referrer)
    return redirect(url_for("main.index"))
