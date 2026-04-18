"""
Transcript chunking service.

Handles:
- Splitting transcripts into chunks by turn grouping
- Section detection (prepared vs qa)
- Token counting and overlap management
- Keyword-based retrieval
"""

from typing import List
from transcripts.models import Transcript, TranscriptTurn, TranscriptChunk

MAX_CHUNK_TOKENS = 1200
TARGET_CHUNK_TOKENS = 1000
OVERLAP_TOKENS = 150
QA_STARTERS = {"did", "what", "how", "why", "when", "where", "who", "is", "are", "was", "were", "can", "could"}


def estimate_tokens(text: str) -> int:
    """Cheap token estimate: ~4 chars per token."""
    return len(text) // 4


def detect_section(turns: List[TranscriptTurn]) -> List[str]:
    """
    Assign section label to each turn (prepared or qa).
    
    Strategy: Switch to "qa" once we see:
    - Content contains "question and answer" or "q&a session"
    - An analyst asks a question (after seeing Operator introducing Q&A)
    
    Returns list of section labels matching turn order.
    """
    sections = []
    current_section = "prepared"
    
    for turn in turns:
        content_lower = turn.content.lower()
        
        # Check for transition to Q&A
        if current_section == "prepared":
            # Look for explicit Q&A session markers
            if ("question" in content_lower and "answer" in content_lower) or \
               ("q&a" in content_lower and "session" in content_lower) or \
               "begin the question" in content_lower:
                current_section = "qa"
        
        sections.append(current_section)
    
    return sections


def _create_chunk(transcript: Transcript, chunk_index: int, section: str, 
                  speaker: str, text: str, sentiment: float = None) -> TranscriptChunk:
    """
    Factory method to create a TranscriptChunk instance.
    
    Args:
        transcript: Parent transcript
        chunk_index: Index of this chunk
        section: Section label (prepared/qa/unknown)
        speaker: Speaker name or label
        text: Chunk text content
        sentiment: Optional sentiment score
    
    Returns:
        Unsaved TranscriptChunk instance
    """
    return TranscriptChunk(
        transcript=transcript,
        chunk_index=chunk_index,
        section=section,
        speaker=speaker,
        text=text,
        token_count=estimate_tokens(text),
        avg_turn_sentiment=sentiment
    )


def _split_by_words(turn: TranscriptTurn, section: str, transcript: Transcript, 
                    start_chunk_index: int) -> List[TranscriptChunk]:
    """
    Split a single turn by words when it's too large even after paragraph/sentence splitting.
    
    This is a last-resort fallback for extremely long run-on content.
    
    Args:
        turn: The turn to split
        section: Section label for chunks
        transcript: Parent transcript
        start_chunk_index: Starting index for generated chunks
    
    Returns:
        List of TranscriptChunk instances
    """
    words = turn.content.split()
    word_chunks = []
    word_chunk = []
    chunk_idx = start_chunk_index
    
    for word in words:
        test_text = f"{turn.speaker}: {' '.join(word_chunk + [word])}"
        test_tokens = estimate_tokens(test_text)
        
        if test_tokens > MAX_CHUNK_TOKENS and word_chunk:
            # Save current word chunk
            chunk_text = f"{turn.speaker}: {' '.join(word_chunk)}"
            word_chunks.append(_create_chunk(
                transcript, chunk_idx, section, turn.speaker, 
                chunk_text, turn.sentiment
            ))
            chunk_idx += 1
            word_chunk = [word]
        else:
            word_chunk.append(word)
    
    # Save remaining words
    if word_chunk:
        chunk_text = f"{turn.speaker}: {' '.join(word_chunk)}"
        word_chunks.append(_create_chunk(
            transcript, chunk_idx, section, turn.speaker,
            chunk_text, turn.sentiment
        ))
    
    return word_chunks


