"""
Workflow Template Storage Utility

Manages per-user workflow templates stored in frontend LocalStorage.
Provides helper functions for template serialization and creation.
"""

import json
import uuid
from typing import List, Dict, Any
from datetime import datetime
from app.models.schemas import WorkflowTemplate, AnalysisContext
import logging

logger = logging.getLogger(__name__)


class TemplateService:
    """Service for creating and managing workflow templates"""
    
    @staticmethod
    def create_template(
        name: str,
        query_pattern: str,
        tables_used: List[str],
        refinement_history: List[Dict[str, Any]],
        user_id: str,
        description: str = ""
    ) -> WorkflowTemplate:
        """
        Create a new workflow template.
        
        Args:
            name: Template name
            query_pattern: Original user query that started the workflow
            tables_used: List of schema.table names used
            refinement_history: List of refinement steps [{intent, query, timestamp}]
            user_id: User identifier
            description: Optional description
            
        Returns:
            WorkflowTemplate object
        """
        template_id = str(uuid.uuid4())
        
        # Extract refinement sequence from history
        refinement_sequence = []
        for i, refinement in enumerate(refinement_history):
            step_num = i + 1
            refinement_sequence.append({
                "step": f"Step {step_num}",
                "intent": refinement.get("intent", "unknown"),
                "description": refinement.get("query", "")
            })
        
        return WorkflowTemplate(
            id=template_id,
            name=name,
            description=description or f"Analysis workflow starting with: {query_pattern[:100]}",
            query_pattern=query_pattern,
            tables_used=tables_used,
            refinement_sequence=refinement_sequence,
            created_at=datetime.utcnow().isoformat(),
            user_id=user_id
        )
    
    @staticmethod
    def template_to_dict(template: WorkflowTemplate) -> Dict[str, Any]:
        """
        Convert template to dictionary for JSON serialization.
        
        Args:
            template: WorkflowTemplate object
            
        Returns:
            Dictionary representation
        """
        return template.model_dump()
    
    @staticmethod
    def dict_to_template(data: Dict[str, Any]) -> WorkflowTemplate:
        """
        Convert dictionary to WorkflowTemplate object.
        
        Args:
            data: Dictionary representation
            
        Returns:
            WorkflowTemplate object
        """
        return WorkflowTemplate(**data)
    
    @staticmethod
    def generate_template_summary(template: WorkflowTemplate) -> str:
        """
        Generate human-readable summary of template.
        
        Args:
            template: WorkflowTemplate
            
        Returns:
            Summary string
        """
        tables = ", ".join(template.tables_used) if template.tables_used else "No tables"
        steps = len(template.refinement_sequence)
        
        summary = f"""Template: {template.name}
Description: {template.description}
Tables Used: {tables}
Refinement Steps: {steps}
Created: {template.created_at}

Workflow:
1. Initial Query: {template.query_pattern}
"""
        
        for i, step in enumerate(template.refinement_sequence, start=2):
            summary += f"{i}. [{step['intent']}] {step['description']}\n"
        
        return summary
    
    @staticmethod
    def extract_template_from_conversation(
        initial_query: str,
        messages: List[Dict[str, Any]],
        user_id: str = "default"
    ) -> WorkflowTemplate:
        """
        Extract a workflow template from conversation history.
        
        Args:
            initial_query: First analysis query
            messages: List of conversation messages with analysis context
            user_id: User identifier
            
        Returns:
            WorkflowTemplate extracted from conversation
        """
        # Extract tables from messages
        tables_used = set()
        refinement_history = []
        
        for msg in messages:
            # Extract table references from SQL or context
            if isinstance(msg, dict):
                if "sqlResult" in msg and msg["sqlResult"]:
                    sql = msg["sqlResult"].get("sql", "")
                    # Simple table extraction from SQL (can be improved)
                    tables_in_sql = TemplateService._extract_tables_from_sql(sql)
                    tables_used.update(tables_in_sql)
                
                # Extract refinement steps
                if msg.get("type") == "user" and msg.get("content"):
                    refinement_history.append({
                        "intent": "refinement",
                        "query": msg["content"],
                        "timestamp": msg.get("timestamp", "")
                    })
        
        # Generate template name from initial query
        template_name = TemplateService._generate_template_name(initial_query)
        
        return TemplateService.create_template(
            name=template_name,
            query_pattern=initial_query,
            tables_used=list(tables_used),
            refinement_history=refinement_history,
            user_id=user_id
        )
    
    @staticmethod
    def _extract_tables_from_sql(sql: str) -> List[str]:
        """
        Simple regex-based table extraction from SQL.
        
        Args:
            sql: SQL query string
            
        Returns:
            List of table names (schema.table format)
        """
        import re
        
        # Pattern to match FROM and JOIN clauses
        patterns = [
            r'FROM\s+(\[?[\w]+\]?\.\[?[\w]+\]?)',
            r'JOIN\s+(\[?[\w]+\]?\.\[?[\w]+\]?)',
        ]
        
        tables = set()
        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            for match in matches:
                # Remove brackets if present
                table = match.replace('[', '').replace(']', '')
                tables.add(table)
        
        return list(tables)
    
    @staticmethod
    def _generate_template_name(query: str) -> str:
        """
        Generate a template name from query.
        
        Args:
            query: User query
            
        Returns:
            Generated template name
        """
        # Truncate and clean query
        name = query[:50].strip()
        if len(query) > 50:
            name += "..."
        
        # Capitalize first letter
        if name:
            name = name[0].upper() + name[1:]
        
        return name or "Untitled Workflow"


# Frontend LocalStorage Helper Functions (for documentation)
"""
Frontend TypeScript helper functions to add to conversationStorage.ts:

// Save template to LocalStorage
export function saveTemplate(template: WorkflowTemplate): void {
  const templates = loadTemplates();
  templates.push(template);
  localStorage.setItem('workflow_templates', JSON.stringify(templates));
}

// Load all templates from LocalStorage
export function loadTemplates(): WorkflowTemplate[] {
  const stored = localStorage.getItem('workflow_templates');
  if (!stored) return [];
  try {
    return JSON.parse(stored);
  } catch (e) {
    console.error('Failed to parse templates:', e);
    return [];
  }
}

// Find template by ID
export function getTemplate(id: string): WorkflowTemplate | null {
  const templates = loadTemplates();
  return templates.find(t => t.id === id) || null;
}

// Delete template
export function deleteTemplate(id: string): void {
  const templates = loadTemplates();
  const filtered = templates.filter(t => t.id !== id);
  localStorage.setItem('workflow_templates', JSON.stringify(filtered));
}

// Search templates by query pattern
export function searchTemplates(searchQuery: string): WorkflowTemplate[] {
  const templates = loadTemplates();
  const query = searchQuery.toLowerCase();
  return templates.filter(t => 
    t.name.toLowerCase().includes(query) ||
    t.query_pattern.toLowerCase().includes(query) ||
    t.description.toLowerCase().includes(query)
  );
}
"""
