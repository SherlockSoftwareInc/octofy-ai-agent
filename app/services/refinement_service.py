"""
Refinement Intent Detection Service

Detects when users want to refine previous analysis vs. starting a new query.
Uses hybrid approach: pattern matching (fast) + LLM fallback (accurate).
"""

import re
import json
from typing import List, Dict, Any, Optional
from app.models.schemas import RefinementIntent, AnalysisContext
from app.services.llm_service import get_llm_service
from app.utils.sanitization import prepare_user_query_for_llm, sanitize_conversation_history
import logging

logger = logging.getLogger(__name__)


class RefinementDetector:
    """Service for detecting refinement intent in user queries"""
    
    # Regex patterns for quick intent detection
    # Order matters: checked sequentially
    REFINEMENT_PATTERNS = {
        "compare": [
            r"\b(compare|vs|versus|against|difference between)\b",
            r"\b(last year|previous|prior|year over year|yoy)\b",
            r"\b(vs\.|compared to|relative to)\b",
        ],
        "filter": [
            r"\b(only|just|filter|where|show me)\s+",
            r"\b(focus on|limit to|exclude|remove|without)\b",
            r"\b(for\s+(?:the\s+)?(?:region|category|type|status|country))\b",
        ],
        "drill_down": [
            r"\b(by|for each|per|breakdown by|group by|split by)\s+(\w+)",
            r"\b(drill down|break down|segment by|categorize by)\b",
            r"\b(show.*by)\b",
        ],
        "trend": [
            r"\b(trend|over time|timeline|progression|evolution)\b",
            r"\b(how.*chang|how.*evolv|how.*grow|how.*declin)\b",
            r"\b(month|quarter|year|week|day)\s+(over|by)\s+(month|quarter|year|week|day)\b",
        ],
        "forecast": [
            r"\b(predict|forecast|project|future|next)\b",
            r"\b(will|would|could)\s+\w+\s+(be|reach|achieve)\b",
        ],
    }
    
    # Confidence threshold for pattern matching
    PATTERN_CONFIDENCE_THRESHOLD = 0.7
    
    # Words that suggest continuation of current analysis
    REFINEMENT_SIGNALS = [
        "also", "too", "additionally", "furthermore", "moreover",
        "show", "display", "add", "include", "and",
        "break", "split", "drill", "focus", "zoom",
        "compare", "contrast", "versus", "vs",
        "filter", "only", "just", "exclude", "without"
    ]
    
    # Words that suggest new query
    NEW_QUERY_SIGNALS = [
        "new", "different", "instead", "now show", "change to",
        "switch", "other", "another"
    ]
    
    def __init__(self):
        self.llm_service = get_llm_service()
    
    def detect_intent(
        self,
        current_query: str,
        previous_context: Optional[AnalysisContext] = None,
        conversation_history: Optional[List[str]] = None
    ) -> RefinementIntent:
        """
        Detect if user wants to refine previous analysis or start new query.
        
        Hybrid approach:
        1. Pattern matching first (fast, ~10ms, no cost)
        2. If confidence < threshold or ambiguous → LLM (accurate, ~1s, ~$0.005)
        
        Args:
            current_query: User's current query
            previous_context: Analysis context from previous message (if any)
            conversation_history: Recent conversation messages
            
        Returns:
            RefinementIntent with intent_type, confidence, and extracted params
        """
        # If no previous context, it's definitely a new query
        if previous_context is None:
            return RefinementIntent(
                intent_type="new_query",
                confidence=1.0,
                target_columns=[],
                filter_values=[]
            )
        
        # Try pattern matching first
        pattern_intent = self._pattern_match(current_query)
        
        if pattern_intent and pattern_intent.confidence >= self.PATTERN_CONFIDENCE_THRESHOLD:
            logger.info(f"Pattern match: {pattern_intent.intent_type} (confidence: {pattern_intent.confidence:.2f})")
            return pattern_intent
        
        # Pattern matching was inconclusive or low confidence → use LLM
        logger.info(f"Pattern matching inconclusive, using LLM classification")
        llm_intent = self._llm_classify(current_query, previous_context, conversation_history or [])
        
        return llm_intent
    
    def _pattern_match(self, query: str) -> Optional[RefinementIntent]:
        """
        Try regex patterns to quickly detect intent.
        
        Args:
            query: User query
            
        Returns:
            RefinementIntent if pattern matched, None otherwise
        """
        query_lower = query.lower()
        
        # Check each intent type's patterns
        for intent_type, patterns in self.REFINEMENT_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, query_lower)
                if match:
                    # Extract target columns/values from match groups
                    target_columns = []
                    filter_values = []
                    comparison_dimension = None
                    
                    if match.groups():
                        # Extract captured groups
                        for group in match.groups():
                            if group:
                                target_columns.append(group.strip())
                    
                    # Special handling for comparison intent
                    if intent_type == "compare":
                        if "last year" in query_lower or "previous year" in query_lower:
                            comparison_dimension = "year"
                        elif "last month" in query_lower or "previous month" in query_lower:
                            comparison_dimension = "month"
                        elif "last quarter" in query_lower:
                            comparison_dimension = "quarter"
                    
                    return RefinementIntent(
                        intent_type=intent_type,
                        confidence=0.8,  # Pattern match gives decent confidence
                        target_columns=target_columns,
                        comparison_dimension=comparison_dimension,
                        filter_values=filter_values
                    )
        
        # Check for refinement vs new query signals
        refinement_score = sum(1 for signal in self.REFINEMENT_SIGNALS if signal in query_lower)
        new_query_score = sum(1 for signal in self.NEW_QUERY_SIGNALS if signal in query_lower)
        
        if new_query_score > refinement_score:
            return RefinementIntent(
                intent_type="new_query",
                confidence=0.7,
                target_columns=[],
                filter_values=[]
            )
        
        # No clear pattern match
        return None
    
    def _llm_classify(
        self,
        query: str,
        previous_context: AnalysisContext,
        conversation_history: List[str]
    ) -> RefinementIntent:
        """
        Use LLM to classify refinement intent.
        
        Args:
            query: Current user query
            previous_context: Previous analysis context
            conversation_history: Recent conversation messages
            
        Returns:
            RefinementIntent from LLM classification
        """
        try:
            # Sanitize inputs to prevent prompt injection
            safe_query = prepare_user_query_for_llm(query)
            safe_history = sanitize_conversation_history(conversation_history, max_messages=3)
            
            # Get column names from previous profile
            previous_columns = []
            if previous_context.data_profile:
                previous_columns = [col.column_name for col in previous_context.data_profile.columns]
            
            # Limit column list length for prompt
            columns_display = ', '.join(previous_columns[:10]) if previous_columns else 'Unknown'
            if len(previous_columns) > 10:
                columns_display += f" (and {len(previous_columns) - 10} more)"
            
            prompt = f"""Classify the user's intent for this query in the context of an ongoing data analysis conversation.

Previous Context:
- User was analyzing data with columns: {columns_display}
- Previous insights: {len(previous_context.insights)} insights generated

Recent Conversation:
{safe_history}

Current Query: "{safe_query}"

Classify the intent as ONE of:
1. drill_down - User wants to see data broken down by a specific dimension/category
2. filter - User wants to narrow down to a specific subset of data
3. compare - User wants temporal or categorical comparison
4. trend - User wants time series analysis or trend visualization
5. forecast - User wants predictions or future projections
6. new_query - This is a completely new question (not refining previous analysis)

Return ONLY a JSON object with this structure:
{{
  "intent_type": "drill_down|filter|compare|trend|forecast|new_query",
  "confidence": 0.0-1.0,
  "target_columns": ["column1", "column2"],
  "comparison_dimension": "year|month|quarter|category|null",
  "filter_values": ["value1", "value2"],
  "reasoning": "brief explanation"
}}

JSON object:"""

            # Call LLM
            response = self.llm_service.chat(prompt, temperature=0.2)
            
            # Parse response
            try:
                response = response.strip()
                if response.startswith("```"):
                    response = response.replace("```json", "").replace("```", "").strip()
                
                result = json.loads(response)
                
                # Validate and construct RefinementIntent
                intent_type = result.get("intent_type", "new_query")
                if intent_type not in ["drill_down", "filter", "compare", "trend", "forecast", "new_query"]:
                    intent_type = "new_query"
                
                return RefinementIntent(
                    intent_type=intent_type,
                    confidence=float(result.get("confidence", 0.8)),
                    target_columns=result.get("target_columns", []),
                    comparison_dimension=result.get("comparison_dimension"),
                    filter_values=result.get("filter_values", [])
                )
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response: {e}")
                logger.error(f"Response was: {response}")
                # Fallback: assume new query
                return RefinementIntent(
                    intent_type="new_query",
                    confidence=0.5,
                    target_columns=[],
                    filter_values=[]
                )
        
        except Exception as e:
            logger.error(f"Error in LLM classification: {str(e)}")
            # Fallback: assume new query
            return RefinementIntent(
                intent_type="new_query",
                confidence=0.5,
                target_columns=[],
                filter_values=[]
            )
    
    def extract_column_references(self, query: str, available_columns: List[str]) -> List[str]:
        """
        Extract column names mentioned in query.
        
        Args:
            query: User query
            available_columns: List of available column names
            
        Returns:
            List of referenced column names
        """
        query_lower = query.lower()
        referenced = []
        
        for col in available_columns:
            col_lower = col.lower()
            # Check if column name appears in query (with word boundaries)
            if re.search(r'\b' + re.escape(col_lower) + r'\b', query_lower):
                referenced.append(col)
        
        return referenced
    
    def is_chart_type_request(self, query: str) -> bool:
        """
        Detect if query is requesting a different chart type.
        
        Args:
            query: User query
            
        Returns:
            True if this is a chart type change request
        """
        chart_patterns = [
            r"\b(show|display|make|create|change to|as)\s+(a\s+)?(bar|line|pie|scatter)\s+(chart|graph|plot)\b",
            r"\b(bar|line|pie|scatter)\s+(chart|graph|plot)\b",
            r"\b(visualize|plot)\s+(as|with)\s+(bar|line|pie|scatter)\b",
        ]
        
        query_lower = query.lower()
        for pattern in chart_patterns:
            if re.search(pattern, query_lower):
                return True
        
        return False
