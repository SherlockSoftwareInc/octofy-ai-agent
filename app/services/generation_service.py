from app.models.schemas import GenerateSQLRequest, GenerateSQLResponse, DiscoveryContext, AgentStatus
import re
import logging
from typing import Optional, Tuple, List, Dict, Any, Generator, Union
from datetime import datetime
from app.services.llm_service import get_llm_service
from app.services.discovery_service import (
    perform_discovery, DiscoveryRequest,
    perform_three_pronged_discovery, check_smart_threshold,
    generate_user_selection_prompt, hydrate_discovery_context_from_skills
)
from app.services.validation_service import validate_sql_with_db
from app.services.vector_store import get_vector_store
from app.services.settings_service import get_settings_for_display
from collections import defaultdict

def parse_table_override_name(raw_name: str) -> Tuple[str, str]:
    cleaned = raw_name.strip().replace('[', '').replace(']', '')
    if '.' in cleaned:
        schema, table = cleaned.split('.', 1)
        return schema.strip() or "dbo", table.strip()
    return "dbo", cleaned.strip()

def hydrate_override_context(table_names: List[str]) -> DiscoveryContext:
    vector_store = get_vector_store()
    selected_schemas = []
    for raw_name in table_names:
        schema_name, table_name = parse_table_override_name(raw_name)
        schema = vector_store.get_schema_by_name(schema_name, table_name)
        if schema:
            selected_schemas.append(schema)
    return DiscoveryContext(
        relevant_tables=selected_schemas,
        similar_queries=[]
    )

def rerank_and_select_tables(few_shot_tables: List[str], value_tables: List[str], schema_tables: List[str]) -> List[str]:
    scores = defaultdict(int)
    display_names = {}
    
    def normalize(name):
        return name.lower().replace('[', '').replace(']', '').strip()
        
    def process_list(tables, weight):
        for t in tables:
            norm = normalize(t)
            if not norm: continue
            scores[norm] += weight
            # Prefer names with dots (schema qualified) (or first encountered if not present)
            if norm not in display_names:
                display_names[norm] = t
            elif '.' in t and '.' not in display_names[norm]:
                display_names[norm] = t
                
                
    process_list(value_tables, 10)  # Value matches are critical
    process_list(few_shot_tables, 5) # Few-shot is strong indicator
    process_list(schema_tables, 2)   # Schema search is backup relevance
    
    # Sort by score descending
    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    # Return top 8 display names
    return [display_names[item[0]] for item in sorted_items[:8]]

def hydrate_discovery_context(table_names: List[str], similar_queries: List[Dict]) -> DiscoveryContext:
    vector_store = get_vector_store()
    # 1. Fetch all schemas (efficient enough for <1000 tables)
    all_schemas = vector_store.get_all_schemas()
    
    # 2. Map normalized names to selection
    target_map = {}
    for t in table_names:
        norm = t.lower().replace('[', '').replace(']', '').strip()
        target_map[norm] = True
        # Also handle implicit dbo if missing
        if '.' not in norm:
            target_map[f"dbo.{norm}"] = True
            
    selected_schemas = []
    for schema in all_schemas:
        full_name = f"{schema.schema_name}.{schema.table_name}".lower()
        if full_name in target_map:
            selected_schemas.append(schema)
    
    # 3. Format similar queries
    formatted_queries = []
    for sq in similar_queries:
        formatted_queries.append({
            "question": sq.get("question", ""),
            "sql": sq.get("sql_query", "") or sq.get("sql", "")
        })
            
    return DiscoveryContext(
        relevant_tables=selected_schemas,
        similar_queries=formatted_queries
    )

def expand_context_with_neighbors(selected_tables: List[str], user_query: str) -> List[str]:
    """
    Use LLM to identify disjoint tables and suggest intermediate glue tables.
    """
    try:
        vector_store = get_vector_store()
        # Ask LLM for suggestions
        llm_service = get_llm_service()
        suggestions = llm_service.suggest_intermediate_tables(selected_tables, user_query)
        
        if not suggestions:
            return selected_tables
            
        logging.info(f"Context Expansion: LLM suggested glue tables: {suggestions}")
        
        # Search for these tables in schema index to verify existence
        verified_additions = []
        for table_suggestion in suggestions:
            # Semantic search for the specific table name
            results = vector_store.search_schemas(table_suggestion, top_k=1)
            for res in results:
                # Basic fuzzy match check
                found_name = f"{res.schema_name}.{res.table_name}"
                simple_suggest = table_suggestion.lower().replace('[', '').replace(']', '').split('.')[-1]
                simple_found = res.table_name.lower()
                
                if simple_suggest in simple_found or simple_found in simple_suggest:
                    verified_additions.append(found_name)
                    
        # Combine unique
        final_set = set(selected_tables)
        final_set.update(verified_additions)
        
        return list(final_set)
        
    except Exception as e:
        print(f"Error in context expansion: {e}")
        return selected_tables

def extract_entities(query: str) -> Tuple[List[str], List[str]]:
    """
    Extract key nouns (entities) and date ranges from query.
    Returns: (entities, date_ranges)
    """
    # Extract potential table/entity names
    entities = []
    date_pattern = r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|January|February|March|April|May|June|July|August|September|October|November|December|\d{4})\b'
    date_ranges = re.findall(date_pattern, query, re.IGNORECASE)
    
    # Extract nouns (simplified: common business terms)
    noun_pattern = r'\b(customers?|orders?|products?|employees?|suppliers?|categories?|shippers?|territories?|region|sales|inventory|transactions?|revenues?|invoices?|shipments?)\b'
    entities = list(set(re.findall(noun_pattern, query, re.IGNORECASE)))
    
    return entities, date_ranges

def score_query_complexity(query: str) -> str:
    """
    Score query complexity to adjust generation strategy.
    Returns: 'simple', 'moderate', or 'complex'
    """
    query_lower = query.lower()
    
    # Complex indicators
    complex_keywords = ['join', 'aggregate', 'group by', 'multiple', 'compare', 'relationship', 'across', 'between', 'correlate']
    complex_count = sum(1 for kw in complex_keywords if kw in query_lower)
    
    if complex_count >= 2:
        return 'complex'
    elif complex_count == 1:
        return 'moderate'
    else:
        return 'simple'


def parse_validation_error(text: str) -> tuple[bool, str, list[str]]:
    """
    Check if the text is a validation error message from the LLM.
    Returns (is_error, error_message, missing_items)
    """
    text = text.strip()
    missing_items = []
    
    if text.startswith("COLUMN_VALIDATION_ERROR") or text.startswith("TABLE_VALIDATION_ERROR"):
        # Format: "TYPE_ERROR: Cannot find ... [item] ..."
        match = re.search(r'\[([^\]]+)\]', text)
        if match:
            missing_items.append(match.group(1))
        return True, text, missing_items
    
    return False, "", []

def lookup_values_for_query(query: str, threshold: float = 0.7) -> Dict[str, List[str]]:
    """
    Look up relevant values in the value index based on the user query.
    
    Args:
        query: User's natural language question
        threshold: Similarity score threshold (0-1)
    
    Returns:
        Dictionary mapping unique values to their metadata
    """
    try:
        vector_store = get_vector_store()
        # Search for values relevant to the query
        results = vector_store.search_values(query, top_k=10)
        
        # Filter by similarity score if available
        filtered_results = []
        for result in results:
            # Check if score field exists and exceeds threshold
            # Note: Milvus L2 distance is lower for more similar items, so invert the logic
            score = result.get('score', 0)
            # L2 distance: lower = more similar, typically between 0-2 for normalized embeddings
            # Convert to similarity score (1 - normalized_distance)
            if score <= (2 - threshold * 2):  # Rough conversion
                filtered_results.append(result)
        
        # Group results by table.column for context injection
        value_map = {}
        for result in filtered_results[:5]:  # Limit to top 5
            entity = result.get('entity', result)
            value = entity.get('value', result.get('value', ''))
            table_name = entity.get('table_name', result.get('table_name', ''))
            column_name = entity.get('column_name', result.get('column_name', ''))
            schema_name = entity.get('schema_name', result.get('schema_name', 'dbo'))
            
            key = f"{schema_name}.{table_name}.{column_name}"
            if key not in value_map:
                value_map[key] = []
            value_map[key].append(value)
        
        return value_map
    except Exception as e:
        print(f"Error looking up values: {e}")
        return {}

