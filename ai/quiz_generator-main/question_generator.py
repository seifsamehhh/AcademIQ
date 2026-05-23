# question_generator.py
import random
from typing import List, Dict, Optional
from nltk.tokenize import sent_tokenize, word_tokenize
from data_structures import QuizQuestion

class IntelligentQuestionGenerator:
    """Generate meaningful, test-like questions"""
    
    def __init__(self):
        self.question_templates = {
            'definition': [
                "What is the definition of '{concept}'?",
                "How is '{concept}' defined in management literature?",
                "Which of the following best describes '{concept}'?",
                "What does the term '{concept}' refer to in organizational contexts?"
            ],
            'application': [
                "In which business scenario would '{concept}' be most applicable?",
                "What is a real-world example of '{concept}' in practice?",
                "When should managers apply the principles of '{concept}'?",
                "Which situation best demonstrates the use of '{concept}' in organizations?"
            ],
            'characteristics': [
                "What is a key characteristic of '{concept}'?",
                "Which feature distinguishes '{concept}' from similar management concepts?",
                "What are the main attributes or components of '{concept}'?",
                "Which statement accurately describes a property of '{concept}'?"
            ],
            'comparison': [
                "What is the main difference between '{concept1}' and '{concept2}'?",
                "How does '{concept1}' differ from '{concept2}' in organizational settings?",
                "Which statement correctly contrasts '{concept1}' and '{concept2}'?",
                "What distinguishes the approach of '{concept1}' from '{concept2}'?"
            ],
            'relationship': [
                "How are '{concept1}' and '{concept2}' typically related in business contexts?",
                "What is the relationship between '{concept1}' and '{concept2}' in management theory?",
                "Which statement best describes how '{concept1}' and '{concept2}' interact?",
                "How do '{concept1}' and '{concept2}' work together in organizational success?"
            ]
        }
        
        # Common business scenarios for application questions
        self.business_scenarios = [
            "A company undergoing digital transformation and needing to manage change effectively",
            "An organization facing ethical dilemmas in international operations",
            "A team experiencing communication breakdowns during a critical project",
            "A manager dealing with conflicting priorities and limited resources",
            "A department implementing new technology while maintaining productivity",
            "An executive team developing a long-term strategy in a volatile market",
            "A company restructuring to improve operational efficiency",
            "An organization managing diverse teams across different cultures"
        ]
    
    def generate_definition_question(self, concept_data: Dict) -> Optional[QuizQuestion]:
        """Generate a definition question"""
        concept = concept_data.get('concept', '')
        definition = concept_data.get('definition', '')
        
        if not concept or not definition:
            return None
        
        # Generate question
        question_template = random.choice(self.question_templates['definition'])
        question = question_template.format(concept=concept)
        
        # Generate distractors (wrong definitions)
        distractors = self._generate_definition_distractors(concept, definition)
        
        # Format options nicely
        options = distractors + [definition]
        random.shuffle(options)
        
        return QuizQuestion(
            question=question,
            options=options,
            correct_answer=definition,
            question_type="multiple_choice",
            context=concept_data.get('context', ''),
            difficulty=0.5,
            keywords=self._extract_keywords_from_concept(concept)
        )
    
    def _generate_definition_distractors(self, concept: str, correct_def: str) -> List[str]:
        """Generate plausible wrong definitions"""
        distractors = []
        
        # Get the main word from concept
        main_word = concept.split()[0].lower() if concept.split() else concept.lower()
        
        # Pattern-based distractors
        patterns = [
            f"A tool for measuring {main_word} effectiveness in organizations",
            f"The historical development and origin of {main_word} theory",
            f"A specific methodology used exclusively in {main_word} research",
            f"The complete opposite approach to traditional {main_word} practices",
            f"A narrow subset of {main_word} focused only on quantitative aspects",
            f"Primarily concerned with the financial aspects of {main_word} implementation",
            f"An outdated theory that has been replaced by modern {main_word} approaches",
            f"Exclusively focused on the technological components of {main_word}"
        ]
        
        # Select 3 unique distractors
        selected_patterns = random.sample(patterns, 3)
        return selected_patterns
    
    def generate_application_question(self, concept_data: Dict) -> Optional[QuizQuestion]:
        """Generate an application question"""
        concept = concept_data.get('concept', '')
        
        if not concept:
            return None
        
        # Generate question
        question_template = random.choice(self.question_templates['application'])
        question = question_template.format(concept=concept)
        
        # Generate correct scenario based on concept type
        concept_lower = concept.lower()
        if any(word in concept_lower for word in ['strateg', 'plan', 'vision', 'goal']):
            correct_scenario = "Developing long-term organizational direction and competitive positioning"
        elif any(word in concept_lower for word in ['operat', 'process', 'efficien', 'productiv']):
            correct_scenario = "Improving daily workflow, resource utilization, and quality control"
        elif any(word in concept_lower for word in ['leader', 'motivat', 'inspire', 'visionary']):
            correct_scenario = "Guiding and influencing team members toward achieving organizational objectives"
        elif any(word in concept_lower for word in ['market', 'custom', 'brand', 'sales']):
            correct_scenario = "Understanding customer needs, positioning products, and creating value"
        elif any(word in concept_lower for word in ['finance', 'budget', 'invest', 'capital']):
            correct_scenario = "Managing financial resources, analyzing investments, and ensuring profitability"
        elif any(word in concept_lower for word in ['risk', 'uncertain', 'threat', 'crisis']):
            correct_scenario = "Identifying potential problems, assessing impacts, and developing mitigation strategies"
        elif any(word in concept_lower for word in ['change', 'transform', 'adapt', 'evolve']):
            correct_scenario = "Managing organizational transitions and adapting to new market conditions"
        elif any(word in concept_lower for word in ['team', 'group', 'collaborat', 'cooperat']):
            correct_scenario = "Building effective working relationships and collaborative environments"
        else:
            correct_scenario = "Addressing organizational challenges and improving business performance"
        
        # Generate distractors (non-business scenarios)
        distractors = [
            "Personal life decision-making and individual lifestyle choices",
            "Technical computer programming and software development tasks",
            "Medical diagnosis, treatment planning, and healthcare delivery",
            "Legal court proceedings, litigation, and judicial decision-making",
            "Artistic creative processes and aesthetic expression",
            "Scientific laboratory research and experimental design",
            "Sports coaching, athletic training, and performance optimization",
            "Culinary arts, cooking techniques, and food preparation"
        ]
        
        # Select 3 distractors, ensuring they're different from correct answer
        selected_distractors = random.sample(distractors, 3)
        
        # Combine and shuffle
        options = selected_distractors + [correct_scenario]
        random.shuffle(options)
        
        return QuizQuestion(
            question=question,
            options=options,
            correct_answer=correct_scenario,
            question_type="multiple_choice",
            context=concept_data.get('context', ''),
            difficulty=0.6,
            keywords=self._extract_keywords_from_concept(concept)
        )
    
    def generate_characteristics_question(self, concept_data: Dict) -> Optional[QuizQuestion]:
        """Generate a characteristics question"""
        concept = concept_data.get('concept', '')
        
        if not concept:
            return None
        
        # Generate question
        question_template = random.choice(self.question_templates['characteristics'])
        question = question_template.format(concept=concept)
        
        # Determine correct characteristic based on concept
        concept_lower = concept.lower()
        correct_char = ""
        
        if any(word in concept_lower for word in ['strateg', 'plan', 'vision']):
            correct_char = "Focuses on long-term organizational direction and competitive positioning"
        elif any(word in concept_lower for word in ['operat', 'process', 'efficien']):
            correct_char = "Emphasizes efficiency, quality control, and optimal resource utilization"
        elif any(word in concept_lower for word in ['leader', 'inspire', 'visionary']):
            correct_char = "Involves inspiring, influencing, and guiding others toward shared goals"
        elif any(word in concept_lower for word in ['manage', 'administer', 'coordinate']):
            correct_char = "Includes planning, organizing, leading, and controlling organizational resources"
        elif any(word in concept_lower for word in ['market', 'custom', 'brand']):
            correct_char = "Centers on understanding customer needs and creating value propositions"
        elif any(word in concept_lower for word in ['finance', 'budget', 'invest']):
            correct_char = "Deals with acquisition, allocation, and management of financial resources"
        elif any(word in concept_lower for word in ['risk', 'uncertain', 'threat']):
            correct_char = "Involves identifying, assessing, and mitigating potential negative outcomes"
        elif any(word in concept_lower for word in ['change', 'transform', 'adapt']):
            correct_char = "Focuses on managing transitions and adapting to new environments"
        elif any(word in concept_lower for word in ['team', 'group', 'collaborat']):
            correct_char = "Emphasizes interpersonal relationships, communication, and cooperation"
        else:
            correct_char = "Contributes to organizational effectiveness and goal achievement"
        
        # Generate distractors (wrong characteristics)
        distractors = [
            "Primarily involves technical skills without consideration of human factors",
            "Can be completely automated without requiring human judgment or discretion",
            "Has no ethical considerations, implications, or moral dimensions",
            "Exists and functions identically across all industries, cultures, and contexts",
            "Requires no specialized knowledge, training, or experience to implement effectively",
            "Focuses exclusively on quantitative metrics without qualitative assessment",
            "Has no connection to organizational strategy, goals, or performance outcomes",
            "Operates independently of market conditions, competition, or external factors"
        ]
        
        # Select 3 distractors
        selected_distractors = random.sample(distractors, 3)
        
        # Combine and shuffle
        options = selected_distractors + [correct_char]
        random.shuffle(options)
        
        return QuizQuestion(
            question=question,
            options=options,
            correct_answer=correct_char,
            question_type="multiple_choice",
            context=concept_data.get('context', ''),
            difficulty=0.55,
            keywords=self._extract_keywords_from_concept(concept)
        )
    
    def generate_comparison_question(self, relationship_data: Dict) -> Optional[QuizQuestion]:
        """Generate a comparison question"""
        concept1 = relationship_data.get('concept1', '')
        concept2 = relationship_data.get('concept2', '')
        
        if not concept1 or not concept2:
            return None
        
        # Generate question
        question_template = random.choice(self.question_templates['comparison'])
        question = question_template.format(concept1=concept1, concept2=concept2)
        
        # Generate correct comparison based on concepts
        concept1_lower = concept1.lower()
        concept2_lower = concept2.lower()
        
        # Determine correct comparison
        if ('strateg' in concept1_lower and 'operat' in concept2_lower) or \
           ('strateg' in concept2_lower and 'operat' in concept1_lower):
            correct_answer = "Strategic management focuses on long-term direction while operational management deals with daily activities"
        elif ('leader' in concept1_lower and 'manage' in concept2_lower) or \
             ('leader' in concept2_lower and 'manage' in concept1_lower):
            correct_answer = "Leadership focuses on inspiring change and innovation while management focuses on maintaining stability and efficiency"
        elif ('effect' in concept1_lower and 'efficien' in concept2_lower) or \
             ('effect' in concept2_lower and 'efficien' in concept1_lower):
            correct_answer = "Effectiveness is about achieving goals and desired outcomes while efficiency is about minimizing waste and optimizing resources"
        elif ('quantitat' in concept1_lower or 'qualitat' in concept2_lower) or \
             ('quantitat' in concept2_lower or 'qualitat' in concept1_lower):
            correct_answer = "Quantitative analysis focuses on numerical data and metrics while qualitative analysis focuses on descriptive information and context"
        else:
            correct_answer = f"{concept1} typically deals with broader organizational aspects while {concept2} focuses on more specific implementation details"
        
        # Generate distractors
        distractors = [
            f"{concept1} and {concept2} are exactly the same concept with different names",
            f"{concept1} always directly causes or leads to {concept2} in all situations",
            f"{concept2} completely replaces and makes {concept1} obsolete in modern organizations",
            f"{concept1} and {concept2} have absolutely no relationship or connection to each other",
            f"{concept1} is purely theoretical while {concept2} is exclusively practical",
            f"{concept2} is always more important and valuable than {concept1} for organizations",
            f"{concept1} applies only to large corporations while {concept2} applies only to small businesses"
        ]
        
        # Select 3 distractors
        selected_distractors = random.sample(distractors, 3)
        
        # Combine and shuffle
        options = selected_distractors + [correct_answer]
        random.shuffle(options)
        
        return QuizQuestion(
            question=question,
            options=options,
            correct_answer=correct_answer,
            question_type="multiple_choice",
            context=relationship_data.get('context', ''),
            difficulty=0.7,
            keywords=self._extract_keywords_from_concept(concept1) + self._extract_keywords_from_concept(concept2)
        )
    
    def generate_short_answer_question(self, paragraph: str, concept: str = "") -> Optional[QuizQuestion]:
        """Generate a short answer question"""
        sentences = sent_tokenize(paragraph)
        if len(sentences) < 2:
            return None
        
        # Find the most substantive sentence
        main_sentence = max(sentences, key=lambda s: len(s.split()))
        
        # Create an analytical question
        if concept:
            question_types = [
                f"Explain how '{concept}' contributes to organizational success in the context described.",
                f"Describe a specific situation where understanding '{concept}' would help resolve the challenges mentioned.",
                f"What practical steps could a manager take to apply '{concept}' based on this information?",
                f"How does the concept of '{concept}' relate to the organizational issue described above?"
            ]
            question = random.choice(question_types)
        else:
            question_types = [
                "Explain the organizational implications of the concept described above.",
                "How would you apply this management principle in a real business situation?",
                "What challenges might organizations face when implementing this approach?",
                "Why is this concept important for modern managers to understand?"
            ]
            question = random.choice(question_types)
        
        # Provide context
        context = f"Context: {main_sentence[:150]}..." if len(main_sentence) > 150 else main_sentence
        
        return QuizQuestion(
            question=question,
            options=[],
            correct_answer=main_sentence,
            question_type="short_answer",
            context=context,
            difficulty=0.65,
            keywords=self._extract_keywords(main_sentence)
        )
    
    def _extract_keywords_from_concept(self, concept: str) -> List[str]:
        """Extract keywords from concept"""
        words = [w.lower() for w in word_tokenize(concept) if w.isalnum() and len(w) > 2]
        stop_words = {'the', 'and', 'for', 'with', 'that', 'this', 'from'}
        keywords = [w for w in words if w not in stop_words]
        return list(set(keywords))[:3]
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        words = [w.lower() for w in word_tokenize(text) if w.isalnum() and len(w) > 3]
        stop_words = {'that', 'with', 'this', 'from', 'have', 'which', 'their', 'about', 'would', 'could'}
        keywords = [w for w in words if w not in stop_words]
        return list(set(keywords))[:3]