def _split_oversized_turn(turn: TranscriptTurn, section: str, transcript: Transcript,
                          start_chunk_index: int) -> List[TranscriptChunk]:
    """
    Split a single turn that exceeds MAX_CHUNK_TOKENS.
    
    Strategy:
    1. Try splitting by paragraphs (\\n\\n)
    2. If no paragraphs, try splitting by sentences
    3. If sentences too large, split by words (last resort)
    
    Args:
        turn: The oversized turn to split
        section: Section label for chunks
        transcript: Parent transcript
        start_chunk_index: Starting index for generated chunks
    
    Returns:
        List of TranscriptChunk instances
    """
    chunks = []
    chunk_idx = start_chunk_index
    
    # Try paragraph splitting first
    paragraphs = turn.content.split('\n\n')
    
    # If no paragraphs, try sentence splitting
    if len(paragraphs) == 1:
        import re
        sentences = re.split(r'(?<=[.!?])\s+', turn.content)
        paragraphs = sentences
    
    para_chunk = []
    para_tokens = 0
    
    for para in paragraphs:
        if not para.strip():
            continue
        
        para_text_with_speaker = f"{turn.speaker}: {para}"
        para_tok = estimate_tokens(para_text_with_speaker)
        
        # If single paragraph/sentence still too large, fall back to word splitting
        if para_tok > MAX_CHUNK_TOKENS:
            # Save accumulated paragraphs first
            if para_chunk:
                chunk_text = '\n\n'.join(para_chunk)
                chunks.append(_create_chunk(
                    transcript, chunk_idx, section, turn.speaker,
                    chunk_text, turn.sentiment
                ))
                chunk_idx += 1
                para_chunk = []
                para_tokens = 0
            
            # Create a temporary turn for just this paragraph and word-split it
            from types import SimpleNamespace
            temp_turn = SimpleNamespace(
                speaker=turn.speaker,
                content=para,
                sentiment=turn.sentiment
            )
            word_split_chunks = _split_by_words(temp_turn, section, transcript, chunk_idx)
            chunks.extend(word_split_chunks)
            chunk_idx += len(word_split_chunks)
            continue
        
        # Check if adding this paragraph would exceed limit
        if para_tokens + para_tok > MAX_CHUNK_TOKENS and para_chunk:
            # Save current paragraph chunk
            chunk_text = '\n\n'.join(para_chunk)
            chunks.append(_create_chunk(
                transcript, chunk_idx, section, turn.speaker,
                chunk_text, turn.sentiment
            ))
            chunk_idx += 1
            para_chunk = [para_text_with_speaker]
            para_tokens = para_tok
        else:
            para_chunk.append(para_text_with_speaker)
            para_tokens += para_tok
    
    # Save remaining paragraphs
    if para_chunk:
        chunk_text = '\n\n'.join(para_chunk)
        chunks.append(_create_chunk(
            transcript, chunk_idx, section, turn.speaker,
            chunk_text, turn.sentiment
        ))
    
    return chunks


