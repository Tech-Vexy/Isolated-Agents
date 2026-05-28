"""AI-powered code generation with validation and testing.

This example demonstrates:
- Code generation with LLMs
- Syntax validation with AST parsing
- Automatic test generation
- Code execution and validation
- Multiple output formats

Usage:
    export OPENAI_API_KEY=sk-...
    python examples/scenarios/code_generation/generate_and_test.py
    
    # Or with a custom prompt:
    python examples/scenarios/code_generation/generate_and_test.py "Create a function to calculate fibonacci numbers"
"""

import os
import sys
from pathlib import Path


def code_generation_agent(prompt: str = None):
    """Generate, validate, and test Python code using AI."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    import ast
    import json
    from datetime import datetime
    import subprocess
    import tempfile
    
    print("Starting code generation agent...")
    
    # Default prompt if none provided
    if not prompt:
        prompt = """Create a Python function that:
1. Takes a list of numbers as input
2. Filters out negative numbers and zeros
3. Returns the sum of the remaining positive numbers
4. Includes proper error handling for invalid inputs
5. Has type hints and a comprehensive docstring"""
    
    print(f"\nPrompt: {prompt}\n")
    
    try:
        # Initialize LLM
        llm = ChatOpenAI(model="gpt-4", temperature=0.2)
        
        # Generate code
        print("Generating code...")
        code_prompt = f"""{prompt}

Requirements:
- Include type hints
- Add comprehensive docstring
- Handle edge cases
- Use descriptive variable names
- Follow PEP 8 style guide

Return ONLY the Python code, no explanations."""
        
        code_response = llm.invoke(code_prompt)
        generated_code = code_response.content
        
        # Extract code from markdown if present
        if "```python" in generated_code:
            generated_code = generated_code.split("```python")[1].split("```")[0].strip()
        elif "```" in generated_code:
            generated_code = generated_code.split("```")[1].split("```")[0].strip()
        
        print(f"✓ Generated {len(generated_code)} characters of code")
        
        # Validate syntax
        print("\nValidating syntax...")
        syntax_valid = True
        syntax_error = None
        
        try:
            ast.parse(generated_code)
            print("✓ Syntax is valid")
        except SyntaxError as e:
            syntax_valid = False
            syntax_error = str(e)
            print(f"✗ Syntax error: {e}")
        
        # Extract function name for testing
        function_name = None
        try:
            tree = ast.parse(generated_code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    function_name = node.name
                    break
        except:
            pass
        
        print(f"✓ Detected function: {function_name or 'unknown'}")
        
        # Generate tests
        print("\nGenerating tests...")
        test_prompt = f"""Generate comprehensive pytest tests for this function:

{generated_code}

Requirements:
- Test normal cases
- Test edge cases
- Test error handling
- Use descriptive test names
- Include docstrings

Return ONLY the test code, no explanations."""
        
        test_response = llm.invoke(test_prompt)
        test_code = test_response.content
        
        # Extract test code from markdown
        if "```python" in test_code:
            test_code = test_code.split("```python")[1].split("```")[0].strip()
        elif "```" in test_code:
            test_code = test_code.split("```")[1].split("```")[0].strip()
        
        print(f"✓ Generated {len(test_code)} characters of test code")
        
        # Validate test syntax
        test_syntax_valid = True
        test_syntax_error = None
        
        try:
            ast.parse(test_code)
            print("✓ Test syntax is valid")
        except SyntaxError as e:
            test_syntax_valid = False
            test_syntax_error = str(e)
            print(f"✗ Test syntax error: {e}")
        
        # Try to run the tests
        print("\nRunning tests...")
        test_results = None
        test_passed = False
        
        if syntax_valid and test_syntax_valid:
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmpdir_path = Path(tmpdir)
                    
                    # Write code file
                    code_file = tmpdir_path / "generated_code.py"
                    code_file.write_text(generated_code)
                    
                    # Write test file
                    test_file = tmpdir_path / "test_generated_code.py"
                    # Add import statement if not present
                    if "from generated_code import" not in test_code and "import generated_code" not in test_code:
                        if function_name:
                            test_code = f"from generated_code import {function_name}\n\n{test_code}"
                    test_file.write_text(test_code)
                    
                    # Run pytest
                    result = subprocess.run(
                        ["python", "-m", "pytest", str(test_file), "-v"],
                        capture_output=True,
                        text=True,
                        timeout=30,
                        cwd=tmpdir
                    )
                    
                    test_results = result.stdout + result.stderr
                    test_passed = result.returncode == 0
                    
                    if test_passed:
                        print("✓ All tests passed")
                    else:
                        print("✗ Some tests failed")
                        
            except subprocess.TimeoutExpired:
                test_results = "Tests timed out after 30 seconds"
                print("✗ Tests timed out")
            except Exception as e:
                test_results = f"Test execution failed: {str(e)}"
                print(f"✗ Test execution error: {e}")
        else:
            test_results = "Tests not run due to syntax errors"
            print("⚠ Tests not run due to syntax errors")
        
        # Generate documentation
        print("\nGenerating documentation...")
        doc_prompt = f"""Generate comprehensive documentation for this code:

{generated_code}

