"""
Insight Generation Service

Detects patterns, trends, and anomalies in data profiles.
Uses hybrid approach: rule-based detection + LLM prioritization for cost optimization.
"""

import pandas as pd
import json
from typing import List, Dict, Any, Optional
from app.models.schemas import DataProfile, Insight, ColumnProfile
from app.services.llm_service import get_llm_service
from app.utils.sanitization import prepare_user_query_for_llm
import logging

logger = logging.getLogger(__name__)


class InsightService:
    """Service for generating actionable insights from data profiles"""
    
    # Configuration
    MAX_INSIGHTS_TO_RETURN = 5
    MIN_OUTLIER_COUNT = 3  # Minimum outliers to report
    HIGH_NULL_THRESHOLD = 20.0  # Percentage
    SPARSE_CATEGORY_THRESHOLD = 50.0  # If one value has >50%
    STRONG_CORRELATION_THRESHOLD = 0.7  # |r| > 0.7
    
    def __init__(self):
        self.llm_service = get_llm_service()
    
    def generate_insights(
        self,
        profile: DataProfile,
        user_query: str,
        df_sample: Optional[pd.DataFrame] = None
    ) -> List[Insight]:
        """
        Generate top insights using hybrid approach:
        1. Rule-based detection → candidate insights (fast, no LLM)
        2. LLM prioritization → top 3-5 insights (single LLM call)
        
        Args:
            profile: DataProfile from profiling service
            user_query: Original user query for context
            df_sample: Optional DataFrame sample for additional context
            
        Returns:
            List of top 5 insights sorted by relevance
        """
        try:
            # Step 1: Detect patterns using rules (no LLM)
            candidates = self._detect_patterns_rules(profile, df_sample)
            
            logger.info(f"Detected {len(candidates)} candidate insights")
            
            # If no candidates or few candidates, return as-is
            if len(candidates) <= self.MAX_INSIGHTS_TO_RETURN:
                return candidates
            
            # Step 2: Use LLM to prioritize (single call)
            prioritized = self._prioritize_with_llm(candidates, user_query, profile)
            
            return prioritized[:self.MAX_INSIGHTS_TO_RETURN]
            
        except Exception as e:
            logger.error(f"Error generating insights: {str(e)}")
            return []
    
    def _detect_patterns_rules(
        self,
        profile: DataProfile,
        df_sample: Optional[pd.DataFrame] = None
    ) -> List[Insight]:
        """
        Rule-based pattern detection (NO LLM calls).
        
        Detects:
        - Outliers in numeric columns
        - High correlations between columns
        - Missing data issues
        - Sparse categorical distributions
        - Datetime-based trends
        
        Returns:
            List of candidate insights (unranked)
        """
        insights = []
        
        # Check each column
        for col in profile.columns:
            col_name = col.column_name
            
            # Numeric column insights
            if col.numeric_stats:
                stats = col.numeric_stats
                
                # Outlier detection
                if len(stats.outliers) >= self.MIN_OUTLIER_COUNT:
                    insights.append(Insight(
                        insight_type="outlier",
                        title=f"Outliers detected in {col_name}",
                        description=f"Found {len(stats.outliers)} outliers in '{col_name}' "
                                  f"(range: {stats.min:.2f} to {stats.max:.2f}, "
                                  f"mean: {stats.mean:.2f}). "
                                  f"Sample outliers: {stats.outliers[:3]}",
                        severity="warning",
                        related_columns=[col_name],
                        confidence=0.9
                    ))
                
                # High null percentage
                if stats.null_percentage > self.HIGH_NULL_THRESHOLD:
                    insights.append(Insight(
                        insight_type="missing_data",
                        title=f"High missing data in {col_name}",
                        description=f"'{col_name}' has {stats.null_percentage:.1f}% missing values "
                                  f"({stats.null_count} out of {profile.row_count} rows). "
                                  f"Consider imputation or investigation.",
                        severity="warning" if stats.null_percentage > 50 else "info",
                        related_columns=[col_name],
                        confidence=1.0
                    ))
                
                # Zero variance (all same value)
                if stats.std == 0 and stats.null_percentage < 100:
                    insights.append(Insight(
                        insight_type="distribution",
                        title=f"{col_name} has no variation",
                        description=f"All values in '{col_name}' are identical ({stats.mean:.2f}). "
                                  f"This column may not be useful for analysis.",
                        severity="info",
                        related_columns=[col_name],
                        confidence=1.0
                    ))
            
            # Categorical column insights
            if col.categorical_stats:
                stats = col.categorical_stats
                
                # Sparse category (one value dominates)
                if stats.top_values and len(stats.top_values) > 0:
                    top_pct = stats.top_values[0]['percentage']
                    if top_pct > self.SPARSE_CATEGORY_THRESHOLD:
                        insights.append(Insight(
                            insight_type="distribution",
                            title=f"{col_name} is heavily skewed",
                            description=f"'{col_name}' is dominated by '{stats.top_values[0]['value']}' "
                                      f"({top_pct:.1f}% of values). "
                                      f"Distribution is highly imbalanced.",
                            severity="info",
                            related_columns=[col_name],
                            confidence=0.8
                        ))
                
                # High cardinality
                if stats.unique_count > profile.row_count * 0.9:
                    insights.append(Insight(
                        insight_type="distribution",
                        title=f"{col_name} has very high cardinality",
                        description=f"'{col_name}' has {stats.unique_count} unique values "
                                  f"out of {profile.row_count} rows (~{(stats.unique_count/profile.row_count*100):.0f}%). "
                                  f"Might be an identifier or unique key.",
                        severity="info",
                        related_columns=[col_name],
                        confidence=0.7
                    ))
                
                # High null percentage
                if stats.null_percentage > self.HIGH_NULL_THRESHOLD:
                    insights.append(Insight(
                        insight_type="missing_data",
                        title=f"High missing data in {col_name}",
                        description=f"'{col_name}' has {stats.null_percentage:.1f}% missing values. "
                                  f"Consider investigation or imputation.",
                        severity="warning" if stats.null_percentage > 50 else "info",
                        related_columns=[col_name],
                        confidence=1.0
                    ))
        
        # Correlation insights
        if profile.correlations:
            for corr in profile.correlations:
                strength = "strong" if abs(corr['correlation']) > self.STRONG_CORRELATION_THRESHOLD else "moderate"
                direction = "positive" if corr['correlation'] > 0 else "negative"
                
                insights.append(Insight(
                    insight_type="correlation",
                    title=f"{strength.capitalize()} {direction} correlation",
                    description=f"'{corr['col1']}' and '{corr['col2']}' have a {strength} "
                              f"{direction} correlation (r={corr['correlation']:.2f}). "
                              f"These variables move together.",
                    severity="info",
                    related_columns=[corr['col1'], corr['col2']],
                    confidence=0.85
                ))
        
        # Datetime insights
        if profile.has_datetime and len(profile.datetime_columns) > 0:
            insights.append(Insight(
                insight_type="trend",
                title="Time-based data detected",
                description=f"Found datetime column(s): {', '.join(profile.datetime_columns)}. "
                          f"Consider time series analysis or trend visualization.",
                severity="info",
                related_columns=profile.datetime_columns,
                confidence=0.9
            ))
        
        # Recommendation based on profiling level
        if profile.profiling_level == "basic" and profile.row_count < 10000:
            insights.append(Insight(
                insight_type="recommendation",
                title="Deeper analysis available",
                description=f"Dataset has {profile.row_count} rows. "
                          f"You can request deeper profiling for outlier detection and correlations.",
                severity="info",
                related_columns=[],
                confidence=0.6
            ))
        
        return insights
    
    def _prioritize_with_llm(
        self,
        candidates: List[Insight],
        user_query: str,
        profile: DataProfile
    ) -> List[Insight]:
        """
        Use LLM to rank candidate insights by relevance to user query.
        
        Single LLM call to optimize cost.
        
        Args:
            candidates: List of candidate insights
            user_query: Original user query
            profile: DataProfile for context
            
        Returns:
            Sorted list of insights (most relevant first)
        """
        try:
            # Sanitize user query to prevent prompt injection
            safe_user_query = prepare_user_query_for_llm(user_query)
            
            # Build prompt with candidate insights
            insight_descriptions = []
            for i, insight in enumerate(candidates):
                insight_descriptions.append(
                    f"{i}. [{insight.insight_type}] {insight.title}: {insight.description[:100]}..."
                )
            
            prompt = f"""Given the user's query and data insights below, rank the top {self.MAX_INSIGHTS_TO_RETURN} most relevant and actionable insights.

User Query: "{safe_user_query}"

Dataset: {profile.row_count} rows, {profile.column_count} columns

Candidate Insights:
{chr(10).join(insight_descriptions)}

Return ONLY a JSON array of insight indices in priority order (most relevant first).
Example: [3, 0, 7, 1, 5]

Consider:
1. Direct relevance to user's question
2. Actionability (can user do something about it?)
3. Significance (how important is this finding?)
4. Surprise factor (is this unexpected?)

JSON array of indices:"""

            # Call LLM
            response = self.llm_service.chat(prompt, temperature=0.3)
            
            # Parse response
            try:
                # Extract JSON array from response
                response = response.strip()
                if response.startswith("```"):
                    # Remove markdown code blocks
                    response = response.replace("```json", "").replace("```", "").strip()
                
                ranked_indices = json.loads(response)
                
                # Validate and reorder insights
                prioritized = []
                for idx in ranked_indices:
                    if 0 <= idx < len(candidates):
                        prioritized.append(candidates[idx])
                
                # Add remaining candidates if we got less than requested
                if len(prioritized) < self.MAX_INSIGHTS_TO_RETURN:
                    for insight in candidates:
                        if insight not in prioritized:
                            prioritized.append(insight)
                            if len(prioritized) >= self.MAX_INSIGHTS_TO_RETURN:
                                break
                
                return prioritized
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM response, using default order: {e}")
                # Fallback: sort by severity and confidence
                return sorted(candidates, 
                            key=lambda x: (x.severity == "critical", x.severity == "warning", x.confidence),
                            reverse=True)
        
        except Exception as e:
            logger.error(f"Error prioritizing with LLM: {str(e)}")
            # Fallback: return candidates as-is
            return candidates
    
    def suggest_refinements(
        self,
        profile: DataProfile,
        insights: List[Insight]
    ) -> List[str]:
        """
        Generate refinement suggestions based on profile and insights.
        
        Rule-based suggestions (NO LLM) for speed.
        
        Args:
            profile: DataProfile
            insights: List of generated insights
            
        Returns:
            List of natural language refinement suggestions
        """
        suggestions = []
        
        # Check for categorical columns
        categorical_cols = [
            col.column_name for col in profile.columns
            if col.categorical_stats and 2 <= col.categorical_stats.unique_count <= 20
        ]
        
        if categorical_cols:
            suggestions.append(f"Drill down by {categorical_cols[0]}")
        
        # Check for datetime columns
        if profile.has_datetime and len(profile.datetime_columns) > 0:
            suggestions.append("Compare with previous period")
            suggestions.append(f"Show trend over {profile.datetime_columns[0]}")
        
        # Check for outliers
        outlier_insights = [i for i in insights if i.insight_type == "outlier"]
        if outlier_insights:
            col_name = outlier_insights[0].related_columns[0] if outlier_insights[0].related_columns else "outliers"
            suggestions.append(f"Filter out {col_name} outliers")
        
        # Check for high cardinality columns (good for filtering)
        high_card_cols = [
            col.column_name for col in profile.columns
            if col.categorical_stats and 20 < col.categorical_stats.unique_count < 100
        ]
        
        if high_card_cols:
            suggestions.append(f"Filter by specific {high_card_cols[0]} values")
        
        # Correlation-based suggestions
        if profile.correlations:
            suggestions.append("Analyze relationship between correlated variables")
        
        # Return top 4 suggestions
        return suggestions[:4]
