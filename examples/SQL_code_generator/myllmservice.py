"""
SQL Code Generator Service - Using Modern LLMService Features

This replaces the old pipeline-based approach with structured outputs,
providing better reliability and type safety for SQL generation.
"""

from typing import Optional, List
from pydantic import BaseModel, Field

from llmservice import BaseLLMService, GenerationRequest
from llmservice.generation_engine import GenerationEngine


# Structured output schemas for SQL generation
class SQLQuery(BaseModel):
    """Schema for simple SQL query extraction"""
    sql_code: str = Field(description="The SQL query code")


class SQLWithExplanation(BaseModel):
    """Schema for SQL with explanation"""
    sql_code: str = Field(description="The SQL query code")
    explanation: str = Field(description="Explanation of what the query does")
    query_type: str = Field(description="Type of query (SELECT, INSERT, UPDATE, DELETE, etc.)")


class OptimizedSQL(BaseModel):
    """Schema for SQL analysis and optimization"""
    sql_query: str = Field(description="The generated SQL query")
    optimized_query: str = Field(description="Optimized version of the query")
    performance_notes: str = Field(description="Notes about performance considerations")
    recommended_indexes: List[str] = Field(
        default_factory=list,
        description="Recommended database indexes"
    )


class MyLLMService(BaseLLMService):
    """SQL Code Generator Service using structured outputs"""

    def __init__(self):
        """Initialize with appropriate settings for code generation"""
        super().__init__(
            default_model_name="gpt-4o-mini",
            max_rpm=20,  # Lower rate limit for complex generations
            max_tpm=20000,  # Higher token limit for code
            max_concurrent_requests=3
        )
        self.engine = GenerationEngine(model_name="gpt-4o-mini")
        self.stats = {
            'total_queries': 0,
            'successful': 0,
            'failed': 0,
            'estimated_cost': 0.0
        }

    def generate_sql_simple(self, user_question: str, database_schema: str) -> Optional[str]:
        """
        Generate SQL query from natural language question.

        Old approach (deprecated):
            pipeline_config = [{
                'type': 'SemanticIsolation',
                'params': {'semantic_element_for_extraction': 'SQL code'}
            }]

        New approach: Structured output with Pydantic schema
        """
        self.stats['total_queries'] += 1

        prompt = f"""
        Database Schema:
        {database_schema}

        User Question: {user_question}

        Generate a SQL query to answer the user's question.
        Return ONLY the SQL code, no explanations.
        """

        try:
            # Use structured output for clean SQL extraction
            result = self.engine.generate_structured(
                prompt=prompt,
                schema=SQLQuery,
                system="You are a SQL expert. Generate clean, efficient SQL queries."
            )

            self.stats['successful'] += 1
            self._estimate_cost()

            return result.sql_code

        except Exception as e:
            self.stats['failed'] += 1
            print(f"Error generating SQL: {e}")
            return None

    def generate_sql_with_explanation(
        self,
        user_question: str,
        database_schema: str
    ) -> Optional[SQLWithExplanation]:
        """
        Generate SQL with detailed explanation.
        Shows the power of structured outputs for complex responses.
        """
        self.stats['total_queries'] += 1

        prompt = f"""
        Database Schema:
        {database_schema}

        User Question: {user_question}

        Generate a SQL query with explanation.
        """

        try:
            result = self.engine.generate_structured(
                prompt=prompt,
                schema=SQLWithExplanation,
                system="""You are a SQL expert. Generate:
                1. Clean, efficient SQL code
                2. Clear explanation of what the query does
                3. Identify the query type (SELECT, INSERT, etc.)"""
            )

            self.stats['successful'] += 1
            self._estimate_cost()

            return result

        except Exception as e:
            self.stats['failed'] += 1
            print(f"Error generating SQL with explanation: {e}")
            return None

    def analyze_and_optimize_query(
        self,
        user_question: str,
        database_schema: str
    ) -> Optional[OptimizedSQL]:
        """
        Generate SQL with optimization suggestions.
        Demonstrates complex structured output with lists.
        """
        self.stats['total_queries'] += 1

        prompt = f"""
        Database Schema:
        {database_schema}

        User Question: {user_question}

        Generate and optimize a SQL query.
        """

        try:
            result = self.engine.generate_structured(
                prompt=prompt,
                schema=OptimizedSQL,
                system="""You are a SQL performance expert. For the user's question:
                1. Generate the SQL query
                2. Provide an optimized version
                3. Explain performance considerations
                4. Recommend specific indexes that would help"""
            )

            self.stats['successful'] += 1
            self._estimate_cost()

            return result

        except Exception as e:
            self.stats['failed'] += 1
            print(f"Error analyzing query: {e}")
            return None

    def generate_sql_batch(
        self,
        queries: List[str],
        database_schema: str
    ) -> List[Optional[str]]:
        """
        Generate multiple SQL queries efficiently.
        Could be enhanced with async for parallel processing.
        """
        results = []
        for query in queries:
            sql = self.generate_sql_simple(query, database_schema)
            results.append(sql)
        return results

    def _estimate_cost(self):
        """Estimate cost based on typical token usage"""
        # Rough estimate: ~500 tokens per SQL generation
        estimated_tokens = 500
        cost_per_token = 0.15e-6  # $0.15 per 1M tokens for gpt-4o-mini
        self.stats['estimated_cost'] += estimated_tokens * cost_per_token

    def get_session_stats(self) -> dict:
        """Get statistics for the current session"""
        return self.stats.copy()


# Alternative implementation showing direct GenerationRequest usage
class SQLServiceAlternative(BaseLLMService):
    """
    Alternative implementation using GenerationRequest directly
    for more control over the generation process.
    """

    def __init__(self):
        super().__init__(
            default_model_name="gpt-4o",  # Using more powerful model
            max_rpm=10
        )

    def generate_sql_with_request(
        self,
        user_question: str,
        database_schema: str
    ) -> Optional[str]:
        """
        Generate SQL using GenerationRequest with response_schema.
        This gives you access to all telemetry and retry mechanisms.
        """
        import json

        request = GenerationRequest(
            user_prompt=f"""
            Schema: {database_schema}
            Question: {user_question}
            Generate SQL query.
            """,
            system_prompt="You are a SQL expert. Return only valid SQL.",
            response_schema=SQLQuery,
            model="gpt-4o",
            operation_name="sql_generation",
            # Can configure retries, reasoning effort, etc.
            number_of_retries=2
        )

        result = self.execute_generation(request)

        if result.success:
            try:
                data = json.loads(result.content)
                sql_obj = SQLQuery(**data)

                # Access rich telemetry
                print(f"Generation took: {result.elapsed_time:.2f}s")
                print(f"Tokens used: {result.usage.get('total_tokens', 0)}")
                print(f"Cost: ${result.usage.get('total_cost', 0):.6f}")

                return sql_obj.sql_code

            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error parsing SQL response: {e}")
                return None
        else:
            print(f"Generation failed: {result.error_message}")
            print(f"Error type: {result.error_type}")
            return None