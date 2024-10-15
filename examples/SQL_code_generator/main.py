# main.py

# to run use  python -m examples.SQL_code_generator.main

import asyncio

from examples.SQL_code_generator.llm_service import MyLLMService


def process_statements_sync():
    service = MyLLMService()

    my_db_desc= """ I have a database table with the following schema:
           Table: bills
           - bill_id (INT, Primary Key)
           - bill_date (DATE)
           - total (DECIMAL) """

    user_question= " retrieve the total spendings for each month in the year 2023, grouped by month and ordered chronologically."

    result = service.create_sql_code(user_question=user_question, database_desc=my_db_desc)
    if result.success:
        # print(f"Result : {result.content}")
        print( " ")
        print(f"Result: ")
        print(f"{result}")
    else:
        print(f"Error in statement : {result.error_message}")


if __name__ == "__main__":

    process_statements_sync()

    # For asynchronous processing
    #asyncio.run(process_statements_async(bank_statements))

    # For synchronous processing
    # process_statements_sync(bank_statements)
