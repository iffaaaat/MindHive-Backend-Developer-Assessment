from src.normalizer import (
    normalize_text,
    extract_numbers,
)


def check(text, expected_normalized, expected_numbers):
    normalized = normalize_text(text)
    numbers = extract_numbers(text)

    print("=" * 70)
    print("ORIGINAL:", text)
    print("NORMALIZED:", normalized)
    print("NUMBERS:", numbers)

    assert normalized == expected_normalized, (
        f"\nNormalization failed"
        f"\nInput:    {text}"
        f"\nExpected: {expected_normalized}"
        f"\nActual:   {normalized}"
    )

    assert numbers == expected_numbers, (
        f"\nNumber extraction failed"
        f"\nInput:    {text}"
        f"\nExpected: {expected_numbers}"
        f"\nActual:   {numbers}"
    )

    print("PASS")
    print()


TESTS = [
    (
        'Bosco Ball Valve 2" PVC',
        "bosco ball valve 2in pvc",
        {"2in"},
    ),

    (
        'Bosco Ball Valve 1/2" PVC',
        "bosco ball valve 1/2in pvc",
        {"1/2in"},
    ),

    (
        "Hitex/Ball/Valve/3/4''/SS304",
        "hitex ball valve 3/4in stainless 304",
        {"3/4in", "304"},
    ),

    (
        "remax - hex - bolt - m8x75 - ZP",
        "remax hex bolt m8x75 zinc plated",
        {"8", "75"},
    ),

    (
        "Stallion Hose Clip 25-38mm Zinc",
        "stallion hose clip 25-38mm zinc",
        {"25", "38"},
    ),

    (
        "pls send Kanto Masking Tape 24Mm General",
        "kanto masking tape 24mm general",
        {"24"},
    ),

    # Regression: Malay colour synonym.
    (
        "Bosco Cable Tie 300mm putih",
        "bosco cable tie 300mm white",
        {"300"},
    ),

    # Regression: misplaced inch marker.
    (
        'Remax Ball Valve " 1PVC',
        "remax ball valve 1in pvc",
        {"1in"},
    ),
]


for text, expected_normalized, expected_numbers in TESTS:
    check(
        text,
        expected_normalized,
        expected_numbers,
    )


print("=" * 70)
print(f"ALL {len(TESTS)} NORMALIZER TESTS PASSED")