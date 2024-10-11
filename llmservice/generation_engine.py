# here is generation_engine.py

import logging

from time import time
from langchain_core.prompts import PromptTemplate
from .llm_handler import  LLMHandler
from string2dict import String2Dict

from indented_logger import setup_logging, log_indent
from proteas import Proteas
from .postprocessor import Postprocessor, PostprocessingResult
from .schemas import GenerationRequest, GenerationResult


setup_logging( level=logging.DEBUG,include_func=True, truncate_messages=False,min_func_name_col=100)
logger = logging.getLogger(__name__)


gpt_models_input_cost = {'gpt-4o': 5 / 1000000,
                         "gpt-4o-2024-08-06": 2.5 / 1000000,
                         'gpt-4o-mini': 0.15 / 1000000,
                         'o1-preview': 15 / 1000000,
                         'o1-mini': 3 / 1000000}

gpt_models_output_cost = {'gpt-4o': 15 / 1000000,
                          "gpt-4o-2024-08-06":   10 / 1000000,
                          'gpt-4o-mini': 0.6 / 1000000,
                          'o1-preview': 60 / 1000000,
                          'o1-mini': 12 / 1000000}






# chat = ChatOpenAI(model="gpt-3.5-turbo-1106").bind(
#     response_format={"type": "json_object"}
# )
#
# output = chat.invoke(
#     [
#         SystemMessage(
#             content="Extract the 'name' and 'origin' of any companies mentioned in the following statement. Return a JSON list."
#         ),
#         HumanMessage(
#             content="Google was founded in the USA, while Deepmind was founded in the UK"
#         ),
#     ]
# )
# print(output.content)



