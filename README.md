# LLMKit

<img src="https://raw.githubusercontent.com/karaposu/llmkit/refs/heads/main/assets/logo_cropped.png" alt="logo" width="200"/>


LLMkit is developed (still ongoing) with the promise of creating a llm based text generation library which follows software development
best practices such 
By emphasizing **Modularity and Separation of Concerns**, **Advanced Error Handling**, and **Modern Software Development Practices** in it's design, 
LLMKit offers a structured approach that stands out against more monolithic frameworks like LangChain.

> "LangChain isn't a library, it's a collection of demos held together by duct tape, fstrings, and prayers."


### Architecture

![LLMKit Architecture](https://raw.githubusercontent.com/karaposu/llmkit/refs/heads/main/assets/llmkit_architecture.png)  <!-- Replace with your image link if hosting it publicly or in the README repository. -->

1. **LLM Handler**: Manages interaction with different LLM providers (e.g., OpenAI, Ollama, Azure).
2. **Generation Engine**: Orchestrates the generation process, including prompt crafting, invoking the LLM, and post-processing.
3. **Proteas**: A sophisticated prompt management system that loads and manages prompt templates from YAML files (`prompt.yaml`).
4. **LLMService (Base Class)**: A base class that serves as a template for users to implement their custom service logic.  
5. **App**: The application that consumes the services provided by LLMKit, receiving structured `generation_result` responses for further processing.

## Features

### Advanced Error Handling

LLMKit incorporates sophisticated error handling mechanisms to ensure robust and reliable interactions with LLMs:

- **Retry Mechanisms**: Utilizes the `tenacity` library to implement retries with exponential backoff for handling transient errors like rate limits or network issues.
- **Custom Exception Handling**: Provides tailored responses to specific errors (e.g., insufficient quota), enabling graceful degradation and clearer insights into failure scenarios.

### Proteas: The Main Prompt Management System

Proteas serves as LLMKit's core prompt management system, offering powerful tools for crafting, managing, and reusing prompts:

- **Prompt Crafting**: Utilizes `PromptTemplate` to create consistent and dynamic prompts based on placeholders and data inputs.
- **Unit Skeletons**: Supports loading and managing prompt templates from YAML files, promoting reusability and organization.

### BaseLLMService Class

LLMKit provides an abstract `BaseLLMService` class to guide users in implementing their own service layers:

- **Modern Software Development Practices**: Encourages adherence to best practices through a well-defined interface.
- **Customization**: Allows developers to tailor the service layer to their specific application needs while leveraging the core functionalities provided by LLMKit.
- **Extensibility**: Facilitates the addition of new features and integrations without modifying the core library.

## Installation

Install LLMKit via pip:

```bash
pip install llmkit
```

## Quick Start

### Core Components

LLMKit provides the following core modules:

- **`llmhandler`**: Manages interactions with different LLM providers.
- **`generation_engine`**: Handles the process of prompt crafting, LLM invocation, and post-processing.
- **`base_service`**: Provides an abstract class that serves as a blueprint for building custom services.

### Creating a Custom LLMService

To create your own service layer, follow these steps:

#### Step 0: Create your prompts.yaml file
Proteas uses a yaml file to load and manage your prompts. Prompts are encouraged to store as prompt template units 
where component of a prompt is decomposed into prompt template units and store in such way. To read more go to proteas docs
(link here)

Create a new Python file (e.g., `prompts.yaml`) 

add these lines 

```commandline
main:


  - name: "input_paragraph"
    statement_suffix: "Here is"
    question_suffix: "What is "
    placeholder_proclamation: input text to be translated
    placeholder: "input_paragraph"


  - name: "translate_to_russian"
    info: > 
      take above text and translate it to russian with a scientific language, Do not output any additiaonal text.
   
```

#### Step 1: Subclass `BaseLLMService`

Create a new Python file (e.g., `my_llm_service.py`) and extend the `BaseLLMService` class.
In your app all llm generation data flow will go through this class.  This is a good way of not coupling rest of your
app logic with LLM relevant logics. 

You simply arange the names of your prompt template units in a list and pass this to generation engine.  

```python
from llmkit.base_service import BaseLLMService
from llmkit.generation_engine import GenerationEngine
import logging

class MyLLMService(BaseLLMService):
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.generation_engine = GenerationEngine(logger=self.logger, model_name="gpt-4o-mini")

    def translate_to_russian(self, input_paragraph: str):
        data_for_placeholders = {'input_paragraph': input_paragraph}
        order = ["input_paragraph", "translate_to_russian"]

        unformatted_prompt = self.generation_engine.craft_prompt(data_for_placeholders, order)

        generation_result = self.generation_engine.generate_output(
            unformatted_prompt, 
            data_for_placeholders,
            response_type="string"
        )

        return generation_result.content
```

#### Step 2: Use the Custom Service

```python
# app.py
from my_llm_service import MyLLMService

if __name__ == '__main__':
    service = MyLLMService()
    result = service.translate_to_russian("Hello, how are you?")
    print(result)
```

Result will be a generation_result object which inludes all the information you need. 




