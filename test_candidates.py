import itertools

import doc_unlocker


def test_common_passwords_precede_expansions():
    candidates, _ = doc_unlocker.build_candidates(None, 1, False, True, True)
    sample = list(itertools.islice(candidates, 500))
    assert "donald" in sample
    assert not any(candidate.startswith("LoveLove") for candidate in sample)
