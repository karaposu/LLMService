#!/usr/bin/env python3
"""
Capital Finder Example - Using Latest LLMService Features

This example demonstrates:
1. Basic text generation
2. Structured output for extracting just the capital name
3. Using Pydantic schemas for guaranteed format

To run:
1. Install llmservice: pip install llmservice (or pip install -e . from root)
2. Set OPENAI_API_KEY in your .env file
3. Run: python  examples/capital_finder/main.py

 python -m examples.capital_finder.main
"""

from myllmservice import MyLLMService


def main():
    # Initialize service with rate limiting
    myllmservice = MyLLMService()

    country = "Turkey"

    print(f"\n{'='*60}")
    print(f"Finding capital of {country}")
    print('='*60)

    # Method 1: Full response with explanation
    print("\n1. Full Response:")
    print("-" * 40)
    result = myllmservice.ask_llm_to_tell_capital(country)
    if result.success:
        print(f"Response: {result.content}")
        print(f"Tokens used: {result.usage.get('total_tokens', 0)}")
        print(f"Cost: ${result.usage.get('total_cost', 0):.6f}")
    else:
        print(f"Error: {result.error_message}")

    # Method 2: Just the capital name using structured output
    print("\n2. Structured Output (just capital name):")
    print("-" * 40)
    capital = myllmservice.get_capital_only(country)
    if capital:
        print(f"Capital: {capital}")
    else:
        print("Failed to extract capital")

    # Method 3: Get detailed information with structured data
    print("\n3. Detailed Structured Information:")
    print("-" * 40)
    info = myllmservice.get_capital_info(country)
    if info:
        print(f"Country: {info.country}")
        print(f"Capital: {info.capital}")
        print(f"Population: {info.population:,}" if info.population else "Population: Unknown")
        print(f"Language: {info.language}" if info.language else "Language: Unknown")
    else:
        print("Failed to get information")

    # Bonus: Process multiple countries efficiently
    print("\n4. Batch Processing Multiple Countries:")
    print("-" * 40)
    countries = ["France", "Japan", "Brazil"]

    for country_name in countries:
        capital = myllmservice.get_capital_only(country_name)
        print(f"{country_name}: {capital}")

    # Show usage statistics
    print("\n" + "="*60)
    print("Session Statistics:")
    print("-" * 40)
    stats = myllmservice.get_usage_stats()
    if stats:
        total_cost = sum(op.get('total_cost', 0) for op in stats.values())
        total_tokens = sum(op.get('total_tokens', 0) for op in stats.values())
        print(f"Total operations: {len(stats)}")
        print(f"Total tokens: {total_tokens}")
        print(f"Total cost: ${total_cost:.6f}")

        for operation, data in stats.items():
            if data.get('total_tokens', 0) > 0:
                print(f"\n  {operation}:")
                print(f"    Total tokens: {data.get('total_tokens', 0)}")
                print(f"    Input tokens: {data.get('input_tokens', 0)}")
                print(f"    Output tokens: {data.get('output_tokens', 0)}")
                print(f"    Cost: ${data.get('total_cost', 0):.6f}")


if __name__ == "__main__":
    main()