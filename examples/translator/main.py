#!/usr/bin/env python3
"""
Translator Example - Using Latest LLMService Features

This example demonstrates:
1. Text translation with structured outputs
2. Batch translation with async processing
3. Multi-language support
4. Translation with metadata (confidence, alternatives)
5. Rate limiting and concurrency control

To run:
1. Install llmservice: pip install llmservice (or pip install -e . from root)
2. Set OPENAI_API_KEY in your .env file
3. Run: python examples/translator/main.py
"""

import asyncio
import time
from typing import List
from myllmservice import MyLLMService


def example_simple_translation():
    """Example 1: Simple text translation"""
    print("\n" + "="*70)
    print("EXAMPLE 1: Simple Translation")
    print("="*70)

    myllmservice = MyLLMService()

    text = "Hello, how are you today? The weather is beautiful."
    target_language = "Spanish"

    translation = myllmservice.translate_simple(text, target_language)
    if translation:
        print(f"Original: {text}")
        print(f"Spanish: {translation}")

    # Try multiple languages
    languages = ["French", "German", "Japanese"]
    print("\nTranslating to multiple languages:")
    for lang in languages:
        result = myllmservice.translate_simple(text, lang)
        if result:
            print(f"{lang}: {result}")


def example_structured_translation():
    """Example 2: Translation with metadata using structured output"""
    print("\n" + "="*70)
    print("EXAMPLE 2: Translation with Metadata")
    print("="*70)

    myllmservice = MyLLMService()

    text = "The quick brown fox jumps over the lazy dog"

    result = myllmservice.translate_with_metadata(text, "Spanish")
    if result:
        print(f"Original: {text}")
        print(f"Translation: {result.translated_text}")
        print(f"Literal Translation: {result.literal_translation}")
        print(f"Confidence: {result.confidence:.2f}")
        if result.alternatives:
            print(f"Alternatives: {', '.join(result.alternatives)}")
        if result.notes:
            print(f"Notes: {result.notes}")


async def example_async_batch_translation():
    """Example 3: Async batch translation for efficiency"""
    print("\n" + "="*70)
    print("EXAMPLE 3: Async Batch Translation")
    print("="*70)

    myllmservice = MyLLMService()

    # Simulate multiple documents to translate
    documents = [
        "Financial report for Q3 2024",
        "Market analysis shows positive trends",
        "Customer satisfaction increased by 15%",
        "New product launch scheduled for next month",
        "Quarterly revenue exceeded expectations"
    ]

    target_language = "Russian"

    print(f"Translating {len(documents)} documents to {target_language}...")
    start_time = time.time()

    # Create async tasks for parallel processing
    tasks = [
        myllmservice.translate_async(doc, target_language, doc_id=i)
        for i, doc in enumerate(documents)
    ]

    # Execute all translations concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    for i, (doc, result) in enumerate(zip(documents, results)):
        if isinstance(result, Exception):
            print(f"\n❌ Document {i}: Error - {result}")
        elif result:
            print(f"\n✅ Document {i}:")
            print(f"   Original: {doc}")
            print(f"   Translated: {result}")
        else:
            print(f"\n❌ Document {i}: Translation failed")

    elapsed = time.time() - start_time
    print(f"\nTotal time for {len(documents)} translations: {elapsed:.2f}s")
    print(f"Average time per translation: {elapsed/len(documents):.2f}s")


def example_contextual_translation():
    """Example 4: Context-aware translation for better accuracy"""
    print("\n" + "="*70)
    print("EXAMPLE 4: Contextual Translation")
    print("="*70)

    myllmservice = MyLLMService()

    # Technical terms that need context
    texts_with_context = [
        ("The bank is closed", "financial institution"),
        ("The bank is steep", "river side"),
        ("Python is powerful", "programming language"),
        ("Python is dangerous", "snake")
    ]

    for text, context in texts_with_context:
        result = myllmservice.translate_with_context(
            text=text,
            target_language="Spanish",
            context=context
        )
        if result:
            print(f"\nText: {text}")
            print(f"Context: {context}")
            print(f"Translation: {result.translated_text}")


def example_document_translation():
    """Example 5: Full document translation with formatting preservation"""
    print("\n" + "="*70)
    print("EXAMPLE 5: Document Translation")
    print("="*70)

    myllmservice = MyLLMService()

    document = """
    Subject: Quarterly Business Review

    Dear Team,

    I'm pleased to share our Q3 results:
    • Revenue: $2.5M (↑15% YoY)
    • New Customers: 150
    • Retention Rate: 92%

    Key Achievements:
    1. Launched new product line
    2. Expanded to 3 new markets
    3. Improved customer satisfaction

    Best regards,
    John Smith
    CEO
    """

    result = myllmservice.translate_document(document, "French")
    if result:
        print("Original Document:")
        print(document)
        print("\nTranslated Document:")
        print(result.translated_document)
        print(f"\nWord Count - Original: {result.original_word_count}")
        print(f"Word Count - Translated: {result.translated_word_count}")
        print(f"Translation Quality: {result.quality_score:.2f}/10")


async def main():
    """Run all examples"""

    # Synchronous examples
    example_simple_translation()
    example_structured_translation()
    example_contextual_translation()
    example_document_translation()

    # Asynchronous example
    await example_async_batch_translation()

    # Print session statistics
    myllmservice = MyLLMService()
    myllmservice.print_session_stats()


if __name__ == "__main__":
    # Run all examples
    asyncio.run(main())