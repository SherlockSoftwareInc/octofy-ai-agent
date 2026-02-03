"""
Activity logging service for user activity tracking.

Provides functions to log user activities, retrieve activity logs,
and compute usage statistics.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_, case
from datetime import datetime, timedelta
from fastapi import Request

from app.models.activity_models import UserActivity


# ============================================================================
# Activity Logging
# ============================================================================

def log_activity(
    db: Session,
    user_id: int,
    activity_type: str,
    activity_data: Optional[Dict[str, Any]] = None,
    tokens_used: Optional[int] = None,
    execution_time: Optional[float] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    request: Optional[Request] = None
) -> UserActivity:
    """
    Log a user activity.
    
    Args:
        db: Database session
        user_id: User ID
        activity_type: Type of activity (e.g., 'sql_generated', 'sql_executed')
        activity_data: Additional activity details as JSON
        tokens_used: Number of LLM tokens consumed
        execution_time: Execution time in seconds
        success: Whether the operation succeeded
        error_message: Error message if failed
        request: FastAPI request object for extracting IP/user-agent
        
    Returns:
        Created UserActivity instance
    """
    # Extract request metadata if available
    ip_address = None
    user_agent = None
    if request:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
    
    activity = UserActivity(
        user_id=user_id,
        activity_type=activity_type,
        activity_data=activity_data,
        tokens_used=tokens_used,
        execution_time=execution_time,
        success=success,
        error_message=error_message,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    db.add(activity)
    db.commit()
    db.refresh(activity)
    
    return activity


def log_sql_generation(
    db: Session,
    user_id: int,
    query: str,
    sql: Optional[str] = None,
    tokens_used: Optional[int] = None,
    execution_time: Optional[float] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    request: Optional[Request] = None,
    **kwargs  # Additional metadata like table_override, query_mode, etc.
) -> UserActivity:
    """Log SQL generation activity."""
    activity_data = {
        "query": query,
        "sql": sql,
        **kwargs
    }
    
    return log_activity(
        db=db,
        user_id=user_id,
        activity_type="sql_generated",
        activity_data=activity_data,
        tokens_used=tokens_used,
        execution_time=execution_time,
        success=success,
        error_message=error_message,
        request=request
    )


def log_sql_execution(
    db: Session,
    user_id: int,
    sql: str,
    rows_affected: Optional[int] = None,
    execution_time: Optional[float] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    request: Optional[Request] = None,
    **kwargs
) -> UserActivity:
    """Log SQL execution activity."""
    activity_data = {
        "sql": sql,
        "rows_affected": rows_affected,
        **kwargs
    }
    
    return log_activity(
        db=db,
        user_id=user_id,
        activity_type="sql_executed",
        activity_data=activity_data,
        execution_time=execution_time,
        success=success,
        error_message=error_message,
        request=request
    )


def log_code_execution(
    db: Session,
    user_id: int,
    code_type: str,  # 'python', 'r', 'sas'
    code: str,
    execution_time: Optional[float] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    request: Optional[Request] = None,
    **kwargs
) -> UserActivity:
    """Log code execution activity (Python/R/SAS)."""
    activity_data = {
        "code_type": code_type,
        "code": code[:500] if code else None,  # Truncate long code
        **kwargs
    }
    
    return log_activity(
        db=db,
        user_id=user_id,
        activity_type=f"{code_type}_executed",
        activity_data=activity_data,
        execution_time=execution_time,
        success=success,
        error_message=error_message,
        request=request
    )


# ============================================================================
# Activity Retrieval
# ============================================================================

def get_user_activities(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    activity_type: Optional[str] = None,
    success_only: Optional[bool] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> List[UserActivity]:
    """
    Get user activities with filtering and pagination.
    
    Args:
        db: Database session
        user_id: User ID
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        activity_type: Filter by activity type
        success_only: Filter by success status
        start_date: Filter activities after this date
        end_date: Filter activities before this date
        
    Returns:
        List of UserActivity instances
    """
    query = db.query(UserActivity).filter(UserActivity.user_id == user_id)
    
    if activity_type:
        query = query.filter(UserActivity.activity_type == activity_type)
    
    if success_only is not None:
        query = query.filter(UserActivity.success == success_only)
    
    if start_date:
        query = query.filter(UserActivity.created_at >= start_date)
    
    if end_date:
        query = query.filter(UserActivity.created_at <= end_date)
    
    return query.order_by(desc(UserActivity.created_at)).offset(skip).limit(limit).all()


def get_activity_count(
    db: Session,
    user_id: int,
    activity_type: Optional[str] = None,
    success_only: Optional[bool] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> int:
    """Get total count of activities matching filters."""
    query = db.query(UserActivity).filter(UserActivity.user_id == user_id)
    
    if activity_type:
        query = query.filter(UserActivity.activity_type == activity_type)
    
    if success_only is not None:
        query = query.filter(UserActivity.success == success_only)
    
    if start_date:
        query = query.filter(UserActivity.created_at >= start_date)
    
    if end_date:
        query = query.filter(UserActivity.created_at <= end_date)
    
    return query.count()


# ============================================================================
# User Statistics
# ============================================================================

def get_user_statistics(db: Session, user_id: int, days: int = 30) -> Dict[str, Any]:
    """
    Get comprehensive user statistics.
    
    Args:
        db: Database session
        user_id: User ID
        days: Number of days to include in statistics (default: 30)
        
    Returns:
        Dictionary with user statistics
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Total activities by type
    activity_counts = db.query(
        UserActivity.activity_type,
        func.count(UserActivity.id).label('count')
    ).filter(
        UserActivity.user_id == user_id,
        UserActivity.created_at >= start_date
    ).group_by(UserActivity.activity_type).all()
    
    activities_by_type = {row.activity_type: row.count for row in activity_counts}
    
    # Success vs failure counts
    success_stats = db.query(
        func.sum(case((UserActivity.success == True, 1), else_=0)).label('success_count'),
        func.sum(case((UserActivity.success == False, 1), else_=0)).label('failure_count')
    ).filter(
        UserActivity.user_id == user_id,
        UserActivity.created_at >= start_date
    ).first()
    
    # Total tokens used
    total_tokens = db.query(
        func.sum(UserActivity.tokens_used)
    ).filter(
        UserActivity.user_id == user_id,
        UserActivity.created_at >= start_date,
        UserActivity.tokens_used.isnot(None)
    ).scalar() or 0
    
    # Average execution time
    avg_execution_time = db.query(
        func.avg(UserActivity.execution_time)
    ).filter(
        UserActivity.user_id == user_id,
        UserActivity.created_at >= start_date,
        UserActivity.execution_time.isnot(None)
    ).scalar() or 0
    
    # Recent activities (last 10)
    recent_activities = get_user_activities(db, user_id, skip=0, limit=10, start_date=start_date)
    
    # Daily activity trend (last 7 days)
    daily_trend = []
    for i in range(6, -1, -1):  # Last 7 days
        day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        
        count = db.query(func.count(UserActivity.id)).filter(
            UserActivity.user_id == user_id,
            UserActivity.created_at >= day_start,
            UserActivity.created_at < day_end
        ).scalar()
        
        daily_trend.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "count": count
        })
    
    return {
        "user_id": user_id,
        "period_days": days,
        "total_activities": sum(activities_by_type.values()),
        "activities_by_type": activities_by_type,
        "success_count": int(success_stats.success_count or 0),
        "failure_count": int(success_stats.failure_count or 0),
        "success_rate": round(
            (success_stats.success_count / (success_stats.success_count + success_stats.failure_count) * 100)
            if (success_stats.success_count or 0) + (success_stats.failure_count or 0) > 0 else 0,
            2
        ),
        "total_tokens_used": int(total_tokens),
        "avg_execution_time": round(float(avg_execution_time), 3),
        "recent_activities": [activity.to_dict() for activity in recent_activities],
        "daily_trend": daily_trend
    }


