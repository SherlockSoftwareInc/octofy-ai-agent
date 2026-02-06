
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
        chart_type_override: Optional[str] = None,
        preserved_x_axis: Optional[str] = None,
        preserved_y_axis: Optional[List[str]] = None
    ) -> Optional[ChartRecommendation]:
        """
        Analyzes the DataFrame and user query to recommend the best visualization.
        
        Args:
            df: DataFrame containing the data to visualize
            user_query: User's original query/question
            chart_type_override: If provided, use this chart type instead of LLM recommendation
            preserved_x_axis: Preserve original x_axis column when changing chart type
            preserved_y_axis: Preserve original y_axis columns when changing chart type
        
        Returns:
            ChartRecommendation or None if no visualization is appropriate
        """
        if df is None or df.empty:
            return None

        # If chart type override is provided, skip LLM and build recommendation directly
        if chart_type_override and chart_type_override != 'none':
            logger.info(f"Using chart type override: {chart_type_override}")
            return self._build_override_recommendation(df, chart_type_override, user_query, preserved_x_axis, preserved_y_axis)

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
            recommendation = self._parse_llm_response(response_text)
            
            # 5. Validate Recommendation
            if recommendation and recommendation.chart_type != 'none':
                if not self._validate_columns(df, recommendation):
                     logger.warning("LLM recommended columns that do not exist in the DataFrame. Falling back to None.")
                     # We could try to heuristics here, but for now just fail gracefully to avoid "empty chart"
                     return None
                
                # 6. Fix axis assignment to ensure consistent conventions
                recommendation = self._fix_axis_assignment(df, recommendation)

            return recommendation

        except Exception as e:
            logger.error(f"Error getting chart recommendation: {e}")
            logger.error(traceback.format_exc())
            return None
    
    def _fix_axis_assignment(self, df: pd.DataFrame, rec: ChartRecommendation) -> ChartRecommendation:
        """
        Ensures axis assignment follows consistent conventions:
        - Bar/Column/Stacked charts: categorical X, numeric Y
        - Line/Area: datetime/categorical X, numeric Y
        - Scatter: numeric X, numeric Y
        - Pie/Treemap/Funnel: categorical X, numeric Y
        """
        chart_type = rec.chart_type
        
        # Chart types that need categorical X, numeric Y
        categorical_x_charts = ['column', 'stackedColumn', 'clusteredColumn', 'pie', 'treemap', 'funnel']
        
        if chart_type not in categorical_x_charts:
            return rec  # Don't modify line, scatter, area, radar, etc.
        
        # Classify columns
        numeric_cols = []
        categorical_cols = []
        
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                numeric_cols.append(col)
            else:
                categorical_cols.append(col)
        
        # Check if x_axis is numeric when it should be categorical
        x_is_numeric = rec.x_axis in numeric_cols
        y_has_categorical = any(y in categorical_cols for y in (rec.y_axis or []))
        
        # If x_axis is numeric and y_axis has categorical, swap them
        if x_is_numeric and y_has_categorical:
            logger.info(f"Fixing axis assignment: swapping x_axis ({rec.x_axis}) with categorical y_axis")
            # Find the first categorical column in y_axis
            categorical_y = next((y for y in rec.y_axis if y in categorical_cols), None)
            if categorical_y:
                old_x = rec.x_axis
                rec.x_axis = categorical_y
                # Replace the categorical in y_axis with the old numeric x
                rec.y_axis = [old_x if y == categorical_y else y for y in rec.y_axis]
        
        # If x_axis is numeric and there are categorical columns available, use categorical for X
        elif x_is_numeric and categorical_cols:
            logger.info(f"Fixing axis assignment: x_axis ({rec.x_axis}) is numeric, using categorical column instead")
            old_x = rec.x_axis
            rec.x_axis = categorical_cols[0]
            # Make sure old_x is in y_axis if it's numeric
            if old_x not in (rec.y_axis or []):
                rec.y_axis = [old_x] + (rec.y_axis or [])
        
        # If y_axis has no numeric columns but there are numeric columns available
        if rec.y_axis:
            y_numerics = [y for y in rec.y_axis if y in numeric_cols]
            if not y_numerics and numeric_cols:
                logger.info(f"Fixing axis assignment: y_axis has no numeric columns, using available numeric columns")
                rec.y_axis = [n for n in numeric_cols if n != rec.x_axis][:3]
        
        return rec

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
   - 'line': Line chart for trends over time or continuous data.
   - 'pie': Pie chart for part-to-whole (only if < 10 categories).
   - 'scatter': Scatter plot for relationship between two numerical variables.
   - 'column': Vertical column chart for comparisons among categories.
   - 'area': Area chart for cumulative trends over time.
   - 'stackedColumn': Stacked vertical column chart for multi-series comparisons.
   - 'clusteredColumn': Grouped vertical columns for side-by-side comparisons.
   - 'treemap': Treemap for hierarchical part-to-whole relationships.
   - 'radar': Radar/spider chart for multivariate data comparison.
   - 'funnel': Funnel chart for sequential stage analysis (e.g., conversion rates).
   - 'none': If no visualization is appropriate (e.g. text/table data only).