Include:
- Overview
- Parameters
- Return value
- Examples
- Edge cases
- Time/space complexity if applicable

Format as Markdown."""
        
        doc_response = llm.invoke(doc_prompt)
        documentation = doc_response.content
        
        print(f"✓ Generated documentation")
        
        # Prepare outputs
        output_dir = Path("/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save generated code
        code_path = output_dir / "generated_code.py"
        code_path.write_text(generated_code)
        print(f"\n✓ Saved: {code_path.name}")
        
        # Save tests
        test_path = output_dir / "test_generated_code.py"
        test_path.write_text(test_code)
        print(f"✓ Saved: {test_path.name}")
        
        # Save documentation
        doc_path = output_dir / "documentation.md"
        doc_path.write_text(documentation)
        print(f"✓ Saved: {doc_path.name}")
        
        # Save validation report
        validation_report = f"""# Code Generation Validation Report

Generated: {datetime.now().isoformat()}

## Prompt
{prompt}

## Validation Results

### Syntax Validation
- **Status**: {'✓ Valid' if syntax_valid else '✗ Invalid'}
- **Error**: {syntax_error or 'None'}

### Test Syntax Validation
- **Status**: {'✓ Valid' if test_syntax_valid else '✗ Invalid'}
- **Error**: {test_syntax_error or 'None'}

### Test Execution
- **Status**: {'✓ Passed' if test_passed else '✗ Failed' if test_results else '⚠ Not Run'}
- **Results**:
```
{test_results or 'N/A'}
```

## Code Metrics
- **Code Length**: {len(generated_code)} characters
- **Test Length**: {len(test_code)} characters
- **Function Name**: {function_name or 'Not detected'}

## Generated Code
```python
{generated_code}
```

## Generated Tests
```python
{test_code}
```
"""
        
        report_path = output_dir / "validation_report.md"
        report_path.write_text(validation_report)
        print(f"✓ Saved: {report_path.name}")
        
        # Save metadata
        metadata = {
            "prompt": prompt,
            "generated_at": datetime.now().isoformat(),
            "function_name": function_name,
            "code_length": len(generated_code),
            "test_length": len(test_code),
            "syntax_valid": syntax_valid,
            "test_syntax_valid": test_syntax_valid,
            "tests_passed": test_passed,
            "model": "gpt-4"
        }
        
        metadata_path = output_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2))
        print(f"✓ Saved: {metadata_path.name}")
        
        print("\n✓ Code generation completed successfully")
        
        return {
            "function_name": function_name,
            "syntax_valid": syntax_valid,
            "tests_passed": test_passed
        }
        
    except Exception as e:
        error_msg = f"Code generation failed: {str(e)}"
        print(f"✗ {error_msg}")
        
        output_dir = Path("/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "error.txt").write_text(error_msg)
        
        raise


if __name__ == "__main__":
    from isolated_agents_sdk import run_agent, Policy, NetworkPolicy
    
    # Check prerequisites
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set", file=sys.stderr)
        print("\nSet it with:")
        print("  export OPENAI_API_KEY=sk-...")
        sys.exit(1)
    
    # Get custom prompt if provided
    custom_prompt = None
    if len(sys.argv) > 1:
        custom_prompt = " ".join(sys.argv[1:])
    
    # Setup directories
    output = Path("./output/code_generation")
    output.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("AI-Powered Code Generation & Testing Agent")
    print("=" * 70)
    print()
    
    # Configure policy
    policy = Policy(
        cpu_cores=2.0,
        memory_mb=2048,
        timeout_seconds=180,
        
        network=NetworkPolicy(
            disabled=False,
            allowed_endpoints=["api.openai.com:443"]
        ),
        
        allowed_env_vars=["OPENAI_API_KEY"],
        
        pip_packages=[
            "langchain-openai",
            "pytest"
        ]
    )
    
    print("Launching agent in isolated container...")
    print()
    
    # Run agent
    result = run_agent(
        agent=code_generation_agent,
        kwargs={"prompt": custom_prompt} if custom_prompt else {},
        working_dir="./workspace",
        host_output_path=output,
        policy=policy
    )
    
    print()
    print("=" * 70)
    
    if result.exit_code == 0:
        print("✓ Code generation completed successfully")
        print()
        
        if result.artifacts:
            print("Generated artifacts:")
            for name, path in result.artifacts.items():
                file_path = Path(path)
                if file_path.exists():
                    size = file_path.stat().st_size
                    print(f"  • {name} ({size:,} bytes)")
            
            # Show generated code
            code_path = result.artifacts.get("generated_code.py")
            if code_path and Path(code_path).exists():
                print()
                print("Generated Code:")
                print("-" * 70)
                code_content = Path(code_path).read_text()
                print(code_content[:500] + ("..." if len(code_content) > 500 else ""))
                print("-" * 70)
            
            # Show validation report location
            report_path = result.artifacts.get("validation_report.md")
            if report_path:
                print()
                print(f"Full validation report: {report_path}")
    else:
        print(f"✗ Code generation failed with exit code {result.exit_code}")
        if result.error:
            print(f"Error: {result.error}")
    
    print("=" * 70)
    
    sys.exit(result.exit_code)
