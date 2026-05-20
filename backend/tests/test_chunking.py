"""
Unit tests for chunk_text — a pure function with no external dependencies.
"""
import pytest
from routes.ingest import chunk_text


def test_single_chunk_for_short_text():
    text = "word " * 10  # 10 words — well under chunk_size=512
    chunks = chunk_text(text.strip())
    assert len(chunks) == 1
    assert chunks[0] == text.strip()


def test_empty_string_produces_one_empty_chunk():
    chunks = chunk_text("")
    assert chunks == [""]


def test_long_text_produces_multiple_chunks():
    text = " ".join(f"word{i}" for i in range(600))  # 600 words
    chunks = chunk_text(text, chunk_size=512, overlap=64)
    assert len(chunks) > 1


def test_overlap_is_preserved():
    """The last `overlap` words of chunk N should appear at the start of chunk N+1."""
    words = [f"w{i}" for i in range(700)]
    text = " ".join(words)
    chunks = chunk_text(text, chunk_size=512, overlap=64)

    tail_of_first = chunks[0].split()[-64:]
    head_of_second = chunks[1].split()[:64]
    assert tail_of_first == head_of_second


def test_all_words_are_present():
    """No words should be dropped across all chunks."""
    words = [f"tok{i}" for i in range(800)]
    text = " ".join(words)
    chunks = chunk_text(text, chunk_size=256, overlap=32)

    # Collect all unique words across chunks; they must cover the original set
    recovered = set()
    for chunk in chunks:
        recovered.update(chunk.split())
    assert recovered == set(words)


def test_exact_chunk_size_boundary():
    """Exactly chunk_size words → exactly one chunk."""
    words = [f"x{i}" for i in range(512)]
    chunks = chunk_text(" ".join(words), chunk_size=512, overlap=64)
    assert len(chunks) == 1
    assert len(chunks[0].split()) == 512
