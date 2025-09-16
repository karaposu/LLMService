"""
Pydantic schemas for structured outputs.
These schemas guarantee type-safe, validated responses from the LLM.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from enum import Enum


# ============================================================================
# Common Extraction Patterns
# ============================================================================

class SemanticIsolation(BaseModel):
    """Schema for semantic isolation responses"""
    answer: str = Field(description="The isolated semantic element")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Confidence score")


class EntityExtraction(BaseModel):
    """Single extracted entity"""
    name: str = Field(description="Entity name or identifier")
    type: str = Field(description="Entity type (person, place, date, etc.)")
    value: str = Field(description="Entity value or content")
    context: Optional[str] = Field(default=None, description="Surrounding context")


class EntitiesList(BaseModel):
    """List of extracted entities"""
    entities: List[EntityExtraction] = Field(description="Extracted entities")
    source_text: Optional[str] = Field(default=None, description="Original text")


# ============================================================================
# Chain of Thought Reasoning
# ============================================================================

class ReasoningStep(BaseModel):
    """Single step in chain-of-thought reasoning"""
    explanation: str = Field(description="Explanation of this step")
    output: str = Field(description="Result or output of this step")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ChainOfThought(BaseModel):
    """Structured chain-of-thought reasoning"""
    steps: List[ReasoningStep] = Field(description="Reasoning steps")
    final_answer: str = Field(description="Final conclusion or answer")
    total_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


# ============================================================================
# Data Extraction Patterns
# ============================================================================

class KeyValuePair(BaseModel):
    """Simple key-value extraction"""
    key: str = Field(description="The key or field name")
    value: Any = Field(description="The extracted value")
    type: Optional[str] = Field(default=None, description="Data type of the value")


class StructuredData(BaseModel):
    """Generic structured data extraction"""
    data: Dict[str, Any] = Field(description="Extracted structured data")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


# ============================================================================
# Medical/Clinical Patterns (Example Domain)
# ============================================================================

class Symptom(BaseModel):
    """Medical symptom"""
    name: str = Field(description="Symptom name")
    severity: Optional[str] = Field(default=None, description="Severity level")
    duration: Optional[str] = Field(default=None, description="Duration")


class PatientInfo(BaseModel):
    """Patient information extraction"""
    name: Optional[str] = Field(default=None, description="Patient name")
    age: Optional[int] = Field(default=None, ge=0, le=150, description="Patient age")
    symptoms: List[Symptom] = Field(default_factory=list, description="List of symptoms")
    diagnosis: Optional[str] = Field(default=None, description="Diagnosis")
    medications: List[str] = Field(default_factory=list, description="Prescribed medications")


# ============================================================================
# Classification Patterns
# ============================================================================

class CategoryEnum(str, Enum):
    """Example category enumeration"""
    technical = "technical"
    business = "business"
    medical = "medical"
    legal = "legal"
    general = "general"
    unknown = "unknown"


class Classification(BaseModel):
    """Document or text classification"""
    category: CategoryEnum = Field(description="Primary category")
    subcategories: List[str] = Field(default_factory=list, description="Subcategories")
    confidence: float = Field(ge=0.0, le=1.0, description="Classification confidence")
    reasoning: Optional[str] = Field(default=None, description="Classification reasoning")


# ============================================================================
# Moderation/Compliance Patterns
# ============================================================================

class ViolationType(str, Enum):
    """Types of content violations"""
    violence = "violence"
    harassment = "harassment"
    hate_speech = "hate_speech"
    sexual = "sexual"
    self_harm = "self_harm"
    spam = "spam"
    none = "none"


class ContentCompliance(BaseModel):
    """Content moderation result"""
    is_safe: bool = Field(description="Whether content is safe")
    violation_type: Optional[ViolationType] = Field(default=None, description="Type of violation if any")
    severity: Optional[str] = Field(default=None, description="Severity of violation")
    explanation: Optional[str] = Field(default=None, description="Explanation of decision")


# ============================================================================
# Question-Answer Patterns
# ============================================================================

class QAPair(BaseModel):
    """Question-answer pair"""
    question: str = Field(description="The question")
    answer: str = Field(description="The answer")
    source: Optional[str] = Field(default=None, description="Source of the answer")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class MultipleChoice(BaseModel):
    """Multiple choice question response"""
    question: str = Field(description="The question")
    options: List[str] = Field(description="Available options")
    selected_option: str = Field(description="Selected answer")
    explanation: Optional[str] = Field(default=None, description="Why this option was selected")


# ============================================================================
# Summary Patterns
# ============================================================================

class BulletPoint(BaseModel):
    """Single bullet point"""
    point: str = Field(description="The bullet point content")
    importance: Optional[str] = Field(default=None, description="Importance level")


class Summary(BaseModel):
    """Document or text summary"""
    title: Optional[str] = Field(default=None, description="Summary title")
    main_points: List[BulletPoint] = Field(description="Main points")
    conclusion: Optional[str] = Field(default=None, description="Summary conclusion")
    word_count: Optional[int] = Field(default=None, ge=0, description="Word count")


# ============================================================================
# Code Generation Patterns
# ============================================================================

class CodeBlock(BaseModel):
    """Code block with metadata"""
    language: str = Field(description="Programming language")
    code: str = Field(description="The code content")
    explanation: Optional[str] = Field(default=None, description="Code explanation")
    dependencies: List[str] = Field(default_factory=list, description="Required dependencies")


class CodeSolution(BaseModel):
    """Complete code solution"""
    problem_statement: str = Field(description="What problem this solves")
    solution_approach: str = Field(description="Approach taken")
    code_blocks: List[CodeBlock] = Field(description="Code implementation")
    complexity: Optional[str] = Field(default=None, description="Time/space complexity")


# ============================================================================
# Mathematical Patterns
# ============================================================================

class MathStep(BaseModel):
    """Mathematical solution step"""
    step_number: int = Field(ge=1, description="Step number")
    operation: str = Field(description="Mathematical operation performed")
    equation: str = Field(description="Equation or expression")
    explanation: str = Field(description="Explanation of the step")


class MathSolution(BaseModel):
    """Mathematical problem solution"""
    problem: str = Field(description="Problem statement")
    steps: List[MathStep] = Field(description="Solution steps")
    final_answer: str = Field(description="Final answer")
    verification: Optional[str] = Field(default=None, description="Answer verification")


# ============================================================================
# Translation Patterns
# ============================================================================

class Translation(BaseModel):
    """Language translation result"""
    source_language: str = Field(description="Source language")
    target_language: str = Field(description="Target language")
    source_text: str = Field(description="Original text")
    translated_text: str = Field(description="Translated text")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    notes: Optional[str] = Field(default=None, description="Translation notes")


# ============================================================================
# Analysis Patterns
# ============================================================================

class SentimentScore(BaseModel):
    """Sentiment analysis score"""
    positive: float = Field(ge=0.0, le=1.0, description="Positive sentiment score")
    negative: float = Field(ge=0.0, le=1.0, description="Negative sentiment score")
    neutral: float = Field(ge=0.0, le=1.0, description="Neutral sentiment score")


class SentimentAnalysis(BaseModel):
    """Sentiment analysis result"""
    overall_sentiment: str = Field(description="Overall sentiment (positive/negative/neutral)")
    scores: SentimentScore = Field(description="Detailed sentiment scores")
    key_phrases: List[str] = Field(default_factory=list, description="Key phrases affecting sentiment")
    explanation: Optional[str] = Field(default=None, description="Analysis explanation")


# ============================================================================
# Utility Functions
# ============================================================================

def get_schema_by_name(schema_name: str) -> type[BaseModel]:
    """Get schema class by name string."""
    schemas = {
        "SemanticIsolation": SemanticIsolation,
        "EntityExtraction": EntityExtraction,
        "EntitiesList": EntitiesList,
        "ChainOfThought": ChainOfThought,
        "StructuredData": StructuredData,
        "PatientInfo": PatientInfo,
        "Classification": Classification,
        "ContentCompliance": ContentCompliance,
        "QAPair": QAPair,
        "Summary": Summary,
        "CodeSolution": CodeSolution,
        "MathSolution": MathSolution,
        "Translation": Translation,
        "SentimentAnalysis": SentimentAnalysis,
    }
    
    if schema_name not in schemas:
        raise ValueError(f"Unknown schema: {schema_name}")
    
    return schemas[schema_name]


def list_available_schemas() -> List[str]:
    """List all available schema names."""
    return [
        "SemanticIsolation",
        "EntityExtraction", 
        "EntitiesList",
        "ChainOfThought",
        "StructuredData",
        "PatientInfo",
        "Classification",
        "ContentCompliance",
        "QAPair",
        "Summary",
        "CodeSolution",
        "MathSolution",
        "Translation",
        "SentimentAnalysis",
    ]