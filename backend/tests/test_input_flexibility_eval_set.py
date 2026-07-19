"""
Evaluation dataset for input flexibility improvements.

Golden test cases covering various user input patterns to validate
production readiness of the RAG system's query understanding.
"""

from typing import Dict, List


# Test cases for query understanding
INPUT_FLEXIBILITY_TEST_CASES = [
    # Basic fetch requests
    {
        "input": "fetch AAPL Q1 2024",
        "expected_intent": "fetch",
        "expected_symbol": "AAPL",
        "expected_quarter": "2024Q1",
        "needs_clarification": False,
        "category": "explicit_fetch"
    },
    {
        "input": "get Microsoft 2024Q2 earnings",
        "expected_intent": "fetch",
        "expected_symbol": "MSFT",
        "expected_quarter": "2024Q2",
        "needs_clarification": False,
        "category": "explicit_fetch"
    },
    
    # Natural language fetch
    {
        "input": "What did Apple say last quarter?",
        "expected_intent": "qa",
        "expected_symbol": None,  # May need clarification or session context
        "expected_quarter": None,  # Relative period "last quarter"
        "needs_clarification": True,  # Without session context
        "category": "natural_question_underspecified"
    },
    {
        "input": "Can you summarize the Apple Q1 2024 call?",
        "expected_intent": "summarize",
        "expected_symbol": "AAPL",
        "expected_quarter": "2024Q1",
        "needs_clarification": False,
        "category": "natural_summarize"
    },
    
    # Section filters
    {
        "input": "summarize AAPL 2024Q1 Q&A only",
        "expected_intent": "summarize",
        "expected_symbol": "AAPL",
        "expected_quarter": "2024Q1",
        "expected_section": "qa",
        "needs_clarification": False,
        "category": "section_filter"
    },
    {
        "input": "What did they say in the prepared remarks about AI?",
        "expected_intent": "qa",
        "expected_section": "prepared",
        "expected_topic": "ai",
        "needs_clarification": True,  # Missing company/quarter
        "category": "section_filter"
    },
    {
        "input": "Give me just the Q&A section",
        "expected_intent": "summarize",
        "expected_section": "qa",
        "needs_clarification": True,  # Missing company/quarter
        "category": "section_filter"
    },
    
    # Speaker filters
    {
        "input": "What did the CFO say about margins?",
        "expected_intent": "qa",
        "expected_speaker": "CFO",
        "expected_topic": "margins",
        "needs_clarification": True,  # Missing company/quarter
        "category": "speaker_filter"
    },
    {
        "input": "Show me CEO comments on guidance",
        "expected_intent": "qa",
        "expected_speaker": "CEO",
        "expected_topic": "guidance",
        "needs_clarification": True,  # Missing company/quarter
        "category": "speaker_filter"
    },
    {
        "input": "What questions did analysts ask about revenue?",
        "expected_intent": "qa",
        "expected_speaker": "Analyst",
        "expected_topic": "revenue",
        "expected_section": "qa",  # Analyst implies Q&A
        "needs_clarification": True,  # Missing company/quarter
        "category": "speaker_filter"
    },
    
    # Topic extraction
    {
        "input": "What did they say about AI investments?",
        "expected_intent": "qa",
        "expected_topic": "ai",
        "needs_clarification": True,
        "category": "topic_extraction"
    },
    {
        "input": "How was revenue growth this quarter?",
        "expected_intent": "qa",
        "expected_topic": "revenue",
        "needs_clarification": True,  # Missing company
        "category": "topic_extraction"
    },
    {
        "input": "Did they give guidance for next year?",
        "expected_intent": "qa",
        "expected_topic": "guidance",
        "needs_clarification": True,
        "category": "topic_extraction"
    },
    
    # Follow-up scenarios (require session context)
    {
        "input": "What about Microsoft?",
        "expected_intent": "qa",
        "expected_symbol": None,  # Needs session context to infer quarter
        "needs_clarification": True,  # Without session context
        "category": "follow_up"
    },
    {
        "input": "Same question but for the CFO",
        "expected_intent": "qa",
        "expected_speaker": "CFO",
        "needs_clarification": False,  # With session context carrying topic
        "requires_session_context": True,
        "category": "follow_up"
    },
    {
        "input": "How about next quarter?",
        "expected_intent": "fetch",  # Changing quarter
        "expected_quarter": None,  # Relative
        "needs_clarification": True,  # Needs resolution
        "category": "follow_up"
    },
    
    # Ambiguous/underspecified
    {
        "input": "What's the latest?",
        "expected_intent": "qa",
        "needs_clarification": True,
        "expected_missing_fields": ["symbol", "quarter"],
        "category": "underspecified"
    },
    {
        "input": "Tell me about earnings",
        "expected_intent": "qa",
        "expected_topic": "earnings",
        "needs_clarification": True,
        "expected_missing_fields": ["symbol", "quarter"],
        "category": "underspecified"
    },
    {
        "input": "Q1 results",
        "expected_intent": "summarize",
        "expected_quarter": None,  # Year missing
        "needs_clarification": True,
        "expected_missing_fields": ["symbol", "year"],
        "category": "underspecified"
    },
    
    # Combined constraints
    {
        "input": "What did Apple's CFO say in Q&A about margins in Q1 2024?",
        "expected_intent": "qa",
        "expected_symbol": "AAPL",
        "expected_quarter": "2024Q1",
        "expected_section": "qa",
        "expected_speaker": "CFO",
        "expected_topic": "margins",
        "needs_clarification": False,
        "category": "complex_combined"
    },
    {
        "input": "Show me CEO prepared remarks on AI from NVDA 2024Q2",
        "expected_intent": "qa",
        "expected_symbol": "NVDA",
        "expected_quarter": "2024Q2",
        "expected_section": "prepared",
        "expected_speaker": "CEO",
        "expected_topic": "ai",
        "needs_clarification": False,
        "category": "complex_combined"
    },
]


def get_test_cases_by_category(category: str) -> List[Dict]:
    """Get test cases filtered by category."""
    return [tc for tc in INPUT_FLEXIBILITY_TEST_CASES if tc.get("category") == category]


def get_all_categories() -> List[str]:
    """Get list of all test categories."""
    return sorted(set(tc.get("category") for tc in INPUT_FLEXIBILITY_TEST_CASES))


# Expected improvements over baseline (keyword/regex) system
EXPECTED_IMPROVEMENTS = {
    "natural_question_underspecified": "Should trigger clarification instead of failing",
    "section_filter": "Should extract and apply section constraints",
    "speaker_filter": "Should extract and apply speaker constraints",
    "topic_extraction": "Should identify topic for focused retrieval",
    "follow_up": "Should use session context to resolve underspecified queries",
    "underspecified": "Should identify missing fields and ask for clarification",
    "complex_combined": "Should handle multiple constraints simultaneously"
}


if __name__ == "__main__":
    # Print summary
    print("Input Flexibility Evaluation Dataset")
    print("=" * 50)
    print(f"Total test cases: {len(INPUT_FLEXIBILITY_TEST_CASES)}")
    print(f"\nCategories ({len(get_all_categories())}):")
    for cat in get_all_categories():
        count = len(get_test_cases_by_category(cat))
        print(f"  - {cat}: {count} cases")
    
    print("\n\nExpected Improvements:")
    for cat, improvement in EXPECTED_IMPROVEMENTS.items():
        print(f"  - {cat}: {improvement}")
