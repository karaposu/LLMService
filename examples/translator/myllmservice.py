"""
Translation Service - Using Modern LLMService Features

This service demonstrates:
- Structured outputs for translations
- Async batch processing
- Rate limiting for API efficiency
- Rich metadata extraction
"""

from typing import Optional, List
from pydantic import BaseModel, Field
import json

from llmservice import BaseLLMService, GenerationRequest
from llmservice.generation_engine import GenerationEngine


# Structured output schemas for translations
class SimpleTranslation(BaseModel):
    """Basic translation output"""
    translated_text: str = Field(description="The translated text")


class TranslationWithMetadata(BaseModel):
    """Translation with additional metadata"""
    translated_text: str = Field(description="The translated text")
    literal_translation: Optional[str] = Field(
        default=None,
        description="Word-for-word translation if meaningful"
    )
    confidence: float = Field(
        ge=0, le=1,
        description="Translation confidence score (0-1)"
    )
    alternatives: List[str] = Field(
        default_factory=list,
        description="Alternative translations if applicable"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Translation notes or warnings"
    )


class ContextualTranslation(BaseModel):
    """Translation with context consideration"""
    translated_text: str = Field(description="The translated text")
    context_used: str = Field(description="How context influenced the translation")


class DocumentTranslation(BaseModel):
    """Full document translation with statistics"""
    translated_document: str = Field(description="The translated document")
    original_word_count: int = Field(description="Word count of original")
    translated_word_count: int = Field(description="Word count of translation")
    quality_score: float = Field(
        ge=0, le=10,
        description="Translation quality score (0-10)"
    )