def chunk_transcript(transcript: Transcript) -> List[TranscriptChunk]:
    """
    Chunk a transcript into TranscriptChunk objects.
    
    Strategy:
    - Group consecutive turns into chunks of TARGET_CHUNK_TOKENS
    - Maintain OVERLAP_TOKENS between adjacent chunks
    - If single turn > MAX_CHUNK_TOKENS, split it using _split_oversized_turn
    
    Returns list of unsaved TranscriptChunk instances.
    """
    turns = list(transcript.turns.all().order_by('turn_index'))
    if not turns:
        return []
    
    sections = detect_section(turns)
    chunks = []
    chunk_index = 0
    
    i = 0
    while i < len(turns):
        chunk_text_parts = []
        chunk_tokens = 0
        chunk_section = sections[i]
        chunk_speakers = set()
        chunk_sentiments = []
        start_turn_idx = i
        
        # Build chunk up to TARGET_CHUNK_TOKENS
        while i < len(turns):
            turn = turns[i]
            turn_text_with_speaker = f"{turn.speaker}: {turn.content}"
            turn_tokens = estimate_tokens(turn_text_with_speaker)
            
            # If single turn is too large and we haven't accumulated content yet,
            # split it using helper method
            if turn_tokens > MAX_CHUNK_TOKENS and not chunk_text_parts:
                oversized_chunks = _split_oversized_turn(
                    turn, sections[i], transcript, chunk_index
                )
                chunks.extend(oversized_chunks)
                chunk_index += len(oversized_chunks)
                i += 1
                break  # Move to next turn
            
            # Check if adding this turn would exceed MAX
            if chunk_tokens + turn_tokens > MAX_CHUNK_TOKENS and chunk_text_parts:
                break  # Chunk is full, save it
            
            # Add turn to current chunk
            chunk_text_parts.append(turn_text_with_speaker)
            chunk_tokens += turn_tokens
            chunk_speakers.add(turn.speaker)
            if turn.sentiment is not None:
                chunk_sentiments.append(turn.sentiment)
            i += 1
            
            # Check if we've reached target size
            if chunk_tokens >= TARGET_CHUNK_TOKENS:
                break
        
        # Save chunk if we accumulated any content
        if chunk_text_parts:
            chunk_text = '\n\n'.join(chunk_text_parts)
            avg_sentiment = sum(chunk_sentiments) / len(chunk_sentiments) if chunk_sentiments else None
            speaker_label = ", ".join(sorted(chunk_speakers)) if len(chunk_speakers) <= 3 else f"{len(chunk_speakers)} speakers"
            
            chunks.append(_create_chunk(
                transcript, chunk_index, chunk_section,
                speaker_label, chunk_text, avg_sentiment
            ))
            chunk_index += 1
            
            # Backtrack for overlap (go back OVERLAP_TOKENS worth of turns)
            overlap_tokens = 0
            overlap_start = i - 1
            while overlap_start >= start_turn_idx and overlap_tokens < OVERLAP_TOKENS:
                overlap_tokens += estimate_tokens(turns[overlap_start].content)
                overlap_start -= 1
            i = max(start_turn_idx + 1, overlap_start + 1)
    
    return chunks


def get_or_create_chunks(transcript: Transcript) -> List[TranscriptChunk]:
    """
    Get existing chunks or create new ones.
    
    Returns list of TranscriptChunk instances.
    """
    existing = list(transcript.chunks.all())
    if existing:
        return existing
    
    chunks = chunk_transcript(transcript)
    if chunks:
        TranscriptChunk.objects.bulk_create(chunks)
    
    return chunks


def score_chunk(chunk: TranscriptChunk, query_words: set) -> float:
    """Score a chunk by keyword overlap."""
    text_words = set(chunk.text.lower().split())
    overlap = len(text_words & query_words)
    return float(overlap)


def retrieve_top_k(transcript: Transcript, query: str, k: int = 8) -> List[TranscriptChunk]:
    """
    Retrieve top-K chunks by keyword scoring.
    
    Scoring:
    - Count query word overlaps in chunk text
    - Boost QA chunks by 0.2 if query is a question
    
    Args:
        transcript: Transcript to search
        query: Search query string
        k: Number of top chunks to return
    
    Returns:
        List of top-K TranscriptChunk instances sorted by score (descending)
    """
    chunks = get_or_create_chunks(transcript)
    if not chunks:
        return []
    
    query_words = set(query.lower().split())
    query_lower = query.strip().lower()
    is_question = (
        query_lower.endswith("?") or 
        (query_words and list(query_words)[0] in QA_STARTERS)
    )
    
    scored = []
    for chunk in chunks:
        score = score_chunk(chunk, query_words)
        # Boost QA chunks for questions
        if is_question and chunk.section == "qa":
            score += 0.2
        scored.append((score, chunk))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored[:k]]
