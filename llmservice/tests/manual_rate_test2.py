# llmservice/manual_rate_test.py

# to run python -m llmservice.manual_rate_test2

import asyncio
import time
from llmservice.base_service import BaseLLMService
from llmservice.schemas import GenerationRequest

class TestService(BaseLLMService):
    def __init__(self):
        # Use a valid model name from your configuration
        # super().__init__(default_model_name="gpt-4o-mini")
        super().__init__(
            default_model_name="gpt-4o-mini",
            max_concurrent_requests=100,   # allow 100 in flight
            max_rpm=7,                   # raise RPM cap to 120/min
            rpm_window_seconds=60
        )

    def say_hi(self):
        """
        Send a single "Say hi." prompt to the LLM and return the response.
        """
        prompt = "Say hi."
        request = GenerationRequest(
            formatted_prompt=prompt,
            model=self.generation_engine.llm_handler.model_name,
            operation_name="say_hi"
        )
        result = self.execute_generation(request)
        return result

    # def show_rates(self, label=""):
    #     """
    #     Print current RPM and TPM with an optional label.
    #     """
    #     rpm = self.get_current_rpm()
    #     tpm = self.get_current_tpm()
    #     ts = time.strftime("%H:%M:%S", time.localtime())
    #     print(f"[{ts}] {label} RPM: {rpm:.2f}, TPM: {tpm:.2f}")

    def mass_say_hi(self, n=10):
        """
        Send the "Say hi." prompt n times synchronously, showing rates after each call.
        """
        for i in range(1, n+1):
            resp = self.say_hi()

            # resp.  
            print(f"Resp {i}:  req_at: {resp.timestamps.generation_requested_at},  enq_at: {resp.timestamps.generation_enqueued_at} , deq_at: {resp.timestamps.generation_dequeued_at}   rpm b4/after/waited: {resp.rpm_at_the_beginning} / {resp.rpm_at_the_end}/ {resp.rpm_waited},  tpm waited: {resp.tpm_waited} ,  total_backoff: {resp.total_backoff_ms}, retried: {resp.retried}"  )
            # self.show_rates(label=f"After sync call {i}")

    async def mass_say_hi_async(self, n=10):
        """
        Send the "Say hi." prompt n times asynchronously, showing rates as tasks complete.
        """
        tasks = []
        for _ in range(n):
            req = GenerationRequest(
                formatted_prompt="what is meaning of life, give me long answer",
                model=self.generation_engine.llm_handler.model_name,
                operation_name="say_hi_async"
            )
            tasks.append(self.execute_generation_async(req))

        for idx, coro in enumerate(asyncio.as_completed(tasks), start=1):
            resp = await coro
            # print(f"Async response {idx}: {res.content}")
           # print(f"Async response {idx}: {res.content}")
            print(f"Resp {idx}:  req_at: {resp.timestamps.generation_requested_at},  enq_at: {resp.timestamps.generation_enqueued_at} , deq_at: {resp.timestamps.generation_dequeued_at}   rpm b4/after/waited: {resp.rpm_at_the_beginning} / {resp.rpm_at_the_end}/ {resp.rpm_waited},  tpm waited: {resp.tpm_waited} ,  total_backoff: {resp.total_backoff_ms}, retried: {resp.retried}"  )
           # print(f"Response {idx}: Success: {resp.success}    retried: {resp.retried} rpm b4: {resp.rpm_at_the_beginning}  rpm after: {resp.rpm_at_the_end} rpm waited:  {resp.rpm_waited} tpm waited: {resp.tpm_waited}   total_backoff_ms: {resp.total_backoff_ms}"  )
           # self.show_rates(label=f"After async call {idx}")

if __name__ == "__main__":
    svc = TestService()

    # Single synchronous call

    # svc.say_hi()
   # print("Single say_hi:", svc.say_hi())
   # svc.show_rates(label="After single call")

    # Mass synchronous calls
    print("\nMass sync responses:")
    svc.mass_say_hi(5)

    # Mass asynchronous calls
    print("\nMass async responses:")
    asyncio.run(svc.mass_say_hi_async(14))