class MyLLMService(BaseLLMService):
    """Modern translation service using structured outputs"""

    def __init__(self):
        """Initialize with appropriate settings for translation"""
        super().__init__(
            default_model_name="gpt-4o-mini",
            max_rpm=30,  # Rate limiting for API protection
            max_tpm=15000,
            max_concurrent_requests=5  # Allow parallel translations
        )
        self.engine = GenerationEngine(model_name="gpt-4o-mini")
        self.translation_count = 0
        self.total_cost_estimate = 0.0

    def translate_simple(
        self,
        text: str,
        target_language: str
    ) -> Optional[str]:
        """
        Simple translation returning just the translated text.

        Replaces old pipeline approach with structured output.
        """
        prompt = f"Translate the following text to {target_language}: {text}"

        try:
            result = self.engine.generate_structured(
                prompt=prompt,
                schema=SimpleTranslation,
                system=f"You are a professional translator. Translate accurately to {target_language}."
            )

            self.translation_count += 1
            self._update_cost_estimate()

            return result.translated_text

        except Exception as e:
            print(f"Translation error: {e}")
            return None

    def translate_with_metadata(
        self,
        text: str,
        target_language: str
    ) -> Optional[TranslationWithMetadata]:
        """
        Translate with rich metadata including confidence and alternatives.
        """
        prompt = f"""
        Translate this text to {target_language}: "{text}"

        Provide:
        1. The translation
        2. A literal translation if it differs significantly
        3. Your confidence level
        4. Any alternative translations
        5. Notes about cultural context or nuances
        """

        try:
            result = self.engine.generate_structured(
                prompt=prompt,
                schema=TranslationWithMetadata,
                system="You are an expert translator providing detailed translation analysis."
            )

            self.translation_count += 1
            self._update_cost_estimate()

            return result

        except Exception as e:
            print(f"Translation error: {e}")
            return None

    async def translate_async(
        self,
        text: str,
        target_language: str,
        doc_id: Optional[int] = None
    ) -> Optional[str]:
        """
        Async translation for batch processing.
        Uses GenerationRequest for full async support.
        """
        request = GenerationRequest(
            user_prompt=f"Translate to {target_language}: {text}",
            system_prompt="You are a professional translator. Provide only the translation.",
            response_schema=SimpleTranslation,
            model="gpt-4o-mini",
            operation_name="batch_translation",
            request_id=doc_id
        )

        result = await self.execute_generation_async(request)

        if result.success:
            try:
                data = json.loads(result.content)
                translation = SimpleTranslation(**data)
                self.translation_count += 1
                self._update_cost_estimate()
                return translation.translated_text
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Parse error for doc {doc_id}: {e}")
                return None
        else:
            print(f"Translation failed for doc {doc_id}: {result.error_message}")
            return None

    def translate_with_context(
        self,
        text: str,
        target_language: str,
        context: str
    ) -> Optional[ContextualTranslation]:
        """
        Context-aware translation for ambiguous terms.
        """
        prompt = f"""
        Text to translate: "{text}"
        Context: {context}
        Target language: {target_language}

        Translate considering the context.
        """

        try:
            result = self.engine.generate_structured(
                prompt=prompt,
                schema=ContextualTranslation,
                system="You are a context-aware translator. Consider the context when translating ambiguous terms."
            )

            self.translation_count += 1
            self._update_cost_estimate()

            return result

        except Exception as e:
            print(f"Contextual translation error: {e}")
            return None

    def translate_document(
        self,
        document: str,
        target_language: str
    ) -> Optional[DocumentTranslation]:
        """
        Translate entire document with formatting preservation.
        """
        prompt = f"""
        Translate this document to {target_language}, preserving formatting:

        {document}

        Maintain:
        - Paragraph structure
        - Bullet points
        - Numbering
        - Special characters
        """

        try:
            result = self.engine.generate_structured(
                prompt=prompt,
                schema=DocumentTranslation,
                system="""You are a document translator.
                Preserve formatting, calculate word counts,
                and assess translation quality (0-10 scale)."""
            )

            self.translation_count += 1
            self._update_cost_estimate(large_document=True)

            return result

        except Exception as e:
            print(f"Document translation error: {e}")
            return None

    def batch_translate_sync(
        self,
        texts: List[str],
        target_language: str
    ) -> List[Optional[str]]:
        """
        Synchronous batch translation.
        For when you don't need async complexity.
        """
        results = []
        for text in texts:
            translation = self.translate_simple(text, target_language)
            results.append(translation)
        return results

    def _update_cost_estimate(self, large_document: bool = False):
        """Estimate translation costs"""
        # Rough estimates
        tokens_per_translation = 300 if not large_document else 1500
        cost_per_million = 0.15  # $0.15 per 1M tokens for gpt-4o-mini
        cost = (tokens_per_translation / 1_000_000) * cost_per_million
        self.total_cost_estimate += cost

    def print_session_stats(self):
        """Print translation session statistics"""
        print("\n" + "="*70)
        print("Translation Session Statistics")
        print("="*70)
        print(f"Total translations: {self.translation_count}")
        print(f"Estimated cost: ${self.total_cost_estimate:.6f}")

        if hasattr(self, 'metrics'):
            snapshot = self.metrics.snapshot()
            print(f"Current RPM: {snapshot.rpm:.2f}")
            print(f"Total cost tracked: ${snapshot.cost:.6f}")


# Alternative implementation for special use cases
class AdvancedTranslationService(BaseLLMService):
    """
    Advanced translation features including:
    - Multi-step translation through pivot languages
    - Style-aware translation
    - Domain-specific terminology
    """

    def __init__(self):
        super().__init__(
            default_model_name="gpt-4o",  # Use more powerful model
            max_rpm=10
        )
        self.engine = GenerationEngine(model_name="gpt-4o")

    def translate_with_style(
        self,
        text: str,
        target_language: str,
        style: str = "formal"
    ) -> Optional[str]:
        """
        Translate with specific style (formal, informal, technical, poetic)
        """
        prompt = f"""
        Translate to {target_language} in {style} style: {text}
        """

        try:
            result = self.engine.generate_structured(
                prompt=prompt,
                schema=SimpleTranslation,
                system=f"Translate maintaining a {style} tone and style."
            )
            return result.translated_text
        except Exception as e:
            print(f"Style translation error: {e}")
            return None