

![LLMSERVICE Logo](https://raw.githubusercontent.com/karaposu/llmkit/refs/heads/main/assets/text_logo_transp.png)


-----------------

A clean, production-ready service layer that centralizes prompts, invocations, and post-processing, ensuring rate-aware, maintainable, and scalable LLM logic in your application.

|             |                                                                                                                                                                                |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Package** | [![PyPI Latest Release](https://img.shields.io/pypi/v/llmservice.svg)](https://pypi.org/project/llmservice/) [![PyPI Downloads](https://img.shields.io/pypi/dm/llmservice.svg?label=PyPI%20downloads)](https://pypi.org/project/llmservice/) |

## Installation

Install LLMService via pip:

```bash
pip install llmservice
```
 

## What makes it unique?

| Feature                             | LLMService                                                                                                                                | LangChain                                                                                                          |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **Result Handling**                 | Returns a single `GenerationResult` dataclass encapsulating success/failure, rich metadata (tokens, cost, latency), and pipeline outcomes | Composes chains of tools and agents; success/failure handling is dispersed via callbacks and exceptions            |
| **Rate-Limit & Throughput Control** | Built-in sliding-window RPM/TPM counters and an adjustable semaphore for concurrency, automatically pausing when you hit your API quota   | Relies on external throttlers or underlying client logic; no native RPM/TPM management                             |
| **Cost Monitoring**                 | Automatic per-model token-level cost calculation and aggregated usage stats for real-time billing insights                                | No built-in cost monitoring—you must implement your own wrappers or middleware                                     |
| **Post-Processing Pipelines**       | Declarative configs for JSON parsing, semantic extraction, validation, and transformation without ad-hoc parsing code                     | Encourages embedding output parsers inside chains or writing ad-hoc post-chain functions, scattering parsing logic |
| **Dependencies**                    | Minimal footprint: only Tenacity, your LLM client, and optionally YAML for prompts                                                        | Broad ecosystem: agents, retrievers, vector stores, callback managers, and other heavy dependencies                |
| **Extensibility**                   | Provides a clear `BaseLLMService` subclassing interface so you encapsulate each business operation and never call the engine directly     | You wire together chains or agents at call-site, mixing business logic with prompt orchestration                   |



LLMService delivers a well-structured alternative to more monolithic frameworks like LangChain.

> "LangChain isn't a library, it's a collection of demos held together by duct tape, fstrings, and prayers." 


## Main Features

* **Minimal Footprint & Low Coupling**  
  Designed for dependency injection—your application code never needs to know about LLM logic.

* **Result Monad Pattern**  
  Returns a `GenerationResult` dataclass for every invocation, encapsulating success/failure status, raw and processed outputs, error details, retry information, and per-step results—giving you full control over custom workflows.

* **Declarative Post-Processing Pipelines**  
  Chain semantic extraction, JSON parsing, string validation, and more via simple, declarative configurations.

* **Rate-Limit-Aware Asynchronous Requests**  
  Dynamically queue and scale workers based on real-time RPM/TPM metrics to maximize throughput without exceeding API quotas.

* **Transparent Cost & Usage Monitoring**  
  Automatically track input/output tokens and compute per-model cost, exposing detailed metadata with each response.

* **Automated Retry & Exponential Backoff**  
  Handle transient errors (rate limits, network hiccups) with configurable retries and exponential backoff powered by Tenacity.

* **Custom Exception Handling**  
  Provide clear, operation-specific fallbacks (e.g., insufficient quota, unsupported region) for graceful degradation.



## Architecture

LLMService provides an abstract `BaseLLMService` class to guide users in implementing their own service layers. It includes `llmhandler`which manages interactions with different LLM providers and `generation_engine` which handles the process of prompt crafting, LLM invocation, and post-processing

![LLMService Architecture](https://raw.githubusercontent.com/karaposu/LLMService/refs/heads/main/assets/architecture.png) 

![schemas](https://raw.githubusercontent.com/karaposu/LLMService/refs/heads/main/assets/schemas.png)  

# Usage 

## Installation

Install LLMService via pip:

```bash
pip install llmservice
```

## Step 1: Subclassing `BaseLLMService` and create methods

Create a new Python file (e.g., `my_llm_service.py`) and extend the `BaseLLMService` class. And all llm using logic of your business logic will be defined here as methods. 


```python
 def translate_to_latin(self, input_paragraph: str) -> GenerationResult:
        my_prompt=f"translate this text to latin {input_paragraph}"

        generation_request = GenerationRequest(
            formatted_prompt=my_prompt,
            model="gpt-4o",  # Use the model specified in __init__
        )

        # Execute the generation synchronously
        generation_result = self.execute_generation(generation_request)
        return generation_result
```

## Step 2: Import your llm layer and use the methods 

```python
# app.py
from my_llm_service import MyLLMService

if __name__ == '__main__':
    service = MyLLMService()
    result = service.translate_to_latin("Hello, how are you?")
    print(result)
    
    # in this case the result will be a generation_result object which inludes all the information you need. 
```

## Step 3: Life is about joyment. Do not miss life. 


# Postprocessing Pipeline  
There are 5 custom methods integrated into LLMservice. These postprocessing methods are the most commonly used methods so 
we are supporting them natively. 

## Method 1: SemanticIsolator

When you want isolate specific semantics (code piece, name, ) from LLM output you can use SemanticIsolater. 

for example: 

lets have such code 

```

from non_exitent_module import run_sql_code_directly
def main():
    service = MyLLMService()

    my_db_desc= """ I have a database table with the following schema:
           Table: bills
           - bill_id (INT, Primary Key)
           - bill_date (DATE)
           - total (DECIMAL) """

    user_question= " retrieve the total spendings for each month in the year 2023, grouped by month and ordered chronologically."

    result = service.create_sql_code(user_question=user_question, database_desc=my_db_desc)
    
    data_from_db=run_sql_code_directly(result.content)

```
As you see we get the LLM output (result.content) directly and use that in another function which runs it as SQL code. 
But what if LLM output includes non-SQL string like "here is your answer: " or "do you need something else?" ?

This is where SemanticIsolator is helpful. You tell it which semantic element it should isolate and it runs a second LLM query to extract that element only.

So for above example we can create my_llm_service method like this:


```
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

```


## Method 2: ConvertToDict

When you ask LLM to output json like response. You also want to convert the response into a dict (usually using json.load() ) but there are many cases where output is missing quotes and jsonload will fail.  ConvertToDict uses module called 
string2dict which handles all edge cases and even there are missing quotes it can understand and convert the string into a dictionary.
 below are some LLM outputs where json.load fails but ConvertToDict can convert


```
 sample_1 

  '{\n    "key": "SELECT DATE_FORMAT(bills.bill_date, \'%Y-%m\') AS month, SUM(bills.total) AS total_spending FROM bills WHERE YEAR(bills.bill_date) = 2023 GROUP BY DATE_FORMAT(bills.bill_date, \'%Y-%m\') ORDER BY month;"\n}'

 sample_2 

  "{\n    'key': 'SELECT DATE_FORMAT(bill_date, \\'%Y-%m\\') AS month, SUM(total) AS total_spendings FROM bills WHERE YEAR(bill_date) = 2023 GROUP BY month ORDER BY month;'\n}"
 
 sample_3

  '{   \'key\': "https://dfasdfasfer.vercel.app/"}'
   
```


## Method 3: ExtractValue

Useful when you asked LLM for json output with field {"answer" : __here_is_LLM answer.__ } and you want to extract the data from the result dict using a key. This pipeline step allows you to automatically extract the value from this dictionary. 

            {
            #     'type': 'ExtractValue',       # if you asked for json output and you want to extract the data from the result dict
            #     'params': {'key': 'answer'}
            # }


## Using Pipeline Methods together
It is common scenario. You can pipe these methods together like this

      - semanticisolator can extract json part
      - ConvertToDict can convert json into a dict 
      - ExtractValue can help you take only value part of the dictonary

Here how it looks in code:

```
pipeline_config = [
            {
                'type': 'SemanticIsolation',   # uses LLMs to isolate specific part of the answer.
                'params': {
                    'semantic_element_for_extraction': 'SQL code'
                }
            }
           , 
           {
               'type': 'ConvertToDict',  # uses string2dict package to convert output to a dict. Handles edge cases.
                 'params': {}
             },
            {
                'type': 'ExtractValue',       # if you asked for json output and you want to extract the data from the result dict
               'params': {'key': 'answer'}
            }
          ]

```

## Async support 
LLMservice supports async methods. 


















some notes to add to future 

The Result Monad enhances error management by providing detailed insights into why a particular operation might have failed, enhancing the robustness of systems that interact with external data.
As evident from the examples, each of these monads facilitates the creation of function chains, employing a paradigm often referred to as a “railroad approach.” This approach visualizes the sequence of functions as a metaphorical railroad track, where the code smoothly travels along, guided by the monadic structure. The beauty of this railroad approach lies in its ability to elegantly manage complex computations and transformations, ensuring a structured and streamlined flow of operations.
