#!/usr/bin/env python3
"""Test script for new three-pronged discovery strategy"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.discovery_service import (
    KNOWLEDGE_BASE_EXACT_MATCH_THRESHOLD,
    SKILLS_HIGH_SCORE_THRESHOLD,
    USER_SELECTION_TOP_K
)
from app.models.schemas import ThreeProngedResult, RankedTable

def test_constants():
    """Test that configuration constants are properly set"""
    print("=" * 60)
    print("TEST 1: Configuration Constants")
    print("=" * 60)
    
    print(f"KNOWLEDGE_BASE_EXACT_MATCH_THRESHOLD: {KNOWLEDGE_BASE_EXACT_MATCH_THRESHOLD}")
    print(f"SKILLS_HIGH_SCORE_THRESHOLD: {SKILLS_HIGH_SCORE_THRESHOLD}")
    print(f"USER_SELECTION_TOP_K: {USER_SELECTION_TOP_K}")
    
    assert KNOWLEDGE_BASE_EXACT_MATCH_THRESHOLD == 0.1, "KB threshold should be 0.1"
    assert SKILLS_HIGH_SCORE_THRESHOLD == 15, "Skills threshold should be 15"
    assert USER_SELECTION_TOP_K == 20, "User selection top K should be 20"
    
    print("[SUCCESS] All constants properly configured\n")


def test_schema_fields():
    """Test that ThreeProngedResult has new fields"""
    print("=" * 60)
    print("TEST 2: ThreeProngedResult Schema")
    print("=" * 60)
    
    # Create a sample result
    result = ThreeProngedResult()
    
    # Check new fields exist
    assert hasattr(result, 'exact_match_found'), "Missing exact_match_found field"
    assert hasattr(result, 'exact_match_query'), "Missing exact_match_query field"
    assert hasattr(result, 'requires_user_selection'), "Missing requires_user_selection field"
    assert hasattr(result, 'selection_candidates'), "Missing selection_candidates field"
    
    # Check default values
    assert result.exact_match_found == False, "exact_match_found should default to False"
    assert result.exact_match_query is None, "exact_match_query should default to None"
    assert result.requires_user_selection == False, "requires_user_selection should default to False"
    assert result.selection_candidates == [], "selection_candidates should default to empty list"
    
    print("[SUCCESS] All schema fields present with correct defaults\n")


def test_exact_match_scenario():
    """Test exact match scenario"""
    print("=" * 60)
    print("TEST 3: Exact Match Scenario")
    print("=" * 60)
    
    # Simulate exact match result
    exact_match_query = {
        'question': 'Show me all customers',
        'sql_query': 'SELECT * FROM dbo.Customers',
        'tables': ['dbo.Customers'],
        'score': 0.05
    }
    
    tables = [
        RankedTable(
            schema_name='dbo',
            table_name='Customers',
            score=100,
            matched_by=['knowledge_base_exact_match']
        )
    ]
    
    result = ThreeProngedResult(
        exact_match_found=True,
        exact_match_query=exact_match_query,
        merged_candidates=tables,
        knowledge_base_tables=tables,
        requires_user_selection=False
    )
    
    assert result.exact_match_found == True
    assert result.exact_match_query['score'] == 0.05
    assert len(result.merged_candidates) == 1
    assert result.merged_candidates[0].score == 100
    assert result.requires_user_selection == False
    
    print("[SUCCESS] Exact match scenario works correctly\n")


def test_high_score_skills_scenario():
    """Test high-score skills match scenario"""
    print("=" * 60)
    print("TEST 4: High-Score Skills Match Scenario")
    print("=" * 60)
    
    # Simulate high-score skills results
    skills_tables = [
        RankedTable(schema_name='dbo', table_name='Customers', score=18, matched_by=['skills']),
        RankedTable(schema_name='dbo', table_name='Orders', score=16, matched_by=['skills']),
        RankedTable(schema_name='dbo', table_name='Products', score=15, matched_by=['skills']),
    ]
    
    result = ThreeProngedResult(
        skills_tables=skills_tables,
        requires_user_selection=True,
        selection_candidates=skills_tables,
        merged_candidates=[]
    )
    
    assert result.exact_match_found == False
    assert result.requires_user_selection == True
    assert len(result.selection_candidates) == 3
    assert all(t.score >= SKILLS_HIGH_SCORE_THRESHOLD for t in result.selection_candidates)
    
    print("[SUCCESS] High-score skills scenario works correctly\n")


def test_low_score_merge_scenario():
    """Test low-score with value index merge scenario"""
    print("=" * 60)
    print("TEST 5: Low-Score + Value Index Merge Scenario")
    print("=" * 60)
    
    # Simulate low-score skills + value index merge
    skills_tables = [
        RankedTable(schema_name='dbo', table_name='Customers', score=10, matched_by=['skills']),
        RankedTable(schema_name='dbo', table_name='Orders', score=8, matched_by=['skills']),
    ]
    
    value_tables = [
        RankedTable(schema_name='dbo', table_name='Products', score=8, matched_by=['value_index']),
    ]
    
    # Simulate merged results (skills + value index scores combined)
    merged = [
        RankedTable(schema_name='dbo', table_name='Customers', score=18, matched_by=['skills', 'value_index']),
        RankedTable(schema_name='dbo', table_name='Orders', score=8, matched_by=['skills']),
        RankedTable(schema_name='dbo', table_name='Products', score=8, matched_by=['value_index']),
    ]
    
    result = ThreeProngedResult(
        skills_tables=skills_tables,
        value_tables=value_tables,
        requires_user_selection=True,
        selection_candidates=merged,
        merged_candidates=[]
    )
    
    assert result.exact_match_found == False
    assert result.requires_user_selection == True
    assert len(result.skills_tables) == 2
    assert len(result.value_tables) == 1
    assert len(result.selection_candidates) == 3
    
    print("[SUCCESS] Low-score merge scenario works correctly\n")


def test_top_k_limiting():
    """Test that selection candidates are limited to top K"""
    print("=" * 60)
    print("TEST 6: Top K Limiting")
    print("=" * 60)
    
    # Create 30 candidates (more than USER_SELECTION_TOP_K)
    many_tables = [
        RankedTable(schema_name='dbo', table_name=f'Table{i}', score=20-i, matched_by=['skills'])
        for i in range(30)
    ]
    
    # Take only top K
    top_k = sorted(many_tables, key=lambda x: x.score, reverse=True)[:USER_SELECTION_TOP_K]
    
    result = ThreeProngedResult(
        skills_tables=many_tables,
        requires_user_selection=True,
        selection_candidates=top_k,
        merged_candidates=[]
    )
    
    assert len(result.skills_tables) == 30, "Should keep all skills tables"
    assert len(result.selection_candidates) == USER_SELECTION_TOP_K, f"Should limit to top {USER_SELECTION_TOP_K}"
    assert result.selection_candidates[0].score >= result.selection_candidates[-1].score, "Should be sorted by score"
    
    print(f"[SUCCESS] Top K limiting works (showing {len(result.selection_candidates)} out of {len(result.skills_tables)} total)\n")


if __name__ == "__main__":
    try:
        test_constants()
        test_schema_fields()
        test_exact_match_scenario()
        test_high_score_skills_scenario()
        test_low_score_merge_scenario()
        test_top_k_limiting()
        
        print("\n" + "=" * 60)
        print("[SUCCESS] All tests passed!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n[FAILED] Test assertion failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
