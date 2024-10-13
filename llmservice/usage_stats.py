# usage_stats.py

from typing import Dict

class UsageStats:
    def __init__(self, model=None):
        self.model = model
        self.total_usage = {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0,
            'input_cost': 0.0,
            'output_cost': 0.0,
            'total_cost': 0.0
        }
        self.operation_usage: Dict[str, Dict[str, float]] = {}

    def update(self, meta, operation_name):
        # Update total usage
        self.total_usage['input_tokens'] += meta.get('input_tokens', 0)
        self.total_usage['output_tokens'] += meta.get('output_tokens', 0)
        self.total_usage['total_tokens'] += meta.get('total_tokens', 0)
        self.total_usage['input_cost'] += meta.get('input_cost', 0.0)
        self.total_usage['output_cost'] += meta.get('output_cost', 0.0)
        self.total_usage['total_cost'] += meta.get('total_cost', 0.0)
        self.total_usage['total_cost'] = round(self.total_usage['total_cost'], 5)

        # Update per-operation usage
        if operation_name not in self.operation_usage:
            self.operation_usage[operation_name] = {
                'input_tokens': 0,
                'output_tokens': 0,
                'total_tokens': 0,
                'input_cost': 0.0,
                'output_cost': 0.0,
                'total_cost': 0.0
            }

        op_usage = self.operation_usage[operation_name]
        op_usage['input_tokens'] += meta.get('input_tokens', 0)
        op_usage['output_tokens'] += meta.get('output_tokens', 0)
        op_usage['total_tokens'] += meta.get('total_tokens', 0)
        op_usage['input_cost'] += meta.get('input_cost', 0.0)
        op_usage['output_cost'] += meta.get('output_cost', 0.0)
        op_usage['total_cost'] += meta.get('total_cost', 0.0)
        op_usage['total_cost'] = round(op_usage['total_cost'], 5)

    def to_dict(self):
        return {
            'model': self.model,
            'total_usage': self.total_usage,
            'operation_usage': self.operation_usage
        }
