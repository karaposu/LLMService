# here is myllmservice.py


# to run python -m examples.other.myllmservice

import logging

# logger = logging.getLogger(__name__)
import asyncio
from llmservice import BaseLLMService, GenerationRequest, GenerationResult
from typing import Optional, Union
from . import prompts


class MyLLMService(BaseLLMService):
    def __init__(self, logger=None, max_concurrent_requests=200):
        super().__init__(
            logger=logging.getLogger(__name__),
            # default_model_name="gpt-4o-mini",
            default_model_name="gpt-4.1-nano",
            max_rpm=500,
            max_concurrent_requests=max_concurrent_requests,
        )
       
    # def filter, parse


   

    def generate_ai_answer(self, chat_history: str, user_msg=None, model = None,
    ) -> GenerationResult:
        
        user_prompt = prompts.GENERATE_AI_ANSWER_PROMPT.format(
            chat_history=chat_history,
            user_msg=user_msg
        )
       
        
        if model is None:
            model= "gpt-4o-mini"

        generation_request = GenerationRequest(
            user_prompt=user_prompt,
            model=model,
            output_type="str",
            operation_name="generate_ai_answer",
            # pipeline_config=pipeline_config,
            # request_id=request_id,
        )

        result = self.execute_generation(generation_request)
        return result
    
    def generate_affirmations_with_llm(self, context: str, category: Optional[str] = None, 
                                     count: int = 5, model: Optional[str] = None) -> GenerationResult:
        """
        Generate positive affirmations based on user context using LLM.
        
        Args:
            context: The user's context/situation for generating relevant affirmations
            category: Optional category for the affirmations
            count: Number of affirmations to generate (default: 5)
            model: LLM model to use (default: gpt-4o-mini)
            
        Returns:
            GenerationResult containing the generated affirmations
        """
        category_line = f'Category: {category}' if category else ''
        # formatted_prompt = prompts.GENERATE_AFFIRMATIONS_PROMPT.format(
        #     count=count,
        #     context=context,
        #     category_line=category_line
        # )


        formatted_prompt = f"""Generate {count} positive affirmations based on the following context:
            
Context: {context}
{category_line}

Requirements:
1. Create powerful, personal affirmations in first person (I am, I have, I can)
2. Make them specific to the given context
3. Keep them concise and memorable
4. Make them positive and present-tense
5. Return as a JSON array of objects with "content" field

CRITICAL: Return ONLY the raw JSON array. Do NOT wrap in ```json``` code blocks. Do NOT add any text before or after. Start directly with [ and end with ]

Example of correct format:
[
    {{"content": "I am confident in my abilities"}},
    {{"content": "I embrace challenges as opportunities to grow"}}
]

Generate the affirmations now. Remember: NO markdown, NO code blocks, ONLY the JSON array."""

        if model is None:
            model = "gpt-4o-mini"
        
        pipeline_config = [
            {
                "type": "ConvertToDict",
                "params": {},
            },

            {
                'type': 'ExtractValue',
                'params': {'key': 'content'} 
            }
        ]
        
        generation_request = GenerationRequest(
            user_prompt=formatted_prompt,
            model=model,
            output_type="json",
            operation_name="generate_affirmations",
            pipeline_config=pipeline_config
        )
        
        result = self.execute_generation(generation_request)
        return result
    


   


def main():
    """
    Main function to test the categorize_simple method of MyLLMService.
    """
    # Initialize the service
    my_llm_service = MyLLMService()


    context= "i want to make million dolars"
    category= ""
    count = 5
    model= None



    try:
      
        generation_result = my_llm_service.generate_affirmations_with_llm(
            context=context,
            category=category,
            count=count
        )

        # Print the result
      

        # print("Generation Result content:", generation_result.content)

        print(" ")
        print(" ")

        print("Generation Result raw_content:", generation_result.raw_content)


        print(" ")
        print(" ")

       
        print("Generation Result raw_response:", generation_result.raw_response)


   

        if generation_result.success:

          

            print("Content:")
            print( generation_result.content)
            print("type Content:", type(generation_result.content))
        else:
            print("Error:")
            print(generation_result.error_message)

            print(" ")
            print(" ")
           

            print("Generation Result raw_response:")
            print( generation_result.raw_response)

            print(" ")

            print(" ")
            print(" ")

          
            print("pipeline_steps_results:")

            print("ConvertToDict Input:")

            print( generation_result.pipeline_steps_results[0].content_before)

            print("ConvertToDict Output:")
            print( generation_result.pipeline_steps_results[0].content_after)

            print("")
            print("ExtractValue input:")
            print( generation_result.pipeline_steps_results[1].content_before)

            print("ExtractValue Output:")
            print( generation_result.pipeline_steps_results[1].content_after)


            # print( generation_result.pipeline_steps_results)


           



            # print("Generation Result:", generation_result)
            # print(" ")
            # print(" ")



    except Exception as e:
        import traceback
        print(f"An exception occurred: {e}")
        print("Full traceback:")
        traceback.print_exc()


if __name__ == "__main__":
    main()
