from app.core.database import get_db_engine
from sqlalchemy import text
import re

def validate_sql_with_db(sql: str) -> tuple[bool, str, list[str]]:
    """
    Validate SQL using the database parser (SET NOEXEC ON).
    Returns (is_valid, error_message, missing_objects)
    """
    if not sql or sql.strip() == "":
        return False, "Empty SQL query generated", []
        
    engine = get_db_engine()
    error_msg = ""
    missing_objects = []
    is_valid = False

    try:
        with engine.connect() as connection:
            # We use a transaction to be safe, though NOEXEC shouldn't modify anything
            with connection.begin():
                # Enable parse-only mode
                connection.execute(text("SET NOEXEC ON"))
                try:
                    # Execute the user's SQL
                    connection.execute(text(sql))
                    is_valid = True
                except Exception as e:
                    raw_error = str(e)
                    # Extract the database error message (usually the last part of SQLAlchemy error)
                    # SQLAlchemy format: (pyodbc.ProgrammingError) ('42S02', "[42S02] [Microsoft][ODBC Driver 17 for SQL Server][SQL Server]Invalid object name 'dbo.NonExistentTable'. (208) (SQLExecDirectW)")
                    
                    # Simplify error message for LLM
                    error_lines = raw_error.split('\n')
                    simplified_error = raw_error
                    
                    # Try to extract the SQL Server error message
                    Match = re.search(r'\[SQL Server\](.*?)(\(\d+\))', raw_error)
                    if Match:
                        simplified_error = Match.group(1).strip()
                    
                    error_msg = simplified_error
                    
                    # Parse for specific items for discovery
                    # "Invalid object name 'xxx'." -> Missing table
                    # "Invalid column name 'xxx'." -> Missing column
                    
                    obj_match = re.search(r"Invalid object name '([^']+)'.", error_msg)
                    if obj_match:
                        missing_objects.append(obj_match.group(1))
                        
                    col_match = re.search(r"Invalid column name '([^']+)'.", error_msg)
                    if col_match:
                        missing_objects.append(col_match.group(1))
                        
                finally:
                    # Always turn NOEXEC OFF before returning connection to pool
                    # Although 'with connection' should handle cleanup, explicit is better
                    connection.execute(text("SET NOEXEC OFF"))
                    
    except Exception as e:
         # Connection error or other setup error
         return False, f"Database connection failed during validation: {str(e)}", []
         
    return is_valid, error_msg, missing_objects
