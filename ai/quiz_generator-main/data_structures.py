from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class QuizQuestion:
    """Data class for quiz questions"""
    question: str
    options: List[str]
    correct_answer: str
    question_type: str  # "multiple_choice" or "short_answer"
    context: str
    difficulty: float  # 0.0 to 1.0
    keywords: List[str]

@dataclass
class DocumentContent:
    """Data class for processed document content"""
    raw_text: str
    sentences: List[str]
    paragraphs: List[str]
    concepts: List[Dict]
    definitions: List[Dict]
    relationships: List[Dict]