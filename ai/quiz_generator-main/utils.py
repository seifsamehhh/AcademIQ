# utils.py
import re

def clean_text_for_display(text: str, max_length: int = 100) -> str:
    """Clean and truncate text for display"""
    if not text:
        return ""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length - 3] + "..."
    
    return text

def calculate_average_difficulty(questions):
    """Calculate average difficulty of questions"""
    if not questions:
        return 0.0
    return sum(q.difficulty for q in questions) / len(questions)

def validate_question(question):
    """Validate that a question is properly formed"""
    if not question.question or len(question.question.strip()) < 10:
        return False
    
    if question.question_type == "multiple_choice":
        if len(question.options) < 2:
            return False
        if not question.correct_answer or question.correct_answer not in question.options:
            return False
    
    return True