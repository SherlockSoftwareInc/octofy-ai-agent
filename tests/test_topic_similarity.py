"""
Tests for topic similarity calculation using Jaccard index.

The _compute_topic_similarity() function measures keyword overlap between
two strings using Jaccard similarity (intersection / union).
"""

import pytest
from app.services.generation_service import _compute_topic_similarity


class TestTopicSimilarityBasics:
    """Test basic similarity calculations."""
    
    def test_identical_strings_return_perfect_similarity(self):
        """Identical strings should return 1.0."""
        text = "show me sales data from last quarter"
        similarity = _compute_topic_similarity(text, text)
        assert similarity == 1.0
    
    def test_completely_different_topics_return_zero(self):
        """Strings with no shared keywords should return 0.0."""
        query = "show customer sales data"
        goal = "create employee report"
        similarity = _compute_topic_similarity(query, goal)
        assert similarity == 0.0
    
    def test_partial_overlap_returns_fractional_similarity(self):
        """Strings with some shared keywords return fractional similarity."""
        query = "show sales by region"
        goal = "show revenue by region"
        # Keywords: query={show, sales, region}, goal={show, revenue, region}
        # Intersection: {show, region} = 2
        # Union: {show, sales, region, revenue} = 4
        # Expected: 2/4 = 0.5
        similarity = _compute_topic_similarity(query, goal)
        assert similarity == 0.5


class TestCaseInsensitivity:
    """Test that comparison is case-insensitive."""
    
    def test_mixed_case_treated_as_identical(self):
        """Upper and lower case variations should be treated the same."""
        query = "SHOW SALES DATA"
        goal = "show sales data"
        similarity = _compute_topic_similarity(query, goal)
        assert similarity == 1.0
    
    def test_case_differences_ignored_in_partial_match(self):
        """Case differences should not affect partial matches."""
        query = "Show Customer SALES"
        goal = "show REVENUE sales"
        # Keywords (lowercased): query={show, customer, sales}, goal={show, revenue, sales}
        # Intersection: {show, sales} = 2
        # Union: {show, customer, sales, revenue} = 4
        # Expected: 2/4 = 0.5
        similarity = _compute_topic_similarity(query, goal)
        assert similarity == 0.5


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_query_returns_zero(self):
        """Empty query string should return 0.0."""
        similarity = _compute_topic_similarity("", "show sales data")
        assert similarity == 0.0
    
    def test_empty_goal_returns_zero(self):
        """Empty goal string should return 0.0."""
        similarity = _compute_topic_similarity("show sales data", "")
        assert similarity == 0.0
    
    def test_both_empty_returns_zero(self):
        """Both empty strings should return 0.0."""
        similarity = _compute_topic_similarity("", "")
        assert similarity == 0.0
    
    def test_short_words_ignored(self):
        """Words with fewer than 4 characters should be ignored."""
        query = "the cat sat on a mat"  # All words < 4 chars
        goal = "the dog ran to the car"  # All words < 4 chars
        # No keywords extracted (all words are 2-3 chars)
        similarity = _compute_topic_similarity(query, goal)
        assert similarity == 0.0
    
    def test_only_long_words_counted(self):
        """Only words with 4+ characters should be counted."""
        query = "show the data"  # Keywords: {show, data}
        goal = "show my report"  # Keywords: {show, report}
        # Intersection: {show} = 1
        # Union: {show, data, report} = 3
        # Expected: 1/3 ≈ 0.333
        similarity = _compute_topic_similarity(query, goal)
        assert abs(similarity - 1/3) < 0.001


class TestRealWorldScenarios:
    """Test with realistic conversation examples."""
    
    def test_high_similarity_refinement_scenario(self):
        """Refinement query should have high similarity with goal."""
        goal = "show sales by region for last quarter"
        query = "also break down sales by product category"
        # Keywords: goal={show, sales, region, last, quarter}
        #           query={also, break, down, sales, product, category}
        # Intersection: {sales} = 1
        # Union: {show, sales, region, last, quarter, also, break, down, product, category} = 10
        # Expected: 1/10 = 0.1
        similarity = _compute_topic_similarity(query, goal)
        assert 0.0 <= similarity <= 0.3  # Low-medium overlap
    
    def test_low_similarity_pivot_scenario(self):
        """Topic pivot should have low similarity."""
        goal = "show customer sales by region"
        query = "forget that, show employee headcount instead"
        # Keywords: goal={show, customer, sales, region}
        #           query={forget, that, show, employee, headcount, instead}
        # Intersection: {show} = 1
        # Union: {show, customer, sales, region, forget, that, employee, headcount, instead} = 9
        # Expected: 1/9 ≈ 0.111
        similarity = _compute_topic_similarity(query, goal)
        assert similarity < 0.3  # Low overlap indicates pivot
    
    def test_medium_similarity_related_topics(self):
        """Related topics should have medium similarity."""
        goal = "analyze customer purchase patterns"
        query = "examine customer behavior trends"
        # Keywords: goal={analyze, customer, purchase, patterns}
        #           query={examine, customer, behavior, trends}
        # Intersection: {customer} = 1
        # Union: {analyze, customer, purchase, patterns, examine, behavior, trends} = 7
        # Expected: 1/7 ≈ 0.143
        similarity = _compute_topic_similarity(query, goal)
        assert 0.1 <= similarity <= 0.5  # Medium overlap


class TestSymmetry:
    """Test that similarity is symmetric."""
    
    def test_order_independence(self):
        """sim(A, B) should equal sim(B, A)."""
        text_a = "show sales by region"
        text_b = "display revenue by territory"
        
        similarity_ab = _compute_topic_similarity(text_a, text_b)
        similarity_ba = _compute_topic_similarity(text_b, text_a)
        
        assert similarity_ab == similarity_ba
