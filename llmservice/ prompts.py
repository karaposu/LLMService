# prompts.py
"""
Simple prompts using regular strings with format placeholders.
Just use {variable} syntax and call .format() when using them.
"""

# ================================================================
# SYSTEM PROMPTS
# ================================================================

SYSTEM_INTENT_UNDERSTANDING = """You are an AI assistant specialized in understanding user requirements and breaking down tasks.
Your job is to analyze the given task and extract all relevant information needed for planning."""

SYSTEM_PLANNING = """You are a strategic planning AI that excels at generating creative solutions.
Your role is to think of multiple different approaches to solve problems, considering various trade-offs."""

SYSTEM_DECISION_MAKING = """You are a decision-making AI that excels at evaluating options and creating detailed plans.
Your role is to select the optimal approach and define clear expectations for execution."""

SYSTEM_IMPLEMENTATION = """You are a technical implementation expert who translates plans into executable actions.
Your role is to create precise, step-by-step instructions that can be directly executed."""

SYSTEM_EVALUATION = """You are a quality assurance expert who evaluates execution results against plans.
Your role is to determine if objectives were met and identify any gaps or failures."""

SYSTEM_ADAPTIVE = """You are an adaptive planning AI that learns from failures and creates improved plans.
Your role is to analyze what went wrong and create a better approach."""

# ================================================================
# AGENT PROMPTS
# ================================================================

UNDERSTAND_INTENT = """Analyze the following task and extract:
1. The main objective (what the user wants to achieve)
2. Any constraints or requirements (technical, time, format)
3. Expected output format (what form should the result take)
4. Success criteria (how do we know when the task is complete)
5. Potential challenges or ambiguities

Task: {task}

{context_section}

Available tools that might be used:
{available_tools}

Provide your analysis in the following JSON format:
{{
    "main_objective": "clear description of what needs to be done",
    "constraints": ["list", "of", "constraints"],
    "expected_output": "description of the expected result format",
    "success_criteria": ["measurable", "success", "indicators"],
    "challenges": ["potential", "difficulties"],
    "requires_clarification": ["ambiguous", "aspects", "if any"]
}}"""

VAGUE_PLANNING = """Based on this task analysis:
{intent_understanding}

Available tools:
{available_tools}

Generate 2-3 DIFFERENT high-level approaches to accomplish this task. 
Each approach should use a different strategy or tool combination.

For each approach, provide:
1. Strategy name (creative, descriptive name)
2. High-level description (2-3 sentences)
3. Tools to be used (which tools and in what order)
4. Pros (advantages of this approach)
5. Cons (disadvantages or risks)
6. Estimated complexity (simple/moderate/complex)
7. Estimated time (fast/medium/slow)

Think creatively - consider:
- Direct vs indirect approaches
- Single tool vs multi-tool solutions
- Automated vs semi-manual approaches
- Quick & dirty vs thorough & precise

Return as JSON array:
[
    {{
        "strategy_name": "The Quick Scanner",
        "description": "Rapidly scan using tool X then summarize",
        "tools_sequence": ["tool_x", "tool_y"],
        "pros": ["fast", "simple"],
        "cons": ["might miss details"],
        "complexity": "simple",
        "estimated_time": "fast"
    }},
    // ... more approaches
]"""

DETERMINISTIC_PLANNING = """Review these solution approaches:
{vague_plans}

Original task requirements:
{intent_understanding}

{selection_criteria_section}

Your job:
1. Select the BEST approach based on the requirements
2. Provide detailed reasoning for your selection
3. Define specific expected outputs at each stage
4. Identify success metrics and potential failure points

Return in JSON format:
{{
    "selected_approach_name": "name of chosen strategy",
    "selection_reasoning": {{
        "why_best": "detailed explanation",
        "trade_offs_accepted": ["list of accepted downsides"],
        "alternatives_rejected": {{
            "approach_name": "why rejected"
        }}
    }},
    "execution_plan": {{
        "phases": [
            {{
                "phase_name": "Data Collection",
                "description": "what happens in this phase",
                "expected_output": "specific description of output",
                "success_indicators": ["measureable", "indicators"],
                "potential_failures": ["what could go wrong"]
            }}
        ],
        "overall_success_metrics": ["final success criteria"],
        "fallback_strategy": "what to do if primary approach fails"
    }},
    "risk_assessment": {{
        "high_risk_points": ["critical failure points"],
        "mitigation_strategies": ["how to handle risks"]
    }}
}}"""

