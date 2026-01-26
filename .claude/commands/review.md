---
description: Review all work, ensure best practices, and rebuild/restart the application
---

# Code Review and Rebuild Workflow

This command reviews all changes made during the session, validates best practices, and restarts the application.

## Steps

1. **Review all changes** made during this session:
   - Examine modified files for correctness
   - Check for any incomplete implementations
   - Verify error handling is in place

2. **Check coding best practices**:
   - Ensure proper code formatting and consistency
   - Verify naming conventions are followed
   - Check for code duplication that should be refactored
   - Validate proper use of types and interfaces

3. **Evaluate efficiency**:
   - Look for performance bottlenecks
   - Check for unnecessary re-renders (frontend)
   - Verify database queries are optimized (backend)
   - Ensure no memory leaks or resource issues

4. **Security audit**:
   - Check for SQL injection vulnerabilities
   - Verify input validation and sanitization
   - Ensure sensitive data is not exposed in logs
   - Validate API endpoints have proper authorization
   - Check for hardcoded secrets or credentials

5. **If issues are found**, fix them before proceeding

6. **Rebuild and restart the application**:
   - Stop any running services
   - Install any new dependencies if needed:
     ```bash
     cd $WORKSPACE && pip install -r requirements.txt
     cd $WORKSPACE/frontend && npm install
     ```
   - Start the backend:
     ```bash
     cd $WORKSPACE && .\myenv\Scripts\activate ; uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
     ```
   - Start the frontend:
     ```bash
     cd $WORKSPACE/frontend && npm run dev
     ```

7. **Verify services are running**:
   - Backend API: http://localhost:8000
   - Frontend: http://localhost:45678
   - API Docs: http://localhost:8000/docs

## Notes

- Always address critical security issues before rebuilding
- Document any significant changes made during the review
- If tests exist, run them before restarting to ensure nothing is broken
