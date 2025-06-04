# llmservice/bench_20_category_example.py
"""
Measure sync-vs-async RTT with the *same* big YAML snippet that the
categoriser passes to the model.  Each “transaction” triggers **two**
ChatCompletion calls (to mimic lvl-1 + lvl-2 categorisation).

Thread-pool  = synchronous .create() calls in a ThreadPoolExecutor(20)
Async gather = await ChatCompletion.acreate() with asyncio.gather()

Expected: async will again be slower **if** stream=True.
"""


# python -m llmservice.bench_20_category_example
import asyncio, time, pathlib, logging, sys, textwrap, concurrent.futures
from llmservice.base_service import BaseLLMService
from llmservice.schemas      import GenerationRequest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s %(message)s",
    stream=sys.stdout,
)

# ─────────────────────────────  test payload  ──────────────────────────────



CATEGORY_TEXT = """
# auto-categorization-trigger
categories:
  - Food & Dining:
      helpers:
        # Identifier
        keyword_identifier: ["xyz"]
        text_rules_for_llm: []
        description: ""
      subcategories:
        - Groceries:
            helpers:
              keyword_identifier: ["SOSEDI", "MJET", "m-jet"]
              text_rules_for_llm: []
              description: ""
            subcategories: []
        - Restaurants:
            helpers:
              keyword_identifier: ["WWW.PZZ.BY", "HOT DONER", "CHAYHONA"]
              text_rules_for_llm: []
              description: ""
            subcategories: []
        - Coffee:
            helpers:
              keyword_identifier: ["KOFEYNYA", "GRAY HOUSE"]
              text_rules_for_llm:
                - "If record contains words like coffea or KAFE, it must be categorized as Coffee."
              description: ""
            subcategories: []
        - Takeout:
            helpers:
              keyword_identifier: []
              text_rules_for_llm: []
              description: ""
            subcategories: []

  - Utilities:
      helpers:
        keyword_identifier: ["vvc"]
        text_rules_for_llm: []
        description: ""
      subcategories:
        - Electricity and Water and Gas:
            helpers:
              keyword_identifier: []
              text_rules_for_llm: []
              description: ""
            subcategories: []
        - Internet and Mobile:
            helpers:
              keyword_identifier: ["Türk Telekom Mobil"]
              text_rules_for_llm: []
              description: ""
            subcategories: []

  - Accommodation:
      helpers:
        keyword_identifier: []
        text_rules_for_llm: []
        description: ""
      subcategories:
        - Accommodation:
            helpers:
              keyword_identifier: []
              text_rules_for_llm: []
              description: ""
            subcategories: []

  - Incoming P2P Transfers:
      helpers:
        keyword_identifier: []
        text_rules_for_llm: []
        description: ""
      subcategories:
        - Incoming Money:
            helpers:
              keyword_identifier: []
              text_rules_for_llm: []
              description: ""
            subcategories: []

  - Outgoing P2P Transfers:
      helpers:
        keyword_identifier: []
        text_rules_for_llm: []
        description: ""
      subcategories:
        - Outgoing Money:
            helpers:
              keyword_identifier: []
              text_rules_for_llm:
                - "Must be towards a person, not to a company name."
              description: ""
            subcategories: []

  - Cash Withdrawal:
      helpers:
        keyword_identifier: []
        text_rules_for_llm: []
        description: ""
      subcategories:
        - Cash Withdrawal:
            helpers:
              keyword_identifier: []
              text_rules_for_llm: []
              description: ""
            subcategories: []

  - Cash Deposit:
      helpers:
        keyword_identifier: []
        text_rules_for_llm: []
        description: ""
      subcategories:
        - Cash Deposit:
            helpers:
              keyword_identifier: []
              text_rules_for_llm: []
              description: ""
            subcategories: []

  - Transportation:
      helpers:
        keyword_identifier: []
        text_rules_for_llm: []
        description: ""
      subcategories:
        - Fuel:
            helpers:
              keyword_identifier: []
              text_rules_for_llm: []
              description: ""
            subcategories: []
        - Taxi:
            helpers:
              keyword_identifier: ["YANDEX.GO"]
              text_rules_for_llm: []
              description: ""
            subcategories: []
        - Travel Tickets:
            helpers:
              keyword_identifier: ["HAVAIST"]
              text_rules_for_llm: []
              description: ""
            subcategories: []
        - Public Transportation:
            helpers:
              keyword_identifier: ["IGA", "ISPARK"]
              text_rules_for_llm: []
              description: ""
            subcategories: []
        - Vehicle Maintenance:
            helpers:
              keyword_identifier: []
              text_rules_for_llm: []
              description: ""
            subcategories: []
        - Car Payments:
            helpers:
              keyword_identifier: []
              text_rules_for_llm: []
              description: ""
            subcategories: []

  - Healthcare:
      helpers:
        keyword_identifier: []
        text_rules_for_llm: []
        description: ""
      subcategories:
        - Medical Bills:
            helpers:
              keyword_identifier: []
              text_rules_for_llm: []
              description: ""
            subcategories: []
        - Health Insurance:
            helpers:
              keyword_identifier: []
              text_rules_for_llm: []
              description: ""
            subcategories: []
        - Medications:
            helpers:
              keyword_identifier: ["ECZANE", "APTEKA"]
              text_rules_for_llm: []
              description: ""
            subcategories: []

  - Retail Purchases:
      helpers:
        keyword_identifier: []
        text_rules_for_llm: []
        description: ""
      subcategories:
        - Clothes:
            helpers:
              keyword_identifier: []
              text_rules_for_llm: []
              description: ""
            subcategories: []
        - Technology Items:
            helpers:
              keyword_identifier: []
              text_rules_for_llm:
                - "If bill is from APPLE and cost is less than $40, it should be classified as an online subscription."
                - "If bill is from Getir and cost is more than $50, it should be classified as retail purchases."
              description: ""
            subcategories: []
        - Other:
            helpers:
              keyword_identifier: []
              text_rules_for_llm: []
              description: ""
            subcategories: []

  - Personal Care:
      helpers:
        keyword_identifier: []
        text_rules_for_llm: []
        description: ""
      subcategories:
        - Personal Grooming:
            helpers:
              keyword_identifier: []
              text_rules_for_llm: []
              description: ""
            subcategories: []
        - Fitness:
            helpers:
              keyword_identifier: []
              text_rules_for_llm: []
              description: ""
            subcategories: []

  - Leisure and Activities in Real Life:
      helpers:
        keyword_identifier: []
        text_rules_for_llm: []
        description: ""
      subcategories:
        - Movies:
            helpers:
              keyword_identifier: []
              text_rules_for_llm: []
              description: ""
            subcategories: []
        - Concerts:
            helpers:
              keyword_identifier: []
              text_rules_for_llm: []
              description: ""
            subcategories: []

  - Online Subscriptions & Services:
      helpers:
        keyword_identifier: []
        text_rules_for_llm: []
        description: ""
      subcategories:
        - Streaming & Digital Subscriptions:
            helpers:
              keyword_identifier: ["NETFLIX", "HULU", "AMAZON PRIME", "youtube+", "SPOTIFY", "APPLE MUSIC", "GOOGLE PLAY"]
              text_rules_for_llm: []
              description: ""
            subcategories: []
        - Cloud Server Payments:
            helpers:
              keyword_identifier: ["AWS", "AMAZON WEB SERVICES", "GOOGLE CLOUD", "GCP", "GOOGLE CLOUD PLATFORM", "DIGITALOCEAN"]
              text_rules_for_llm: []
              description: ""
            subcategories: []
"""



