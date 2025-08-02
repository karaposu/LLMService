#!/usr/bin/env python3
"""Debug script to test string2dict with our JSON"""

from string2dict import String2Dict
import json

# Read the raw content
with open('raw_debug_txt.txt', 'r') as f:
    raw_content = f.read()

print("Raw content:")
print(repr(raw_content[:200]))
print()

# Try with String2Dict
s2d = String2Dict()
try:
    result = s2d.run(raw_content)
    print("String2Dict result:")
    print(f"Type: {type(result)}")
    print(f"Value: {result}")
except Exception as e:
    print(f"String2Dict error: {e}")
    import traceback
    traceback.print_exc()

print()

# Try with standard json.loads
try:
    json_result = json.loads(raw_content)
    print("json.loads result:")
    print(f"Type: {type(json_result)}")
    print(f"Value: {json_result}")
except Exception as e:
    print(f"json.loads error: {e}")

print()

# Try compact JSON (single line)
compact_json = json.dumps(json.loads(raw_content))
print("Trying compact JSON with String2Dict:")
print(f"Compact: {compact_json[:100]}...")
try:
    compact_result = s2d.run(compact_json)
    print(f"Compact result type: {type(compact_result)}")
    print(f"Compact result: {compact_result}")
except Exception as e:
    print(f"Compact String2Dict error: {e}")