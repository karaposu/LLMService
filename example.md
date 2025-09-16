# Using Structured Outputs with LLMService

This guide demonstrates how to use the new Structured Outputs feature with the Responses API.

## Quick Start

### 1. Simple Extraction with Built-in Schemas

```python
from llmservice.generation_engine import GenerationEngine
from llmservice.structured_schemas import SemanticIsolation, EntitiesList

# Initialize engine
engine = GenerationEngine(model_name="gpt-4o-mini")

# Extract specific semantic element
text = "The patient John Doe, age 45, has diabetes and hypertension. He takes metformin daily."
result = engine.semantic_isolation_v2(
    content=text,
    element="medications"
)
print(result)  # Output: "metformin"

# Extract entities
entities = engine.extract_entities(text)
for entity in entities:
    print(f"{entity['name']} ({entity['type']})")
# Output:
# John Doe (Person)
# diabetes (Condition)
# hypertension (Condition)
# metformin (Medication)
```

### 2. Custom Schema Definition

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from llmservice.generation_engine import GenerationEngine

# Define your custom schema
class ProductReview(BaseModel):
    product_name: str = Field(description="Name of the product")
    rating: float = Field(ge=1, le=5, description="Rating from 1 to 5")
    pros: List[str] = Field(description="Positive aspects")
    cons: List[str] = Field(description="Negative aspects")
    recommendation: bool = Field(description="Whether reviewer recommends")

# Initialize engine
engine = GenerationEngine(model_name="gpt-4o-mini")

# Process unstructured text
review_text = """
The new MacBook Pro M3 is incredible! The performance is blazing fast,
battery lasts all day. However, it's very expensive at $3500 and the 
keyboard could be better. Overall I'd give it 4.5 stars and recommend it
for professionals who need the power.
"""

# Generate structured output
review = engine.generate_structured(
    prompt=review_text,
    schema=ProductReview,
    system="Extract review information from the text"
)

# Access data with type safety
print(f"Product: {review.product_name}")
print(f"Rating: {review.rating}/5")
print(f"Pros: {', '.join(review.pros)}")
print(f"Cons: {', '.join(review.cons)}")
print(f"Recommended: {review.recommendation}")
```

### 3. Using with GenerationRequest

```python
from llmservice.generation_engine import GenerationEngine
from llmservice.schemas import GenerationRequest
from pydantic import BaseModel, Field
from typing import List

# Define schema for medical extraction
class MedicalRecord(BaseModel):
    patient_name: str = Field(description="Patient's full name")
    age: int = Field(ge=0, le=150, description="Patient age")
    conditions: List[str] = Field(description="Medical conditions")
    medications: List[str] = Field(description="Current medications")
    allergies: List[str] = Field(default_factory=list, description="Known allergies")

# Create generation request with schema
engine = GenerationEngine(model_name="gpt-4o-mini")

request = GenerationRequest(
    user_prompt="John Smith, 52 years old, has type 2 diabetes and high blood pressure. He takes metformin and lisinopril. Allergic to penicillin.",
    system_prompt="Extract medical information",
    response_schema=MedicalRecord,  # Pass the schema here
    reasoning_effort="low",  # Low reasoning for better format compliance
    model="gpt-4o-mini"
)

# Generate with structured output
result = engine.generate_output(request)

if result.success:
    # Parse the JSON response to Pydantic model
    import json
    data = json.loads(result.content)
    record = MedicalRecord(**data)
    
    print(f"Patient: {record.patient_name}, Age: {record.age}")
    print(f"Conditions: {', '.join(record.conditions)}")
    print(f"Medications: {', '.join(record.medications)}")
    print(f"Allergies: {', '.join(record.allergies)}")
```

### 4. Complex Nested Structures

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# Define nested schemas
class Address(BaseModel):
    street: str
    city: str
    state: str
    zip_code: str

class ContactInfo(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[Address] = None

class Employee(BaseModel):
    name: str
    employee_id: str
    department: str
    role: str
    contact: ContactInfo
    skills: List[str]
    years_experience: int

# Process employee information
engine = GenerationEngine(model_name="gpt-4o-mini")

text = """
Jane Doe (ID: EMP001) works as a Senior Software Engineer in the Engineering
department. She has 8 years of experience and is skilled in Python, JavaScript,
and cloud architecture. You can reach her at jane.doe@company.com or 
555-0123. She works from our San Francisco office at 123 Market St, SF, CA 94105.
"""

employee = engine.generate_structured(
    prompt=text,
    schema=Employee,
    system="Extract employee information"
)

print(f"Name: {employee.name}")
print(f"Role: {employee.role} in {employee.department}")
print(f"Email: {employee.contact.email}")
print(f"Office: {employee.contact.address.city}, {employee.contact.address.state}")
```

### 5. Chain of Thought with Structured Output

```python
from llmservice.structured_schemas import ChainOfThought

engine = GenerationEngine(model_name="gpt-4o-mini")

# Complex problem requiring step-by-step reasoning
problem = """
A store offers a 20% discount on all items. If you buy 3 shirts at $25 each
and 2 pants at $40 each, and there's an additional 10% off for purchases over
$100 after the initial discount, what's the final price?
"""

solution = engine.process_with_schema(
    content=problem,
    schema=ChainOfThought,
    instructions="Solve this step by step"
)

# Access structured reasoning steps
for i, step in enumerate(solution.steps, 1):
    print(f"Step {i}: {step.explanation}")
    print(f"         Result: {step.output}")

print(f"\nFinal Answer: {solution.final_answer}")
```

### 6. With GPT-5 Models

