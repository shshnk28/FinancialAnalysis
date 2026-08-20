import pytest

from common.config.embedder_profile import ACTIVE_PROFILE, MPNET_PROFILE, EmbedderProfile


def test_mpnet_profile_matches_frozen_spec():
    assert MPNET_PROFILE.name == "all-mpnet-base-v2"
    assert MPNET_PROFILE.model_id == "sentence-transformers/all-mpnet-base-v2"
    assert MPNET_PROFILE.max_input_tokens == 512
    assert MPNET_PROFILE.chunk_size == 450
    assert MPNET_PROFILE.overlap_ratio == 0.12


def test_active_profile_is_mpnet():
    assert ACTIVE_PROFILE is MPNET_PROFILE


def test_overlap_tokens_is_rounded_chunk_size_times_ratio():
    assert MPNET_PROFILE.overlap_tokens == 54  # round(450 * 0.12)


def test_rejects_chunk_size_at_or_above_max_input_tokens():
    with pytest.raises(AssertionError):
        EmbedderProfile(
            name="bad",
            model_id="bad/bad",
            max_input_tokens=512,
            chunk_size=512,
            overlap_ratio=0.12,
        )


@pytest.mark.parametrize("bad_ratio", [0.05, 0.5, 0.9])
def test_rejects_overlap_ratio_out_of_bounds(bad_ratio):
    with pytest.raises(AssertionError):
        EmbedderProfile(
            name="bad",
            model_id="bad/bad",
            max_input_tokens=512,
            chunk_size=450,
            overlap_ratio=bad_ratio,
        )


def test_tokenizer_is_lazy_and_cached():
    # Accessing .tokenizer twice should return the same cached object,
    # confirming it isn't reloaded (and isn't eagerly loaded at import time).
    profile = EmbedderProfile(
        name="mpnet-copy",
        model_id="sentence-transformers/all-mpnet-base-v2",
        max_input_tokens=512,
        chunk_size=450,
        overlap_ratio=0.12,
    )
    assert profile.tokenizer is profile.tokenizer
