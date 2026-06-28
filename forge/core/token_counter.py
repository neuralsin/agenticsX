"""
FORGE Token Counter — Tiktoken-based usage tracker.
Provides token counting for all agents and context management.
"""

import tiktoken


# Use cl100k_base encoding (GPT-4 / modern model tokenizer)
# This is a reasonable approximation for Qwen and DeepSeek models
_encoder = None


def _get_encoder():
    """Lazy-load the tiktoken encoder."""
    global _encoder
    if _encoder is None:
        try:
            _encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # Fallback: rough estimate if tiktoken fails
            _encoder = None
    return _encoder


def count_tokens(text: str) -> int:
    """
    Count the number of tokens in a text string.
    Uses tiktoken cl100k_base encoding for accuracy.
    Falls back to word-based estimation if tiktoken unavailable.
    
    Args:
        text: The text to count tokens for.
    
    Returns:
        Approximate token count.
    """
    if not text:
        return 0
    
    encoder = _get_encoder()
    if encoder is not None:
        try:
            return len(encoder.encode(text))
        except Exception:
            pass
    
    # Fallback: roughly 4 chars per token (common approximation)
    return max(1, len(text) // 4)


def count_tokens_messages(messages: list[dict]) -> int:
    """
    Count total tokens across a list of chat messages.
    Each message dict has 'role' and 'content' keys.
    Adds overhead tokens for message formatting.
    
    Args:
        messages: List of {"role": str, "content": str} dicts.
    
    Returns:
        Total token count including formatting overhead.
    """
    total = 0
    for msg in messages:
        # Each message has ~4 tokens of formatting overhead
        total += 4
        total += count_tokens(msg.get("content", ""))
        total += count_tokens(msg.get("role", ""))
    # Every reply is primed with assistant prefix
    total += 2
    return total


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """
    Truncate text to fit within a token budget.
    
    Args:
        text: Text to truncate.
        max_tokens: Maximum number of tokens.
    
    Returns:
        Truncated text that fits within the budget.
    """
    if not text:
        return text
    
    encoder = _get_encoder()
    if encoder is not None:
        try:
            tokens = encoder.encode(text)
            if len(tokens) <= max_tokens:
                return text
            truncated_tokens = tokens[:max_tokens]
            return encoder.decode(truncated_tokens) + "\n... [TRUNCATED]"
        except Exception:
            pass
    
    # Fallback: character-based truncation
    char_limit = max_tokens * 4
    if len(text) <= char_limit:
        return text
    return text[:char_limit] + "\n... [TRUNCATED]"
