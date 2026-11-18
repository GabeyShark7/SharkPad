import re

from spellchecker import SpellChecker

from sharkpad.paths import app_data_path

spell = SpellChecker(distance=2)
ignored_words = set()
no_autocorrect = set()

spell.word_frequency.load_words([
    "lol", "lmao", "omg", "idk", "tbh", "brb", "btw", "fyi", "asap", "aka", "diy", "faq", "irl",
    "imo", "smh", "ngl", "jk", "ty", "thx", "pls", "plz", "ok", "okay", "gonna", "wanna", "gotta",
    "wifi", "app", "apps", "api", "apis", "cpu", "gpu", "ram", "usb", "pdf", "pdfs", "url", "urls",
    "html", "css", "email", "emails", "online", "offline", "login", "logout", "username", "website",
    "blog", "vlog", "podcast", "selfie", "emoji", "emojis", "meme", "memes", "youtube", "tiktok",
    "instagram", "google", "github", "python", "javascript", "java", "laptop", "smartphone",
    "covid", "etc", "vs", "eg", "ie", "mol", "lim", "sin", "cos", "tan", "dx", "dy", "kg", "km",
    "cm", "mm", "ml", "mg", "hz", "kj", "dna", "rna", "atp", "adp", "nadh", "nadph", "ph",
])

WORD_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")
CONTRACTION_ENDINGS = {"s", "t", "re", "ve", "ll", "d", "m"}


def normalize(word):
    return word.replace("’", "'").lower()


def is_known(word):
    """True if the word (any case, with or without an apostrophe ending) is spelled right."""
    w = normalize(word)
    if w in ignored_words or spell.known([w]):
        return True
    base, apostrophe, ending = w.partition("'")
    return bool(apostrophe) and ending in CONTRACTION_ENDINGS and (base in ignored_words or bool(spell.known([base])))


def skip_word(text, start, word):
    """Words we don't judge: single letters, acronyms, mixed case, and names."""
    letters = word.replace("'", "").replace("’", "")
    if len(letters) < 2:
        return True
    if letters.isupper():
        return True
    if any(ch.isupper() for ch in letters[1:]):
        return True
    if word[0].isupper():
        if normalize(word).endswith("'s"):
            return True
        before = text[:start].rstrip(" \t\"'(“‘[")
        if before and before[-1] not in ".!?:\n ":
            return True
    return False


def find_misspellings(text, cursor_pos=-1):
    """Return [(start, end, word)] for misspelled words. The word the cursor is in
    is left alone, so it isn't flagged while you're still typing it."""
    candidates = []
    for m in WORD_RE.finditer(text):
        word = m.group()
        if m.start() <= cursor_pos <= m.end() or skip_word(text, m.start(), word):
            continue
        candidates.append((m.start(), m.end(), word))

    verdict = {}
    for _s, _e, word in candidates:
        key = normalize(word)
        if key not in verdict:
            verdict[key] = not is_known(word)
    return [c for c in candidates if verdict[normalize(c[2])]]


def load_user_dictionary():
    try:
        with open(app_data_path("dictionary.txt"), encoding="utf-8") as f:
            words = [line.strip() for line in f if line.strip()]
        if words:
            spell.word_frequency.load_words(words)
    except OSError:
        pass


def add_to_dictionary(word):
    """Permanently add word to the spell checker (saved between sessions)."""
    w = normalize(word)
    spell.word_frequency.load_words([w])
    try:
        with open(app_data_path("dictionary.txt"), "a", encoding="utf-8") as f:
            f.write(w + "\n")
    except OSError:
        pass
