# from usage_stats import UsageStats

class UsageStats:
    def __init__(self, model=None):
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.input_cost = 0.0
        self.output_cost = 0.0
        self.total_cost = 0.0
        self.model = model


    def update(self, meta):
        self.input_tokens += meta.get("input_tokens", 0)
        self.output_tokens += meta.get("output_tokens", 0)
        self.total_tokens += meta.get("total_tokens", 0)
        self.input_cost += meta.get("input_cost", 0.0)
        self.output_cost += meta.get("output_cost", 0.0)
        self.total_cost += meta.get("total_cost", 0.0)
        self.total_cost = round(self.total_cost, 5)

    def to_dict(self):
        return self.__dict__

