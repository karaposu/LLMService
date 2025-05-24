pipeline_config = [
            {
                'type': 'SemanticIsolation',   # uses LLMs to isolate specific part of the answer.
                'params': {
                    'semantic_element_for_extraction': 'SQL code'
                }
            }
        ]
            # {
            #     'type': 'ConvertToDict',  # uses string2dict package to convert output to a dict. Handles edge cases.
            #     'params': {}
            # },
            # {
            #     'type': 'ExtractValue',       # if you asked for json output and you want to extract the data from the result dict
            #     'params': {'key': 'answer'}
            # }
            # {
            #     'type': 'StringMatchValidation', # not implemented yet. But it can be useful for various scenarios.
            #     'params': {'expected_string': 'answer'}
            # }
            # {
            #     'type': 'JsonLoad',      # classic plain jsonload. We suggest ConvertToDict pipeline instead.
            #     'params': {}
            # }