/**
 * Workflow Template Storage Utility
 * 
 * Manages per-user workflow templates in LocalStorage
 */

import type { WorkflowTemplate } from '../types/conversation';

const TEMPLATES_KEY = 'workflow_templates';

/**
 * Save a template to LocalStorage
 */
export function saveTemplate(template: WorkflowTemplate): void {
  const templates = loadTemplates();
  templates.push(template);
  localStorage.setItem(TEMPLATES_KEY, JSON.stringify(templates));
}

/**
 * Load all templates from LocalStorage
 */
export function loadTemplates(): WorkflowTemplate[] {
  const stored = localStorage.getItem(TEMPLATES_KEY);
  if (!stored) return [];
  
  try {
    return JSON.parse(stored);
  } catch (e) {
    console.error('Failed to parse templates:', e);
    return [];
  }
}

/**
 * Find template by ID
 */
export function getTemplate(id: string): WorkflowTemplate | null {
  const templates = loadTemplates();
  return templates.find(t => t.id === id) || null;
}

/**
 * Delete template by ID
 */
export function deleteTemplate(id: string): void {
  const templates = loadTemplates();
  const filtered = templates.filter(t => t.id !== id);
  localStorage.setItem(TEMPLATES_KEY, JSON.stringify(filtered));
}

/**
 * Search templates by query pattern, name, or description
 */
export function searchTemplates(searchQuery: string): WorkflowTemplate[] {
  const templates = loadTemplates();
  const query = searchQuery.toLowerCase();
  
  return templates.filter(t => 
    t.name.toLowerCase().includes(query) ||
    t.query_pattern.toLowerCase().includes(query) ||
    t.description.toLowerCase().includes(query)
  );
}

/**
 * Update an existing template
 */
export function updateTemplate(id: string, updates: Partial<WorkflowTemplate>): boolean {
  const templates = loadTemplates();
  const index = templates.findIndex(t => t.id === id);
  
  if (index === -1) return false;
  
  templates[index] = { ...templates[index], ...updates };
  localStorage.setItem(TEMPLATES_KEY, JSON.stringify(templates));
  return true;
}

/**
 * Get template count
 */
export function getTemplateCount(): number {
  return loadTemplates().length;
}

/**
 * Export templates as JSON string
 */
export function exportTemplates(): string {
  return localStorage.getItem(TEMPLATES_KEY) || '[]';
}

/**
 * Import templates from JSON string
 */
export function importTemplates(jsonString: string): boolean {
  try {
    const templates = JSON.parse(jsonString);
    if (!Array.isArray(templates)) return false;
    
    localStorage.setItem(TEMPLATES_KEY, jsonString);
    return true;
  } catch (e) {
    console.error('Failed to import templates:', e);
    return false;
  }
}
