# my_llm_service.py


from llmservice import BaseLLMService, GenerationRequest, GenerationResult


class MyLLMService(BaseLLMService):
    
    def create_sql_code(self, user_question: str,  database_desc,) -> GenerationResult:
    
        formatted_prompt = f"""Here is my database description: {database_desc},
                            and here is what the user wants to learn: {user_question}.
                            I want you to generate a SQL query. answer should contain only SQL code."""
         
        pipeline_config = [
            {
                'type': 'SemanticIsolation',   # uses LLM to isolate specific part of the answer.
                'params': {
                    'semantic_element_for_extraction': 'SQL code'
                }
            }
        ]
        
        generation_request = GenerationRequest(
            formatted_prompt=formatted_prompt,
            model="gpt-4o", 
            pipeline_config=pipeline_config,
        )

        generation_result = self.execute_generation(generation_request)
        return generation_result



