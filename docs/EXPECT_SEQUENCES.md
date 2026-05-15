# Expect Sequences Guide

## Overview

**Expect Sequences** provide a powerful mechanism to define, validate, and monitor expected agent outputs. This feature enables:
- **Output Validation** - Verify agents produce expected results
- **Testing** - Automated testing of agent behavior
- **Monitoring** - Runtime validation of agent outputs
- **Debugging** - Identify when agents deviate from expectations
- **Documentation** - Self-documenting expected behavior

## Table of Contents

1. [Basic Concepts](#basic-concepts)
2. [Defining Expect Sequences](#defining-expect-sequences)
3. [Validation Modes](#validation-modes)
4. [Pattern Matching](#pattern-matching)
5. [Structured Data Expectations](#structured-data-expectations)
6. [File Output Expectations](#file-output-expectations)
7. [Multimodal Output Expectations](#multimodal-output-expectations)
8. [Sequence Ordering](#sequence-ordering)
9. [Conditional Expectations](#conditional-expectations)
10. [Error Handling](#error-handling)
11. [Testing with Expect Sequences](#testing-with-expect-sequences)
12. [Advanced Patterns](#advanced-patterns)

---

## Basic Concepts

### What are Expect Sequences?

Expect sequences define the expected outputs, artifacts, and behaviors of an agent. They can validate:
- Return values
- File outputs
- Console output
- API calls
- State changes
- Resource usage

### Why Use Expect Sequences?

1. **Reliability** - Ensure agents behave consistently
2. **Testing** - Automated validation of agent behavior
3. **Monitoring** - Detect unexpected behavior in production
4. **Documentation** - Clear specification of expected behavior
5. **Debugging** - Quickly identify deviations

---

## Defining Expect Sequences

### Basic Expectation

Define simple expectations using the `@expect` decorator:

```python
from isolated_agents_sdk import isolated_agent, expect

@isolated_agent(working_dir="./workspace")
@expect(
    return_value={"status": "success"},
    artifacts=["output.txt"]
)
@dependencies("langchain", "langchain-openai")
def simple_agent(query: str):
    """Agent with basic expectations."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    llm = ChatOpenAI(model="gpt-4")
    result = llm.invoke(query)
    
    Path("/output/output.txt").write_text(result.content)
    return {"status": "success"}

# Automatically validates expectations
result = simple_agent("Hello")
# Raises ExpectationError if expectations not met
```

### Multiple Expectations

Define multiple expectations for comprehensive validation:

```python
from isolated_agents_sdk import isolated_agent, expect

@isolated_agent(working_dir="./workspace")
@expect(
    return_value={"status": "success", "count": int},
    artifacts=["data.json", "summary.txt"],
    execution_time_max=30.0,  # Max 30 seconds
    memory_usage_max=512  # Max 512 MB
)
@dependencies("langchain", "langchain-openai")
def multi_expect_agent(query: str):
    """Agent with multiple expectations."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    import json
    
    llm = ChatOpenAI(model="gpt-4")
    result = llm.invoke(query)
    
    # Generate expected outputs
    data = {"result": result.content, "length": len(result.content)}
    Path("/output/data.json").write_text(json.dumps(data))
    Path("/output/summary.txt").write_text(f"Length: {len(result.content)}")
    
    return {"status": "success", "count": len(result.content)}

result = multi_expect_agent("Explain AI")
```

---

## Validation Modes

### Strict Mode (Default)

All expectations must be met exactly:

```python
@expect(
    return_value={"status": "success", "count": 42},
    mode="strict"  # Default
)
def strict_agent():
    return {"status": "success", "count": 42}  # Must match exactly
```

### Partial Mode

Only specified fields must match:

```python
@expect(
    return_value={"status": "success"},  # Other fields ignored
    mode="partial"
)
def partial_agent():
    return {
        "status": "success",
        "count": 42,  # Extra fields allowed
        "timestamp": "2024-01-01"
    }
```

### Lenient Mode

Expectations are warnings, not errors:

```python
@expect(
    return_value={"status": "success"},
    mode="lenient"  # Logs warnings instead of raising errors
)
def lenient_agent():
    return {"status": "error"}  # Logs warning but doesn't fail
```

### Type-Only Mode

Only validate types, not values:

```python
@expect(
    return_value={"status": str, "count": int, "data": dict},
    mode="type_only"
)
def type_agent():
    return {
        "status": "any string",  # Any string value accepted
        "count": 999,  # Any int value accepted
        "data": {"key": "value"}  # Any dict accepted
    }
```

---

## Pattern Matching

### Regex Patterns

Use regex for flexible string matching:

```python
from isolated_agents_sdk import expect, Pattern

@expect(
    return_value={
        "status": Pattern(r"^(success|completed)$"),
        "email": Pattern(r"^[\w\.-]+@[\w\.-]+\.\w+$"),
        "id": Pattern(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    }
)
def pattern_agent():
    return {
        "status": "success",
        "email": "user@example.com",
        "id": "550e8400-e29b-41d4-a716-446655440000"
    }
```

### Range Patterns

Validate numeric ranges:

```python
from isolated_agents_sdk import expect, Range

@expect(
    return_value={
        "score": Range(0, 100),  # Between 0 and 100
        "temperature": Range(-273.15, None),  # Above absolute zero
        "count": Range(1, 1000, inclusive=True)  # 1 to 1000 inclusive
    }
)
def range_agent():
    return {
        "score": 85,
        "temperature": 20.5,
        "count": 500
    }
```

### Custom Validators

Define custom validation functions:

```python
from isolated_agents_sdk import expect, Validator

def is_even(value):
    return value % 2 == 0

def is_valid_email(value):
    import re
    return re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", value) is not None

@expect(
    return_value={
        "count": Validator(is_even, "Must be even number"),
        "email": Validator(is_valid_email, "Must be valid email")
    }
)
def custom_validator_agent():
    return {
        "count": 42,
        "email": "user@example.com"
    }
```

---

## Structured Data Expectations

### JSON Schema Validation

Validate JSON outputs against schemas:

```python
from isolated_agents_sdk import expect, JsonSchema

@expect(
    artifacts={
        "data.json": JsonSchema({
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer", "minimum": 0},
                "email": {"type": "string", "format": "email"}
            },
            "required": ["name", "age"]
        })
    }
)
@dependencies("jsonschema")
def json_schema_agent():
    from pathlib import Path
    import json
    
    data = {
        "name": "Alice",
        "age": 30,
        "email": "alice@example.com"
    }
    Path("/output/data.json").write_text(json.dumps(data))
    return {"status": "success"}
```

### DataFrame Expectations

Validate pandas DataFrame outputs:

```python
from isolated_agents_sdk import expect, DataFrameSchema

@expect(
    artifacts={
        "data.csv": DataFrameSchema(
            columns=["name", "age", "city"],
            dtypes={"name": "object", "age": "int64", "city": "object"},
            row_count_min=1,
            row_count_max=1000
        )
    }
)
@dependencies("pandas")
def dataframe_agent():
    import pandas as pd
    from pathlib import Path
    
    df = pd.DataFrame({
        "name": ["Alice", "Bob"],
        "age": [30, 25],
        "city": ["NYC", "LA"]
    })
    df.to_csv("/output/data.csv", index=False)
    return {"status": "success"}
```

---

## File Output Expectations

### File Existence

Expect specific files to be created:

```python
@expect(
    artifacts=["output.txt", "data.json", "chart.png"]
)
def file_existence_agent():
    from pathlib import Path
    
    Path("/output/output.txt").write_text("content")
    Path("/output/data.json").write_text("{}")
    Path("/output/chart.png").write_bytes(b"PNG data")
    
    return {"status": "success"}
```

### File Content

Validate file contents:

```python
from isolated_agents_sdk import expect, FileContent

@expect(
    artifacts={
        "output.txt": FileContent(
            contains="success",
            not_contains="error",
            min_length=10,
            max_length=1000
        ),
        "data.json": FileContent(
            json_valid=True,
            json_schema={"type": "object"}
        )
    }
)
def file_content_agent():
    from pathlib import Path
    import json
    
    Path("/output/output.txt").write_text("Operation completed successfully")
    Path("/output/data.json").write_text(json.dumps({"status": "ok"}))
    
    return {"status": "success"}
```

### File Properties

Validate file properties:

```python
from isolated_agents_sdk import expect, FileProperties

@expect(
    artifacts={
        "image.png": FileProperties(
            size_min=1024,  # At least 1KB
            size_max=10*1024*1024,  # At most 10MB
            mime_type="image/png"
        ),
        "data.csv": FileProperties(
            size_min=100,
            mime_type="text/csv",
            encoding="utf-8"
        )
    }
)
def file_properties_agent():
    from pathlib import Path
    from PIL import Image
    
    # Create image
    img = Image.new('RGB', (100, 100), color='blue')
    img.save("/output/image.png")
    
    # Create CSV
    Path("/output/data.csv").write_text("name,age\nAlice,30\n")
    
    return {"status": "success"}
```

---

## Multimodal Output Expectations

### Image Expectations

Validate image outputs:

```python
from isolated_agents_sdk import expect, ImageExpectation

@expect(
    artifacts={
        "chart.png": ImageExpectation(
            format="PNG",
            width_min=800,
            width_max=1920,
            height_min=600,
            height_max=1080,
            aspect_ratio=(16, 9),
            color_mode="RGB"
        )
    }
)
@dependencies("pillow", "matplotlib")
def image_agent():
    import matplotlib.pyplot as plt
    
    plt.figure(figsize=(16, 9))
    plt.plot([1, 2, 3, 4])
    plt.savefig("/output/chart.png", dpi=100)
    plt.close()
    
    return {"status": "success"}
```

### Audio Expectations

Validate audio outputs:

```python
from isolated_agents_sdk import expect, AudioExpectation

@expect(
    artifacts={
        "speech.mp3": AudioExpectation(
            format="MP3",
            duration_min=1.0,  # At least 1 second
            duration_max=60.0,  # At most 60 seconds
            sample_rate=44100,
            channels=2  # Stereo
        )
    }
)
@dependencies("pydub")
def audio_agent():
    from pydub import AudioSegment
    from pydub.generators import Sine
    
    # Generate 5 second tone
    tone = Sine(440).to_audio_segment(duration=5000)
    tone.export("/output/speech.mp3", format="mp3")
    
    return {"status": "success"}
```

### Video Expectations

Validate video outputs:

```python
from isolated_agents_sdk import expect, VideoExpectation

@expect(
    artifacts={
        "output.mp4": VideoExpectation(
            format="MP4",
            duration_min=1.0,
            duration_max=300.0,  # Max 5 minutes
            width=1920,
            height=1080,
            fps=30,
            codec="h264"
        )
    }
)
@dependencies("opencv-python")
def video_agent():
    import cv2
    import numpy as np
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter("/output/output.mp4", fourcc, 30.0, (1920, 1080))
    
    for i in range(90):  # 3 seconds at 30 fps
        frame = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
        out.write(frame)
    
    out.release()
    return {"status": "success"}
```

---

## Sequence Ordering

### Ordered Expectations

Validate outputs are created in specific order:

```python
from isolated_agents_sdk import expect, Sequence

@expect(
    artifacts=Sequence([
        "step1.txt",  # Must be created first
        "step2.txt",  # Then this
        "step3.txt"   # Finally this
    ]),
    ordered=True
)
def ordered_agent():
    from pathlib import Path
    import time
    
    Path("/output/step1.txt").write_text("Step 1")
    time.sleep(0.1)
    Path("/output/step2.txt").write_text("Step 2")
    time.sleep(0.1)
    Path("/output/step3.txt").write_text("Step 3")
    
    return {"status": "success"}
```

### Temporal Expectations

Validate timing between outputs:

```python
from isolated_agents_sdk import expect, TemporalSequence

@expect(
    artifacts=TemporalSequence([
        ("start.txt", 0),  # Created immediately
        ("progress.txt", 5),  # Created after 5 seconds
        ("complete.txt", 10)  # Created after 10 seconds
    ]),
    tolerance=1.0  # ±1 second tolerance
)
def temporal_agent():
    from pathlib import Path
    import time
    
    Path("/output/start.txt").write_text("Started")
    time.sleep(5)
    Path("/output/progress.txt").write_text("In progress")
    time.sleep(5)
    Path("/output/complete.txt").write_text("Complete")
    
    return {"status": "success"}
```

---

## Conditional Expectations

### Input-Based Expectations

Different expectations based on input:

```python
from isolated_agents_sdk import expect, ConditionalExpect

@expect(
    return_value=ConditionalExpect(
        condition=lambda input: input["mode"],
        expectations={
            "fast": {"status": "success", "quality": Range(0, 50)},
            "balanced": {"status": "success", "quality": Range(50, 80)},
            "quality": {"status": "success", "quality": Range(80, 100)}
        }
    )
)
def conditional_agent(mode: str):
    quality_map = {"fast": 30, "balanced": 65, "quality": 95}
    return {"status": "success", "quality": quality_map[mode]}

# Different expectations based on mode
result1 = conditional_agent("fast")  # Expects quality 0-50
result2 = conditional_agent("quality")  # Expects quality 80-100
```

### State-Based Expectations

Expectations based on agent state:

```python
from isolated_agents_sdk import expect, StateBasedExpect

@expect(
    artifacts=StateBasedExpect(
        states={
            "initial": ["config.json"],
            "processing": ["config.json", "temp.txt"],
            "complete": ["config.json", "output.txt"]
        }
    )
)
def stateful_agent():
    from pathlib import Path
    
    # Initial state
    Path("/output/config.json").write_text("{}")
    
    # Processing state
    Path("/output/temp.txt").write_text("processing")
    
    # Complete state
    Path("/output/temp.txt").unlink()  # Remove temp file
    Path("/output/output.txt").write_text("done")
    
    return {"status": "success"}
```

---

## Error Handling

### Expected Errors

Define expected error conditions:

```python
from isolated_agents_sdk import expect, ExpectError

@expect(
    errors=ExpectError(
        types=[ValueError, KeyError],
        message_pattern=r"Invalid input: .*"
    )
)
def error_agent(value: int):
    if value < 0:
        raise ValueError(f"Invalid input: {value}")
    return {"status": "success"}

# Validates error is raised as expected
try:
    error_agent(-1)
except ValueError:
    pass  # Expected
```

### Retry Expectations

Expect retries on failure:

```python
from isolated_agents_sdk import expect, RetryExpectation

@expect(
    retries=RetryExpectation(
        max_attempts=3,
        backoff_factor=2.0,
        success_on_attempt=2  # Expect success on 2nd attempt
    )
)
@retry(max_attempts=3, backoff=2.0)
def retry_agent():
    import random
    if random.random() < 0.5:
        raise Exception("Temporary failure")
    return {"status": "success"}
```

---

## Testing with Expect Sequences

### Unit Testing

Use expect sequences in unit tests:

```python
import pytest
from isolated_agents_sdk import isolated_agent, expect

@isolated_agent(working_dir="./workspace")
@expect(
    return_value={"status": "success", "count": int},
    artifacts=["output.txt"],
    execution_time_max=5.0
)
def test_agent(query: str):
    from pathlib import Path
    Path("/output/output.txt").write_text(query)
    return {"status": "success", "count": len(query)}

def test_agent_behavior():
    """Test agent meets expectations."""
    result = test_agent("test query")
    assert result.expectations_met is True
    assert result.return_value["status"] == "success"

def test_agent_artifacts():
    """Test agent creates expected artifacts."""
    result = test_agent("test")
    assert "output.txt" in result.artifacts
    assert result.artifacts["output.txt"].exists()
```

### Integration Testing

Test agent compositions:

```python
from isolated_agents_sdk import chain, expect

@expect(
    return_value={"status": "success"},
    artifacts=["research.txt", "article.txt", "final.txt"]
)
@chain(agents=[researcher, writer, editor])
def test_pipeline(topic: str):
    """Test entire pipeline meets expectations."""
    pass

def test_pipeline_integration():
    """Test pipeline produces expected outputs."""
    result = test_pipeline("AI Safety")
    assert result.expectations_met is True
    assert len(result.artifacts) == 3
```

### Property-Based Testing

Use hypothesis for property-based testing:

```python
from hypothesis import given, strategies as st
from isolated_agents_sdk import expect

@expect(
    return_value={"status": "success", "length": int},
    artifacts=["output.txt"]
)
def property_agent(text: str):
    from pathlib import Path
    Path("/output/output.txt").write_text(text)
    return {"status": "success", "length": len(text)}

@given(st.text(min_size=1, max_size=1000))
def test_agent_properties(text):
    """Test agent with random inputs."""
    result = property_agent(text)
    assert result.expectations_met is True
    assert result.return_value["length"] == len(text)
```

---

## Advanced Patterns

### Snapshot Testing

Compare outputs against saved snapshots:

```python
from isolated_agents_sdk import expect, Snapshot

@expect(
    artifacts={
        "output.txt": Snapshot("snapshots/output.txt"),
        "data.json": Snapshot("snapshots/data.json", mode="json")
    }
)
def snapshot_agent():
    from pathlib import Path
    import json
    
    Path("/output/output.txt").write_text("Expected output")
    Path("/output/data.json").write_text(json.dumps({"key": "value"}))
    
    return {"status": "success"}

# First run creates snapshots
result = snapshot_agent()

# Subsequent runs compare against snapshots
result = snapshot_agent()  # Validates against saved snapshots
```

### Fuzzy Matching

Allow approximate matches:

```python
from isolated_agents_sdk import expect, FuzzyMatch

@expect(
    return_value={
        "text": FuzzyMatch("expected output", similarity=0.8),
        "score": FuzzyMatch(85.5, tolerance=5.0)
    }
)
def fuzzy_agent():
    return {
        "text": "expected output with minor differences",  # 80%+ similar
        "score": 87.2  # Within ±5.0 of 85.5
    }
```

### Performance Expectations

Validate performance characteristics:

```python
from isolated_agents_sdk import expect, Performance

@expect(
    performance=Performance(
        execution_time_max=10.0,
        memory_usage_max=512,  # MB
        cpu_usage_max=80,  # Percent
        network_calls_max=5,
        disk_writes_max=10
    )
)
def performance_agent():
    # Agent implementation
    return {"status": "success"}
```

### Probabilistic Expectations

Handle non-deterministic outputs:

```python
from isolated_agents_sdk import expect, Probabilistic

@expect(
    return_value={
        "status": "success",
        "score": Probabilistic(
            distribution="normal",
            mean=75.0,
            std=10.0,
            confidence=0.95  # 95% confidence interval
        )
    }
)
def probabilistic_agent():
    import random
    score = random.gauss(75.0, 10.0)
    return {"status": "success", "score": score}
```

---

## Best Practices

### 1. **Start Simple**
- Begin with basic expectations (return values, artifacts)
- Add complexity as needed
- Use lenient mode during development

### 2. **Be Specific**
- Define clear, testable expectations
- Use type hints and schemas
- Document expected behavior

### 3. **Handle Variability**
- Use ranges for numeric values
- Use patterns for strings
- Use fuzzy matching for approximate values

### 4. **Test Thoroughly**
- Write unit tests with expectations
- Use property-based testing
- Test edge cases

### 5. **Monitor in Production**
- Use lenient mode in production
- Log expectation violations
- Alert on critical failures

### 6. **Document Expectations**
- Expectations serve as documentation
- Keep them up to date
- Use descriptive names

---

## Configuration

### Global Configuration

Configure expect behavior globally:

```python
from isolated_agents_sdk import configure_expectations

configure_expectations(
    default_mode="lenient",  # Default validation mode
    log_violations=True,  # Log expectation violations
    raise_on_violation=False,  # Don't raise errors in production
    snapshot_dir="./snapshots",  # Snapshot directory
    enable_performance_tracking=True  # Track performance metrics
)
```

### Per-Agent Configuration

Configure per agent:

```python
@expect(
    return_value={"status": "success"},
    config={
        "mode": "strict",
        "log_violations": True,
        "timeout": 30.0
    }
)
def configured_agent():
    return {"status": "success"}
```

---

## Summary

Expect Sequences provide comprehensive output validation:

1. **Basic Expectations** - Return values, artifacts, execution time
2. **Validation Modes** - Strict, partial, lenient, type-only
3. **Pattern Matching** - Regex, ranges, custom validators
4. **Structured Data** - JSON schema, DataFrame validation
5. **File Expectations** - Existence, content, properties
6. **Multimodal** - Images, audio, video validation
7. **Sequence Ordering** - Ordered and temporal expectations
8. **Conditional** - Input and state-based expectations
9. **Error Handling** - Expected errors and retries
10. **Testing** - Unit, integration, property-based testing
11. **Advanced** - Snapshots, fuzzy matching, performance, probabilistic

These capabilities enable reliable, testable, and maintainable agent systems.

---

**Next Steps:**
- Review [COMPOSABILITY.md](COMPOSABILITY.md) for agent composition
- See [MULTIMODAL_OUTPUTS.md](MULTIMODAL_OUTPUTS.md) for output formats
- Check [DECORATORS.md](DECORATORS.md) for decorator details