# exporter.py
import random
from typing import List
from data_structures import QuizQuestion

class QuizExporter:
    """Export clean, professional quizzes"""
    
    @staticmethod
    def export_to_txt(questions: List[QuizQuestion], output_path: str):
        """Export quiz to text file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("MANAGEMENT KNOWLEDGE ASSESSMENT\n")
            f.write("=" * 70 + "\n\n")
            
            f.write("Instructions:\n")
            f.write("- Read each question carefully before answering.\n")
            f.write("- For multiple choice questions, select the BEST answer.\n")
            f.write("- For short answer questions, provide 2-3 complete sentences.\n")
            f.write("- Time suggested: 60 minutes for complete assessment.\n")
            f.write("=" * 70 + "\n\n")
            
            for i, q in enumerate(questions, 1):
                f.write(f"QUESTION {i}:\n")
                f.write(f"{q.question}\n")
                f.write(f"[{q.question_type.replace('_', ' ').title()} | Difficulty: {q.difficulty:.1f}/1.0]\n\n")
                
                if q.question_type == "multiple_choice":
                    f.write("Choose the best answer:\n")
                    # Shuffle options for fairness
                    options = q.options.copy()
                    random.shuffle(options)
                    
                    for j, option in enumerate(options, 1):
                        # Clean and truncate option
                        clean_opt = option.strip()
                        if clean_opt.endswith('...'):
                            clean_opt = clean_opt[:-3]
                        if len(clean_opt) > 100:
                            clean_opt = clean_opt[:97] + "..."
                        
                        f.write(f"  {chr(64 + j)}. {clean_opt}\n")
                    
                    f.write("\n")
                
                elif q.question_type == "short_answer":
                    f.write("Provide a concise answer (2-3 sentences):\n")
                    f.write("_" * 60 + "\n")
                    f.write("\n" * 3)
                
                f.write("-" * 70 + "\n\n")
            
            # Answer key (separate section)
            f.write("\n" + "=" * 70 + "\n")
            f.write("ANSWER KEY AND EXPLANATIONS\n")
            f.write("=" * 70 + "\n\n")
            
            for i, q in enumerate(questions, 1):
                f.write(f"Question {i}: {q.question}\n")
                
                if q.question_type == "multiple_choice":
                    # Find correct option letter
                    for j, option in enumerate(q.options, 1):
                        if option == q.correct_answer:
                            f.write(f"✓ Correct Answer: {chr(64 + j)}\n")
                            break
                    f.write(f"  Explanation: {q.correct_answer}\n")
                else:
                    f.write(f"✓ Sample Answer: {q.correct_answer[:200]}...\n")
                    f.write(f"  Key points should include: {', '.join(q.keywords[:3])}\n")
                
                f.write("-" * 70 + "\n")
            
            # Statistics
            f.write("\n" + "=" * 70 + "\n")
            f.write("ASSESSMENT SUMMARY\n")
            f.write("=" * 70 + "\n")
            f.write(f"Total Questions: {len(questions)}\n")
            mc_count = sum(1 for q in questions if q.question_type == "multiple_choice")
            sa_count = sum(1 for q in questions if q.question_type == "short_answer")
            f.write(f"Multiple Choice Questions: {mc_count}\n")
            f.write(f"Short Answer Questions: {sa_count}\n")
            
            # Difficulty distribution
            easy = sum(1 for q in questions if q.difficulty < 0.5)
            medium = sum(1 for q in questions if 0.5 <= q.difficulty < 0.7)
            hard = sum(1 for q in questions if q.difficulty >= 0.7)
            f.write(f"\nDifficulty Breakdown:\n")
            f.write(f"  Easy (<0.5): {easy} questions\n")
            f.write(f"  Medium (0.5-0.7): {medium} questions\n")
            f.write(f"  Hard (>0.7): {hard} questions\n")