# concept_extractor.py
import re
from typing import List, Dict
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

class ConceptExtractor:
    """Extract meaningful concepts and definitions from text"""
    
    def __init__(self):
        try:
            self.stop_words = set(stopwords.words('english'))
        except:
            self.stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 
                              'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been'}
        self.lemmatizer = WordNetLemmatizer()
        
        # Common pronouns to exclude
        self.pronouns = {
            'it', 'he', 'she', 'they', 'we', 'you', 'i', 'me', 'him', 'her', 'them', 'us',
            'this', 'that', 'these', 'those', 'my', 'your', 'his', 'her', 'its', 'our', 'their'
        }
        
        # Common invalid starters for concepts
        self.invalid_starters = {
            'tell', 'what', 'how', 'why', 'when', 'where', 'which', 'who',
            'explain', 'describe', 'define', 'discuss', 'analyze', 'evaluate',
            'figure', 'table', 'chapter', 'section', 'page', 'example'
        }
        
        # Common management/business concepts (seed list)
        self.common_management_concepts = {
            'strategic management', 'operational management', 'leadership', 'management',
            'decision making', 'change management', 'risk management', 'project management',
            'human resources', 'organizational behavior', 'business ethics', 'corporate governance',
            'financial management', 'marketing strategy', 'supply chain', 'quality control',
            'performance management', 'team building', 'conflict resolution', 'stakeholder management',
            'innovation management', 'knowledge management', 'talent management', 'crisis management'
        }
    
    def clean_text(self, text: str) -> str:
        """Clean text for better processing"""
        # Remove page numbers, headers, footers
        text = re.sub(r'\bPage\s+\d+\b', '', text)
        text = re.sub(r'\b\d+\s*/\s*\d+\b', '', text)
        text = re.sub(r'^\d+\.?\s*', '', text, flags=re.MULTILINE)  # Remove numbered lists
        text = re.sub(r'^[A-Z][A-Z\s]+$', '', text, flags=re.MULTILINE)  # Remove all caps lines
        
        # Remove references and citations
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'\(.*?\)', '', text)
        
        # Remove common prefixes that aren't concepts
        text = re.sub(r'\b(?:For example|For instance|Specifically|In particular|That is|i\.e\.|e\.g\.)\b[^.!?]*[.!?]', '', text, flags=re.IGNORECASE)
        
        return text
    
    def extract_real_concepts(self, text: str) -> List[Dict]:
        """Extract meaningful concepts with their context"""
        concepts = []
        
        # Clean the text
        text = self.clean_text(text)
        sentences = sent_tokenize(text)
        
        # First pass: Look for explicit definitions
        for sentence in sentences:
            # Skip very short sentences
            if len(sentence.split()) < 6:
                continue
            
            # Pattern 1: "X is Y" pattern
            is_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+(?:is|are|was|were)\s+([^,.]+?)(?:\.|,)'
            matches = re.findall(is_pattern, sentence)
            for concept, definition in matches:
                if self._is_valid_concept(concept):
                    concepts.append({
                        'concept': concept,
                        'type': 'definition',
                        'context': sentence,
                        'definition': definition.strip(),
                        'score': 10  # High score for explicit definitions
                    })
            
            # Pattern 2: "X refers to Y" pattern
            refers_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+(?:refers to|means|defined as)\s+([^,.]+?)(?:\.|,)'
            matches = re.findall(refers_pattern, sentence, re.IGNORECASE)
            for concept, definition in matches:
                if self._is_valid_concept(concept):
                    concepts.append({
                        'concept': concept,
                        'type': 'definition',
                        'context': sentence,
                        'definition': definition.strip(),
                        'score': 10
                    })
        
        # Second pass: Look for capitalized terms that appear multiple times
        all_capital_terms = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', text)
        term_freq = {}
        for term in all_capital_terms:
            if self._is_valid_concept(term):
                term_freq[term] = term_freq.get(term, 0) + 1
        
        # Add frequent terms as concepts
        for term, freq in term_freq.items():
            if freq >= 2:  # Appears at least twice
                # Find a sentence containing this term
                context_sentence = ""
                for sentence in sentences:
                    if term in sentence and len(sentence.split()) > 5:
                        context_sentence = sentence
                        break
                
                if context_sentence:
                    concepts.append({
                        'concept': term,
                        'type': 'term',
                        'context': context_sentence,
                        'definition': '',
                        'score': min(8, freq * 2)  # Score based on frequency
                    })
        
        # Third pass: Look for common management concepts in text
        for common_concept in self.common_management_concepts:
            if common_concept in text.lower():
                # Find a sentence containing this concept
                context_sentence = ""
                for sentence in sentences:
                    if common_concept in sentence.lower() and len(sentence.split()) > 5:
                        context_sentence = sentence
                        break
                
                if context_sentence:
                    # Capitalize the concept
                    concept_title = ' '.join([word.capitalize() for word in common_concept.split()])
                    concepts.append({
                        'concept': concept_title,
                        'type': 'common',
                        'context': context_sentence,
                        'definition': '',
                        'score': 7
                    })
        
        # Remove duplicates (keep highest score)
        unique_concepts = {}
        for concept_data in concepts:
            concept = concept_data['concept']
            if concept not in unique_concepts or concept_data['score'] > unique_concepts[concept]['score']:
                unique_concepts[concept] = concept_data
        
        # Sort by score and return top concepts
        sorted_concepts = sorted(unique_concepts.values(), key=lambda x: x['score'], reverse=True)
        return sorted_concepts[:25]  # Return top 25 concepts
    
    def _is_valid_concept(self, term: str) -> bool:
        """Check if a term is a valid concept"""
        term_lower = term.lower()
        
        # 1. Check for pronouns
        if term_lower in self.pronouns:
            return False
        
        # 2. Check for invalid starters
        first_word = term_lower.split()[0] if term_lower.split() else ""
        if first_word in self.invalid_starters:
            return False
        
        # 3. Check word count
        words = term.split()
        if len(words) < 1 or len(words) > 5:
            return False
        
        # 4. Check for common invalid patterns
        invalid_patterns = [
            r'^[A-Z]\s*$',  # Single capital letter
            r'^Figure\s+\d+',  # Figure references
            r'^Table\s+\d+',  # Table references
            r'^Chapter\s+\d+',  # Chapter references
            r'^Section\s+\d+',  # Section references
            r'^\d+\s*\.',  # Numbered items
            r'^[A-Z][a-z]+\s+and\s+[A-Z][a-z]+$',  # Just "X and Y" without context
            r'^.*\?$',  # Ends with question mark
        ]
        
        for pattern in invalid_patterns:
            if re.match(pattern, term):
                return False
        
        # 5. Check if it's a fragment (ends with preposition/article)
        if term_lower.endswith((' a', ' an', ' the', ' of', ' in', ' on', ' at', ' to', ' for', ' with', ' by')):
            return False
        
        # 6. Check if all words are too short (likely not a concept)
        if all(len(word) <= 2 for word in words):
            return False
        
        return True
    
    def extract_definitions(self, text: str) -> List[Dict]:
        """Extract concept definitions from text"""
        definitions = []
        sentences = sent_tokenize(text)
        
        for sentence in sentences:
            # Clean sentence
            sentence_clean = re.sub(r'\[.*?\]|\(.*?\)', '', sentence)
            
            # Definition patterns
            patterns = [
                (r'\b([A-Z][a-zA-Z\s]{3,})\s+(?:is|are)\s+([^,.!?]+?)(?:\.|,|!|\?|which|that|who)', 'is'),
                (r'\b([A-Z][a-zA-Z\s]{3,})\s+(?:refers to|means)\s+([^,.!?]+?)(?:\.|,|!|\?|which|that)', 'refers'),
                (r'\b([A-Z][a-zA-Z\s]{3,})\s+(?:can be defined as|is defined as)\s+([^,.!?]+?)(?:\.|,|!|\?|which|that)', 'defined'),
                (r'\b([A-Z][a-zA-Z\s]{3,})\s+involves\s+([^,.!?]+?)(?:\.|,|!|\?|which|that)', 'involves'),
                (r'\b([A-Z][a-zA-Z\s]{3,})\s+consists of\s+([^,.!?]+?)(?:\.|,|!|\?|which|that)', 'consists'),
            ]
            
            for pattern, def_type in patterns:
                matches = re.findall(pattern, sentence_clean, re.IGNORECASE)
                for match in matches:
                    if len(match) == 2:
                        concept, definition = match
                        concept = concept.strip()
                        definition = definition.strip()
                        
                        # Validate concept
                        if (self._is_valid_concept(concept) and 
                            len(definition.split()) > 2 and 
                            len(definition.split()) < 30):
                            
                            # Clean up definition
                            if definition.endswith(('.', ',', ';', ':')):
                                definition = definition[:-1]
                            
                            definitions.append({
                                'concept': concept,
                                'definition': definition,
                                'type': def_type,
                                'sentence': sentence_clean,
                                'quality_score': self._rate_definition_quality(definition)
                            })
        
        # Sort by quality score
        definitions.sort(key=lambda x: x['quality_score'], reverse=True)
        return definitions[:20]  # Return top 20 definitions
    
    def _rate_definition_quality(self, definition: str) -> int:
        """Rate the quality of a definition"""
        score = 0
        
        # Length-based scoring
        word_count = len(definition.split())
        if 5 <= word_count <= 20:
            score += 3
        elif word_count > 20:
            score += 1
        
        # Check for keywords indicating good definition
        good_keywords = ['process', 'method', 'approach', 'technique', 'system', 
                        'framework', 'model', 'theory', 'concept', 'principle']
        
        for keyword in good_keywords:
            if keyword in definition.lower():
                score += 2
        
        # Check for vague words (penalize)
        vague_words = ['thing', 'stuff', 'something', 'anything', 'everything']
        for word in vague_words:
            if word in definition.lower():
                score -= 2
        
        return max(1, score)
    
    def extract_relationships(self, text: str, concepts: List[Dict]) -> List[Dict]:
        """Extract relationships between concepts"""
        relationships = []
        
        if len(concepts) < 2:
            return relationships
        
        # Get concept names
        concept_names = [c['concept'] for c in concepts]
        
        # Find sentences with multiple concepts
        sentences = sent_tokenize(text)
        
        for sentence in sentences:
            concepts_in_sentence = []
            for concept_name in concept_names:
                if concept_name in sentence:
                    concepts_in_sentence.append(concept_name)
            
            # If we have 2+ concepts in sentence, check for relationships
            if len(concepts_in_sentence) >= 2:
                sentence_lower = sentence.lower()
                
                # Check for comparison words
                comparison_words = ['versus', 'vs', 'compared to', 'unlike', 'different from', 
                                   'contrasts with', 'whereas', 'while', 'in contrast to']
                
                for word in comparison_words:
                    if word in sentence_lower:
                        # Find pairs of concepts
                        for i in range(len(concepts_in_sentence) - 1):
                            for j in range(i + 1, len(concepts_in_sentence)):
                                relationships.append({
                                    'concept1': concepts_in_sentence[i],
                                    'concept2': concepts_in_sentence[j],
                                    'relationship': 'comparison',
                                    'context': sentence,
                                    'score': 8
                                })
                
                # Check for association words
                association_words = ['and', 'or', 'with', 'together with', 'along with', 'as well as']
                for word in association_words:
                    if word in sentence_lower and 'and so on' not in sentence_lower:
                        # Only add if concepts are mentioned near each other
                        for i in range(len(concepts_in_sentence) - 1):
                            for j in range(i + 1, len(concepts_in_sentence)):
                                # Check if concepts are within 10 words of each other
                                words = sentence.split()
                                try:
                                    idx1 = words.index(concepts_in_sentence[i].split()[0])
                                    idx2 = words.index(concepts_in_sentence[j].split()[0])
                                    if abs(idx1 - idx2) <= 10:
                                        relationships.append({
                                            'concept1': concepts_in_sentence[i],
                                            'concept2': concepts_in_sentence[j],
                                            'relationship': 'association',
                                            'context': sentence,
                                            'score': 5
                                        })
                                except:
                                    pass
        
        # Remove duplicates
        unique_relationships = {}
        for rel in relationships:
            key = tuple(sorted([rel['concept1'], rel['concept2']]) + [rel['relationship']])
            if key not in unique_relationships or rel['score'] > unique_relationships[key]['score']:
                unique_relationships[key] = rel
        
        return list(unique_relationships.values())[:15]  # Return top 15 relationships