def validate_schema_completeness(context: DiscoveryContext, user_query: str, llm_service) -> Tuple[bool, List[str], str]:
    """
    Validate if all referenced tables (foreign keys) are present in the context.
    Uses LLM to analyze schema descriptions for table references.
    
    Args:
        context: Current discovery context with table schemas
        user_query: User's natural language query
        llm_service: LLM service instance for validation
        
    Returns:
        Tuple of (is_complete, missing_tables, analysis)
        - is_complete: True if all referenced tables are present
        - missing_tables: List of missing table names (empty if complete)
        - analysis: LLM's explanation of the validation result
    """
    try:
        # Skip validation if no tables in context
        if not context.relevant_tables or len(context.relevant_tables) == 0:
            return True, [], "No tables in context to validate"
        
        # Call LLM to validate schema references
        validation_result = llm_service.validate_schema_references(
            context.relevant_tables,
            user_query
        )
        
        # Parse the validation result
        is_complete = True
        missing_tables = []
        analysis = ""
        
        lines = validation_result.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith("SCHEMA_COMPLETE:"):
                complete_status = line.split(":", 1)[1].strip().upper()
                is_complete = complete_status == "YES"
            elif line.startswith("MISSING_TABLES:"):
                tables_str = line.split(":", 1)[1].strip()
                if tables_str and tables_str.upper() != "NONE":
                    # Parse comma-separated table names
                    missing_tables = [t.strip() for t in tables_str.split(",") if t.strip()]
            elif line.startswith("ANALYSIS:"):
                analysis = line.split(":", 1)[1].strip()
        
        # Log the validation outcome
        logging.info(f"Schema validation - Complete: {is_complete}, Missing: {missing_tables}")
        
        return is_complete, missing_tables, analysis
        
    except Exception as e:
        # On error, assume complete to avoid blocking SQL generation
        logging.error(f"Error validating schema completeness: {e}")
        return True, [], f"Validation error: {e}"


def search_data_objects(query: str) -> GenerateSQLResponse:
    """
    Search for relevant database objects based on user query.
    Queries both schema and value indexes and returns unique [schema].[table] objects sorted by relevance.
    
    Args:
        query: User's search query
    
    Returns:
        GenerateSQLResponse with objects list in explanation field
    """
    try:
        vector_store = get_vector_store()
        from app.core.config import settings as app_settings
        if not app_settings.VECTOR_DB_ENABLED:
            return GenerateSQLResponse(
                sql="",
                explanation="Vector search is disabled on this server. Enable VECTOR_DB_ENABLED to use object search.",
                query_type="search",
                context_text=f"Searched for: {query}"
            )
        # Track objects with their best (lowest) score - L2 distance where lower = more similar
        object_scores: Dict[str, float] = {}
        object_metadata: Dict[str, Dict[str, Optional[str]]] = {}

        def normalize_table_type(raw_type: Optional[str]) -> Optional[str]:
            if not raw_type:
                return None
            normalized = raw_type.strip().lower()
            if normalized == "table":
                return "Table"
            if normalized == "view":
                return "View"
            return raw_type.strip()
        
        # Search schema index for relevant tables
        # Use the internal _search_collection to get scores
        from pymilvus import utility
        
        if utility.has_collection(app_settings.MILVUS_COLLECTION_SCHEMA):
            embedding = vector_store._get_embedding(query)
            schema_results = vector_store._search_collection(
                app_settings.MILVUS_COLLECTION_SCHEMA,
                embedding,
                ['schema_name', 'table_name', 'table_type'],
                top_k=10,
                score_threshold=1.5  # Relaxed threshold for object search (L2 distance)
            )
            for result in schema_results:
                entity = result.get('entity', result)
                schema_name = entity.get('schema_name') or 'dbo'
                table_name = entity.get('table_name', '')
                table_type = normalize_table_type(entity.get('table_type'))
                score = result.get('score', 999)
                if table_name:
                    obj_key = f"[{schema_name}].[{table_name}]"
                    # Keep the best (lowest) score for each object
                    if obj_key not in object_scores or score < object_scores[obj_key]:
                        object_scores[obj_key] = score
                    if obj_key not in object_metadata or (table_type and not object_metadata[obj_key].get("type")):
                        object_metadata[obj_key] = {
                            "schema": schema_name,
                            "name": table_name,
                            "type": table_type
                        }
        
        # Search value index for relevant tables
        value_results = vector_store.search_values(query, top_k=10)
        for result in value_results:
            entity = result.get('entity', result)
            schema_name = entity.get('schema_name') or 'dbo'
            table_name = entity.get('table_name', '')
            score = result.get('score', 999)
            if table_name:
                obj_key = f"[{schema_name}].[{table_name}]"
                # Keep the best (lowest) score for each object
                if obj_key not in object_scores or score < object_scores[obj_key]:
                    object_scores[obj_key] = score
                if obj_key not in object_metadata:
                    object_metadata[obj_key] = {
                        "schema": schema_name,
                        "name": table_name,
                        "type": None
                    }
        
        # Sort objects by score (lower = more relevant)
        sorted_objects = sorted(object_scores.keys(), key=lambda x: object_scores[x])
        
        objects_payload = [
            {
                "schema": object_metadata.get(obj, {}).get("schema", "dbo"),
                "name": object_metadata.get(obj, {}).get("name", obj.strip("[]").split("].[")[-1]),
                "type": object_metadata.get(obj, {}).get("type")
            }
            for obj in sorted_objects
        ]

        if sorted_objects:
            # Format as markdown list
            objects_list = "\n".join([f"• {obj}" for obj in sorted_objects])
            explanation = f"**Found {len(sorted_objects)} relevant database object(s):**\n\n{objects_list}"
        else:
            explanation = "No matching database objects found for your search. Try different keywords or check the value index."
        
        return GenerateSQLResponse(
            sql="",
            explanation=explanation,
            objects=objects_payload,
            query_type="search",
            context_text=f"Searched for: {query}"
        )
    except Exception as e:
        # Log detailed error for debugging but return generic message to user
        logging.error(f"Error searching data objects: {e}")
        return GenerateSQLResponse(
            sql="",
            explanation="An error occurred while searching database objects. Please try again or refine your search.",
            query_type="search",
            context_text=f"Search failed for: {query}"
        )


