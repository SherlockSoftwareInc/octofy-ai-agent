"""
Rate limiter for Code Advisor endpoint.
Simple in-memory rate limiting per API key.
"""

from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Tuple
import threading


class RateLimiter:
    """
    Simple in-memory rate limiter for Code Advisor.
    Limits requests per API key per time window.
    """
    
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed in window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = defaultdict(list)
        self.lock = threading.Lock()
    
    def is_allowed(self, api_key: str) -> Tuple[bool, str]:
        """
        Check if request is allowed for this API key.
        
        Args:
            api_key: API key to check
            
        Returns:
            Tuple of (is_allowed, message)
        """
        with self.lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=self.window_seconds)
            
            # Clean old requests outside the window
            if api_key in self.requests:
                self.requests[api_key] = [
                    ts for ts in self.requests[api_key] 
                    if ts > cutoff
                ]
            
            # Check limit
            current_count = len(self.requests[api_key])
            
            if current_count >= self.max_requests:
                # Calculate when they can try again
                reset_time = self.requests[api_key][0] + timedelta(seconds=self.window_seconds)
                seconds_until_reset = max(0, int((reset_time - now).total_seconds()))
                return False, f"Rate limit exceeded. Try again in {seconds_until_reset} seconds."
            
            # Allow request and record timestamp
            self.requests[api_key].append(now)
            remaining = self.max_requests - current_count - 1
            return True, f"{remaining} requests remaining in current window"
    
    def reset(self, api_key: str = None):
        """
        Reset rate limit for specific key or all keys.
        Useful for testing.
        
        Args:
            api_key: Specific key to reset, or None to reset all
        """
        with self.lock:
            if api_key:
                if api_key in self.requests:
                    del self.requests[api_key]
            else:
                self.requests.clear()


# Global instance for Code Advisor endpoint
# Can be configured via environment variables in config.py
code_advisor_rate_limiter = RateLimiter(
    max_requests=10,  # 10 requests
    window_seconds=60  # per minute
)
