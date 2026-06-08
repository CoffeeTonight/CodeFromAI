"""
DQL Tokenizer (Python implementation)

This will eventually be a full tokenizer equivalent to tokenizeDQL in dql_parser.js.
"""

from typing import List, Dict, Any


def tokenize(query: str) -> List[Dict[str, Any]]:
    """
    Tokenize a DQL query string.
    Currently a stub. Will be implemented to match the JS tokenizer.
    """
    # Placeholder - real implementation will go here
    return [{"type": "RAW", "value": query}]