def _detect_turn_type_fast(query: str, planning_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Fast turn-type detection using keyword-based heuristics.
    
    Detects conversation turn types:
    - confirmation: User agrees to proceed ("yes", "ok", "sounds good")
    - correction: User changes specific details ("no, I meant...", "actually...")
    - pivot: User switches topics (low keyword overlap + signal words)
    - refinement: User adds details to existing goal (high overlap + signal words)
    
    Args:
        query: User's current message
        planning_context: Current planning state with "goal" field
    
    Returns:
        Dict with turn_type, confidence, reasoning, topic_similarity, or None if no clear pattern
    """
    query_lower = query.lower().strip()
    goal = planning_context.get("goal", "")
    
    # 1. CONFIRMATION SIGNALS (highest priority)
    confirmation_signals = [
        r'\b(yes|yeah|yep|yup|sure|ok|okay|sounds good|looks good|correct|right|perfect|go ahead|proceed)\b',
        r'^(y|k)\b',  # Short affirmatives
    ]
    for pattern in confirmation_signals:
        if re.search(pattern, query_lower):
            return {
                "turn_type": "confirmation",
                "confidence": 0.95,
                "reasoning": "User confirmed with affirmative language",
                "topic_similarity": 1.0
            }
    
    # 2. CORRECTION SIGNALS (2+ signals required)
    correction_signals = [
        r'\b(no|not|nope|incorrect|wrong|actually|instead|rather)\b',
        r'\b(i\s+\w+\s+meant|meant|should be|change)\b',  # "i meant", "i actually meant", etc.
        r'\b(different|other|another)\b',
    ]
    correction_count = sum(1 for pattern in correction_signals if re.search(pattern, query_lower))
    
    if correction_count >= 2:
        return {
            "turn_type": "correction",
            "confidence": 0.85,
            "reasoning": f"Multiple correction signals detected ({correction_count})",
            "topic_similarity": 0.5
        }
    
    # 3. KEYWORD OVERLAP CALCULATION (for pivot vs refinement)
    topic_similarity = _compute_topic_similarity(query, goal)
    
    # 4. PIVOT DETECTION (low overlap + pivot signals)
    pivot_signals = [
        r'\b(instead|now|new|different|switch|change to)\b',
        r'\b(forget|ignore|nevermind|scratch that)\b',
    ]
    pivot_signal_count = sum(1 for pattern in pivot_signals if re.search(pattern, query_lower))
    
    if pivot_signal_count > 0 and topic_similarity < 0.3:
        return {
            "turn_type": "pivot",
            "confidence": 0.85,
            "reasoning": f"Pivot signals detected ({pivot_signal_count}) with low topic overlap ({topic_similarity:.2f})",
            "topic_similarity": topic_similarity
        }
    
    # 5. REFINEMENT DETECTION (refinement signals + higher overlap)
    refinement_signals = [
        r'\b(also|too|additionally|furthermore|plus|and)\b',
        r'\b(add|include|show|break down|filter|only)\b',
        r'\b(more|specifically|detailed|by)\b',
    ]
    refinement_signal_count = sum(1 for pattern in refinement_signals if re.search(pattern, query_lower))
    
    if refinement_signal_count >= 2:
        return {
            "turn_type": "refinement",
            "confidence": 0.80,
            "reasoning": f"Multiple refinement signals detected ({refinement_signal_count})",
            "topic_similarity": topic_similarity
        }
    
    # No clear pattern detected
    return None


def _compute_topic_similarity(query: str, goal: str) -> float:
    """
    Compute topic similarity between two strings using Jaccard index.
    
    Extracts keywords (4+ character words) from both strings and calculates
    the Jaccard similarity coefficient: |intersection| / |union|.
    
    This is used by pivot detection to determine if the user is switching topics
    or refining the current goal.
    
    Args:
        query: Current user query string
        goal: Previous goal or context string
    
    Returns:
        float: Similarity score from 0.0 (no overlap) to 1.0 (identical)
    
    Examples:
        >>> _compute_topic_similarity("show sales data", "show sales data")
        1.0
        >>> _compute_topic_similarity("show sales", "show revenue")
        0.5
        >>> _compute_topic_similarity("show sales", "employee count")
        0.0
    """
    def extract_keywords(text: str) -> set:
        """Extract 4+ character words as keywords."""
        if not text:
            return set()
        words = re.findall(r'\b\w{4,}\b', text.lower())
        return set(words)
    
    query_keywords = extract_keywords(query)
    goal_keywords = extract_keywords(goal)
    
    # Handle edge cases: empty keyword sets
    if not query_keywords or not goal_keywords:
        return 0.0
    
    # Calculate Jaccard index: intersection / union
    intersection = query_keywords & goal_keywords
    union = query_keywords | goal_keywords
    
    return len(intersection) / len(union) if union else 0.0


def _classify_turn_type_llm(query: str, planning_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    LLM-based turn-type classification fallback for ambiguous cases.
    
    Uses an LLM to analyze conversation context and classify the user's turn type
    when fast pattern matching is insufficient. Includes conversation history for
    better context understanding.
    
    Args:
        query: Current user message
        planning_context: Planning state including goal, conversation_history, etc.
    
    Returns:
        Dict with fields:
            - turn_type: One of "refinement", "correction", "pivot", "confirmation", "clarification"
            - confidence: Float in [0.0, 1.0]
            - reasoning: Explanation of classification
            - topic_similarity: Float in [0.0, 1.0]
            - changed_requirements: List of requirement keys that changed (for corrections)
            - new_requirements: List of new requirements added (for refinements)
        
        On error, returns fallback REFINEMENT classification with confidence=0.5
    """
    import json
    
    try:
        llm_service = get_llm_service()
        
        # Build conversation history string
        history_text = ""
        for turn in planning_context.get("conversation_history", []):
            user_msg = turn.get("user", "")
            assistant_msg = turn.get("assistant", "")
            history_text += f"User: {user_msg}\nAssistant: {assistant_msg}\n"
        
        # Build classification prompt
        prompt = f"""You are analyzing a planning conversation to classify the user's latest message.

Current Goal: {planning_context.get("goal", "Not yet established")}

Conversation History:
{history_text if history_text else "No previous conversation"}

Latest User Message: {query}

Classify this message as one of the following turn types:
1. **refinement**: User is adding details or constraints to the existing goal (e.g., "also filter by region")
2. **correction**: User is changing a specific detail they previously stated (e.g., "no, I meant 2023, not 2022")
3. **pivot**: User is switching to a completely different topic (e.g., from sales to employees)
4. **confirmation**: User is agreeing to proceed (e.g., "yes", "ok", "sounds good")
5. **clarification**: User is answering a specific question the assistant asked

Respond with JSON:
{{
    "turn_type": "refinement|correction|pivot|confirmation|clarification",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation of why this classification",
    "topic_similarity": 0.0-1.0,
    "changed_requirements": ["list", "of", "changed", "keys"],
    "new_requirements": ["list", "of", "new", "requirements"]
}}

IMPORTANT: Only return the JSON object, no additional text."""
        
        # Call LLM with temperature=0.3 for consistent but slightly flexible responses
        response = llm_service.chat(prompt, temperature=0.3)
        
        # Clean markdown code blocks if present
        response_clean = response.strip()
        if response_clean.startswith("```"):
            response_clean = re.sub(r'^```(?:json)?\s*\n', '', response_clean)
            response_clean = re.sub(r'\n```\s*$', '', response_clean)
        
        # Parse JSON
        result = json.loads(response_clean)
        
        # Validate required fields
        required_fields = ["turn_type", "confidence", "reasoning", "topic_similarity"]
        if not all(field in result for field in required_fields):
            raise ValueError(f"Missing required fields. Got: {list(result.keys())}")
        
        # Validate turn_type is valid enum value
        valid_turn_types = ["refinement", "correction", "pivot", "confirmation", "clarification"]
        if result["turn_type"] not in valid_turn_types:
            raise ValueError(f"Invalid turn_type: {result['turn_type']}")
        
        # Validate confidence and topic_similarity are in [0, 1]
        if not (0.0 <= result["confidence"] <= 1.0):
            raise ValueError(f"Confidence out of bounds: {result['confidence']}")
        if not (0.0 <= result["topic_similarity"] <= 1.0):
            raise ValueError(f"Topic similarity out of bounds: {result['topic_similarity']}")
        
        # Ensure optional fields exist with defaults
        result.setdefault("changed_requirements", [])
        result.setdefault("new_requirements", [])
        
        return result
        
    except Exception as e:
        # Log error and return fallback
        logging.error(f"LLM turn-type classification failed: {e}")
        return {
            "turn_type": "refinement",
            "confidence": 0.5,
            "reasoning": f"Fallback classification due to error: {str(e)}",
            "topic_similarity": 0.5,
            "changed_requirements": [],
            "new_requirements": []
        }


def _serialize_planning_context(planning_context: Dict[str, Any]) -> str:
    """
    Serialize planning context to JSON, converting sets to lists.
    
    Planning context uses sets for rejected_tables, confirmed_tables, and
    last_auto_checked to efficiently track table state. This function converts
    those sets to lists for JSON serialization.
    
    Args:
        planning_context: Planning state dictionary potentially containing set fields
    
    Returns:
        JSON string representation of planning context with sets converted to lists
    """
    import json
    
    # Create a shallow copy to avoid modifying the original
    serializable_context = {}
    
    for key, value in planning_context.items():
        # Convert sets to lists for JSON serialization
        if isinstance(value, set):
            serializable_context[key] = list(value)
        else:
            serializable_context[key] = value
    
    return json.dumps(serializable_context)


def planning_conversation(query: str, planning_context: Optional[Dict[str, Any]] = None) -> GenerateSQLResponse:
    """
    Intelligent planning mode with LLM-driven conversation and smart clarification detection.
    
    Strategy:
    - Ask questions only when information is ambiguous or missing
    - Auto-check tables with >90% confidence
    - Guide user efficiently toward complete planning
    
    Args:
        query: User's current message
        planning_context: Accumulated planning state from previous turns
            {
                "goal": str,  # User's stated analysis objective
                "selected_tables": List[str],  # User-checked tables
                "suggested_tables": List[Dict],  # AI-suggested tables
                "requirements": List[Dict],  # Filters, date ranges, business logic
                "conversation_history": List[Dict],  # Previous Q&A
                "turn_count": int
            }
    
    Returns:
        GenerateSQLResponse with:
            - explanation: AI's conversational response
            - objects: Suggested tables with auto_checked flag
            - context_text: Updated planning_context JSON
            - query_type: "plan"
    """
    import json
    
    try:
        llm_service = get_llm_service()
        vector_store = get_vector_store()
        
        # Initialize or load context
        if not planning_context:
            planning_context = {
                "goal": "",
                "selected_tables": [],
                "suggested_tables": [],
                "requirements": [],
                "conversation_history": [],
                "turn_count": 0,
                # NEW: Intent evolution tracking fields
                "goal_history": [],  # List of previous goals (for pivot detection)
                "rejected_tables": set(),  # Tables user explicitly rejected
                "confirmed_tables": set(),  # Tables user explicitly confirmed
                "adjustments": [],  # List of corrections/refinements made
                "last_auto_checked": set()  # Tables that were auto-checked in previous turn
            }
        else:
            # Ensure new fields exist for backward compatibility
            planning_context.setdefault("goal_history", [])
            planning_context.setdefault("adjustments", [])
            
            # Convert list fields to sets for efficient lookups (backward compatibility)
            for field in ["rejected_tables", "confirmed_tables", "last_auto_checked"]:
                if field not in planning_context:
                    planning_context[field] = set()
                elif isinstance(planning_context[field], list):
                    planning_context[field] = set(planning_context[field])
        
        # Step 1: Use LLM to analyze user intent with smart clarification detection
        # Serialize context for JSON (convert sets to lists)
        context_for_prompt = {}
        for key, value in planning_context.items():
            if isinstance(value, set):
                context_for_prompt[key] = list(value)
            else:
                context_for_prompt[key] = value
        
        intent_prompt = f"""You are a data analysis planning assistant. Analyze the user's message:

Previous Context: {json.dumps(context_for_prompt, indent=2)}
User Message: {query}

Determine:
1. Is the user's goal clear? (yes/no)
2. Are there ambiguities that MUST be resolved before finding tables? (list them)
3. Is there enough info to suggest database tables? (yes/no)
4. What critical questions need answers? (only if truly necessary)

Respond in JSON:
{{
    "goal_clear": true/false,
    "goal_statement": "Clear 1-sentence goal",
    "critical_ambiguities": ["ambiguity1", "ambiguity2"],
    "ready_for_search": true/false,
    "required_questions": [
        {{"question": "...", "reason": "why this must be asked"}}
    ],
    "requirements_extracted": [
        {{"type": "time_period|filter|metric|grouping", "value": "..."}}
    ]
}}

IMPORTANT: Only ask questions if information is genuinely ambiguous or missing critical details.
If the user said "sales analysis", assume they want revenue unless they specify otherwise.
Be helpful, not interrogative."""

        try:
            intent_response = llm_service.chat(intent_prompt)
            # Clean up response - remove markdown code blocks if present
            intent_response_clean = intent_response.strip()
            if intent_response_clean.startswith("```"):
                intent_response_clean = re.sub(r'^```(?:json)?\s*\n', '', intent_response_clean)
                intent_response_clean = re.sub(r'\n```\s*$', '', intent_response_clean)
            intent_data = json.loads(intent_response_clean)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse intent JSON: {e}. Response: {intent_response}")
            # Fallback: assume basic intent
            intent_data = {
                "goal_clear": True,
                "goal_statement": query,
                "critical_ambiguities": [],
                "ready_for_search": True,
                "required_questions": [],
                "requirements_extracted": []
            }
        
        # Step 2: Update planning context
        if intent_data.get("goal_statement"):
            planning_context["goal"] = intent_data["goal_statement"]
        
        for req in intent_data.get("requirements_extracted", []):
            planning_context["requirements"].append(req)
        
        planning_context["conversation_history"].append({
            "turn": planning_context["turn_count"],
            "user": query,
            "intent": intent_data
        })
        planning_context["turn_count"] += 1
        
        # Step 3: Perform semantic search if ready
        suggested_objects = []
        auto_checked_tables = []
        
        if intent_data.get("ready_for_search"):
            search_query = planning_context.get("goal", "") + " " + query
            search_result = search_data_objects(search_query)
            suggested_objects = search_result.objects or []
            
            # Step 4: Determine which tables to auto-check (>90% confidence)
            if suggested_objects and len(suggested_objects) > 0:
                # Build table descriptions for confidence prompt
                table_list = [
                    f"[{obj.schema_name}].[{obj.name}] ({obj.type or 'Table'})"
                    for obj in suggested_objects
                ]
                
                confidence_prompt = f"""Given this user goal: {planning_context.get("goal", query)}

And these suggested tables: {', '.join(table_list)}

Which tables are ESSENTIAL (>90% confidence needed) for this analysis?

Respond with JSON:
{{
    "essential_tables": ["[schema].[table]", ...],
    "reasoning": {{"[schema].[table]": "why essential"}}
}}

Be conservative - only mark as essential if absolutely required for the stated goal.
Maximum 3 essential tables."""

                try:
                    confidence_response = llm_service.chat(confidence_prompt)
                    # Clean up response
                    confidence_response_clean = confidence_response.strip()
                    if confidence_response_clean.startswith("```"):
                        confidence_response_clean = re.sub(r'^```(?:json)?\s*\n', '', confidence_response_clean)
                        confidence_response_clean = re.sub(r'\n```\s*$', '', confidence_response_clean)
                    confidence_data = json.loads(confidence_response_clean)
                    auto_checked_tables = confidence_data.get("essential_tables", [])
                except (json.JSONDecodeError, Exception) as e:
                    logging.error(f"Failed to parse confidence JSON: {e}")
                    # Fallback: auto-check top 1 table
                    if suggested_objects:
                        auto_checked_tables = [f"[{suggested_objects[0].schema_name}].[{suggested_objects[0].name}]"]
                
                # Normalize auto-checked table names and mark objects
                auto_checked_normalized = []
                for table_name in auto_checked_tables:
                    normalized = table_name.strip().replace('[', '').replace(']', '')
                    auto_checked_normalized.append(normalized)
                
                # Mark auto-checked objects
                for obj in suggested_objects:
                    obj_key = f"{obj.schema_name}.{obj.name}"
                    if obj_key in auto_checked_normalized or f"[{obj.schema_name}].[{obj.name}]" in auto_checked_tables:
                        obj.auto_checked = True
                
                # Add to selected tables in context
                planning_context["selected_tables"] = list(set(
                    planning_context.get("selected_tables", []) + auto_checked_tables
                ))
        
        # Step 5: Generate conversational response
        response_prompt = f"""Generate a helpful response for this planning conversation.

Context: {json.dumps(context_for_prompt, indent=2)}
Intent Analysis: {json.dumps(intent_data, indent=2)}
Number of Suggested Tables: {len(suggested_objects)}
Auto-Checked Tables: {json.dumps(auto_checked_tables, indent=2)}

Guidelines:
1. Acknowledge their input warmly
2. ONLY ask questions from intent_data["required_questions"] (if any exist)
3. If tables found, say: "Based on your question about [topic], please review the following tables and select the ones you want to use in the analysis:"
4. If tables were auto-checked, mention: "I've pre-selected tables that are essential for your analysis, but you can adjust the selection."
5. Keep it conversational and helpful, not robotic
6. If planning seems complete (goal clear, tables selected, requirements noted), say: "Your planning is complete! Switch to 'Generate SQL' or another mode when you're ready to create the code."

Format as markdown. Be concise but friendly. Maximum 4 sentences."""

        ai_response = llm_service.chat(response_prompt)
        
        return GenerateSQLResponse(
            sql="",
            explanation=ai_response,
            objects=suggested_objects,
            query_type="plan",
            context_text=_serialize_planning_context(planning_context)
        )
        
    except Exception as e:
        logging.error(f"Error in planning conversation: {e}")
        return GenerateSQLResponse(
            sql="",
            explanation=f"I encountered an issue during planning. Let's try again: {str(e)}",
            query_type="plan",
            context_text=_serialize_planning_context(planning_context) if planning_context else "{}"
        )


def generate_planning_summary(planning_context: Dict[str, Any]) -> str:
    """
    Generate a structured markdown summary from planning context.
    
    Args:
        planning_context: Accumulated planning state
    
    Returns:
        Formatted summary for display and code generation
    """
    import json
    
    try:
        llm_service = get_llm_service()
        
        # Serialize context for JSON (convert sets to lists)
        context_for_prompt = {}
        for key, value in planning_context.items():
            if isinstance(value, set):
                context_for_prompt[key] = list(value)
            else:
                context_for_prompt[key] = value
        
        # Extract user's original request from conversation history
        user_messages = [turn.get("user", "") for turn in planning_context.get("conversation_history", [])]
        original_request = user_messages[0] if user_messages else planning_context.get("goal", "")
        
        prompt = f"""Create a concise summary from this planning conversation for code generation.

**User's Primary Request:** {original_request}

**Full Planning Context:** {json.dumps(context_for_prompt, indent=2)}

CRITICAL: The summary must focus on WHAT THE USER WANTS TO ACHIEVE (their primary analysis request), NOT just list tables.

Format as markdown:
## Primary Request
[Restate the user's original analysis question/goal in clear terms - this is the MAIN focus]

## Data Sources
[List only the selected tables - keep this section minimal]
• [schema].[table]
• ...

## Additional Requirements
[ONLY if user specified filters, date ranges, grouping, metrics, etc.]
• [requirement]

Guidelines:
- The "Primary Request" section is THE MOST IMPORTANT - it should clearly state what the user wants to analyze or find out
- Selected tables are SUPPORTING information, not the main focus
- Keep total summary under 150 words
- This summary will be sent directly to code generation, so it must clearly communicate the user's intent"""

        summary = llm_service.chat(prompt)
        return summary
        
    except Exception as e:
        logging.error(f"Error generating planning summary: {e}")
        # Fallback: simple summary focusing on user's primary request
        user_messages = [turn.get("user", "") for turn in planning_context.get("conversation_history", [])]
        original_request = user_messages[0] if user_messages else planning_context.get("goal", "Analysis goal not specified")
        
        tables = planning_context.get("selected_tables", [])
        requirements = planning_context.get("requirements", [])
        
        summary = f"## Primary Request\n{original_request}\n\n"
        if tables:
            summary += f"## Data Sources\n"
            for table in tables:
                summary += f"• {table}\n"
            summary += "\n"
        if requirements:
            summary += "## Additional Requirements\n"
            for req in requirements[:5]:  # Limit to 5
                req_value = req.get("value", str(req))
                summary += f"• {req_value}\n"
        
        return summary


def generate_sql_for_request(request: GenerateSQLRequest, previous_sql: Optional[str] = None, query_history: Optional[str] = None) -> Generator[Union[AgentStatus, Dict[str, Any]], None, None]:
    # Check for plan mode first - conversational planning
    if request.queryMode == "plan":
        yield AgentStatus(step_id=1, message="Thinking about your data needs...")
        result = planning_conversation(request.query, request.planning_context)
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return
    
    # Check for search mode - user explicitly chose to search objects
    if request.queryMode == "search":
        yield AgentStatus(step_id=1, message="Searching database objects...")
        result = search_data_objects(request.query)
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return
    
    yield AgentStatus(step_id=1, message="Initializing agent and loading settings...")

    
    # Load settings for dynamic configuration
    vector_store = get_vector_store()
    try:
        # Get fresh LLM service instance to ensure latest settings
        llm_service = get_llm_service()
        
        # Load database metadata from skills data source instead of settings
        from app.services.skills_service import get_skills_service
        skills_service = get_skills_service()
        data_source = skills_service.load_primary_data_source()
        
        if data_source:
            friendly_name = data_source.name
            db_description = data_source.description
            db_keywords = data_source.keywords
        else:
            # Fallback to defaults if skills not available
            friendly_name = "Database"
            db_description = "Primary database"
            db_keywords = []
    except Exception as e:
        print(f"Failed to load database metadata, using defaults: {e}")
        friendly_name = "Database"
        db_description = "Primary database"
        db_keywords = []
    
    # Stage 1: Query Analysis & Intent
    yield AgentStatus(step_id=2, message="Analyzing query and intent...")
    
    # If forceGeneral flag is set (user explicitly chose "General Answer"), skip classification
    if request.forceGeneral:
        yield AgentStatus(step_id=3, message="Processing general query...")
        result = _handle_general_query(request, llm_service)
        yield {"type": "result", "payload": result}
        yield {"type": "done"}
        return

    # Classification removed: Always assume 'database' query unless forceGeneral is set

    # Extract entities and score complexity for database queries
    entities, date_ranges = extract_entities(request.query)
    query_complexity = score_query_complexity(request.query)
    
    yield AgentStatus(step_id=3, message=f"Analyzed query. Complexity: {query_complexity}. Entities: {', '.join(entities) if entities else 'None'}")
    
    # Stage 2: Discovery & Context Synthesis (Multi-Source Retrieval)
    yield AgentStatus(step_id=4, message="Discovering relevant tables and schemas...")
    
    table_override = [t for t in (request.table_override or []) if t]
    use_table_override = len(table_override) > 0

    if use_table_override:
        yield AgentStatus(step_id=4, message="Locking context to user-selected tables...")
        context = hydrate_override_context(table_override)
        if not context.relevant_tables:
            result = GenerateSQLResponse(
                sql="",
                explanation="No matching schemas were found for the selected objects. Please verify the table names and try again.",
                query_type="database",
                context_text="Selected tables not found"
            )
            yield {"type": "result", "payload": result}
            yield {"type": "done"}
            return
    elif request.context:
        # If context is explicitly provided, use it
        context = request.context
    else:
        # Multi-Source Discovery
        
        
        # 1. NER & Value Discovery (Focused)
        # Extract specific entities to avoid noisy value searches (e.g. searching for "how" or "much")
        yield AgentStatus(step_id=5, message="Identifying filter values and entities...")
        filter_values = llm_service.extract_filter_values(request.query)
        value_tables = []
        if filter_values:
            logging.info(f"Discovery: Extracted filter values: {filter_values}")
            for val in filter_values:
                # Search for each specific entity
                v_res = vector_store.search_values(val, top_k=3)
                value_tables.extend([f"{r.get('schema_name', 'dbo')}.{r.get('table_name')}" for r in v_res if r.get('table_name')])
        else:
            # Fallback to broad search if no entities found
            value_results = vector_store.search_values(request.query, top_k=5)
            value_tables = [f"{r.get('schema_name', 'dbo')}.{r.get('table_name')}" for r in value_results if r.get('table_name')]
            
        # 2. Few-Shot Discovery
        # Search for similar queries to get table hints
        yield AgentStatus(step_id=6, message="Searching knowledge base for similar queries...")
        similar_queries = vector_store.search_fewshots(request.query, top_k=3, knowledge_type="sql_query")
        few_shot_sqls = [q.get('sql_query', '') or q.get('sql', '') for q in similar_queries]
        few_shot_tables = llm_service.extract_tables_from_sql(few_shot_sqls)
        
        # 3. Schema Index Discovery
        schema_results = vector_store.search_schemas(request.query, top_k=5)
        schema_tables = [f"{s.schema_name}.{s.table_name}" for s in schema_results]
        
        # 4. Re-rank and Filter
        final_table_list = rerank_and_select_tables(few_shot_tables, value_tables, schema_tables)
        logging.info(f"Discovery: Selected tables after reranking: {final_table_list}")
        
        # 5. Hydrate Context (Initial)
        context = hydrate_discovery_context(final_table_list, similar_queries)
        
        # 6. Path Finding (Context Expansion)
        # Check if the initial selection needs glue tables
        yield AgentStatus(step_id=7, message="Analyzing schema relationships and path finding...")
        expanded_list = expand_context_with_neighbors(final_table_list, request.query)
        if len(expanded_list) > len(final_table_list):
            logging.info(f"Discovery: Expanded context from {len(final_table_list)} to {len(expanded_list)} tables.")
            context = hydrate_discovery_context(expanded_list, similar_queries)
    
    if not use_table_override:
        # Stage 2.3: Schema Completeness Validation - Check if all referenced tables are present
        yield AgentStatus(step_id=8, message="Validating schema completeness...")
        is_complete, missing_tables, validation_analysis = validate_schema_completeness(
            context, 
            request.query, 
            llm_service
        )
        
        # If missing tables detected, attempt auto-discovery
        if not is_complete and missing_tables:
            logging.info(f"Schema validation found missing tables: {missing_tables}")
            logging.info(f"Validation analysis: {validation_analysis}")
            
            discovery_feedback = ""
            tables_added = []
            tables_not_found = []
            
            # Limit to max 5 missing tables to avoid excessive discovery calls
            for missing_table in missing_tables[:5]:
                try:
                    # Search for the missing table in vector database
                    disc_res = perform_discovery(DiscoveryRequest(query=missing_table, top_k=3))
                    
                    # Add newly discovered tables to context
                    newly_added = False
                    for table in disc_res.context.relevant_tables:
                        # Check if this table matches what we're looking for
                        table_full_name = f"{table.schema_name}.{table.table_name}"
                        
                        # Only add if not already in context
                        if not any(t.table_name == table.table_name and t.schema_name == table.schema_name 
                                  for t in context.relevant_tables):
                            context.relevant_tables.append(table)
                            discovery_feedback += f"\n- Auto-discovered and added: {table_full_name}"
                            tables_added.append(table_full_name)
                            newly_added = True
                            logging.info(f"Auto-discovered missing table: {table_full_name}")
                    
                    if not newly_added:
                        # Check if table was already in context
                        already_present = any(
                            missing_table.lower() in f"{t.schema_name}.{t.table_name}".lower()
                            for t in context.relevant_tables
                        )
                        if not already_present:
                            tables_not_found.append(missing_table)
                            
                except Exception as e:
                    logging.error(f"Error discovering missing table {missing_table}: {e}")
                    tables_not_found.append(missing_table)
            
            # If we couldn't find some tables, return error asking user to sync schemas
            if tables_not_found:
                missing_list = "\n".join([f"- {t}" for t in tables_not_found])
                result = GenerateSQLResponse(
                    sql="",
                    explanation=f"""I detected that the following referenced tables are missing from the database schema index:

{missing_list}

**Reason:** {validation_analysis}

**Next Steps:**
1. Please ensure these tables exist in your database
2. Go to the Schema Management page and sync these table schemas
3. Then try your query again

Alternatively, if these table references are incorrect, please rephrase your query.""",
                    query_type="database",
                    context_text=f"Missing schemas: {', '.join(tables_not_found)}"
                )
                yield {"type": "result", "payload": result}
                yield {"type": "done"}
                return
            
            # Log successful auto-discovery
            if tables_added:
                logging.info(f"Auto-discovery successful. Added tables: {tables_added}")
        
        # Stage 2.5: Value Index Lookup - Get relevant values for the query
        yield AgentStatus(step_id=9, message="Checking value index for specific data mappings...")
        value_mappings = lookup_values_for_query(request.query)
    else:
        value_mappings = {}
    
    # Build dynamic database info from settings
    keywords_str = ", ".join(db_keywords[:5]) if db_keywords else "business data"
    database_info = f"{friendly_name}: {db_description} ({keywords_str})."
    
    # Stage 3: Build Reference Section (Complexity-Mapped Knowledge Base Examples)
    sql_references = []
    
    # Map knowledge base examples to complexity level
    complexity_relevant_queries = []
    for sq in (context.similar_queries or []):
        if sq.get("sql", "").strip():
            # Prefer queries with similar complexity
            sq_complexity = score_query_complexity(sq.get("question", ""))
            if sq_complexity == query_complexity or not complexity_relevant_queries:
                complexity_relevant_queries.append(sq)
    
    # Build numbered knowledge base examples
    for idx, sq in enumerate(complexity_relevant_queries[:3], start=1):  # Limit to top 3 mapped examples
        sql_references.append(f"Question {idx}: {sq.get('question', 'N/A')}\nSQL:\n```sql\n{sq.get('sql')}\n```")

    reference_text = "\n\n".join(sql_references) if sql_references else "No previous examples available."
    
    # Build value mappings reference section
    value_context = ""
    if value_mappings:
        value_context = "\n### VERIFIED DATA MAPPINGS\n"
        for key, values in list(value_mappings.items())[:5]:  # Limit to top 5 mappings
            unique_vals = list(set(values))
            # Format: The value 'Seafood' was found in: [dbo].[Categories].[CategoryName]
            val_str = ", ".join(repr(v) for v in unique_vals)
            value_context += f"- The value(s) {val_str} was found in: {key}\n"

    # Log the initial context
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Build initial schema text
    schema_parts = []
    for t in context.relevant_tables:
        if use_table_override and t.description:
            schema_parts.append(t.description)
            continue

        # Format table header
        t_text = f"Table: {t.schema_name or 'dbo'}.{t.table_name}\nDescription: {t.description or 'No description'}\nColumns:"
        # Format columns
        if t.columns:
            for col in t.columns:
                t_text += f"\n  - {col.name} ({col.data_type}): {col.description or ''}"
        else:
             t_text += "\n  (No columns defined)"
        schema_parts.append(t_text)
    
    initial_schema_text = "\n\n".join(schema_parts)

    context_guard = ""
    if use_table_override:
        context_guard = "### USER-SELECTED CONTEXT\nYou must only use the following schema context provided by the user. Do not reference tables outside of this selection.\n\n"

    initial_prompt = f"""{database_info}

### QUERY ANALYSIS
Complexity Level: {query_complexity}
Extracted Entities: {', '.join(entities) if entities else 'None'}
Date Ranges: {', '.join(date_ranges) if date_ranges else 'None'}

### KNOWLEDGE BASE EXAMPLES
{reference_text}{value_context}

{context_guard}### DATABASE SCHEMA
{initial_schema_text}

### REASONING PROCESS
1. Identify the entities and values in the user's request.
2. Look at the "VERIFIED DATA MAPPINGS" to see which tables contain the specific data values (e.g., 'Canada' in Customers).
3. Look at the "DATABASE SCHEMA" to find the relationships between these tables.
4. If tables are disjoint (e.g., Categories and Customers), find the "bridge" tables (like Orders, OrderDetails) to join them.
5. Construct the JOIN path step-by-step.

### ATTEMPT HISTORY
First attempt.

## CRITICAL SQL RULES

### 1. SCHEMA ADHERENCE
- Use ONLY the tables and columns defined in the provided schema.
- Pay strict attention to column data types such as INT, VARCHAR, and DATETIME.
- Never assume column names or data types that are not explicitly shown.

### 2. DATA TYPE MATCHING & JOINS
- **CRITICAL**: Before filtering on a column, verify the user's value matches the column's data type.
- If the user provides a STRING value but the target column is INT or NUMERIC, you must JOIN to a related table to look up the ID.
- ALWAYS analyze foreign key relationships found in column descriptions.
- Generate JOIN queries when filtering by attributes from related tables.
- When joining a related table to resolve a type mismatch, do NOT filter on the foreign key ID column using a string value.
- Examine all columns in the joined table's schema and select the column where the data type matches your filter value type and the column name suggests it stores that type of value (e.g., Code, Name).

### 3. TABLE ALIASING & QUALIFICATION
- You MUST use table aliases for every table, such as `FROM dbo.Orders AS o`.
- Every column must be prefixed with its assigned alias, such as `o.OrderID` or `c.CustomerName`.

### 4. T-SQL SYNTAX
- Use `SELECT TOP n` for limiting the number of results.
- Use `DATEPART()` for date components.
- Use `CAST()` for type conversions.
- Use the `N''` prefix for Unicode strings.

### 5. QUERY ANALYSIS PROCESS
- Identify the main entity the user is asking for, such as orders, customers, or products.
- Identify specified filters or conditions, such as customer names or date ranges.
- Compare the data type of each filter value against the target column.
- If a type mismatch exists, determine which related table to JOIN to resolve it.
- Analyze the foreign key relationships between the relevant tables.

### 6. ERROR HANDLING
- If a required column is missing from the schema, return: "COLUMN_VALIDATION_ERROR: Cannot find column [column_name]".
- If a required table is missing, return: "TABLE_VALIDATION_ERROR: Cannot find table [table_name]".

### 7. OUTPUT FORMAT
- When generating T-SQL queries, always provide the explanation at the very top of the response, enclosed within a /* ... */ comment block. The code should follow immediately after the comment block.

Target Request: {request.query}
"""

    # Stage 3: Reasoning-First Generation & Iterative Validation
    current_context_history = []
    error_msg = "Unknown error"
    
    # Build accumulated query history (all user requests from conversation start)
    combined_query = request.query
    if query_history:
        combined_query = f"{query_history}. {request.query}"
    
    for attempt in range(5):
        yield AgentStatus(step_id=10 + attempt, message=f"Generating SQL (Attempt {attempt + 1})..." if attempt == 0 else f"Refining SQL (Attempt {attempt + 1})...")
        # Dynamically build schema text
        schema_text = "\n".join([
            f"{t.description}"
            for t in context.relevant_tables
            if t.description
        ])

        # Build attempt history section with failed SQL and errors
        attempt_history_section = ""
        
        target_request_section = f"Target Request: {combined_query}"
        
        if current_context_history:
            attempt_history_section = "\n### PREVIOUS ATTEMPTS (Learn from these errors)\n"
            attempt_history_section += "\n".join(current_context_history)
            
            # Add context about previous failures to the target request
            failure_summary = f"\n\nPrevious attempt failed with: {error_msg}"
            target_request_section = f"Target Request: {combined_query}{failure_summary}\nPlease fix the issues and generate correct SQL."
        else:
            attempt_history_section = "### ATTEMPT HISTORY\nFirst attempt."

        # Construct the full prompt with failed SQL and error details
        current_prompt = f"""{database_info}

### QUERY ANALYSIS
Complexity Level: {query_complexity}
Extracted Entities: {', '.join(entities) if entities else 'None'}

### KNOWLEDGE BASE EXAMPLES
{reference_text}{value_context}

{context_guard}### DATABASE SCHEMA
{schema_text}

{attempt_history_section}

## CRITICAL SQL RULES

### 1. SCHEMA ADHERENCE
- Use ONLY the tables and columns defined in the provided schema.
- Pay strict attention to column data types such as INT, VARCHAR, and DATETIME.
- Never assume column names or data types that are not explicitly shown.

### 2. DATA TYPE MATCHING & JOINS
- **CRITICAL**: Before filtering on a column, verify the user's value matches the column's data type.
- If the user provides a STRING value but the target column is INT or NUMERIC, you must JOIN to a related table to look up the ID.
- ALWAYS analyze foreign key relationships found in column descriptions.
- Generate JOIN queries when filtering by attributes from related tables.
- When joining a related table to resolve a type mismatch, do NOT filter on the foreign key ID column using a string value.
- Examine all columns in the joined table's schema and select the column where the data type matches your filter value type and the column name suggests it stores that type of value (e.g., Code, Name).

### 3. TABLE ALIASING & QUALIFICATION
- You MUST use table aliases for every table, such as `FROM dbo.Orders AS o`.
- Every column must be prefixed with its assigned alias, such as `o.OrderID` or `c.CustomerName`.

### 4. T-SQL SYNTAX
- Use `SELECT TOP n` for limiting the number of results.
- Use `DATEPART()` for date components.
- Use `CAST()` for type conversions.
- Use the `N''` prefix for Unicode strings.

### 5. QUERY ANALYSIS PROCESS
- Identify the main entity the user is asking for, such as orders, customers, or products.
- Identify specified filters or conditions, such as customer names or date ranges.
- Compare the data type of each filter value against the target column.
- If a type mismatch exists, determine which related table to JOIN to resolve it.
- Analyze the foreign key relationships between the relevant tables.

### 6. ERROR HANDLING
- If a required column is missing from the schema, return: "COLUMN_VALIDATION_ERROR: Cannot find column [column_name]".
- If a required table is missing, return: "TABLE_VALIDATION_ERROR: Cannot find table [table_name]".

### 7. OUTPUT FORMAT
- When generating T-SQL queries, always provide the explanation at the very top of the response, enclosed within a /* ... */ comment block. The code should follow immediately after the comment block.

{target_request_section}
"""

        # Generate SQL query
        sql = llm_service.generate_sql_with_context(request.query, current_prompt)
        
        # Store the generated SQL for later use in attempt history
        generated_sql = sql.strip() if sql else ""
        
        # Validate
        is_special_error, error_text, special_missing = parse_validation_error(sql)
        if is_special_error:
            is_valid, error_msg, missing_cols = False, error_text, special_missing
        else:
            is_valid, error_msg, missing_cols = validate_sql_with_db(sql)

        if is_valid:
            result = GenerateSQLResponse(
                sql=sql,
                explanation="The following code might be able to retrieve the data you requested.",
                query_type="database",
                context_text=current_prompt,
                context_history=current_context_history
            )
            yield {"type": "result", "payload": result}
            yield {"type": "done"}
            return

        # Stage 3.5: Intelligent Recovery Logic
        discovery_feedback = ""
        recovery_instruction = ""
        
        # Check if this is a special validation error (TABLE_VALIDATION_ERROR or COLUMN_VALIDATION_ERROR)
        if not use_table_override and is_special_error and missing_cols:
            # Missing Object recovery - search for the missing objects in vector database
            for missing_obj in missing_cols:
                disc_res = perform_discovery(DiscoveryRequest(query=missing_obj, top_k=5))
                newly_added = False
                for table in disc_res.context.relevant_tables:
                    # Only add if not already in context
                    if not any(t.table_name == table.table_name for t in context.relevant_tables):
                        context.relevant_tables.append(table)
                        discovery_feedback += f"\n- Found new table: {table.table_name} (searched for: {missing_obj})"
                        newly_added = True
                
                # If we found new tables, also do a broader search to find related tables that were excluded
                if newly_added:
                    # Perform additional discovery with broader context to find more related tables
                    broader_query = f"{request.query} {missing_obj}"
                    broader_disc = perform_discovery(DiscoveryRequest(query=broader_query, top_k=5))
                    for table in broader_disc.context.relevant_tables:
                        # Exclude tables already in context
                        if not any(t.table_name == table.table_name for t in context.relevant_tables):
                            context.relevant_tables.append(table)
                            discovery_feedback += f"\n- Found additional related table: {table.table_name}"
            
            if discovery_feedback:
                recovery_instruction = f"Missing Object Recovery: Searched vector database and added newly discovered tables. Retry with updated schema."
            else:
                # No new tables found - stop trying and ask user for more information
                result = GenerateSQLResponse(
                    sql="",
                    explanation=f"I could not find the required objects ({', '.join(missing_cols)}) in the database schema. Please provide more information about:\n1. The correct table or column names\n2. The database schema you're referring to\n3. More context about the data you're trying to query",
                    query_type="database",
                    context_text=current_prompt,
                    context_history=current_context_history
                )
                yield {"type": "result", "payload": result}
                yield {"type": "done"}
                return
        elif not use_table_override and missing_cols:
            # Database validation error with missing objects
            for col in missing_cols:
                disc_res = perform_discovery(DiscoveryRequest(query=col, top_k=3))
                newly_added = False
                for table in disc_res.context.relevant_tables:
                    if not any(t.table_name == table.table_name for t in context.relevant_tables):
                        context.relevant_tables.append(table)
                        discovery_feedback += f"\n- Found new relevant table: {table.table_name}"
                        newly_added = True
                
                # If found, do a broader search for related tables
                if newly_added:
                    broader_query = f"{request.query} {col}"
                    broader_disc = perform_discovery(DiscoveryRequest(query=broader_query, top_k=5))
                    for table in broader_disc.context.relevant_tables:
                        if not any(t.table_name == table.table_name for t in context.relevant_tables):
                            context.relevant_tables.append(table)
                            discovery_feedback += f"\n- Found additional related table: {table.table_name}"
            
            recovery_instruction = "Missing Object Recovery: New tables added. Retry with updated schema."
        elif "Invalid column name" in error_msg or "Ambiguous column name" in error_msg:
            # Ambiguity/Logic Error recovery
            recovery_instruction = f"Self-Correction: {error_msg}\nRe-examine the join logic and ensure all columns are properly qualified with table aliases."
        elif "type mismatch" in error_msg.lower() or "cannot be converted" in error_msg.lower():
            # Type Mismatch recovery
            recovery_instruction = f"Type Mismatch: {error_msg}\nEnsure data types match in comparisons. Use CAST() when necessary."
        else:
            recovery_instruction = f"Query Error: {error_msg}\nReview the SQL syntax and schema constraints."

        # Record this failure into history with clear SQL query and error message
        # Only include "Failed Query:" if generated_sql contains "select" (actual SQL query)
        if generated_sql and "select" in generated_sql.lower():
            failure_entry = f"Attempt {attempt+1}:\nUser Request: {combined_query}\nFailed Query:\n{generated_sql}\n\nError Message:\n{error_msg}{discovery_feedback}\n\nRecovery Strategy:\n{recovery_instruction}"
        else:
            failure_entry = f"Attempt {attempt+1}:\nUser Request: {combined_query}\nError Message:\n{error_msg}{discovery_feedback}\n\nRecovery Strategy:\n{recovery_instruction}"
        current_context_history.append(failure_entry)

    # Stage 4: Final Output after exhausting retries
    # Stage 4: Final Output after exhausting retries
    result = GenerateSQLResponse(
        sql="",
        explanation=f"Failed after 5 attempts. Final error: {error_msg}. Please try rephrasing your query or providing more context.",
        query_type="database",
        context_text=current_prompt,
        context_history=current_context_history
    )
    yield {"type": "result", "payload": result}
    yield {"type": "done"}

def _handle_general_query(request, llm_service):
    # (Helper function logic for general classification to keep main function clean)
    system_prompt = "You are a helpful AI assistant for the database."
    response_text = llm_service.chat_completion(
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": request.query}],
        temperature=0.7
    )
    return GenerateSQLResponse(sql="", explanation=response_text, query_type="general")


def regenerate_sql_with_error_feedback(
    original_request: str,
    failed_sql: str,
    error_message: str,
    schema_context: str,
    attempt_number: int
) -> str:
    """
    Regenerates SQL query based on execution error feedback.
    
    This is a lightweight regeneration function used in the auto-retry loop.
    It focuses specifically on fixing the error without re-running the full
    4-stage discovery pipeline.
    
    Args:
        original_request: User's natural language query
        failed_sql: SQL that failed execution
        error_message: Error traceback from database
        schema_context: Schema descriptions used in original generation
        attempt_number: Current retry attempt (2-5)
        
    Returns:
        Regenerated SQL query as string
    """
    llm_service = get_llm_service()
    
    # Build a focused prompt for error correction
    prompt = f"""You are a T-SQL expert fixing a query that failed execution.

ORIGINAL USER REQUEST:
{original_request}

FAILED SQL QUERY:
{failed_sql}

EXECUTION ERROR:
{error_message}

DATABASE SCHEMA CONTEXT:
{schema_context}

ATTEMPT NUMBER: {attempt_number} of 5

INSTRUCTIONS:
1. Carefully analyze the error message to identify the root cause
2. Maintain the original intent and logic of the query
3. Fix ONLY the specific issue causing the error
4. Follow T-SQL best practices:
   - Use proper table aliases to avoid ambiguous columns
   - Use CAST() for type conversions when needed
   - Qualify all column names with table aliases
   - Use square brackets for reserved words
   - Ensure all referenced tables and columns exist in the schema

COMMON ERROR PATTERNS:
- "Invalid object name" → Check table name spelling and schema
- "Invalid column name" → Verify column exists in schema
- "Ambiguous column name" → Add table alias qualifiers
- "Type mismatch" → Use CAST() or CONVERT()
- "Syntax error" → Check T-SQL syntax (JOIN conditions, WHERE clause, etc.)

OUTPUT:
Return ONLY the corrected SQL query, with no additional text, markdown, or explanation.
"""
    
    try:
        # Call LLM with low temperature for consistency
        fixed_sql = llm_service.chat(prompt, temperature=0.1)
        
        # Clean up any LLM artifacts (markdown blocks, etc.)
        fixed_sql = fixed_sql.strip()
        
        # Remove markdown code blocks
        fixed_sql = re.sub(r'^```sql\s*\n?', '', fixed_sql, flags=re.IGNORECASE)
        fixed_sql = re.sub(r'^```\s*\n?', '', fixed_sql)
        fixed_sql = re.sub(r'\n?```$', '', fixed_sql)
        
        # Remove common prefixes
        if fixed_sql.lower().startswith('sql:'):
            fixed_sql = fixed_sql[4:].strip()
        
        logging.info(f"Regenerated SQL on attempt {attempt_number}")
        return fixed_sql
        
    except Exception as e:
        logging.error(f"Error regenerating SQL: {str(e)}")
        # Return original SQL as fallback
        return failed_sql
    