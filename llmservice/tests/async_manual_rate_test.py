# llmservice/manual_rate_test.py

# to run python -m llmservice.manual_rate_test



import asyncio
import time
from llmservice.base_service import BaseLLMService
from llmservice.schemas import GenerationRequest

from llmservice.live_metrics   import attach_file_handler   # ← 

class TestService(BaseLLMService):
    def __init__(self):
        # Use a valid model name from your configuration
        # super().__init__(default_model_name="gpt-4o-mini")
        super().__init__(
            default_model_name="gpt-4o-mini",
            max_concurrent_requests=100,   # allow 100 in flight
            max_rpm=120,                   # raise RPM cap to 120/min
            rpm_window_seconds=60,
            enable_metrics_logging=True
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
        return result.content

    def show_rates(self, label: str = "") -> None:
        rpm   = self.get_current_rpm()
        repm  = self.get_current_repmin()
        tpm   = self.get_current_tpm()
        cost  = self.get_total_cost()
        now   = time.strftime("%H:%M:%S", time.localtime())
        print(f"[{now}] {label} "
              f"RPM:{rpm:.2f} RePM:{repm:.2f} TPM:{tpm:.2f}  Cost:${cost:.6f}")

    def mass_say_hi(self, n=10):
        """
        Send the "Say hi." prompt n times synchronously, showing rates after each call.
        """
        for i in range(1, n+1):
            resp = self.say_hi()
            #print(f"Response {i}: {resp}")
            print(f"Response {i} received")
            self.show_rates(label=f"After sync call {i}")

    # async def mass_say_hi_async(self, n=10):
    #     """
    #     Send the "Say hi." prompt n times asynchronously, showing rates as tasks complete.
    #     """
    #     tasks = []
    #     for _ in range(n):
    #         req = GenerationRequest(
    #             formatted_prompt="what is meaning of life, give me long answer",
    #             # model=self.generation_engine.llm_handler.model_name,
    #             operation_name="say_hi_async"
    #         )
    #         tasks.append(self.execute_generation_async(req))

    #     for idx, coro in enumerate(asyncio.as_completed(tasks), 1):
    #         try:
    #             res = await coro
    #             status = "OK" if res.success else "ERR"
    #         except Exception as e:
    #             status, res = f"EXC {e}", None
    #         print(f"Async response {idx}: {status}")
     
    async def mass_say_hi_async(self, n=10):
        tasks = []
        for i in range(n):
            req = GenerationRequest(
                formatted_prompt="What is the meaning of life? Give a long answer.",
                model=self.generation_engine.llm_handler.model_name,
                operation_name="say_hi_async",
                request_id=f"async-{i+1}"               # ← tag
            )
            tasks.append(self.execute_generation_async(req))

        for coro in asyncio.as_completed(tasks):
            try:
                res = await coro
                # print(f"[OK ] {res.request_id} success={res.success}")
                print(f"[OK] {res.request_id} success={res.success} "
                        f"in_tok={res.meta.get('input_tokens')} "
                        f"out_tok={res.meta.get('output_tokens')} "
                        f"total_tok={res.meta.get('total_tokens')}")
            except Exception as e:
                print(f"[EXC] {e}")


       
        # for idx, coro in enumerate(asyncio.as_completed(tasks), start=1):
        #     res = await coro
        #     #print(f"Async response {idx}: {res.content}")
        #     print(f"Async response received {idx}")
        #     self.show_rates(label=f"After async call {idx}")


async def main():
    svc = TestService()                         # loop is running now
    # svc.setup_metrics_log_file("llm_metrics.log")

    attach_file_handler(svc.metrics, path="llm_metrics.log") 

    print("Single say_hi:", svc.say_hi())
    svc.show_rates(label="After single call")

    print("\nMass sync responses:")
    svc.mass_say_hi(5)

    print("\nMass async responses:")
    await svc.mass_say_hi_async(10)

    print("sent :", list(svc.metrics.sent_ids))
    print("rcved:", list(svc.metrics.rcv_ids))
    print("diff :", set(svc.metrics.sent_ids) - set(svc.metrics.rcv_ids))
    await asyncio.sleep(0.2)


if __name__ == "__main__":
    asyncio.run(main())


