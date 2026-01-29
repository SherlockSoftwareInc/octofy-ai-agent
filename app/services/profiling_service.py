"""
Data Profiling Service

Analyzes DataFrames and extracts statistical profiles, patterns, and anomalies.
Implements smart profiling levels based on dataset size to maintain <10s performance target.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from app.models.schemas import (
    DataProfile,
    ColumnProfile,
    NumericStats,
    CategoricalStats
)
import logging

logger = logging.getLogger(__name__)


class ProfilingService:
    """Service for profiling DataFrames and extracting statistical insights"""
    
    # Configuration thresholds
    MAX_ROWS_FOR_DISTRIBUTION = 10000  # For outlier/distribution analysis
    MAX_ROWS_FOR_RELATIONSHIP = 5000   # For correlation analysis
    MAX_COLS_FOR_RELATIONSHIP = 10     # Maximum columns for correlation
    IQR_MULTIPLIER = 3.0               # IQR multiplier for outlier detection
    CORRELATION_THRESHOLD = 0.5        # Minimum |r| to report correlation
    
    def profile_dataframe(
        self,
        df: pd.DataFrame,
        max_rows_for_advanced: int = MAX_ROWS_FOR_DISTRIBUTION
    ) -> DataProfile:
        """
        Profile a DataFrame with smart level selection based on size.
        
        Profiling Levels:
        - basic: Always (row/col counts, dtypes, null%, basic stats) - ~0.5s for 10k rows
        - distribution: If rows < 10k (outliers, histograms) - ~1-2s additional
        - relationship: If rows < 5k AND cols < 10 (correlations) - ~1-2s additional
        
        Args:
            df: DataFrame to profile
            max_rows_for_advanced: Maximum rows to enable advanced profiling
            
        Returns:
            DataProfile with statistics and patterns
        """
        try:
            row_count = len(df)
            column_count = len(df.columns)
            
            # Determine profiling level
            if row_count < self.MAX_ROWS_FOR_RELATIONSHIP and column_count < self.MAX_COLS_FOR_RELATIONSHIP:
                profiling_level = "relationship"
            elif row_count < self.MAX_ROWS_FOR_DISTRIBUTION:
                profiling_level = "distribution"
            else:
                profiling_level = "basic"
            
            logger.info(f"Profiling {row_count} rows x {column_count} cols at '{profiling_level}' level")
            
            # Profile each column
            column_profiles = []
            datetime_columns = []
            
            for col in df.columns:
                series = df[col]
                dtype = str(series.dtype)
                
                # Check if datetime
                if pd.api.types.is_datetime64_any_dtype(series):
                    datetime_columns.append(col)
                    dtype = "datetime"
                
                # Profile based on type
                if pd.api.types.is_numeric_dtype(series):
                    numeric_stats = self._profile_numeric_column(
                        series, 
                        include_outliers=(profiling_level in ["distribution", "relationship"])
                    )
                    column_profiles.append(ColumnProfile(
                        column_name=col,
                        data_type=dtype,
                        numeric_stats=numeric_stats
                    ))
                else:
                    categorical_stats = self._profile_categorical_column(series)
                    column_profiles.append(ColumnProfile(
                        column_name=col,
                        data_type=dtype,
                        categorical_stats=categorical_stats
                    ))
            
            # Calculate correlations if relationship level
            correlations = None
            if profiling_level == "relationship":
                correlations = self._calculate_correlations(df)
            
            return DataProfile(
                row_count=row_count,
                column_count=column_count,
                columns=column_profiles,
                correlations=correlations,
                has_datetime=len(datetime_columns) > 0,
                datetime_columns=datetime_columns,
                profiling_level=profiling_level
            )
            
        except Exception as e:
            logger.error(f"Error profiling DataFrame: {str(e)}")
            # Return minimal profile on error
            return DataProfile(
                row_count=len(df),
                column_count=len(df.columns),
                columns=[],
                profiling_level="basic"
            )
    
    def _profile_numeric_column(
        self, 
        series: pd.Series, 
        include_outliers: bool = True
    ) -> NumericStats:
        """
        Calculate statistics for numeric column.
        
        Args:
            series: Numeric pandas Series
            include_outliers: Whether to detect outliers (slower)
            
        Returns:
            NumericStats with min, max, mean, median, std, quartiles, outliers
        """
        # Handle null values
        valid_series = series.dropna()
        null_count = len(series) - len(valid_series)
        null_percentage = (null_count / len(series) * 100) if len(series) > 0 else 0
        
        # If all nulls, return minimal stats
        if len(valid_series) == 0:
            return NumericStats(
                min=0, max=0, mean=0, median=0, std=0,
                q25=0, q75=0,
                null_count=null_count,
                null_percentage=null_percentage,
                outliers=[]
            )
        
        # Calculate basic stats
        stats = {
            'min': float(valid_series.min()),
            'max': float(valid_series.max()),
            'mean': float(valid_series.mean()),
            'median': float(valid_series.median()),
            'std': float(valid_series.std()) if len(valid_series) > 1 else 0,
            'q25': float(valid_series.quantile(0.25)),
            'q75': float(valid_series.quantile(0.75)),
        }
        
        # Detect outliers using IQR method
        outliers = []
        if include_outliers:
            outliers = self._detect_outliers(valid_series)
        
        return NumericStats(
            **stats,
            null_count=null_count,
            null_percentage=null_percentage,
            outliers=outliers[:10]  # Limit to 10 outliers to avoid large payloads
        )
    
    def _profile_categorical_column(self, series: pd.Series) -> CategoricalStats:
        """
        Calculate statistics for categorical/string column.
        
        Args:
            series: Categorical pandas Series
            
        Returns:
            CategoricalStats with unique count, top values, frequencies
        """
        # Handle null values
        valid_series = series.dropna()
        null_count = len(series) - len(valid_series)
        null_percentage = (null_count / len(series) * 100) if len(series) > 0 else 0
        
        # Calculate unique count
        unique_count = valid_series.nunique()
        
        # Get top 5 values with counts and percentages
        top_values = []
        if len(valid_series) > 0:
            value_counts = valid_series.value_counts().head(5)
            total = len(valid_series)
            
            for value, count in value_counts.items():
                # Convert value to string for JSON serialization
                value_str = str(value)
                if len(value_str) > 100:  # Truncate very long strings
                    value_str = value_str[:100] + "..."
                
                top_values.append({
                    'value': value_str,
                    'count': int(count),
                    'percentage': round((count / total * 100), 2)
                })
        
        return CategoricalStats(
            unique_count=unique_count,
            top_values=top_values,
            null_count=null_count,
            null_percentage=null_percentage
        )
    
    def _detect_outliers(self, series: pd.Series) -> List[Any]:
        """
        Detect outliers using IQR method: values outside [Q1-3*IQR, Q3+3*IQR]
        
        Args:
            series: Numeric pandas Series
            
        Returns:
            List of outlier values
        """
        try:
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            
            lower_bound = q1 - (self.IQR_MULTIPLIER * iqr)
            upper_bound = q3 + (self.IQR_MULTIPLIER * iqr)
            
            outliers = series[(series < lower_bound) | (series > upper_bound)]
            
            # Convert to list and limit size
            outlier_list = outliers.tolist()
            return [float(x) for x in outlier_list[:20]]  # Limit to 20 outliers
            
        except Exception as e:
            logger.error(f"Error detecting outliers: {str(e)}")
            return []
    
    def _calculate_correlations(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Calculate Pearson correlations for numeric columns.
        Only reports correlations where |r| > threshold.
        
        Args:
            df: DataFrame with numeric columns
            
        Returns:
            List of correlation dictionaries [{col1, col2, correlation}]
        """
        try:
            # Select only numeric columns
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            
            if len(numeric_cols) < 2:
                return []
            
            # Calculate correlation matrix
            corr_matrix = df[numeric_cols].corr()
            
            # Extract significant correlations
            correlations = []
            for i, col1 in enumerate(numeric_cols):
                for j, col2 in enumerate(numeric_cols):
                    if i < j:  # Only upper triangle (avoid duplicates)
                        corr_value = corr_matrix.loc[col1, col2]
                        
                        # Only report if above threshold and not NaN
                        if not pd.isna(corr_value) and abs(corr_value) > self.CORRELATION_THRESHOLD:
                            correlations.append({
                                'col1': col1,
                                'col2': col2,
                                'correlation': round(float(corr_value), 3)
                            })
            
            # Sort by absolute correlation (strongest first)
            correlations.sort(key=lambda x: abs(x['correlation']), reverse=True)
            
            return correlations[:10]  # Limit to top 10 correlations
            
        except Exception as e:
            logger.error(f"Error calculating correlations: {str(e)}")
            return []