def get_all_users_overview(db: Session, days: int = 7) -> Dict[str, Any]:
    """
    Get system-wide statistics for all users.
    
    Args:
        db: Database session
        days: Number of days to include (default: 7)
        
    Returns:
        Dictionary with system-wide statistics
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Total activities
    total_activities = db.query(func.count(UserActivity.id)).filter(
        UserActivity.created_at >= start_date
    ).scalar()
    
    # Total tokens
    total_tokens = db.query(func.sum(UserActivity.tokens_used)).filter(
        UserActivity.created_at >= start_date,
        UserActivity.tokens_used.isnot(None)
    ).scalar() or 0
    
    # Top users by activity
    top_users = db.query(
        UserActivity.user_id,
        func.count(UserActivity.id).label('activity_count')
    ).filter(
        UserActivity.created_at >= start_date
    ).group_by(UserActivity.user_id).order_by(desc('activity_count')).limit(10).all()
    
    # Activity by type
    activity_by_type = db.query(
        UserActivity.activity_type,
        func.count(UserActivity.id).label('count')
    ).filter(
        UserActivity.created_at >= start_date
    ).group_by(UserActivity.activity_type).all()
    
    return {
        "period_days": days,
        "total_activities": total_activities,
        "total_tokens_used": int(total_tokens),
        "top_users": [{"user_id": row.user_id, "activity_count": row.activity_count} for row in top_users],
        "activity_by_type": {row.activity_type: row.count for row in activity_by_type}
    }
