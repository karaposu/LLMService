#!/usr/bin/env python3
"""
SQL Code Generator Example - Using Latest LLMService Features

This example demonstrates:
1. Generating SQL queries from natural language
2. Using structured outputs for clean SQL extraction
3. Validating SQL syntax
4. Handling multiple database schemas

To run:
1. Install llmservice: pip install llmservice (or pip install -e . from root)
2. Set OPENAI_API_KEY in your .env file
3. Run: python examples/SQL_code_generator/main.py
"""

from myllmservice import MyLLMService


def main():
    myllmservice = MyLLMService()

    # Example 1: Simple query generation
    print("\n" + "="*70)
    print("EXAMPLE 1: Simple SQL Query Generation")
    print("="*70)

    db_schema = """
    Database: company_db
    Table: employees
    - employee_id (INT, Primary Key)
    - name (VARCHAR(100))
    - department (VARCHAR(50))
    - salary (DECIMAL)
    - hire_date (DATE)
    """

    query = "Find all employees in the IT department with salary over 70000"

    result = myllmservice.generate_sql_simple(
        user_question=query,
        database_schema=db_schema
    )

    if result:
        print(f"\nUser Query: {query}")
        print(f"\nGenerated SQL:\n{result}")
    else:
        print("Failed to generate SQL")

    # Example 2: Complex query with structured output
    print("\n" + "="*70)
    print("EXAMPLE 2: Complex Query with Explanation")
    print("="*70)

    complex_schema = """
    Database: bills_db
    Tables:
    1. bills
       - bill_id (INT, Primary Key)
       - customer_id (INT, Foreign Key)
       - bill_date (DATE)
       - total (DECIMAL)
       - status (VARCHAR(20))

    2. customers
       - customer_id (INT, Primary Key)
       - name (VARCHAR(100))
       - email (VARCHAR(100))
       - registration_date (DATE)
    """

    complex_query = """
    Get the total spending for each customer in 2023,
    but only for customers who registered before 2023,
    ordered by total spending descending
    """

    sql_result = myllmservice.generate_sql_with_explanation(
        user_question=complex_query,
        database_schema=complex_schema
    )

    if sql_result:
        print(f"\nUser Query: {complex_query}")
        print(f"\nGenerated SQL:\n{sql_result.sql_code}")
        print(f"\nExplanation: {sql_result.explanation}")
        print(f"\nQuery Type: {sql_result.query_type}")
    else:
        print("Failed to generate SQL")

    # Example 3: Multiple query generation
    print("\n" + "="*70)
    print("EXAMPLE 3: Batch Query Generation")
    print("="*70)

    queries = [
        "Count all bills from January 2023",
        "Find the customer with highest total spending",
        "List all unpaid bills older than 30 days"
    ]

    print("\nGenerating multiple queries:")
    for q in queries:
        print(f"\n• Query: {q}")
        sql = myllmservice.generate_sql_simple(q, complex_schema)
        if sql:
            print(f"  SQL: {sql}")

    # Example 4: Query validation and optimization
    print("\n" + "="*70)
    print("EXAMPLE 4: Query Analysis and Optimization")
    print("="*70)

    analysis_query = "Get average bill amount by month for year 2023"

    analysis = myllmservice.analyze_and_optimize_query(
        user_question=analysis_query,
        database_schema=complex_schema
    )

    if analysis:
        print(f"\nOriginal Request: {analysis_query}")
        print(f"\nSQL Query:\n{analysis.sql_query}")
        print(f"\nOptimized Query:\n{analysis.optimized_query}")
        print(f"\nPerformance Notes: {analysis.performance_notes}")
        print(f"\nIndexes Recommended: {', '.join(analysis.recommended_indexes) if analysis.recommended_indexes else 'None'}")
    else:
        print("Failed to analyze query")

    # Show session statistics
    print("\n" + "="*70)
    print("Session Statistics")
    print("="*70)

    stats = myllmservice.get_session_stats()
    print(f"\nTotal queries generated: {stats['total_queries']}")
    print(f"Successful: {stats['successful']}")
    print(f"Failed: {stats['failed']}")
    print(f"Estimated cost: ${stats.get('estimated_cost', 0):.6f}")


if __name__ == "__main__":
    main()