class GenerationEngine:
    def __init__(self, llm_handler=None, model_name=None, logger=None, debug=False):
        self.logger = logger or logging.getLogger(__name__)
        self.debug = debug
        self.s2d = String2Dict()

        if llm_handler:
            self.llm_handler = llm_handler
        else:
            self.llm_handler = LLMHandler(model_name=model_name)

        self.proteas = Proteas()

        self.postprocessor = Postprocessor(logger=self.logger, debug=self.debug)

        if self.debug:
            pass

    def load_prompts(self, yaml_file_path):
        # yaml_file = 'prompts.yaml'
        self.proteas.load_unit_skeletons_from_yaml(yaml_file_path)

    def pick_model(self, name_of_model):
        self.llm_handler.model_name=name_of_model
        self.llm_handler.change_model( name_of_model)

    def class_logger(self):
        if self.debug:
            pass


    def craft_prompt(self, placeholder_dict, order):

        unformatted_prompt = self.proteas.craft(units=order,    placeholder_dict=placeholder_dict  )
        return unformatted_prompt


    def refine_output(self,  ):
        pass


    def answer_isolator_refiner(self, answer_to_be_refined , answer_isolater_refinement_config ):

        semantic_element_for_extraction  =answer_isolater_refinement_config["semantic_element_for_extraction"]

        order = ["answer_to_be_refined", "semantic_element_for_extraction", "answer_refiner"]
        data_for_placeholders = {"answer_to_be_refined": answer_to_be_refined,
                                 "semantic_element_for_extraction": semantic_element_for_extraction
                                 }

        unformatted_refiner_prompt = self.craft_prompt(data_for_placeholders, order)

        refiner_result = self.generate(
            unformatted_template=unformatted_refiner_prompt,
            data_for_placeholders=data_for_placeholders
        )

        if self.debug:
            self.logger.debug(f"refiner_result: {refiner_result.content}")


    def generate_output(self, generation_request: GenerationRequest) -> GenerationResult:
        # Unpack the GenerationRequest
        placeholders = generation_request.data_for_placeholders
        unformatted_prompt = generation_request.unformatted_prompt
        postprocess_config = generation_request.postprocess_config
        answer_isolator_refinement_config = generation_request.answer_isolator_refinement_config
        operation_name = generation_request.operation_name

        generation_result = self.generate(
            unformatted_template=unformatted_prompt,
            data_for_placeholders=placeholders
        )

        # Assign request_id and operation_name
        generation_result.request_id = generation_request.request_id
        generation_result.operation_name = generation_request.operation_name

        if generation_request.postprocess_config:
            postprocessing_result = self.postprocessor.postprocess( generation_result.content, generation_request.postprocess_config)
            generation_result.postprocessing_result = postprocessing_result
            if postprocessing_result.success:
                generation_result.content = postprocessing_result.result
            else:
                generation_result.success = False
                generation_result.error_message = postprocessing_result.error
        else:
            generation_result.postprocessing_result = None

        return generation_result

    def cost_calculator(self, input_token, output_token, model_name):
        if model_name not in gpt_models_input_cost or model_name not in gpt_models_output_cost:
            self.logger.error(f"Unsupported model name: {model_name}")
            raise ValueError(f"Unsupported model name: {model_name}")

        input_cost = gpt_models_input_cost[model_name] * int(input_token)
        output_cost = gpt_models_output_cost[model_name] * int(output_token)

        return input_cost, output_cost


    def generate(self, unformatted_template=None, data_for_placeholders=None, preprompts=None,  debug=False):

        if preprompts:
            unformatted_prompt = self.proteas.craft(
                units= preprompts,
                placeholder_dict=data_for_placeholders,
            )

        meta = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "elapsed_time_for_invoke": 0,
            "input_cost": 0,
            "output_cost": 0,
            "total_cost": 0,
        }

        t0 = time()
        #self.logger.debug( f"Starting generate method with template: {unformatted_template} and data: {data_for_placeholders}")

        from langchain_core.prompts.string import get_template_variables
        from langchain_core.prompts.string import check_valid_template


        # existing_placeholders = self.extract_placeholders(unformatted_template)
        existing_placeholders=get_template_variables(unformatted_template, "f-string")
        missing_placeholders = set(existing_placeholders) - set(data_for_placeholders.keys())

        if missing_placeholders:
            #self.logger.error(f"Missing data for placeholders: {missing_placeholders}")
            raise ValueError(f"Missing data for placeholders: {missing_placeholders}")

        filtered_data = {key: value for key, value in data_for_placeholders.items() if key in existing_placeholders}

        prompt = PromptTemplate.from_template(unformatted_template)
        formatted_prompt = prompt.format(**filtered_data)


        t1 = time()
        r, success = self.llm_handler.invoke(prompt=formatted_prompt)
        #self.logger.debug(f"LLM invoke response: {r}, success: {success}")

        if not success:

            return GenerationResult(success= success,
                                    meta= meta,
                                    content= None,
                                    elapsed_time= 0,
                                    error_message= "LLM invocation failed",
                                    model= self.llm_handler.model_name,
                                    formatted_prompt= formatted_prompt)


        t2 = time()
        elapsed_time_for_invoke = t2 - t1
        meta["elapsed_time_for_invoke"] = elapsed_time_for_invoke
        #self.logger.debug(f"Elapsed time for LLM invocation: {elapsed_time_for_invoke}")

        if self.llm_handler.OPENAI_MODEL:
            try:
                meta["input_tokens"] = r.usage_metadata["input_tokens"]
                meta["output_tokens"] = r.usage_metadata["output_tokens"]
                meta["total_tokens"] = r.usage_metadata["total_tokens"]
               # self.logger.debug(f"Token usage metadata: {r.usage_metadata}")
            except KeyError as e:
                #self.logger.error(f"Missing token metadata in response: {e}")
                return "error", formatted_prompt, meta, False

            input_cost, output_cost = self.cost_calculator(meta["input_tokens"], meta["output_tokens"],
                                                           self.llm_handler.model_name)
            meta["input_cost"] = input_cost
            meta["output_cost"] = output_cost
            meta["total_cost"] = input_cost + output_cost
          #  self.logger.debug( f"Calculated costs - Input: {input_cost}, Output: {output_cost}, Total: {meta['total_cost']}")

        # return r.content, formatted_prompt, meta, success
       # return GenerationResponse(content=r.content, formatted_prompt=formatted_prompt, meta=meta, success=success)

        return GenerationResult(success=success,
                                meta=meta,
                                content=r.content,
                                elapsed_time=0,
                                error_message=None,
                                model=self.llm_handler.model_name,
                                formatted_prompt=formatted_prompt)




    async def invoke_llm_async(self, formatted_prompt):
        """Asynchronously invokes the LLM with the formatted prompt."""
        t_start = time()
        response, success = await self.llm_handler.invoke_async(prompt=formatted_prompt)
        t_end = time()
        elapsed_time = t_end - t_start

        if not success:
            self.logger.error(f"LLM invocation failed with response: {response}")
            return None, success, elapsed_time

        return response, success, elapsed_time


def main():
    import logging

    # Set up basic logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('GenerationEngineExample')

    # Initialize the GenerationEngine with a specific model (e.g., 'gpt-4')
    gen_engine = GenerationEngine(logger=logger, model_name='gpt-4o')

    # Define the unformatted prompt directly
    unformatted_prompt = "Translate the following text to French:\n\n{text_to_translate}"

    # Data for placeholders
    data_for_placeholders = {
        'text_to_translate': "Hello, how are you?"
    }

    # Create a GenerationRequest
    generation_request = GenerationRequest(
        data_for_placeholders=data_for_placeholders,
        unformatted_prompt=unformatted_prompt,
        operation_name='translate_to_french',
        request_id='example_request_1'
    )

    # Generate the output
    generation_result = gen_engine.generate_output(generation_request)

    # Check if generation was successful
    if generation_result.success:
        print("Generated content:")
        print(generation_result.content)
    else:
        print("Generation failed:")
        print(f"Error: {generation_result.error_message}")

if __name__ == '__main__':
    main()
