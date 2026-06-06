CHOSEONG = ["ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]
JUNGSEONG = ["ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅗ", "ㅘ", "ㅙ", "ㅚ", "ㅛ", "ㅜ", "ㅝ", "ㅞ", "ㅟ", "ㅠ", "ㅡ", "ㅢ", "ㅣ"]
JONGSEONG = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]

CONSONANTS = {"r": "ㄱ", "R": "ㄲ", "s": "ㄴ", "e": "ㄷ", "E": "ㄸ", "f": "ㄹ", "a": "ㅁ", "q": "ㅂ", "Q": "ㅃ", "t": "ㅅ", "T": "ㅆ", "d": "ㅇ", "w": "ㅈ", "W": "ㅉ", "c": "ㅊ", "z": "ㅋ", "x": "ㅌ", "v": "ㅍ", "g": "ㅎ"}
VOWELS = {"k": "ㅏ", "o": "ㅐ", "i": "ㅑ", "O": "ㅒ", "j": "ㅓ", "p": "ㅔ", "u": "ㅕ", "P": "ㅖ", "h": "ㅗ", "y": "ㅛ", "n": "ㅜ", "b": "ㅠ", "m": "ㅡ", "l": "ㅣ"}
COMPOUND_VOWELS = {("ㅗ", "ㅏ"): "ㅘ", ("ㅗ", "ㅐ"): "ㅙ", ("ㅗ", "ㅣ"): "ㅚ", ("ㅜ", "ㅓ"): "ㅝ", ("ㅜ", "ㅔ"): "ㅞ", ("ㅜ", "ㅣ"): "ㅟ", ("ㅡ", "ㅣ"): "ㅢ"}
DOUBLE_FINALS = {("ㄱ", "ㅅ"): "ㄳ", ("ㄴ", "ㅈ"): "ㄵ", ("ㄴ", "ㅎ"): "ㄶ", ("ㄹ", "ㄱ"): "ㄺ", ("ㄹ", "ㅁ"): "ㄻ", ("ㄹ", "ㅂ"): "ㄼ", ("ㄹ", "ㅅ"): "ㄽ", ("ㄹ", "ㅌ"): "ㄾ", ("ㄹ", "ㅍ"): "ㄿ", ("ㄹ", "ㅎ"): "ㅀ", ("ㅂ", "ㅅ"): "ㅄ"}
SPLIT_FINALS = {value: key for key, value in DOUBLE_FINALS.items()}


def compose(initial: str, vowel: str, final: str = "") -> str:
    return chr(0xAC00 + CHOSEONG.index(initial) * 588 + JUNGSEONG.index(vowel) * 28 + JONGSEONG.index(final))


def decompose(char: str) -> tuple[str, str, str] | None:
    code = ord(char) - 0xAC00
    if code < 0 or code > 11171:
        return None
    return CHOSEONG[code // 588], JUNGSEONG[(code % 588) // 28], JONGSEONG[code % 28]


def apply_hangul_key(text: str, key: str) -> str:
    consonant = CONSONANTS.get(key)
    vowel = VOWELS.get(key)
    if not consonant and not vowel:
        return text + key
    if not text:
        return consonant or vowel or key
    last = text[-1]
    prefix = text[:-1]
    syllable = decompose(last)
    if vowel:
        if syllable:
            initial, current_vowel, final = syllable
            if final:
                if final in SPLIT_FINALS:
                    left_final, next_initial = SPLIT_FINALS[final]
                    return prefix + compose(initial, current_vowel, left_final) + compose(next_initial, vowel)
                return prefix + compose(initial, current_vowel) + compose(final, vowel)
            combined = COMPOUND_VOWELS.get((current_vowel, vowel))
            return prefix + compose(initial, combined) if combined else text + vowel
        if last in CHOSEONG:
            return prefix + compose(last, vowel)
        combined = COMPOUND_VOWELS.get((last, vowel))
        return prefix + combined if combined else text + vowel
    if syllable:
        initial, current_vowel, final = syllable
        if not final and consonant in JONGSEONG:
            return prefix + compose(initial, current_vowel, consonant)
        combined = DOUBLE_FINALS.get((final, consonant))
        return prefix + compose(initial, current_vowel, combined) if combined else text + consonant
    return text + consonant