```python
# GPT-5 models benefit from structured outputs for format compliance
engine = GenerationEngine(model_name="gpt-5-mini")

class AnalysisResult(BaseModel):
    summary: str = Field(description="Brief summary")
    key_points: List[str] = Field(description="Main points")
    sentiment: str = Field(description="Overall sentiment")
    confidence: float = Field(ge=0, le=1, description="Confidence score")

# Use low reasoning_effort for better format compliance with GPT-5
result = engine.generate_structured(
    prompt="Analyze the impact of AI on healthcare in 2024",
    schema=AnalysisResult,
    reasoning_effort="low",  # Important for GPT-5 format compliance
    model="gpt-5-mini"
)

print(f"Summary: {result.summary}")
print(f"Sentiment: {result.sentiment} (confidence: {result.confidence:.2%})")
```

## Key Benefits

1. **No Parsing Errors**: Guaranteed valid JSON matching your schema
2. **Type Safety**: IDE autocomplete and type checking with Pydantic models
3. **Validation**: Automatic validation of data types and constraints
4. **GPT-5 Compatible**: Works reliably even with high reasoning models
5. **Clean Code**: No need for complex parsing pipelines

## Best Practices

### 1. Schema Design
- Keep schemas simple and focused
- Use clear, descriptive field names
- Provide good field descriptions
- Use Optional for fields that might be missing

### 2. Model Selection
- Use `gpt-4o-mini` for most structured extraction tasks
- Use `gpt-5-mini` with `reasoning_effort="low"` for format compliance
- Avoid setting `verbosity` to "low" with gpt-4o-mini (not supported)

### 3. Error Handling
```python
try:
    result = engine.generate_structured(
        prompt=text,
        schema=MySchema
    )
    # Use result
except ValueError as e:
    print(f"Generation failed: {e}")
    # Handle error
```

### 4. Performance Tips
- Reuse schema classes across multiple calls
- Keep prompts concise and clear
- Use system prompts to guide extraction
- Set `reasoning_effort="low"` for simple extraction tasks

## Migration from Old Pipelines

### Before (with pipelines and String2Dict):
```python
result = engine.generate_output(GenerationRequest(
    user_prompt="Extract symptoms from: Patient has headache and fever",
    pipeline_config=[
        {'type': 'SemanticIsolation', 
         'params': {'semantic_element_for_extraction': 'symptoms'}},
        {'type': 'ConvertToDict'},
        {'type': 'ExtractValue', 'params': {'key': 'answer'}}
    ]
))
# Often failed with parsing errors
```

### After (with Structured Outputs):
```python
from llmservice.structured_schemas import SemanticIsolation

result = engine.process_with_schema(
    content="Patient has headache and fever",
    schema=SemanticIsolation,
    instructions="Extract symptoms"
)
print(result.answer)  # Guaranteed to work!
```

## Available Built-in Schemas

- `SemanticIsolation`: Extract specific semantic elements
- `EntitiesList`: Extract named entities
- `ChainOfThought`: Step-by-step reasoning
- `Summary`: Document summarization
- `SentimentAnalysis`: Sentiment scoring
- `Classification`: Document classification
- `QAPair`: Question-answer pairs
- `Translation`: Language translation
- `PatientInfo`: Medical information extraction
- `CodeSolution`: Code generation with explanation

See `llmservice/structured_schemas/structured_outputs.py` for all available schemas.

## Troubleshooting

### Issue: "Invalid schema" errors
- Ensure all fields are properly typed
- Check that Optional fields have defaults
- Verify enum values are valid

### Issue: "Unsupported value" errors
- Don't use `verbosity="low"` with gpt-4o-mini
- Check model-specific parameter support

### Issue: Response type showing as "text"
- Ensure you're passing `response_schema` parameter
- Check that schema is a valid Pydantic BaseModel

## Complete Example Script

```python
#!/usr/bin/env python3
"""
Complete example of using Structured Outputs with LLMService
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from llmservice.generation_engine import GenerationEngine

# Define your data model
class CustomerFeedback(BaseModel):
    customer_name: Optional[str] = Field(default=None, description="Customer name if mentioned")
    product: str = Field(description="Product being reviewed")
    rating: float = Field(ge=1, le=5, description="Rating score")
    issues: List[str] = Field(default_factory=list, description="Problems mentioned")
    positives: List[str] = Field(default_factory=list, description="Positive aspects")
    needs_followup: bool = Field(description="Whether this needs customer service followup")

def analyze_feedback(text: str) -> CustomerFeedback:
    """Analyze customer feedback and return structured data."""
    engine = GenerationEngine(model_name="gpt-4o-mini")
    
    return engine.generate_structured(
        prompt=text,
        schema=CustomerFeedback,
        system="Analyze this customer feedback and extract key information"
    )

# Example usage
if __name__ == "__main__":
    feedback_text = """
    Hi, this is Sarah Johnson. I bought your Premium Coffee Maker last week.
    The coffee quality is excellent and I love the programmable timer! 
    However, the water reservoir leaks sometimes and the instruction manual
    was confusing. I'd rate it 3.5 stars. Can someone help with the leak issue?
    """
    
    result = analyze_feedback(feedback_text)
    
    print(f"Customer: {result.customer_name or 'Not specified'}")
    print(f"Product: {result.product}")
    print(f"Rating: {result.rating}/5")
    print(f"Issues: {', '.join(result.issues)}")
    print(f"Positives: {', '.join(result.positives)}")
    print(f"Needs followup: {'Yes' if result.needs_followup else 'No'}")
    
    # Output:
    # Customer: Sarah Johnson
    # Product: Premium Coffee Maker
    # Rating: 3.5/5
    # Issues: water reservoir leaks, instruction manual confusing
    # Positives: excellent coffee quality, programmable timer
    # Needs followup: Yes
```

This is the new, clean way to get structured data from LLMs - no more parsing errors!