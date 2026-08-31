from ai_assistant.help import chunk_markdown

_DOC = """\
# InternStore help & policies

Intro paragraph that should be dropped.

## Delivery and shipping

We deliver within our service area. Standard delivery is 1-3 business
days.

## Returns and refunds

Non-perishable items can be returned within 14 days. Perishable items
cannot be returned for change-of-mind reasons.
"""


def test_chunk_markdown_one_chunk_per_section_drops_title_and_preamble():
    chunks = chunk_markdown(_DOC, "faq.md")

    assert [c["heading"] for c in chunks] == ["Delivery and shipping", "Returns and refunds"]
    assert all(c["source"] == "faq.md" for c in chunks)
    assert all(c["ordinal"] == 0 for c in chunks)
    # Hard-wrapped source lines are collapsed back into flowing prose.
    assert "1-3 business days." in chunks[0]["content"]
    assert "\n" not in chunks[0]["content"]
    assert "Intro paragraph" not in " ".join(c["content"] for c in chunks)


def test_chunk_ids_are_deterministic_across_runs():
    first = chunk_markdown(_DOC, "faq.md")
    second = chunk_markdown(_DOC, "faq.md")

    assert [c["chunk_id"] for c in first] == [c["chunk_id"] for c in second]
    # Distinct sections get distinct ids.
    assert first[0]["chunk_id"] != first[1]["chunk_id"]


def test_long_section_is_split_on_paragraph_boundaries():
    para = "word " * 120  # ~600 chars
    doc = f"## Big section\n\n{para}\n\n{para}\n\n{para}\n"

    chunks = chunk_markdown(doc, "faq.md")

    assert len(chunks) > 1
    assert [c["ordinal"] for c in chunks] == list(range(len(chunks)))
    assert all(c["heading"] == "Big section" for c in chunks)
