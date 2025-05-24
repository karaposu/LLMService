# main.py

import asyncio
from examples.translater.myllmservice import MyLLMService

async def process_statements_async(statements):
    service = MyLLMService()
    tasks = []

    for idx, statement in enumerate(statements):
        # Schedule asynchronous translation
        task = service.translate_to_russian_async(input_paragraph=statement, request_id=idx)
        tasks.append(task)

    # Gather results
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, Exception):
            print(f"Error processing statement: {result}")
        else:
            print(f"Translated content: {result.content}")

def process_statements_sync(statements):
    service = MyLLMService()

    for idx, statement in enumerate(statements):
        result = service.translate_to_russian(input_paragraph=statement, request_id=idx)
        if result.success:
            print(f"Translated content for statement {idx}: {result.content}")
        else:
            print(f"Error in statement {idx}: {result.error_message}")


if __name__ == "__main__":
    bank_statements = ["Bank statement 1", "Bank statement 2", "Bank statement 3"]
    process_statements_sync(bank_statements)

    # For asynchronous processing
    #asyncio.run(process_statements_async(bank_statements))

    # For synchronous processing
    # process_statements_sync(bank_statements)
