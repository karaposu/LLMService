# my_llm_service.py

from llmservice import BaseLLMService, GenerationRequest, GenerationResult

class MyLLMService(BaseLLMService):
    
    
    def ask_llm_to_tell_capital(self,user_input: str,) -> GenerationResult:
        
        prompt= f"bring me the capital of this country: {user_input}"
        generation_request = GenerationRequest(
            formatted_prompt=prompt,
            model="gpt-4o",  
        )
        generation_result = self.execute_generation(generation_request)
        return generation_result
    
    
    def bring_only_capital(self,user_input: str,) -> GenerationResult:


        prompt= f"bring me the capital of this {user_input}"
      
        
        pipeline_config = [
            {
                'type': 'SemanticIsolation',   # uses LLMs to isolate specific part of the answer.
                'params': {
                    'semantic_element_for_extraction': 'just the capital'
                }
            }
          

        ]
        generation_request = GenerationRequest(
           
            formatted_prompt=prompt,
            model="gpt-4o-mini",  # Use the model specified in __init__
            pipeline_config=pipeline_config,
          
        )

        # Execute the generation synchronously
        generation_result = self.execute_generation(generation_request)
        return generation_result







