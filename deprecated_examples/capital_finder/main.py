# this is an standalone example code
# you need to install llmservice via "pip install llmservice"
# you need to put your openai api key as "OPENAI_API_KEY=KEY_HERE" into a .env file in the same directory of your python env

from myllmservice import MyLLMService


llmservice= MyLLMService()
our_input= "Turkey"

generation_result =llmservice.ask_llm_to_tell_capital(our_input)
print(generation_result)
print(generation_result.content)



generation_result =llmservice.bring_only_capital(our_input)
print(generation_result)
print(generation_result.content)




