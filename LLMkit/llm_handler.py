# here is llm_handler.py

import os
from pathlib import Path
import logging
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type, RetryCallState

import httpx
import asyncio


from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain_community.llms import Ollama
from openai import RateLimitError


# @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))

logging.getLogger("langchain_community.llms").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger('httpcore').setLevel(logging.WARNING)

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")


class LLMHandler:
    def __init__(self, model_name: str, system_prompt=None, logger=None):
        self.llm = self._initialize_llm(model_name)
        self.system_prompt = system_prompt
        self.model_name=model_name
        self.logger = logger if logger else logging.getLogger(__name__)

        # Set the level of the logger
        self.logger.setLevel(logging.DEBUG)
        self.max_retries = 2  # Set the maximum retries allowed

        self.OPENAI_MODEL = False

        if self.is_it_gpt_model(model_name):
            self.OPENAI_MODEL= True

    def is_it_gpt_model(self, model_name):
        # return model_name in ["gpt-4o-mini", "gpt-4", "gpt-4o", "gpt-3.5"]
        return model_name in ["gpt-4o-mini", "gpt-4", "gpt-4o", "gpt-3.5", "gpt-4o-2024-08-06", "chatgpt-4o-latest", "gpt-4o-mini-2024-07-18", "o1-mini", "o1-preview"]


    def change_model(self, model_name):
        self.llm = self._initialize_llm(model_name)

    def _initialize_llm(self, model_name: str):

        if self.is_it_gpt_model(model_name):

            return ChatOpenAI(api_key=os.getenv("OPENAI_API_KEY"),
                              model_name=model_name,
                              # max_tokens=15000
                              )
        elif model_name=="custom":
            ollama_llm=""
            return ollama_llm
        else:
            if not self._is_ollama_model_downloaded(model_name):
                print(f"The Ollama model '{model_name}' is not downloaded.")
                print(f"To download it, run the following command:")
                print(f"ollama pull {model_name}")
                raise ValueError(f"The Ollama model '{model_name}' is not downloaded.")
            return Ollama(model=model_name)

    def _is_ollama_model_downloaded(self, model_name: str) -> bool:
        #todo check OLLAMA_MODELS path

        # # Define the Ollama model directory (replace with actual directory)
        # ollama_model_dir = Path("~/ollama/models")  # Replace with the correct path
        # model_file = ollama_model_dir / f"{model_name}.model"  # Adjust the file extension if needed
        #
        # # Check if the model file exists
       # model_file.exists()#
        return  True

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, RateLimitError)),
        # Retry on HTTPStatusError and RateLimitError
        stop=stop_after_attempt(2),  # Stop after 2 attempts
        wait=wait_random_exponential(min=1, max=60)  # Exponential backoff between retries
    )
    def invoke(self, prompt: str, retry_state: RetryCallState = None):
    # def invoke_safe(self, prompt: str, retry_state: RetryCallState = None):
        try:
            if self.system_prompt:
                response = self.llm.invoke(prompt=prompt, context=self.system_prompt)
            else:

                response = self.llm.invoke(prompt)
            success=True

            return response, success

        except RateLimitError as e:
            error_message = str(e)
            error_code = getattr(e, 'code', None)
            success = False

            # Try to get the error code from e.json_body if available
            if not error_code and hasattr(e, 'json_body') and e.json_body:
                error_code = e.json_body.get('error', {}).get('code')

            # Fallback: check if 'insufficient_quota' is in the error message
            if not error_code and 'insufficient_quota' in error_message:
                error_code = 'insufficient_quota'

            if error_code == 'insufficient_quota':
                self.logger.error("OpenAI credit is finished.")
                return "OpenAI credit is finished" ,success

            # Handle other rate limit errors
            self.logger.warning(f"RateLimitError occurred: {error_message}. Retrying...")
            if retry_state and self._retry_count_is_max(retry_state):
                return "OpenAI credit is finished" ,success

            raise  # Re-raise the error to trigger the retry mechanism

        except httpx.HTTPStatusError as e:
            success = False
            if e.response.status_code == 429:
                self.logger.warning("Rate limit exceeded: 429 Too Many Requests. Retrying...")

                # Check if this is the last retry attempt
                if retry_state and self._retry_count_is_max(retry_state):
                    return "OpenAI credit is finished" , success

                raise  # Re-raise the error to trigger the retry mechanism

            self.logger.error(f"HTTP error occurred: {e}")
            raise

        except Exception as e:
            self.logger.error(f"An error occurred: {e}")
            raise

    async def invoke_async(self, prompt: str):
        try:
            if self.system_prompt:
                response = await self.llm.agenerate([prompt], system_prompt=self.system_prompt)
            else:
                response = await self.llm.agenerate([prompt])
            success = True
            return response.generations[0][0], success
        except Exception as e:
            self.logger.error(f"An error occurred: {e}")
            return str(e), False

    def _retry_count_is_max(self, retry_state: RetryCallState) -> bool:
        """
        Helper function to check if the retry limit is reached.
        Compares the current attempt number with the max_retries set.
        """
        current_attempt = retry_state.attempt_number
        return current_attempt >= self.max_retries