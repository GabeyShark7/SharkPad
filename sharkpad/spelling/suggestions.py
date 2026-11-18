from sharkpad.spelling.words import ignored_words, is_known, no_autocorrect, normalize, skip_word, spell

COMMON_TYPOS = {
    "i": "I", "im": "I'm", "ive": "I've", "ill": None, "id": None, "alot": "a lot",
    "teh": "the", "hte": "the", "wich": "which", "whihc": "which", "becuase": "because",
    "becasue": "because", "beacuse": "because", "recieve": "receive", "recieved": "received",
    "beleive": "believe", "freind": "friend", "thier": "their", "untill": "until",
    "occured": "occurred", "seperate": "separate", "definately": "definitely", "wierd": "weird",
    "tommorow": "tomorrow", "tomorow": "tomorrow", "truely": "truly", "goverment": "government",
    "enviroment": "environment", "accomodate": "accommodate", "acheive": "achieve",
    "arguement": "argument", "calender": "calendar", "concious": "conscious", "existance": "existence",
    "foriegn": "foreign", "independant": "independent", "occurence": "occurrence",
    "posession": "possession", "publically": "publicly", "succesful": "successful",
    "suprise": "surprise", "tounge": "tongue", "wether": "whether", "writting": "writing",
}

AUTOCORRECT_MIN_FREQ = 500
AUTOCORRECT_RATIO = 3
_INDEX_MIN_FREQ = 2000

_contractions = None
_near_index = None


def _deletes(word, depth=2):
    found, frontier = {word}, {word}
    for _ in range(depth):
        frontier = {w[:i] + w[i + 1:] for w in frontier for i in range(len(w))}
        found |= frontier
    return found


def _edit_distance(a, b):
    if abs(len(a) - len(b)) > 2:
        return 3
    prev2, prev = None, list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        prev2, prev = prev, cur
    return prev[-1]


def build_word_indexes():
    global _contractions, _near_index
    words = spell.word_frequency.dictionary
    _contractions = {c.replace("'", ""): c for c in words if "'" in c}
    index = {}
    for w, f in list(words.items()):
        if f >= _INDEX_MIN_FREQ and len(w) >= 4 and w.isalpha():
            for d in _deletes(w):
                index.setdefault(d, []).append(w)
    _near_index = index


def _two_edits_away(w):
    if _near_index is None:
        return set()
    found = set()
    for d in _deletes(w):
        found.update(_near_index.get(d, ()))
    return {c for c in found if _edit_distance(w, c) <= 2}


def _apostrophe_fix(w):
    """dont -> don't, theyre -> they're (or None)."""
    return _contractions.get(w) if _contractions else None


def _transpositions(w):
    return {w[:i] + w[i + 1] + w[i] + w[i + 2:] for i in range(len(w) - 1)}


def _match_case(original, fix):
    if original[:1].isupper() and fix[:1].islower():
        return fix[:1].upper() + fix[1:]
    return fix


def suggestions(word, limit=6):
    """Best corrections first: the most common real words that are closest."""
    w = normalize(word)
    ranked = []

    for i in range(1, len(w)):
        with_apostrophe = w[:i] + "'" + w[i:]
        if spell.known([with_apostrophe]):
            ranked.append(with_apostrophe)

    freq = spell.word_frequency.dictionary
    others = (spell.known(spell.edit_distance_1(w)) or _two_edits_away(w)) - {w}
    ranked += sorted(others, key=lambda c: -freq.get(c, 0))

    result = list(dict.fromkeys(ranked))[:limit]
    if word[:1].isupper():
        result = [s[:1].upper() + s[1:] for s in result]
    return result


def autocorrection(text, start, word):
    """The confident fix for a just-typed word, or None to leave it alone.

    Only fixes obvious typos into common words. Anything uncertain is left
    for the red underline and right-click suggestions instead.
    """
    w = normalize(word)
    if w in no_autocorrect or w in ignored_words:
        return None
    if w in COMMON_TYPOS:
        fix = COMMON_TYPOS[w]
        return _match_case(word, fix) if fix else None
    if skip_word(text, start, word) or is_known(word) or not w.isalpha():
        return None

    fix = _apostrophe_fix(w)
    if fix:
        return _match_case(word, fix)

    freq = spell.word_frequency.dictionary
    swaps = spell.known(_transpositions(w))

    if len(w) <= 4:
        cands = {c: freq[c] for c in swaps}
    else:
        d1 = spell.edit_distance_1(w)
        cands = {c: freq[c] for c in spell.known(d1)}
        for e in d1:
            f = _apostrophe_fix(e)
            if f:
                cands[f] = max(cands.get(f, 0), freq.get(f, 0))

    need = AUTOCORRECT_MIN_FREQ
    if not cands and len(w) >= 6:
        cands = {c: freq[c] for c in _two_edits_away(w)}
        need *= 4
    if not cands:
        return None

    score = {c: f * (5 if c in swaps else 1) for c, f in cands.items()}
    ranked = sorted(score.values(), reverse=True)
    best = max(score, key=score.get)
    runner_up = ranked[1] if len(ranked) > 1 else 0
    if cands[best] < need or score[best] < AUTOCORRECT_RATIO * runner_up:
        return None
    return _match_case(word, best)
