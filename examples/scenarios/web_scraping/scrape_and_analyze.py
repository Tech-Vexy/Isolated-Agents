"""Web scraping with AI-powered analysis.

This example demonstrates:
- HTTP requests with network isolation
- HTML parsing and content extraction
- AI-powered content analysis
- Structured output generation
- Error handling and validation

Usage:
    export OPENAI_API_KEY=sk-...
    python examples/scenarios/web_scraping/scrape_and_analyze.py
"""

import os
import sys
from pathlib import Path


def scrape_and_analyze_agent():
    """Scrape a website and analyze its content with AI."""
    import requests
    from bs4 import BeautifulSoup
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    import json
    from datetime import datetime
    
    print("Starting web scraping agent...")
    
    # Target URL (using a safe example site)
    url = "https://example.com"
    
    try:
        # Scrape website
        print(f"Fetching content from {url}...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract text content
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        text = soup.get_text()
        # Clean whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        print(f"✓ Scraped {len(text)} characters")
        
        # Extract metadata
        title = soup.find('title')
        title_text = title.string if title else "No title"
        
        meta_description = soup.find('meta', attrs={'name': 'description'})
        description = meta_description.get('content', '') if meta_description else ''
        
        # Analyze with LLM
        print("Analyzing content with AI...")
        llm = ChatOpenAI(model="gpt-4")
        
        analysis_prompt = f"""Analyze this website content and provide:
1. Main topic/purpose
2. Key points (3-5 bullet points)
3. Target audience
4. Content quality assessment

Website: {url}
Title: {title_text}
Content: {text[:2000]}"""
        
        analysis = llm.invoke(analysis_prompt)
        
        print(f"✓ Analysis completed ({len(analysis.content)} characters)")
        
        # Generate summary
        summary_prompt = f"Summarize this website in 2-3 sentences: {text[:1000]}"
        summary = llm.invoke(summary_prompt)
        
        # Prepare outputs
        output_dir = Path("/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save raw content
        (output_dir / "scraped_content.txt").write_text(text)
        
        # Save analysis
        (output_dir / "analysis.txt").write_text(analysis.content)
        
        # Save summary
        (output_dir / "summary.txt").write_text(summary.content)
        
        # Save metadata
        metadata = {
            "url": url,
            "title": title_text,
            "description": description,
            "content_length": len(text),
            "scraped_at": datetime.now().isoformat(),
            "status_code": response.status_code,
            "content_type": response.headers.get('content-type', 'unknown')
        }
        (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
        
        # Save structured report
        report = f"""# Web Scraping Report

## Website Information
- **URL**: {url}
- **Title**: {title_text}
- **Scraped**: {metadata['scraped_at']}
- **Content Length**: {len(text)} characters

## Summary
{summary.content}

## Detailed Analysis
{analysis.content}

## Metadata
- Status Code: {response.status_code}
- Content Type: {response.headers.get('content-type', 'unknown')}
- Description: {description or 'N/A'}
"""
        (output_dir / "report.md").write_text(report)
        
        print(f"✓ All outputs saved successfully")
        print(f"  • scraped_content.txt ({len(text)} chars)")
        print(f"  • analysis.txt")
        print(f"  • summary.txt")
        print(f"  • metadata.json")
        print(f"  • report.md")
        
        return "Scraping and analysis completed successfully"
        
    except requests.RequestException as e:
        error_msg = f"HTTP request failed: {e}"
        print(f"✗ {error_msg}")
        
        output_dir = Path("/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "error.txt").write_text(error_msg)
        
        raise
    except Exception as e:
        error_msg = f"Analysis failed: {e}"
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
    
    # Create output directory
    output = Path("./output/web_scraping")
    output.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("Web Scraping & Analysis Agent")
    print("=" * 60)
    print()
    
    # Configure policy
    policy = Policy(
        # Resource limits
        cpu_cores=2.0,
        memory_mb=2048,
        timeout_seconds=120,
        
        # Network access (restricted to specific endpoints)
        network=NetworkPolicy(
            disabled=False,
            allowed_endpoints=[
                "example.com:443",
                "api.openai.com:443"
            ]
        ),
        
        # Environment variables
        allowed_env_vars=["OPENAI_API_KEY"],
        
        # Required packages
        pip_packages=[
            "requests",
            "beautifulsoup4",
            "langchain-openai",
            "lxml"  # Better HTML parsing
        ]
    )
    
    print("Launching agent in isolated container...")
    print()
    
    # Run agent
    result = run_agent(
        agent=scrape_and_analyze_agent,
        working_dir="./workspace",
        host_output_path=output,
        policy=policy
    )
    
    print()
    print("=" * 60)
    
    if result.exit_code == 0:
        print("✓ Agent completed successfully")
        print()
        
        # Display results
        if result.artifacts:
            print("Generated artifacts:")
            for name, path in result.artifacts.items():
                file_path = Path(path)
                if file_path.exists():
                    size = file_path.stat().st_size
                    print(f"  • {name} ({size} bytes)")
            
            # Show summary if available
            summary_path = result.artifacts.get("summary.txt")
            if summary_path and Path(summary_path).exists():
                print()
                print("Summary:")
                print("-" * 60)
                print(Path(summary_path).read_text())
                print("-" * 60)
            
            # Show report location
            report_path = result.artifacts.get("report.md")
            if report_path:
                print()
                print(f"Full report available at: {report_path}")
    else:
        print(f"✗ Agent failed with exit code {result.exit_code}")
        if result.error:
            print(f"Error: {result.error}")
        
        # Check for error file
        error_file = output / "error.txt"
        if error_file.exists():
            print()
            print("Error details:")
            print(error_file.read_text())
    
    print("=" * 60)
    
    sys.exit(result.exit_code)
