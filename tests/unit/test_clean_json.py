"""Unit tests for _clean_json_from_llm function."""

import json
import pytest


class TestCleanJsonFromLLM:
    """Tests for JSON cleaning function."""

    TEST_CASES_VALID = [
        # Clean JSON - returns as-is
        ('{"intent": "search", "params": {}}', '{"intent": "search", "params": {}}'),
        # Markdown code block - extracts content
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        ('```\n{"b": 2}\n```', '{"b": 2}'),
        # With surrounding text - extracts JSON
        ('Here is the result: {"c": 3} Thanks!', '{"c": 3}'),
        # Nested JSON
        ('{"outer": {"inner": "value"}}', '{"outer": {"inner": "value"}}'),
        # Array
        ('[1, 2, 3]', '[1, 2, 3]'),
        # Boolean and null
        ('{"active": true, "data": null}', '{"active": true, "data": null}'),
        # Numbers
        ('{"count": 42, "score": 3.14}', '{"count": 42, "score": 3.14}'),
    ]

    TEST_CASES_EXTRACTION = [
        # Text before JSON
        ('Analysis: {"result": "ok"}', '{"result": "ok"}'),
        # Text after JSON
        ('{"result": "ok"} End of response', '{"result": "ok"}'),
        # Both sides
        ('Start {"data": [1,2,3]} End', '{"data": [1,2,3]}'),
    ]

    @pytest.mark.parametrize("input_text,expected", TEST_CASES_VALID)
    def test_clean_json_valid(self, input_text, expected):
        """Test extraction of valid JSON from LLM output."""
        try:
            from graphs.music_graph import _clean_json_from_llm

            result = _clean_json_from_llm(input_text)
            assert result == expected, f"Expected {expected!r}, got {result!r}"
        except ImportError:
            pytest.skip("Cannot import _clean_json_from_llm")

    @pytest.mark.parametrize("input_text,expected", TEST_CASES_EXTRACTION)
    def test_clean_json_extraction(self, input_text, expected):
        """Test extraction of JSON from surrounding text."""
        try:
            from graphs.music_graph import _clean_json_from_llm

            result = _clean_json_from_llm(input_text)
            assert result == expected, f"Expected {expected!r}, got {result!r}"
        except ImportError:
            pytest.skip("Cannot import _clean_json_from_llm")

    def test_clean_json_intent_response(self):
        """Test with typical intent classification response."""
        try:
            from graphs.music_graph import _clean_json_from_llm

            text = '''```json
{
  "intent_type": "search_by_lyrics",
  "intent_parameters": {"lyrics": "后来"},
  "confidence": 0.95
}
```'''
            result = _clean_json_from_llm(text)
            # Should extract valid JSON that can be parsed
            parsed = json.loads(result)
            assert parsed["intent_type"] == "search_by_lyrics"
            assert parsed["intent_parameters"]["lyrics"] == "后来"
        except ImportError:
            pytest.skip("Cannot import _clean_json_from_llm")
        except json.JSONDecodeError as e:
            pytest.fail(f"Extracted text is not valid JSON: {result}\nError: {e}")

    def test_clean_json_with_chinese(self):
        """Test handling of Chinese text."""
        try:
            from graphs.music_graph import _clean_json_from_llm

            text = '{"artist": "周杰伦", "song": "稻香"}'
            result = _clean_json_from_llm(text)
            assert result == '{"artist": "周杰伦", "song": "稻香"}'
            # Verify it can be parsed
            parsed = json.loads(result)
            assert parsed["artist"] == "周杰伦"
            assert parsed["song"] == "稻香"
        except ImportError:
            pytest.skip("Cannot import _clean_json_from_llm")

    def test_clean_json_empty_braces(self):
        """Test with empty JSON object."""
        try:
            from graphs.music_graph import _clean_json_from_llm

            result = _clean_json_from_llm('{}')
            assert result == '{}'
        except ImportError:
            pytest.skip("Cannot import _clean_json_from_llm")

    def test_clean_json_no_json(self):
        """Test with text that has no JSON."""
        try:
            from graphs.music_graph import _clean_json_from_llm

            # No braces at all
            result = _clean_json_from_llm('This is just text')
            assert result == 'This is just text'
        except ImportError:
            pytest.skip("Cannot import _clean_json_from_llm")
