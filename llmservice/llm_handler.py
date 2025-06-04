# here is llm_handler.py


# to run python -m llmservice.llm_handler
import os
from pathlib import Path
import logging
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type, RetryCallState, AsyncRetrying, Retrying

from typing import Any, List, Tuple, Dict, Optional
import httpx
import asyncio
from datetime import timedelta
from .schemas import InvokeResponseData, InvocationAttempt
from .schemas import ErrorType
from .utils import _now_dt

from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
# from langchain_community.llms import Ollama
from langchain_ollama import OllamaLLM as Ollama
from openai import RateLimitError , PermissionDeniedError

#
# LangChainDeprecationWarning: The class `Ollama` was deprecated in LangChain 0.3.1 and will be removed in
# 1.0.0. An updated version of the class exists in the :class:`~langchain-ollama package and should be used instead. To
# use it run `pip install -U :class:`~langchain-ollama` and
# import as `from :class:`~langchain_ollama import OllamaLLM``.



# @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))

logging.getLogger("langchain_community.llms").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger('httpcore').setLevel(logging.WARNING)

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")


gpt_models_cost = {
    'gpt-4o-search-preview':    {'input_token_cost': 2.5e-6,  'output_token_cost': 10e-6},
    'gpt-4o-mini-search-preview': {'input_token_cost': 2.5e-6,  'output_token_cost': 0.6e-6},
    'gpt-4.5-preview':          {'input_token_cost': 75e-6,   'output_token_cost': 150e-6},
    'gpt-4.1-nano':             {'input_token_cost': 0.1e-6,  'output_token_cost': 0.4e-6},
    'gpt-4.1-mini':             {'input_token_cost': 0.4e-6,  'output_token_cost': 1.6e-6},
    'gpt-4.1':                  {'input_token_cost': 2e-6,    'output_token_cost': 8e-6},
    'gpt-4o':                   {'input_token_cost': 2.5e-6,  'output_token_cost': 10e-6},
    'gpt-4o-audio-preview':     {'input_token_cost': 2.5e-6,  'output_token_cost': 10e-6},
    'gpt-4o-mini':              {'input_token_cost': 0.15e-6, 'output_token_cost': 0.6e-6},
    'o1':                       {'input_token_cost': 15e-6,   'output_token_cost': 60e-6},
    'o1-pro':                   {'input_token_cost': 150e-6,  'output_token_cost': 600e-6},
    'o3':                       {'input_token_cost': 10e-6,   'output_token_cost': 40e-6},
    'o4-mini':                  {'input_token_cost': 1.1e-6,  'output_token_cost': 4.4e-6},
}


gpt_model_list= list(gpt_models_cost.keys())


