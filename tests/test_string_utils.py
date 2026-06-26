from src.plugins.chatbot.utils.string_utils import StringUtils


class TestCleanText:
    def test_removes_punctuation(self):
        assert StringUtils.clean_text("hello, world!") == "helloworld"

    def test_keeps_chinese(self):
        assert StringUtils.clean_text("你好，世界！") == "你好世界"

    def test_keeps_alphanumeric(self):
        assert StringUtils.clean_text("abc123") == "abc123"

    def test_keeps_underscore(self):
        assert StringUtils.clean_text("a_b_c") == "a_b_c"

    def test_empty_string(self):
        assert StringUtils.clean_text("") == ""

    def test_none_string(self):
        assert StringUtils.clean_text(None) == ""

    def test_mixed_content(self):
        assert StringUtils.clean_text("Hello你好123_测试!@#") == "Hello你好123_测试"


class TestLevenshteinDistance:
    def test_identical_strings(self):
        assert StringUtils.levenshtein_distance("hello", "hello") == 0

    def test_completely_different(self):
        assert StringUtils.levenshtein_distance("abc", "xyz") == 3

    def test_one_empty(self):
        assert StringUtils.levenshtein_distance("hello", "") == 5

    def test_both_empty(self):
        assert StringUtils.levenshtein_distance("", "") == 0

    def test_one_insertion(self):
        assert StringUtils.levenshtein_distance("cat", "cats") == 1

    def test_one_substitution(self):
        assert StringUtils.levenshtein_distance("cat", "cut") == 1

    def test_symmetric(self):
        assert StringUtils.levenshtein_distance("abc", "def") == StringUtils.levenshtein_distance("def", "abc")


class TestFuzzyMatch:
    def test_exact_match(self):
        assert StringUtils.fuzzy_match("hello world", "hello world") is True

    def test_keyword_contained(self):
        assert StringUtils.fuzzy_match("hello world", "world") is True

    def test_cleaned_match(self):
        assert StringUtils.fuzzy_match("hello, world!", "helloworld") is True

    def test_edit_distance_within_threshold(self):
        assert StringUtils.fuzzy_match("hello", "hallo") is True

    def test_edit_distance_exceeds_threshold(self):
        assert StringUtils.fuzzy_match("hello", "xyzzz") is False

    def test_empty_text(self):
        assert StringUtils.fuzzy_match("", "hello") is False

    def test_empty_keyword(self):
        assert StringUtils.fuzzy_match("hello", "") is False

    def test_custom_threshold(self):
        assert StringUtils.fuzzy_match("abcdef", "abcxyz", threshold=3) is True
        assert StringUtils.fuzzy_match("abcdef", "abcxyz", threshold=2) is False


class TestContainsAllChars:
    def test_all_chars_present(self):
        assert StringUtils.contains_all_chars("hello world", "world") is True

    def test_missing_char(self):
        assert StringUtils.contains_all_chars("hello", "xyz") is False

    def test_empty_text(self):
        assert StringUtils.contains_all_chars("", "a") is False

    def test_empty_keyword(self):
        assert StringUtils.contains_all_chars("hello", "") is True

    def test_order_doesnt_matter(self):
        assert StringUtils.contains_all_chars("abc", "cba") is True
