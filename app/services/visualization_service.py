
import pandas as pd
import json
import logging
import traceback
from typing import List, Dict, Any, Optional
from app.models.schemas import ChartRecommendation
from app.services.llm_service import get_llm_service
from app.utils.logging_utils import log_llm_interaction

logger = logging.getLogger(__name__)

class VisualizationService:
    def __init__(self):
        self.llm_service = get_llm_service()

    def get_chart_recommendation(
        self, 
        df: pd.DataFrame, 
        user_query: str,
        chart_type_override: Optional[str] = None
    ) -> Optional[ChartRecommendation]:
        """
        Analyzes the DataFrame and user query to recommend the best visualization.
        
        Args:
            df: DataFrame containing the data to visualize
            user_query: User's original query/question
            chart_type_override: If provided, use this chart type instead of LLM recommendation
        
        Returns:
            ChartRecommendation or None if no visualization is appropriate
        """
        if df is None or df.empty:
            return None

        # If chart type override is provided, skip LLM and build recommendation directly
        if chart_type_override and chart_type_override != 'none':
            logger.info(f"Using chart type override: {chart_type_override}")
            return self._build_override_recommendation(df, chart_type_override, user_query)

        # 1. Profile the Data
        profile = self._profile_data(df)

        # 2. Build the Consultant Prompt
        prompt = self._build_consultant_prompt(profile, user_query)

        # 3. Call LLM
        try:
            # We use the 'chat' method of the LLM service. 
            # ideally, we would use structured output if available, but JSON mode via prompt is safer for cross-provider
            response_text = self.llm_service.chat(prompt, temperature=0.1)
            
            # 4. Parse Response
            # 4. Parse Response
            recommendation = self._parse_llm_response(response_text)
            
            # 5. Validate Recommendation
            if recommendation and recommendation.chart_type != 'none':
                if not self._validate_columns(df, recommendation):
                     logger.warning("LLM recommended columns that do not exist in the DataFrame. Falling back to None.")
                     # We could try to heuristics here, but for now just fail gracefully to avoid "empty chart"
                     return None

            return recommendation

        except Exception as e:
            logger.error(f"Error getting chart recommendation: {e}")
            logger.error(traceback.format_exc())
            return None

    def _profile_data(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Extracts metadata from the DataFrame to help the LLM understand it.
        """
        # Limit sample to 5 rows
        sample_head = df.head(5).to_dict(orient='records')
        
        # Column types
        dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}
        
        # Cardinality (unique count) for object/category columns to see if they are good for grouping
        cardinality = {}
        for col in df.columns:
            if df[col].dtype == 'object' or df[col].dtype.name == 'category':
                cardinality[col] = df[col].nunique()
            else:
                cardinality[col] = "N/A" # Numeric/Date usually high cardinality

        return {
            "columns": list(df.columns),
            "dtypes": dtypes,
            "row_count": len(df),
            "sample_data": sample_head,
            "categorical_cardinality": cardinality
        }

    def _build_consultant_prompt(self, profile: Dict[str, Any], user_query: str) -> str:
        
        return f"""You are a Data Visualization Expert.
        
Your goal is to recommend the best chart type to visualize the provided dataset based on the user's intent.

### USER CONTENT
User Question: "{user_query}"

### DATA PROFILE
- Total Rows: {profile['row_count']}
- Columns: {', '.join(profile['columns'])}
- Data Types: {json.dumps(profile['dtypes'])}
- Categorical Cardinality (Unique Values): {json.dumps(profile['categorical_cardinality'])}

### DATA SAMPLE (First 5 rows)
{json.dumps(profile['sample_data'], indent=2, default=str)}

### INSTRUCTIONS
1. Analyze the user's intent and the data structure.
2. Select the most appropriate chart type from this list:
   - 'bar': Comparisons among categories.
   - 'line': Trends over time.
   - 'pie': Part-to-whole (only if < 10 categories).
   - 'scatter': Relationship between two numerical variables.
   - 'kpi': Single big number (if result is 1 row/1 col).
   - 'none': If no visualization is appropriate (e.g. text/table data only).

3. Determine the X-Axis and Y-Axis columns.
   - Bar/Line: X is usually categorical/time, Y is numeric.
   - Scatter: X and Y are numeric.
   - Pie: X is label, Y is value.
   - **STRICT CONSTRAINT**: You MUST use columns EXACTLY as listed in "DATA PROFILE - Columns". Do NOT invent columns (e.g., if 'country' is not in the list, do not use it). If the desired column is missing, choose the best alternative or return "none".

4. Provide a Chart Title that summarizes the insight.
5. Provide a short "Explanation" of why you chose this chart.

### OUTPUT FORMAT
Return valid JSON ONLY. No markdown, no explanations outside the JSON.

{{
  "chart_type": "bar" | "line" | "pie" | "scatter" | "kpi" | "none",
  "x_axis": "column_name", 
  "y_axis": ["column_name1", ...],
  "title": "Chart Title",
  "explanation": "Reasoning...",
  "colors": null
}}
"""

    def _parse_llm_response(self, response_text: str) -> Optional[ChartRecommendation]:
        try:
            # Clean markdown code blocks if present
            cleaned_text = response_text.replace("```json", "").replace("```", "").strip()
            
            # Find the first { and last }
            start = cleaned_text.find('{')
            end = cleaned_text.rfind('}')
            
            if start != -1 and end != -1:
                json_str = cleaned_text[start:end+1]
                data = json.loads(json_str)
                
                # Normalize type to lowercase
                if 'chart_type' in data:
                    data['chart_type'] = data['chart_type'].lower()
                
                return ChartRecommendation(**data)
            else:
                logger.warning(f"Could not find JSON in LLM response: {response_text[:100]}...")
                return None
                
        except Exception as e:
            logger.error(f"Failed to parse LLM chart recommendation: {e}")
            logger.debug(f"Raw Response: {response_text}")
            return None

    def _validate_columns(self, df: pd.DataFrame, rec: ChartRecommendation) -> bool:
        """
        Verifies that the recommended x_axis and y_axis columns exist in the DataFrame.
        Attempts case-insensitive matching and updates the recommendation object if needed.
        """
        columns = list(df.columns)
        columns_lower = {c.lower(): c for c in columns}
        
        # Validate X-Axis
        if rec.x_axis:
            if rec.x_axis in columns:
                pass # valid
            elif rec.x_axis.lower() in columns_lower:
                rec.x_axis = columns_lower[rec.x_axis.lower()] # Auto-correct case
            else:
                logger.warning(f"Invalid X-Axis: {rec.x_axis}. Available: {columns}")
                return False
                
        # Validate Y-Axis
        if rec.y_axis:
            valid_y = []
            for y_col in rec.y_axis:
                if y_col in columns:
                    valid_y.append(y_col)
                elif y_col.lower() in columns_lower:
                    valid_y.append(columns_lower[y_col.lower()]) # Auto-correct case
                else:
                    logger.warning(f"Invalid Y-Axis col: {y_col}. Available: {columns}")
                    
            if not valid_y:
                return False # No valid Y columns
            rec.y_axis = valid_y
            
        # Validate Colors
        if rec.colors:
            # Filter out any values that look like the example placeholder or are clearly invalid
            valid_colors = []
            for color in rec.colors:
                if isinstance(color, str) and color.startswith('#') and len(color) in [4, 7]:
                    valid_colors.append(color)
                # Allow named colors if needed, but for now stick to hex or safe defaults
            
            # If we filtered everything out (or it was just the placeholder), set to None to force default colors
            if not valid_colors:
                rec.colors = None
            else:
                rec.colors = valid_colors

        return True

    def _build_override_recommendation(
        self, 
        df: pd.DataFrame, 
        chart_type: str,
        user_query: str = ""
    ) -> Optional[ChartRecommendation]:
        """
        Build a chart recommendation using explicit chart type override.
        Attempts to intelligently select x/y axes based on data types.
        
        Args:
            df: DataFrame to visualize
            chart_type: The chart type requested by user
            user_query: Original user query for context
        
        Returns:
            ChartRecommendation with the specified chart type
        """
        columns = list(df.columns)
        
        # Separate numeric and categorical columns
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        datetime_cols = df.select_dtypes(include=['datetime64']).columns.tolist()
        
        # If no numeric columns found, try to identify columns that might be numeric
        # (sometimes numeric values are stored as strings after serialization)
        if not numeric_cols and categorical_cols:
            potential_numeric = []
            for col in categorical_cols:
                try:
                    # Try to convert to numeric - if most values convert, treat as numeric
                    converted = pd.to_numeric(df[col], errors='coerce')
                    non_null_ratio = converted.notna().sum() / len(converted) if len(converted) > 0 else 0
                    if non_null_ratio > 0.8:  # 80% of values can be converted
                        potential_numeric.append(col)
                except:
                    pass
            
            if potential_numeric:
                numeric_cols = potential_numeric
                # Remove these from categorical since they're actually numeric
                categorical_cols = [c for c in categorical_cols if c not in potential_numeric]
        
        x_axis = None
        y_axis = []
        
        if chart_type == 'line':
            # Line charts: prefer datetime/categorical for X, numeric for Y
            if datetime_cols:
                x_axis = datetime_cols[0]
            elif categorical_cols:
                x_axis = categorical_cols[0]
            elif columns:
                x_axis = columns[0]
            y_axis = numeric_cols[:3] if numeric_cols else []
            
            # Fallback: if we have x_axis but no y_axis, use remaining columns
            if x_axis and not y_axis:
                remaining = [c for c in columns if c != x_axis]
                y_axis = remaining[:3]
            
        elif chart_type == 'bar':
            # Bar charts: categorical X, numeric Y
            if categorical_cols:
                x_axis = categorical_cols[0]
            elif columns:
                x_axis = columns[0]
            y_axis = numeric_cols[:3] if numeric_cols else []
            
            # Fallback: if we have x_axis but no y_axis, use remaining columns
            if x_axis and not y_axis:
                remaining = [c for c in columns if c != x_axis]
                y_axis = remaining[:3]
            
        elif chart_type == 'pie':
            # Pie charts: categorical label, single numeric value
            if categorical_cols:
                x_axis = categorical_cols[0]
            elif columns:
                x_axis = columns[0]
            y_axis = numeric_cols[:1] if numeric_cols else []
            
            # Fallback: use second column if available
            if x_axis and not y_axis and len(columns) > 1:
                remaining = [c for c in columns if c != x_axis]
                y_axis = remaining[:1]
            
        elif chart_type == 'scatter':
            # Scatter: two numeric columns
            if len(numeric_cols) >= 2:
                x_axis = numeric_cols[0]
                y_axis = [numeric_cols[1]]
            elif len(numeric_cols) == 1 and columns:
                x_axis = columns[0]
                y_axis = numeric_cols
            elif len(columns) >= 2:
                # Fallback: use first two columns
                x_axis = columns[0]
                y_axis = [columns[1]]
                
        elif chart_type == 'kpi':
            # KPI: single value
            if numeric_cols:
                y_axis = [numeric_cols[0]]
            elif columns:
                y_axis = [columns[0]]
        
        # Final fallback if we still couldn't determine axes
        if not x_axis and not y_axis:
            if len(columns) >= 2:
                x_axis = columns[0]
                y_axis = [columns[1]]
            elif len(columns) == 1:
                y_axis = [columns[0]]
        
        # Ensure y_axis is never None when we have columns to work with
        if not y_axis and x_axis and len(columns) > 1:
            y_axis = [c for c in columns if c != x_axis][:3]
        
        return ChartRecommendation(
            chart_type=chart_type,  # type: ignore
            x_axis=x_axis,
            y_axis=y_axis if y_axis else None,
            title=f"Data Visualization ({chart_type.title()} Chart)",
            explanation=f"User requested {chart_type} chart visualization",
            colors=None
        )
