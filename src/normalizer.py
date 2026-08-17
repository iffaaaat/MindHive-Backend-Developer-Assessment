import re
import unicodedata


# Keep this intentionally small.
# These are general domain abbreviations rather than
# mappings to specific catalogue products.
TERM_ALIASES = {
    "zp": "zinc plated",
    "ss304": "stainless 304",
    "ss316": "stainless 316",
    "putih": "white",
}


def normalize_text(text):
    if not text:
        return ""

    text = unicodedata.normalize(
        "NFKC",
        str(text),
    )

    text = text.lower()

    # --------------------------------------------------
    # Normalize inch measurements.
    #
    # Fractional dimensions are temporarily protected
    # so "/" is not treated as a general separator.
    #
    # Examples:
    #   1/2"   -> 1<FRAC>2in
    #   3/4''  -> 3<FRAC>4in
    #   2"     -> 2in
    # --------------------------------------------------

    text = re.sub(
        r"(\d+)\s*/\s*(\d+)\s*(?:''|\"|”)",
        r"\1<FRAC>\2in",
        text,
    )

    # Handle a misplaced inch marker before the number.
    #
    # Example:
    #   " 1PVC -> 1in PVC
    #
    # This is a noisy reversal of the usual:
    #   1" PVC
    
    text = re.sub(
        r"(?:''|\"|”)\s*(\d+(?:\.\d+)?)\s*(?=[a-z])",
        r"\1in ",
        text,
    )

    text = re.sub(
        r"(\d+(?:\.\d+)?)\s*(?:''|\"|”)",
        r"\1in",
        text,
    )

    # --------------------------------------------------
    # General separators.
    #
    # Example:
    #   Hitex/Ball/Valve -> Hitex Ball Valve
    #
    # Fraction slashes are protected by <FRAC>.
    # --------------------------------------------------

    text = re.sub(
        r"[/_|,;:]+",
        " ",
        text,
    )

    # Restore protected fractional dimensions.
    text = text.replace(
        "<FRAC>",
        "/",
    )

    # Remove common order prefixes.
    text = re.sub(
        r"^\s*(item|product|order|qty)\s*[-:=]?\s*",
        "",
        text,
    )

    # Remove lightweight conversational noise.
    text = re.sub(
        r"\b(?:please|pls|need|urgent|send)\b",
        " ",
        text,
    )

    # Expand a deliberately small set of
    # general terminology aliases.
    for source, target in TERM_ALIASES.items():
        text = re.sub(
            rf"\b{re.escape(source)}\b",
            target,
            text,
        )

    # Remove separator-style hyphens surrounded by
    # whitespace while preserving ranges such as:
    # 25-38mm
    text = re.sub(
        r"\s+-\s+",
        " ",
        text,
    )

    # Collapse repeated whitespace.
    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def extract_numbers(text):
    """
    Extract numeric product attributes while preserving
    fractional and decimal inch dimensions.

    Examples:

        2"       -> {"2in"}
        1/2"     -> {"1/2in"}
        M8x75    -> {"8", "75"}
        304      -> {"304"}
        25-38mm  -> {"25", "38"}
    """

    text = normalize_text(text)

    values = set()

    # -----------------------------------
    # 1. Capture fractional inches first
    # -----------------------------------

    fraction_matches = re.findall(
        r"\b\d+/\d+in\b",
        text,
    )

    values.update(fraction_matches)

    # Remove them before looking for ordinary
    # inch measurements. Otherwise:
    #
    # 1/2in would also match 2in
    # 3/4in would also match 4in
    remaining = re.sub(
        r"\b\d+/\d+in\b",
        " ",
        text,
    )


    # -----------------------------------
    # 2. Capture normal/decimal inches
    # -----------------------------------

    inch_matches = re.findall(
        r"\b\d+(?:\.\d+)?in\b",
        remaining,
    )

    values.update(inch_matches)

    # Remove them before generic number extraction.
    remaining = re.sub(
        r"\b\d+(?:\.\d+)?in\b",
        " ",
        remaining,
    )


    # -----------------------------------
    # 3. Capture all other numbers
    # -----------------------------------

    for match in re.findall(
        r"\d+(?:\.\d+)?",
        remaining,
    ):
        values.add(match)

    return values