3. Determine the X-Axis and Y-Axis columns using these STRICT conventions:
   - **Column/StackedColumn/ClusteredColumn**: X-axis MUST be the categorical/label column, Y-axis MUST be the numeric value column(s).
   - **Line/Area**: X-axis is time/date column (preferred) or categorical, Y-axis is numeric.
   - **Scatter**: Both X and Y are numeric columns.
   - **Pie/Treemap/Funnel**: X is the label/category column, Y is the single numeric value column.
   - **AXIS RULE**: For column-type charts, ALWAYS put the category/label column (e.g., ProductName, Country, Status) on X-axis and the numeric measure (e.g., TotalSales, Count, Revenue) on Y-axis.
   - **STRICT CONSTRAINT**: You MUST use columns EXACTLY as listed in "DATA PROFILE - Columns". Do NOT invent columns (e.g., if 'country' is not in the list, do not use it). If the desired column is missing, choose the best alternative or return "none".

4. Provide a Chart Title that summarizes the insight.
5. Provide a short "Explanation" of why you chose this chart.

### OUTPUT FORMAT
Return valid JSON ONLY. No markdown, no explanations outside the JSON.

{{
  "chart_type": "line" | "pie" | "scatter" | "column" | "area" | "stackedColumn" | "clusteredColumn" | "treemap" | "radar" | "funnel" | "none",
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
        user_query: str = "",
        preserved_x_axis: Optional[str] = None,
        preserved_y_axis: Optional[List[str]] = None
    ) -> Optional[ChartRecommendation]:
        """
        Build a chart recommendation using explicit chart type override.
        Uses intelligent column classification and cardinality analysis for axis mapping.
        
        Args:
            df: DataFrame to visualize
            chart_type: The chart type requested by user
            user_query: Original user query for context
            preserved_x_axis: Preserve original x_axis column when changing chart type
            preserved_y_axis: Preserve original y_axis columns when changing chart type
        
        Returns:
            ChartRecommendation with the specified chart type
        """
        # If preserved columns are provided, use them directly
        if preserved_x_axis is not None and preserved_y_axis is not None:
            logger.info(f"Using preserved axes: x={preserved_x_axis}, y={preserved_y_axis}")
            return ChartRecommendation(
                chart_type=chart_type,
                x_axis=preserved_x_axis,
                y_axis=preserved_y_axis,
                explanation=f"Chart type changed to {chart_type} with preserved column selections"
            )
        columns = list(df.columns)
        
        # === 1. Classify Columns (improved detection) ===
        datetime_cols = []
        numeric_cols = []
        categorical_cols = []
        
        for col in df.columns:
            # Detect Datetime
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                datetime_cols.append(col)
            # Detect Numeric
            elif pd.api.types.is_numeric_dtype(df[col]):
                numeric_cols.append(col)
            # Detect Categorical (check if strings might be dates first)
            else:
                try:
                    sample = df[col].dropna().iloc[0] if len(df[col].dropna()) > 0 else None
                    if sample is not None:
                        pd.to_datetime(sample)
                        datetime_cols.append(col)
                    else:
                        categorical_cols.append(col)
                except (ValueError, TypeError, IndexError):
                    categorical_cols.append(col)
        
        # If no numeric columns found, try to identify columns that might be numeric
        # (sometimes numeric values are stored as strings after serialization)
        if not numeric_cols and categorical_cols:
            potential_numeric = []
            for col in categorical_cols:
                try:
                    converted = pd.to_numeric(df[col], errors='coerce')
                    non_null_ratio = converted.notna().sum() / len(converted) if len(converted) > 0 else 0
                    if non_null_ratio > 0.8:  # 80% of values can be converted
                        potential_numeric.append(col)
                except:
                    pass
            
            if potential_numeric:
                numeric_cols = potential_numeric
                categorical_cols = [c for c in categorical_cols if c not in potential_numeric]
        
        x_axis = None
        y_axis = []
        explanation = f"User requested {chart_type} chart visualization"
        
        # === 2. Chart Type Specific Axis Mapping ===
        
        if chart_type == 'line':
            # Line charts: prefer datetime for X, numeric for Y (time series)
            if datetime_cols:
                x_axis = datetime_cols[0]
            elif categorical_cols:
                x_axis = categorical_cols[0]
            elif columns:
                x_axis = columns[0]
            y_axis = numeric_cols[:3] if numeric_cols else []
            
            if x_axis and not y_axis:
                remaining = [c for c in columns if c != x_axis]
                y_axis = remaining[:3]
            
            if datetime_cols and numeric_cols:
                explanation = "Time-based data detected. Line chart shows trends over time."
            
        # Note: 'bar' chart type removed - use 'column' instead
            
        elif chart_type == 'column':
            # Vertical column charts: categorical on X-axis, numeric on Y-axis
            if categorical_cols:
                x_axis = categorical_cols[0]
            elif columns:
                x_axis = columns[0]
            y_axis = numeric_cols[:3] if numeric_cols else []
            
            if x_axis and not y_axis:
                remaining = [c for c in columns if c != x_axis]
                y_axis = remaining[:3]
            
            explanation = "Vertical column chart for categorical comparison."
            
        elif chart_type in ('stackedColumn', 'clusteredColumn'):
            # Stacked/Clustered columns: categorical X, multiple numeric Y
            if categorical_cols:
                x_axis = categorical_cols[0]
            elif columns:
                x_axis = columns[0]
            y_axis = numeric_cols[:5] if numeric_cols else []
            
            if x_axis and not y_axis:
                remaining = [c for c in columns if c != x_axis]
                y_axis = remaining[:5]
            
            chart_label = "Stacked" if chart_type == 'stackedColumn' else "Clustered"
            explanation = f"{chart_label} column chart for multi-series comparison."
            
        # Note: 'stackedBar' chart type removed - use 'stackedColumn' instead
            
        elif chart_type == 'pie':
            # Pie charts: categorical label, single numeric value
            if categorical_cols:
                x_axis = categorical_cols[0]
                cardinality = df[categorical_cols[0]].nunique()
                if cardinality > 10:
                    explanation = f"Pie chart with {cardinality} slices. Consider using column chart for better readability."
                else:
                    explanation = "Pie chart showing part-to-whole relationship."
            elif columns:
                x_axis = columns[0]
            y_axis = numeric_cols[:1] if numeric_cols else []
            
            if x_axis and not y_axis and len(columns) > 1:
                remaining = [c for c in columns if c != x_axis]
                y_axis = remaining[:1]
            
        elif chart_type == 'scatter':
            # Scatter: two numeric columns
            if len(numeric_cols) >= 2:
                x_axis = numeric_cols[0]
                y_axis = [numeric_cols[1]]
                explanation = "Scatter plot for correlation analysis between two numeric variables."
            elif len(numeric_cols) == 1 and columns:
                x_axis = columns[0]
                y_axis = numeric_cols
            elif len(columns) >= 2:
                x_axis = columns[0]
                y_axis = [columns[1]]
        
        elif chart_type == 'treemap':
            # Treemap: categorical label, single numeric value (like pie)
            if categorical_cols:
                x_axis = categorical_cols[0]
            elif columns:
                x_axis = columns[0]
            y_axis = numeric_cols[:1] if numeric_cols else []
            
            if x_axis and not y_axis and len(columns) > 1:
                remaining = [c for c in columns if c != x_axis]
                y_axis = remaining[:1]
            
            explanation = "Treemap showing hierarchical part-to-whole relationship."
        
        elif chart_type == 'area':
            # Area charts: similar to line charts (time series)
            if datetime_cols:
                x_axis = datetime_cols[0]
            elif categorical_cols:
                x_axis = categorical_cols[0]
            elif columns:
                x_axis = columns[0]
            y_axis = numeric_cols[:3] if numeric_cols else []
            
            if x_axis and not y_axis:
                remaining = [c for c in columns if c != x_axis]
                y_axis = remaining[:3]
            
            explanation = "Area chart showing cumulative trends."
        
        elif chart_type == 'radar':
            # Radar charts: categorical for angle axis, numeric for values
            if categorical_cols:
                x_axis = categorical_cols[0]
            elif columns:
                x_axis = columns[0]
            y_axis = numeric_cols[:5] if numeric_cols else []
            
            if x_axis and not y_axis:
                remaining = [c for c in columns if c != x_axis]
                y_axis = remaining[:5]
            
            explanation = "Radar chart for multivariate data comparison."
        
        elif chart_type == 'funnel':
            # Funnel charts: categorical label (stage), single numeric value
            if categorical_cols:
                x_axis = categorical_cols[0]
            elif columns:
                x_axis = columns[0]
            y_axis = numeric_cols[:1] if numeric_cols else []
            
            if x_axis and not y_axis and len(columns) > 1:
                remaining = [c for c in columns if c != x_axis]
                y_axis = remaining[:1]
            
            explanation = "Funnel chart for sequential stage analysis."
        
        # === 3. Final Fallbacks ===
        if not x_axis and not y_axis:
            if len(columns) >= 2:
                x_axis = columns[0]
                y_axis = [columns[1]]
            elif len(columns) == 1:
                y_axis = [columns[0]]
        
        if not y_axis and x_axis and len(columns) > 1:
            y_axis = [c for c in columns if c != x_axis][:3]
        
        return ChartRecommendation(
            chart_type=chart_type,  # type: ignore
            x_axis=x_axis,
            y_axis=y_axis if y_axis else None,
            title=f"Data Visualization ({chart_type.replace('stacked', 'Stacked ').replace('clustered', 'Clustered ').title()} Chart)",
            explanation=explanation,
            colors=None
        )