ACTION_PLANNING = """Convert this plan into executable steps:
{selected_plan}

Available tools with their parameters:
{available_tools}

Create a detailed action plan where each step is directly executable.
Include exact parameters, dependencies, and expected outputs.

Rules:
- Each step must use either a specific tool or be an LLM prompt
- Include all necessary parameters with example values
- Specify dependencies between steps clearly
- Be very specific about expected output format

Return as JSON array:
[
    {{
        "step_number": 1,
        "action_type": "tool",  // or "llm"
        "tool": "web_search",   // tool name or "llm" for LLM calls
        "parameters": {{
            "query": "specific search query",
            "num_results": 5
        }},
        "depends_on": [],       // step numbers this depends on
        "expected_output": {{
            "type": "list",
            "description": "list of search results with title, url, snippet",
            "example": [{{"title": "...", "url": "...", "snippet": "..."}}]
        }},
        "purpose": "why this step is needed"
    }},
    {{
        "step_number": 2,
        "action_type": "llm",
        "tool": "llm",
        "parameters": {{
            "prompt": "Analyze these search results and extract key information: {{step_1_results}}"
        }},
        "depends_on": [1],
        "expected_output": {{
            "type": "structured_text",
            "description": "summary of key findings"
        }},
        "purpose": "extract insights from search results"
    }}
    // ... more steps
]"""

EVALUATE_RESULTS = """Evaluate these execution results against the original plan:

Original Intent:
{original_intent}

Planned Execution:
{selected_plan}

Actual Results:
{execution_results}

Analyze:
1. Did each step produce the expected outputs?
2. Were the overall success criteria met?
3. What worked well?
4. What failed or fell short?
5. Is the task complete or does it need retry?

Return in JSON format:
{{
    "overall_success": true/false,
    "success_percentage": 0-100,
    "step_evaluations": [
        {{
            "step": 1,
            "success": true/false,
            "expected_vs_actual": "comparison description",
            "issues": ["list of problems if any"]
        }}
    ],
    "criteria_evaluation": {{
        "criterion": "met/not met/partially met"
    }},
    "strengths": ["what worked well"],
    "failures": [
        {{
            "description": "what failed",
            "severity": "critical/major/minor",
            "root_cause": "why it failed",
            "fixable": true/false,
            "fix_suggestion": "how to fix it"
        }}
    ],
    "recommendation": "complete/retry/abort",
    "retry_guidance": {{
        "focus_areas": ["what to focus on in retry"],
        "skip_steps": [1, 2],  // steps that succeeded and can be skipped
        "modify_approach": "how to adjust the approach"
    }}
}}"""

RETRY_PLANNING = """Learn from this failure and create an improved plan:

Failure Analysis:
{failure_analysis}

Previous Attempts:
{previous_attempts}

Available Tools:
{available_tools}

Create an updated action plan that:
1. Addresses the specific failures identified
2. Leverages successful steps from previous attempts
3. Uses different approaches for failed steps
4. Includes additional validation/verification steps

Important:
- Don't repeat the same mistakes
- Be more specific with parameters if previous ones were too vague
- Add error handling for critical steps
- Consider using different tools if previous ones weren't suitable

Return the same action plan format as before, but with improvements based on lessons learned."""

# ================================================================
# UTILITY PROMPTS
# ================================================================

SUMMARIZE = """Summarize the following content in {max_length} words or less.
Style: {style_instruction}

Content:
{content}

Summary:"""

EXTRACT_INFO = """Extract the following information from the content:
{info_types_list}

Content:
{content}

Return the extracted information in {output_format} format.
If any information is not found, indicate it as null or "not found"."""

CLASSIFY = """Classify the following content into {classification_instruction} of these categories:
{categories}

Content:
{content}

Return in JSON format:
{{
    "classification": {classification_format},
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}"""