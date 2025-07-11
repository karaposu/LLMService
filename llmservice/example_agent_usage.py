# example_agent_usage.py
"""
Example of using the Agent Framework with LLMService
"""

import asyncio
from llmservice import BaseLLMService
from llmservice.base_agent import WebSearchAgent, Tool, BaseAgent, AgentContext

# Example: Create a custom agent for code generation
class CodeGenerationAgent(BaseAgent):
    """Agent specialized in generating and testing code."""
    
    def __init__(self, llm_service: BaseLLMService):
        tools = [
            Tool(
                name="generate_code",
                description="Generate code based on requirements",
                parameters={"requirements": "str", "language": "str"},
                function=self._generate_code
            ),
            Tool(
                name="test_code",
                description="Test the generated code",
                parameters={"code": "str", "test_cases": "list"},
                function=self._test_code
            ),
            Tool(
                name="refactor_code",
                description="Refactor code based on feedback",
                parameters={"code": "str", "feedback": "str"},
                function=self._refactor_code
            ),
            Tool(
                name="document_code",
                description="Add documentation to code",
                parameters={"code": "str"},
                function=self._document_code
            )
        ]
        
        super().__init__(llm_service, tools, model="gpt-4o", verbose=True)
    
    async def _generate_code(self, requirements: str, language: str) -> str:
        """Generate code using LLM."""
        request = GenerationRequest(
            system_prompt=f"You are an expert {language} programmer.",
            user_prompt=f"Generate code for: {requirements}",
            model=self.model,
            operation_name="code_generation"
        )
        
        result = await self.llm_service.execute_generation_async(request)
        return result.content if result.success else "Failed to generate code"
    
    async def _test_code(self, code: str, test_cases: list) -> dict:
        """Mock code testing."""
        # In real implementation, this would execute the code
        return {
            "passed": len(test_cases),
            "failed": 0,
            "errors": []
        }
    
    async def _refactor_code(self, code: str, feedback: str) -> str:
        """Refactor code based on feedback."""
        request = GenerationRequest(
            user_prompt=f"Refactor this code based on feedback:\n\nCode:\n{code}\n\nFeedback:\n{feedback}",
            model=self.model,
            operation_name="code_refactoring"
        )
        
        result = await self.llm_service.execute_generation_async(request)
        return result.content if result.success else code
    
    async def _document_code(self, code: str) -> str:
        """Add documentation to code."""
        request = GenerationRequest(
            user_prompt=f"Add comprehensive documentation to this code:\n{code}",
            model=self.model,
            operation_name="code_documentation"
        )
        
        result = await self.llm_service.execute_generation_async(request)
        return result.content if result.success else code


# Example: Task-specific agent with custom planning
class DataAnalysisAgent(BaseAgent):
    """Agent for data analysis tasks."""
    
    def __init__(self, llm_service: BaseLLMService):
        tools = [
            Tool(
                name="load_data",
                description="Load data from various sources",
                parameters={"source": "str", "format": "str"},
                function=self._load_data
            ),
            Tool(
                name="analyze_data",
                description="Perform statistical analysis",
                parameters={"data": "any", "analysis_type": "str"},
                function=self._analyze_data
            ),
            Tool(
                name="visualize_data",
                description="Create data visualizations",
                parameters={"data": "any", "chart_type": "str"},
                function=self._visualize_data
            ),
            Tool(
                name="generate_insights",
                description="Generate insights from analysis",
                parameters={"analysis_results": "dict"},
                function=self._generate_insights
            )
        ]
        
        super().__init__(llm_service, tools, model="gpt-4o-mini", verbose=True)
    
    async def _load_data(self, source: str, format: str) -> dict:
        """Mock data loading."""
        return {"data": "mock_data", "rows": 1000, "columns": 10}
    
    async def _analyze_data(self, data: any, analysis_type: str) -> dict:
        """Mock data analysis."""
        return {
            "analysis_type": analysis_type,
            "results": {"mean": 50, "std": 10, "correlation": 0.8}
        }
    
    async def _visualize_data(self, data: any, chart_type: str) -> str:
        """Mock visualization creation."""
        return f"Created {chart_type} visualization"
    
    async def _generate_insights(self, analysis_results: dict) -> str:
        """Generate insights using LLM."""
        request = GenerationRequest(
            user_prompt=f"Generate business insights from this analysis: {analysis_results}",
            model=self.model,
            operation_name="insight_generation"
        )
        
        result = await self.llm_service.execute_generation_async(request)
        return result.content if result.success else "No insights generated"


