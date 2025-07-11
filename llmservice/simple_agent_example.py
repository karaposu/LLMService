# simple_agent_example.py


# to run python -m llmservice.simple_agent_example
import asyncio
from llmservice.myllmservice import MyLLMService
from llmservice.base_agent import BaseAgent, Tool

class SimpleAgent(BaseAgent):
    """Simplified agent with sync interface."""
    
    def run_sync(self, task: str, context: dict = None):
        """Synchronous wrapper for the async run method."""
        return asyncio.run(self.run(task, context))

# Usage
def main():
    # Create service
    llm_service = MyLLMService(
        max_concurrent_requests=10,
        default_model_name="gpt-4o-mini"
    )
    
    # Create agent with simple tools
    agent = SimpleAgent(
        llm_service=llm_service,
        tools=[
            Tool(
                name="calculator",
                description="Perform calculations",
                parameters={"expression": "str"},
                function=lambda expression: eval(expression)  # Simple calc
            )
        ],
        verbose=True
    )
    
    # Run task
    result = agent.run_sync("Calculate the compound interest on $10,000 at 5% for 10 years")
    
    print(f"\nTask completed: {result.current_state}")
    print(f"Total cost: ${result.total_cost:.4f}")

if __name__ == "__main__":
    main()