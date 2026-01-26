from fastapi import APIRouter, HTTPException, Depends
from typing import List
import logging
from app.models.schemas import (
    ContributionItem, ContributionRequest, ContributionResponse,
    ApproveContributionRequest, ApproveContributionResponse
)
from app.services.vector_store import get_vector_store
from app.core.auth import verify_api_key

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Input Validation Constants ---
MAX_QUESTION_LENGTH = 2000
MAX_SQL_LENGTH = 4000
MAX_USER_ID_LENGTH = 128

# --- Public Contribution Endpoint ---

@router.post("/contributions", response_model=ContributionResponse)
def submit_contribution(request: ContributionRequest, api_key: str = Depends(verify_api_key)):
    """
    Submit a new contribution to the staging area.
    This is the user-facing endpoint for the "Contribute Example" button.
    """
    # Input validation
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    if not request.sql_query or not request.sql_query.strip():
        raise HTTPException(status_code=400, detail="SQL query cannot be empty")
    
    if len(request.question) > MAX_QUESTION_LENGTH:
        raise HTTPException(status_code=400, detail=f"Question exceeds maximum length of {MAX_QUESTION_LENGTH} characters")
    
    if len(request.sql_query) > MAX_SQL_LENGTH:
        raise HTTPException(status_code=400, detail=f"SQL query exceeds maximum length of {MAX_SQL_LENGTH} characters")
    
    if request.user_id and len(request.user_id) > MAX_USER_ID_LENGTH:
        raise HTTPException(status_code=400, detail=f"User ID exceeds maximum length of {MAX_USER_ID_LENGTH} characters")
    
    try:
        vector_store = get_vector_store()
        # Check for similarity with existing knowledge base items
        is_similar, similarity_score, similar_to_id = vector_store.check_similarity(
            request.question, 
            threshold=0.9,
            knowledge_type=request.knowledge_type
        )
        
        # Insert into contribution library
        contribution_id = vector_store.insert_contribution(
            question=request.question,
            sql_query=request.sql_query,
            knowledge_type=request.knowledge_type or "sql_query",
            user_id=request.user_id
        )
        
        return ContributionResponse(
            success=True,
            message="Thank you! Your contribution has been submitted for review.",
            contribution_id=str(contribution_id),
            similarity_warning=is_similar,
            similarity_score=similarity_score if is_similar else None
        )
    except Exception as e:
        logger.error(f"Failed to submit contribution: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit contribution. Please try again.")


# --- Admin Contribution Management Endpoints ---

@router.get("/admin/contributions", response_model=List[ContributionItem])
def get_contributions(api_key: str = Depends(verify_api_key)):
    """
    Get all pending contributions for admin review.
    """
    try:
        vector_store = get_vector_store()
        raw_items = vector_store.get_all_contributions()
        results = []
        for r in raw_items:
            # Check similarity for each item
            is_similar, similarity_score, similar_to_id = vector_store.check_similarity(
                r.get("question", ""),
                threshold=0.9,
                knowledge_type=r.get("knowledge_type")
            )
            
            results.append(ContributionItem(
                id=str(r.get("id")),
                question=r.get("question"),
                sql_query=r.get("sql_query"),
                knowledge_type=r.get("knowledge_type", "sql_query"),
                submitted_at=r.get("submitted_at"),
                user_id=r.get("user_id"),
                status=r.get("status", "pending"),
                similarity_score=similarity_score if is_similar else None,
                similar_to_id=str(similar_to_id) if similar_to_id else None
            ))
        return results
    except Exception as e:
        logger.error(f"Failed to fetch contributions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch contributions")


@router.post("/admin/contributions/approve")
def approve_contribution(request: ApproveContributionRequest, api_key: str = Depends(verify_api_key)):
    """
    Approve a contribution and move it to the Knowledge Base.
    Optionally allows editing the question during approval.
    """
    if not request.contribution_id:
        raise HTTPException(status_code=400, detail="Invalid contribution ID")
    
    try:
        vector_store = get_vector_store()
        # Move to knowledge base (with optional edited question and SQL)
        new_id = vector_store.move_contribution_to_knowledge_base(
            int(request.contribution_id),
            edited_question=request.edited_question,
            edited_sql=request.edited_sql,
            knowledge_type=request.knowledge_type
        )
        
        logger.info(f"Approved contribution {request.contribution_id} -> knowledge base")
        return ApproveContributionResponse(
            success=True,
            message="Contribution approved and added to Knowledge Base.",
            knowledge_base_id=str(new_id) if new_id else None
        )
    except Exception as e:
        logger.error(f"Failed to approve contribution {request.contribution_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to approve contribution")


@router.delete("/admin/contributions/{contribution_id}")
def reject_contribution(contribution_id: str, api_key: str = Depends(verify_api_key)):
    """
    Reject/delete a contribution from the staging area.
    """
    if not contribution_id:
        raise HTTPException(status_code=400, detail="Invalid contribution ID")
    
    try:
        vector_store = get_vector_store()
        vector_store.delete_contribution(int(contribution_id))
        logger.info(f"Rejected contribution {contribution_id}")
        return {"status": "success", "message": "Contribution rejected and removed."}
    except Exception as e:
        logger.error(f"Failed to reject contribution {contribution_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to reject contribution")