import time
from datetime import datetime, timezone


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
        self._llm_cache = {}

        if self.is_it_gpt_model(model_name):
            self.OPENAI_MODEL= True

    def is_it_gpt_model(self, model_name):
        # return model_name in ["gpt-4o-mini", "gpt-4", "gpt-4o", "gpt-3.5"]
        return model_name in gpt_model_list

    
    # def change_model(self, model_name):
    #     self.llm = self._initialize_llm(model_name)

    def change_model(self, model_name):
        # 1) update the internal model reference
        self.llm = self._initialize_llm(model_name)
        # 2) **also** update the handler’s own model_name attribute
        self.model_name = model_name

   
    def _init_meta(self) -> Dict[str, Any]:
        """
        Return a fresh metadata dict for token‐usage and cost:
            {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "input_cost": 0,
                "output_cost": 0,
                "total_cost": 0,
            }
        """
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "input_cost": 0,
            "output_cost": 0,
            "total_cost": 0,
        }

    

    def _initialize_llm(self, model_name: str):

        if self.is_it_gpt_model(model_name):
            if model_name== "gpt-4o-search-preview":
               
               return ChatOpenAI(api_key=os.getenv("OPENAI_API_KEY"),
                                model_name=model_name,
                                model_kwargs={
                                    "web_search_options": {
                                        "search_context_size": "high"
                                    }
                                }

                                 
                                )
            else:
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
    

    
    
    def _invoke_impl(self, prompt: str) -> Tuple[Any, bool, Optional[ErrorType]]:
   
        """
        Your original logic, unchanged. Returns (response, success)
        or raises to trigger a retry.
        """
        try:
            if self.system_prompt:
                response = self.llm.invoke(prompt=prompt, context=self.system_prompt)
            else:
                response = self.llm.invoke(prompt)
            return response, True, None

        except RateLimitError as e:
            error_message = str(e)
            error_code = getattr(e, "code", None)
            # existing insufficient_quota fallback
            if not error_code and hasattr(e, "json_body") and e.json_body:
                error_code = e.json_body.get("error", {}).get("code")
            if not error_code and "insufficient_quota" in error_message:
                error_code = "insufficient_quota"
            
            if error_code == "insufficient_quota":
                self.logger.error("OpenAI credit is finished.")
                return "OpenAI credit is finished.", False, ErrorType.INSUFFICIENT_QUOTA

            self.logger.warning(f"RateLimitError occurred: {error_message}. Retrying...")
            # if last retry, return fallback
            raise

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                self.logger.warning("Rate limit exceeded: 429 Too Many Requests. Retrying...")
                raise
            self.logger.error(f"HTTP error occurred: {e}")
            raise

        except PermissionDeniedError as e:
            error_message = str(e)
            error_code = getattr(e, "code", None)
            if error_code == "unsupported_country_region_territory":
             
                self.logger.error("Country, region, or territory not supported.")
                return "Country, region, or territory not supported.", False, ErrorType.UNSUPPORTED_REGION
            
            self.logger.error(f"PermissionDeniedError occurred: {error_message}")
            raise

        except Exception as e:
            self.logger.error(f"An error occurred: {e}")
            raise


    async def _invoke_async_impl(self, prompt: str) -> Tuple[Any, bool]:
        """
        Core async logic, exactly your existing code minus the @retry decorator.
        Returns (response, True) or raises to trigger a retry.
        """
        if not hasattr(self.llm, "ainvoke"):
            raise NotImplementedError(f"{type(self.llm).__name__} does not support async ainvoke")

        try:
            response = await self.llm.ainvoke(prompt)
            return response, True, None
        
        except RateLimitError as e:
            # replicate your existing RateLimitError handling:
            msg = str(e)
            code = getattr(e, "code", None)
            if not code and hasattr(e, "json_body") and e.json_body:
                code = e.json_body.get("error", {}).get("code")
            if not code and "insufficient_quota" in msg:
                code = "insufficient_quota"
            if code == "insufficient_quota":
                self.logger.error("OpenAI credit is finished.")
                return "OpenAI credit is finished.", False, ErrorType.INSUFFICIENT_QUOTA
            self.logger.warning(f"RateLimitError: {msg}. Retrying…")
            raise

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                self.logger.warning("429 Too Many Requests. Retrying…")
                raise
            self.logger.error(f"HTTP error: {e}")
            raise

        except PermissionDeniedError as e:
            msg = str(e)
            code = getattr(e, "code", None)
            if code == "unsupported_country_region_territory":
                self.logger.error("Territory not supported.")
                return "Country/region not supported.", False, ErrorType.UNSUPPORTED_REGION
            self.logger.error(f"PermissionDeniedError: {msg}")
            raise

        except Exception as e:
            self.logger.error(f"Async invoke error: {e}")
            raise




    def invoke(self, prompt: str) -> InvokeResponseData:
        """
        Synchronous invoke that records every attempt in `attempts`.
        """
        attempts: List[InvocationAttempt] = []
        final_response = None
        final_success  = False
        
        try:
                for attempt in Retrying(
                    retry=retry_if_exception_type((httpx.HTTPStatusError, RateLimitError)),
                    stop=stop_after_attempt(self.max_retries),
                    wait=wait_random_exponential(min=1, max=60),
                    reraise=True
                ):
                    with attempt:
                        n = attempt.retry_state.attempt_number
                        start = _now_dt()
                        try:
                            resp, success, error_type = self._invoke_impl(prompt)
                            final_response = resp
                            final_success  = success
                        except Exception as e:
                            # Tenacity will catch and retry if it matches your retry predicate
                            # We still want to record this attempt's timing & error
                            end = _now_dt()
                            backoff = timedelta(seconds=attempt.retry_state.next_action.sleep) \
                                    if attempt.retry_state.next_action else None
                            attempts.append(InvocationAttempt(
                                attempt_number  = n,
                                invoke_start_at = start,
                                invoke_end_at   = end,
                                backoff_after_ms   = backoff,
                                error_message   = str(e)
                            ))
                            raise  # let Tenacity handle retrying
                        else:
                            # successful attempt
                            end = _now_dt()
                            # no backoff_after on a success
                            attempts.append(InvocationAttempt(
                                attempt_number  = n,
                                invoke_start_at = start,
                                invoke_end_at   = end,
                                backoff_after_ms   = None,
                                error_message   = None
                            ))
                

                meta=self._init_meta()

                # print("final_response: ",final_response)
                if final_success:

                    in_cost, out_cost = self.cost_calculator(
                            final_response.usage_metadata["input_tokens"],  final_response.usage_metadata["output_tokens"], self.model_name or self.llm_handler.model_name
                        )
                    
                    total_cost= in_cost+ out_cost

                


                    meta["input_tokens"]  =  final_response.usage_metadata["input_tokens"]
                    meta["output_tokens"] =  final_response.usage_metadata["output_tokens"]
                    meta["total_tokens"]  =  final_response.usage_metadata["output_tokens"] + final_response.usage_metadata["input_tokens"]
                    
                    meta["input_cost"]= in_cost
                    meta["output_cost"]= out_cost
                    meta["total_cost"]= total_cost

                
                return InvokeResponseData(
                    success = final_success,
                    response = final_response,
                    attempts = attempts, 
                    usage= meta,
                    error_type=error_type
                )
        
        except Exception as final_exc:
            # All retries exhausted, Tenacity has re-raised the last exception.
            # You can turn it into a “failed” InvokeResponseData here:
            meta = self._init_meta()
            return InvokeResponseData(
                success=False,
                response=None,
                attempts=attempts,
                usage=meta,
                error_type= ErrorType.INSUFFICIENT_QUOTA
            )
                


    async def invoke_async(self, prompt: str) -> InvokeResponseData:
        """
        Asynchronous invoke with identical structure.
        """
        attempts: List[InvocationAttempt] = []
        final_response = None
        final_success  = False

        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((httpx.HTTPStatusError, RateLimitError)),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_random_exponential(min=1, max=60),
            reraise=True
        ):
            with attempt:
                n = attempt.retry_state.attempt_number
                start = _now_dt()
                try:
                    resp, success,  error_type = await self._invoke_async_impl(prompt)
                    final_response = resp
                    final_success  = success
                except Exception as e:
                    end = _now_dt()
                    backoff = timedelta(seconds=attempt.retry_state.next_action.sleep) \
                              if attempt.retry_state.next_action else None
                    attempts.append(InvocationAttempt(
                        attempt_number  = n,
                        invoke_start_at = start,
                        invoke_end_at   = end,
                        backoff_after_ms   = backoff,
                        error_message   = str(e)
                    ))
                    raise
                else:
                    end = _now_dt()
                    attempts.append(InvocationAttempt(
                        attempt_number  = n,
                        invoke_start_at = start,
                        invoke_end_at   = end,
                        backoff_after_ms   = None,
                        error_message   = None
                    ))
         
        meta=self._init_meta()


        if final_success:
            in_cost, out_cost = self.cost_calculator(
                    final_response.usage_metadata["input_tokens"],  final_response.usage_metadata["output_tokens"], self.model_name or self.llm_handler.model_name
                )
            
            total_cost= in_cost+ out_cost

         

            meta["input_tokens"]  =  final_response.usage_metadata["input_tokens"]
            meta["output_tokens"] =  final_response.usage_metadata["output_tokens"]
            meta["total_tokens"]  =  final_response.usage_metadata["output_tokens"] + final_response.usage_metadata["input_tokens"]
            
            meta["input_cost"]= in_cost
            meta["output_cost"]= out_cost
            meta["total_cost"]= total_cost

        
        return InvokeResponseData(
            success = final_success,
            response = final_response,
            attempts = attempts, 
            usage= meta, 
            error_type=error_type
        )
    

   

    
    
   
    


    def cost_calculator(self, input_token, output_token, model_name):
        """
        Calculate input/output costs based on the gpt_models_cost dict.

        :param input_token: number of input tokens (int or numeric str)
        :param output_token: number of output tokens (int or numeric str)
        :param model_name: model key in gpt_models_cost
        :return: (input_cost, output_cost)

          in_cost, out_cost = self.cost_calculator(
                meta["input_tokens"], meta["output_tokens"], model_name or self.llm_handler.model_name
            )
        """
        # Ensure the model exists
        info = gpt_models_cost.get(model_name)
        if info is None:
            self.logger.error(f"cost_calculator error: Unsupported model name: {model_name}")
            raise ValueError(f"cost_calculator error: Unsupported model name: {model_name}")
        
        # Parse token counts
        itoks = int(input_token)
        otoks = int(output_token)

        # Multiply by per-token rates
        inp_rate = info['input_token_cost']
        out_rate = info['output_token_cost']
        input_cost  = inp_rate  * itoks
        output_cost = out_rate * otoks

        return input_cost, output_cost
    
    
    

    def _retry_count_is_max(self, retry_state: RetryCallState) -> bool:
        """
        Helper function to check if the retry limit is reached.
        Compares the current attempt number with the max_retries set.
        """
        current_attempt = retry_state.attempt_number
        return current_attempt >= self.max_retries
    




def main():
   
    llm_handler=LLMHandler(model_name="gpt-4o-search-preview")
    # llm_handler=LLMHandler(model_name="gpt-4o-mini")
    sample_prompt= "web search yap ve bana bugun bursadaki hava durumunu ver"

    r=llm_handler.invoke(sample_prompt)

    print(r)



if __name__ == "__main__":
    main()