TRANSACTIONS  = [f"TX-{i:02d} dummy text" for i in range(20)]   # 20 “records”



def craft_prompt(tx: str) -> str:
    """Exact style the categoriser uses: YAML blob + helpers + tx text."""
    return textwrap.dedent(
        f"""
        ### Category schema
        
        {CATEGORY_TEXT}
       
        ### Task
        Decide which lvl-1 / lvl-2 category best fits **this transaction**:
            {tx}

        Respond with JSON {{ "lvl1": "...", "lvl2": "..." }} only.
        """
    ).strip()


# ───────────────────────────── concrete service ────────────────────────────
class CatBenchService(BaseLLMService):
    """Just adds the two-call wrapper used in RecordManager."""

    # ---------- one “record”, sync ----------
    def two_lvl_sync(self, tx: str):
        p = craft_prompt(tx)
        # lvl-1
        req = GenerationRequest(formatted_prompt=p, model="gpt-4o-mini")
        _   = self.execute_generation(req)
        # lvl-2 (in real code prompt is refined – not needed for timing)
        _   = self.execute_generation(req)

    # ---------- one “record”, async ----------
    async def two_lvl_async(self, tx: str):
        p = craft_prompt(tx)
        req = GenerationRequest(formatted_prompt=p, model="gpt-4o-mini")
        await self.execute_generation_async(req)  # lvl-1
        await self.execute_generation_async(req)  # lvl-2


# ───────────────────────────── benchmarks ──────────────────────────────────
def bench_thread_pool(svc: CatBenchService) -> float:
    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(TRANSACTIONS)) as tp:
        list(tp.map(svc.two_lvl_sync, TRANSACTIONS))
    return time.perf_counter() - t0


async def bench_asyncio_gather(svc: CatBenchService) -> float:
    t0 = time.perf_counter()
    await asyncio.gather(*(svc.two_lvl_async(tx) for tx in TRANSACTIONS))
    return time.perf_counter() - t0


# ─────────────────────────────── main  ─────────────────────────────────────
if __name__ == "__main__":
    svc = CatBenchService(show_logs=False)  # reuse *one* LLM client/session

    # -------- thread-pool (sync) ----------
    dt_sync = bench_thread_pool(svc)

    # -------- async gather  ----------
    dt_async = asyncio.run(bench_asyncio_gather(svc))

    print()
    print(f"Thread-pool   (20×2 calls) Δ = {dt_sync:5.2f} s")
    print(f"Async gather  (20×2 calls) Δ = {dt_async:5.2f} s")
