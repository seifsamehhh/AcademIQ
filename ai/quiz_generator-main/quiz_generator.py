# quiz_generator.py
import random
from typing import List
from document_loader import DocumentLoader
from concept_extractor import ConceptExtractor
from question_generator import IntelligentQuestionGenerator
from data_structures import DocumentContent, QuizQuestion

class QuizGenerator:
    """Main quiz generator with intelligent question creation"""
    
    def __init__(self):
        self.loader = DocumentLoader()
        self.extractor = ConceptExtractor()
        self.question_gen = IntelligentQuestionGenerator()
    
    def process_document(self, file_path: str) -> DocumentContent:
        """Process document and extract content"""
        # Load document
        if file_path.lower().endswith('.pdf'):
            text = self.loader.load_pdf(file_path)
        elif file_path.lower().endswith(('.ppt', '.pptx')):
            text = self.loader.load_ppt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path}")
        
        # Process text
        text_clean, sentences, paragraphs = self.loader.process_text(text)
        
        # Extract concepts and relationships
        concepts = self.extractor.extract_real_concepts(text_clean)
        definitions = self.extractor.extract_definitions(text_clean)
        relationships = self.extractor.extract_relationships(text_clean, concepts)
        
        print(f"Found {len(concepts)} valid concepts after filtering pronouns")
        print(f"Found {len(definitions)} clear definitions")
        print(f"Found {len(relationships)} relationships between concepts")
        
        # Show sample concepts
        if concepts:
            print("\nSample concepts found:")
            for i, concept_data in enumerate(concepts[:5], 1):
                print(f"  {i}. {concept_data['concept']}")
        
        return DocumentContent(
            raw_text=text_clean,
            sentences=sentences,
            paragraphs=paragraphs,
            concepts=concepts,
            definitions=definitions,
            relationships=relationships
        )
    
    def generate_quiz(self, document: DocumentContent, num_questions: int = 10) -> List[QuizQuestion]:
        """Generate intelligent quiz questions"""
        questions = []
        
        # 1. Definition questions (30%) - only if we have good definitions
        num_def = max(1, int(num_questions * 0.3))
        for definition in document.definitions[:num_def]:
            question = self.question_gen.generate_definition_question(definition)
            if question:
                questions.append(question)
        
        # 2. Application questions (30%) - use concepts with context
        num_app = max(1, int(num_questions * 0.3))
        for concept_data in document.concepts[:num_app]:
            question = self.question_gen.generate_application_question(concept_data)
            if question:
                questions.append(question)
        
        # 3. Characteristics questions (20%)
        num_char = max(1, int(num_questions * 0.2))
        for concept_data in document.concepts[num_app:num_app + num_char]:
            question = self.question_gen.generate_characteristics_question(concept_data)
            if question:
                questions.append(question)
        
        # 4. Comparison questions (10%)
        num_comp = max(1, int(num_questions * 0.1))
        for rel in document.relationships[:num_comp]:
            question = self.question_gen.generate_comparison_question(rel)
            if question:
                questions.append(question)
        
        # 5. Short answer questions (10%)
        num_short = max(1, int(num_questions * 0.1))
        # Try to associate paragraphs with concepts
        for i, paragraph in enumerate(document.paragraphs[:num_short]):
            # Find a concept mentioned in this paragraph
            associated_concept = ""
            for concept_data in document.concepts:
                if concept_data['concept'].lower() in paragraph.lower():
                    associated_concept = concept_data['concept']
                    break
            
            question = self.question_gen.generate_short_answer_question(paragraph, associated_concept)
            if question:
                questions.append(question)
        
        # If we don't have enough questions, create more application questions
        if len(questions) < num_questions:
            needed = num_questions - len(questions)
            for concept_data in document.concepts[len(questions):len(questions) + needed]:
                question = self.question_gen.generate_application_question(concept_data)
                if question:
                    questions.append(question)
        
        # Limit to requested number and shuffle
        questions = questions[:num_questions]
        random.shuffle(questions)
        
        # Set difficulty
        for i, q in enumerate(questions):
            base_diff = 0.5
            if q.question_type == "short_answer":
                base_diff += 0.1
            if 'comparison' in q.question.lower() or 'difference' in q.question.lower():
                base_diff += 0.1
            
            q.difficulty = min(0.9, base_diff + (i % 4) * 0.05)
        
        return questions