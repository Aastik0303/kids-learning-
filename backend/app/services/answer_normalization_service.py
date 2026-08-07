import re
import string


NUMBER_WORDS = {
    "zero": "0",
    "oh": "0",
    "one": "1",
    "won": "1",
    "two": "2",
    "too": "2",
    "to": "2",
    "three": "3",
    "tree": "3",
    "free": "3",
    "four": "4",
    "for": "4",
    "fore": "4",
    "five": "5",
    "fife": "5",
    "six": "6",
    "sicks": "6",
    "seven": "7",
    "eight": "8",
    "ate": "8",
    "nine": "9",
    "nein": "9",
    "ten": "10",
}

ARTICLES = {"a", "an", "the"}
FILLERS = {
    "um", "uh", "mmm", "hmm", "please", "answer", "is", "it", "its", "it's",
    "number", "letter", "colour", "color", "one", "i", "think", "maybe",
    "that", "this", "like", "well", "so", "just", "gonna", "wanna",
}
INTENT_PREFIXES = {"i think it's", "i think its", "i think", "maybe it's", "maybe its", "it is", "it's", "that one is"}

COLOURS = {"red", "blue", "yellow", "green", "orange", "purple", "pink", "white", "black", "brown"}
SHAPES = {"circle", "square", "triangle", "rectangle", "star", "diamond", "oval", "heart"}

# Map common child speech mis-recognitions to correct terms
SPEECH_CORRECTIONS = {
    "rectngle": "rectangle",
    "rectangl": "rectangle",
    "rectange": "rectangle",
    "trangel": "triangle",
    "trangle": "triangle",
    "triangel": "triangle",
    "trinagle": "triangle",
    "sqare": "square",
    "squar": "square",
    "squere": "square",
    "circl": "circle",
    "circel": "circle",
    "sircle": "circle",
    "circul": "circle",
    "hart": "heart",
    "stare": "star",
    "starr": "star",
    "ovel": "oval",
    "diamund": "diamond",
    "dimond": "diamond",
    "dimand": "diamond",
    "perple": "purple",
    "purpel": "purple",
    "purpl": "purple",
    "orang": "orange",
    "oranje": "orange",
    "yello": "yellow",
    "yelloe": "yellow",
    "gren": "green",
    "grean": "green",
    "bloo": "blue",
    "blew": "blue",
    "whit": "white",
    "wite": "white",
    "blak": "black",
    "brun": "brown",
    "braun": "brown",
    "pnik": "pink",
    "aple": "apple",
    "appel": "apple",
    "boll": "ball",
    "kat": "cat",
    "dogg": "dog",
    "fsh": "fish",
    "eg": "egg",
}


def _clean(text: str) -> str:
    cleaned = text.strip().lower()
    cleaned = cleaned.translate(str.maketrans({mark: " " for mark in string.punctuation}))
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _singular(token: str) -> str:
    if token.endswith("ies"):
        return token[:-3] + "y"
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token


def _replace_number_words(tokens: list[str]) -> list[str]:
    return [NUMBER_WORDS.get(token, token) for token in tokens]


def _apply_speech_corrections(tokens: list[str]) -> list[str]:
    """Fix common speech recognition errors for child speech."""
    return [SPEECH_CORRECTIONS.get(token, token) for token in tokens]


def _strip_common_phrasing(tokens: list[str]) -> list[str]:
    while tokens and tokens[0] in {"it", "its", "the", "a", "an", "answer", "i"}:
        tokens.pop(0)
    while tokens and tokens[0] in {"is", "says", "say", "think", "believe", "see"}:
        tokens.pop(0)
    return [token for token in tokens if token not in {"please", "um", "uh", "mmm", "hmm"}]


def _strip_intent_phrases(text: str) -> str:
    """Remove common child intent phrases like 'I think it's' from the start."""
    lowered = text.lower().strip()
    for prefix in sorted(INTENT_PREFIXES, key=len, reverse=True):
        if lowered.startswith(prefix):
            return text[len(prefix):].strip()
    return text


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def _fuzzy_match_token(token: str, candidates: set[str], max_distance: int = 2) -> str:
    """Try to fuzzy-match a token against a set of candidate words."""
    if token in candidates:
        return token
    if len(token) < 3:
        return token
    best_match = token
    best_distance = max_distance + 1
    for candidate in candidates:
        if abs(len(token) - len(candidate)) > max_distance:
            continue
        distance = _levenshtein_distance(token, candidate)
        if distance < best_distance:
            best_distance = distance
            best_match = candidate
    return best_match if best_distance <= max_distance else token


def normalize_answer(text: str, answer_type: str | None = None) -> str:
    """Normalize nursery speech while preserving phrase answers."""
    cleaned = _clean(text)
    if not cleaned:
        return ""

    # Strip intent phrases first
    cleaned = _strip_intent_phrases(cleaned)
    if not cleaned:
        return ""

    tokens = _strip_common_phrasing(cleaned.split())
    tokens = _replace_number_words(tokens)
    tokens = _apply_speech_corrections(tokens)
    tokens = [_singular(token) for token in tokens if token not in ARTICLES]

    if not tokens:
        return ""

    answer_type = (answer_type or "").lower()

    if len(tokens) == 1:
        # Try fuzzy matching for single-token answers
        if answer_type in {"identify_colour"}:
            return _fuzzy_match_token(tokens[0], COLOURS)
        if answer_type in {"identify_shape"}:
            return _fuzzy_match_token(tokens[0], SHAPES)
        return tokens[0]

    if answer_type in {"select_number", "count_objects"} or tokens[0] == "number":
        numeric = [token for token in tokens if token.isdigit()]
        if numeric:
            return numeric[-1]

    if answer_type in {"select_letter"} or tokens[0] == "letter":
        letters = [token for token in tokens if len(token) == 1 and token.isalpha()]
        if letters:
            return letters[-1]

    if answer_type in {"identify_colour"}:
        colours = [_fuzzy_match_token(token, COLOURS) for token in tokens]
        matched = [token for token in colours if token in COLOURS]
        if matched:
            return matched[-1]

    if answer_type in {"identify_shape"}:
        shapes = [_fuzzy_match_token(token, SHAPES) for token in tokens]
        matched = [token for token in shapes if token in SHAPES]
        if matched:
            return matched[-1]

    # Common voice phrases like "the red one" should match simple one-word answers.
    meaningful = [token for token in tokens if token not in FILLERS]
    if len(meaningful) == 1:
        return meaningful[0]

    return " ".join(meaningful or tokens)


def answers_match(child_answer: str, correct_answer: str, answer_type: str | None = None) -> bool:
    normalized_child = normalize_answer(child_answer, answer_type)
    normalized_correct = normalize_answer(correct_answer, answer_type)
    if normalized_child == normalized_correct:
        return True
    # Fuzzy fallback: if normalized answers are very close (distance <= 1), accept
    if len(normalized_child) >= 3 and len(normalized_correct) >= 3:
        if _levenshtein_distance(normalized_child, normalized_correct) <= 1:
            return True
    return False