async def main():
    """Example usage of different agents."""
    
    # Initialize LLMService
    from llmservice import BaseLLMService
    
    class MyLLMService(BaseLLMService):
        """Your LLMService implementation."""
        pass
    
    llm_service = MyLLMService(
        default_model_name="gpt-4o-mini",
        max_rpm=100,
        max_tpm=100000,
        enable_metrics_logging=True
    )
    
    # Example 1: Web Search Agent
    print("=== Web Search Agent Example ===")
    search_agent = WebSearchAgent(llm_service)
    
    search_result = await search_agent.run(
        "Find the latest developments in quantum computing and summarize the key breakthroughs"
    )
    
    print(f"Task completed: {search_result.current_state}")
    print(f"Total LLM calls: {search_result.total_llm_calls}")
    print(f"Total cost: ${search_result.total_cost:.4f}")
    
    # Example 2: Code Generation Agent
    print("\n=== Code Generation Agent Example ===")
    code_agent = CodeGenerationAgent(llm_service)
    
    code_result = await code_agent.run(
        "Create a Python function that implements a binary search tree with insert, delete, and search operations"
    )
    
    print(f"Task completed: {code_result.current_state}")
    print(f"Generated code with {len(code_result.execution_results)} steps")
    
    # Example 3: Data Analysis Agent
    print("\n=== Data Analysis Agent Example ===")
    data_agent = DataAnalysisAgent(llm_service)
    
    analysis_result = await data_agent.run(
        "Load sales data, analyze trends, create visualizations, and provide actionable insights"
    )
    
    print(f"Task completed: {analysis_result.current_state}")
    print(f"Retry count: {analysis_result.retry_count}")
    
    # Show usage stats
    print("\n=== Overall LLMService Stats ===")
    usage_stats = llm_service.get_usage_stats()
    print(f"Total usage: {usage_stats}")


# Custom agent with specific error handling
class RobustAgent(BaseAgent):
    """Example of agent with custom error handling and retry logic."""
    
    async def _evaluate_results(self, context: AgentContext) -> bool:
        """Override evaluation with custom logic."""
        # First do standard evaluation
        success = await super()._evaluate_results(context)
        
        if not success:
            # Custom analysis of what went wrong
            failed_steps = [
                r for r in context.execution_results 
                if not r.get('success', False)
            ]
            
            if failed_steps:
                # Log specific failures
                print(f"Failed steps: {failed_steps}")
                
                # Determine if retry would help
                retryable_errors = ['timeout', 'rate_limit', 'temporary_failure']
                should_retry = any(
                    any(err in str(step.get('error', '')).lower() 
                        for err in retryable_errors)
                    for step in failed_steps
                )
                
                if not should_retry and context.retry_count > 0:
                    # Don't retry if it's not a retryable error
                    context.max_retries = context.retry_count
        
        return success


# Running agents in parallel
async def parallel_agent_example():
    """Example of running multiple agents in parallel."""
    llm_service = BaseLLMService()
    
    # Create multiple agents
    agents = [
        WebSearchAgent(llm_service),
        CodeGenerationAgent(llm_service),
        DataAnalysisAgent(llm_service)
    ]
    
    # Define tasks
    tasks = [
        "Research the latest AI trends",
        "Generate a Python web scraper",
        "Analyze customer feedback data"
    ]
    
    # Run all agents in parallel
    results = await asyncio.gather(*[
        agent.run(task) for agent, task in zip(agents, tasks)
    ])
    
    # Aggregate results
    total_cost = sum(r.total_cost for r in results)
    total_calls = sum(r.total_llm_calls for r in results)
    
    print(f"Completed {len(results)} tasks")
    print(f"Total cost across all agents: ${total_cost:.4f}")
    print(f"Total LLM calls: {total_calls}")


if __name__ == "__main__":
    asyncio.run(main())