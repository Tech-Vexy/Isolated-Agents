# Multimodal Output Support Guide

## Overview

The Isolated Agents SDK provides comprehensive **multimodal output support** that enables agents to:
- Generate and handle multiple output formats (text, images, audio, video, PDFs, etc.)
- Automatically detect and classify output types
- Stream large outputs efficiently
- Convert between formats
- Validate output integrity
- Support structured data formats (JSON, YAML, CSV, Parquet, etc.)

## Table of Contents

1. [Supported Output Formats](#supported-output-formats)
2. [Output Format Detection](#output-format-detection)
3. [Text Outputs](#text-outputs)
4. [Image Outputs](#image-outputs)
5. [Audio Outputs](#audio-outputs)
6. [Video Outputs](#video-outputs)
7. [Document Outputs](#document-outputs)
8. [Structured Data Outputs](#structured-data-outputs)
9. [Binary Outputs](#binary-outputs)
10. [Streaming Outputs](#streaming-outputs)
11. [Format Conversion](#format-conversion)
12. [Output Validation](#output-validation)
13. [Advanced Patterns](#advanced-patterns)

---

## Supported Output Formats

### Text Formats
- Plain text (`.txt`)
- Markdown (`.md`)
- HTML (`.html`)
- LaTeX (`.tex`)
- Rich text (`.rtf`)
- Code files (`.py`, `.js`, `.java`, etc.)

### Image Formats
- PNG (`.png`)
- JPEG (`.jpg`, `.jpeg`)
- GIF (`.gif`)
- SVG (`.svg`)
- WebP (`.webp`)
- TIFF (`.tiff`)
- BMP (`.bmp`)

### Audio Formats
- MP3 (`.mp3`)
- WAV (`.wav`)
- FLAC (`.flac`)
- OGG (`.ogg`)
- AAC (`.aac`)
- M4A (`.m4a`)

### Video Formats
- MP4 (`.mp4`)
- AVI (`.avi`)
- MOV (`.mov`)
- WebM (`.webm`)
- MKV (`.mkv`)
- FLV (`.flv`)

### Document Formats
- PDF (`.pdf`)
- DOCX (`.docx`)
- XLSX (`.xlsx`)
- PPTX (`.pptx`)
- ODT (`.odt`)
- EPUB (`.epub`)

### Structured Data Formats
- JSON (`.json`)
- YAML (`.yaml`, `.yml`)
- CSV (`.csv`)
- TSV (`.tsv`)
- Parquet (`.parquet`)
- Avro (`.avro`)
- Protocol Buffers (`.pb`)
- MessagePack (`.msgpack`)

### Binary Formats
- ZIP (`.zip`)
- TAR (`.tar`, `.tar.gz`)
- SQLite (`.db`, `.sqlite`)
- HDF5 (`.h5`, `.hdf5`)
- Pickle (`.pkl`)

---

## Output Format Detection

### Automatic Detection

The SDK automatically detects output formats based on file extensions and content:

```python
from isolated_agents_sdk import isolated_agent, output_format

@isolated_agent(working_dir="./workspace")
@output_format(auto_detect=True)  # Automatic format detection
@dependencies("pillow", "langchain", "langchain-openai")
def image_generator(prompt: str):
    """Generate image from text prompt."""
    from langchain_openai import ChatOpenAI
    from PIL import Image
    from pathlib import Path
    
    # Generate image (example using DALL-E)
    llm = ChatOpenAI(model="gpt-4")
    # ... image generation logic ...
    
    # Save as PNG
    img = Image.new('RGB', (512, 512), color='blue')
    img.save("/output/generated.png")
    
    return {"format": "image/png", "size": (512, 512)}

result = image_generator("A beautiful sunset")
print(f"Output format: {result.output_format}")  # "image/png"
print(f"Output file: {result.artifacts['generated.png']}")
```

### Explicit Format Declaration

Declare expected output formats explicitly:

```python
from isolated_agents_sdk import isolated_agent, output_format

@isolated_agent(working_dir="./workspace")
@output_format(
    formats=["image/png", "image/jpeg"],  # Expected formats
    primary="image/png"  # Primary format
)
@dependencies("pillow")
def multi_format_generator(prompt: str, format: str = "png"):
    """Generate image in specified format."""
    from PIL import Image
    from pathlib import Path
    
    img = Image.new('RGB', (512, 512), color='blue')
    
    if format == "png":
        img.save("/output/generated.png")
    elif format == "jpeg":
        img.save("/output/generated.jpg", quality=95)
    
    return {"format": f"image/{format}"}

result = multi_format_generator("A sunset", format="jpeg")
```

---

## Text Outputs

### Plain Text

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./workspace")
@dependencies("langchain", "langchain-openai")
def text_generator(topic: str):
    """Generate plain text content."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    llm = ChatOpenAI(model="gpt-4")
    result = llm.invoke(f"Write about: {topic}")
    
    Path("/output/content.txt").write_text(result.content)
    return {"format": "text/plain", "length": len(result.content)}

result = text_generator("AI Safety")
print(result.artifacts["content.txt"])
```

### Markdown

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./workspace")
@dependencies("langchain", "langchain-openai")
def markdown_generator(topic: str):
    """Generate markdown documentation."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    llm = ChatOpenAI(model="gpt-4")
    result = llm.invoke(f"Write markdown documentation about: {topic}")
    
    Path("/output/documentation.md").write_text(result.content)
    return {"format": "text/markdown"}

result = markdown_generator("API Documentation")
print(result.artifacts["documentation.md"])
```

### HTML

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./workspace")
@dependencies("langchain", "langchain-openai")
def html_generator(content: str):
    """Generate HTML page."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    llm = ChatOpenAI(model="gpt-4")
    result = llm.invoke(f"Convert to HTML: {content}")
    
    html = f"""<!DOCTYPE html>
<html>
<head><title>Generated Content</title></head>
<body>{result.content}</body>
</html>"""
    
    Path("/output/page.html").write_text(html)
    return {"format": "text/html"}

result = html_generator("Welcome to my site")
print(result.artifacts["page.html"])
```

---

## Image Outputs

### PNG Images

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./workspace")
@dependencies("pillow", "matplotlib")
def chart_generator(data: list):
    """Generate PNG chart."""
    import matplotlib.pyplot as plt
    from pathlib import Path
    
    plt.figure(figsize=(10, 6))
    plt.plot(data)
    plt.title("Data Visualization")
    plt.savefig("/output/chart.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    return {"format": "image/png", "dpi": 300}

result = chart_generator([1, 4, 2, 8, 5, 7])
print(result.artifacts["chart.png"])
```

### JPEG Images

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./workspace")
@dependencies("pillow")
def photo_processor(input_path: str):
    """Process and save as JPEG."""
    from PIL import Image
    from pathlib import Path
    
    img = Image.open(input_path)
    img = img.resize((800, 600))
    img.save("/output/processed.jpg", quality=95, optimize=True)
    
    return {"format": "image/jpeg", "quality": 95}

result = photo_processor("input.png")
print(result.artifacts["processed.jpg"])
```

### SVG Graphics

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./workspace")
@dependencies("svgwrite")
def svg_generator(shapes: list):
    """Generate SVG graphics."""
    import svgwrite
    from pathlib import Path
    
    dwg = svgwrite.Drawing("/output/graphic.svg", size=("400px", "400px"))
    
    for shape in shapes:
        if shape["type"] == "circle":
            dwg.add(dwg.circle(
                center=(shape["x"], shape["y"]),
                r=shape["radius"],
                fill=shape["color"]
            ))
    
    dwg.save()
    return {"format": "image/svg+xml"}

result = svg_generator([
    {"type": "circle", "x": 100, "y": 100, "radius": 50, "color": "blue"}
])
print(result.artifacts["graphic.svg"])
```

---

## Audio Outputs

### MP3 Audio

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./workspace")
@network(enabled=True)
@dependencies("openai", "pydub")
def text_to_speech(text: str):
    """Convert text to MP3 audio."""
    from openai import OpenAI
    from pathlib import Path
    
    client = OpenAI()
    response = client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=text
    )
    
    response.stream_to_file("/output/speech.mp3")
    return {"format": "audio/mpeg", "duration": len(text) / 15}

result = text_to_speech("Hello, this is a test of text to speech.")
print(result.artifacts["speech.mp3"])
```

### WAV Audio

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./workspace")
@dependencies("scipy", "numpy")
def audio_generator(frequency: int, duration: float):
    """Generate WAV audio file."""
    import numpy as np
    from scipy.io import wavfile
    from pathlib import Path
    
    sample_rate = 44100
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = np.sin(2 * np.pi * frequency * t)
    
    wavfile.write("/output/tone.wav", sample_rate, audio.astype(np.float32))
    return {"format": "audio/wav", "sample_rate": sample_rate}

result = audio_generator(440, 2.0)  # 440 Hz for 2 seconds
print(result.artifacts["tone.wav"])
```

---

## Video Outputs

### MP4 Video

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./workspace")
@dependencies("opencv-python", "numpy")
def video_generator(frames: int):
    """Generate MP4 video."""
    import cv2
    import numpy as np
    from pathlib import Path
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter("/output/video.mp4", fourcc, 30.0, (640, 480))
    
    for i in range(frames):
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        out.write(frame)
    
    out.release()
    return {"format": "video/mp4", "frames": frames, "fps": 30}

result = video_generator(90)  # 3 seconds at 30 fps
print(result.artifacts["video.mp4"])
```

### WebM Video

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./workspace")
@dependencies("opencv-python")
def webm_generator(input_video: str):
    """Convert video to WebM format."""
    import cv2
    from pathlib import Path
    
    cap = cv2.VideoCapture(input_video)
    fourcc = cv2.VideoWriter_fourcc(*'VP80')
    out = cv2.VideoWriter("/output/video.webm", fourcc, 30.0, (640, 480))
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        out.write(frame)
    
    cap.release()
    out.release()
    return {"format": "video/webm"}

result = webm_generator("input.mp4")
print(result.artifacts["video.webm"])
```

---

## Document Outputs

### PDF Documents

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./workspace")
@dependencies("reportlab", "langchain", "langchain-openai")
def pdf_generator(content: str):
    """Generate PDF document."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from pathlib import Path
    
    c = canvas.Canvas("/output/document.pdf", pagesize=letter)
    c.drawString(100, 750, "Generated Document")
    
    # Add content
    y = 700
    for line in content.split('\n'):
        c.drawString(100, y, line[:80])
        y -= 20
        if y < 100:
            c.showPage()
            y = 750
    
    c.save()
    return {"format": "application/pdf"}

result = pdf_generator("This is the content of the PDF document.")
print(result.artifacts["document.pdf"])
```

### DOCX Documents

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./workspace")
@dependencies("python-docx", "langchain", "langchain-openai")
def docx_generator(content: str):
    """Generate DOCX document."""
    from docx import Document
    from pathlib import Path
    
    doc = Document()
    doc.add_heading("Generated Document", 0)
    
    for paragraph in content.split('\n\n'):
        doc.add_paragraph(paragraph)
    
    doc.save("/output/document.docx")
    return {"format": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}

result = docx_generator("This is the content.\n\nWith multiple paragraphs.")
print(result.artifacts["document.docx"])
```

### XLSX Spreadsheets

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./workspace")
@dependencies("openpyxl", "pandas")
def excel_generator(data: dict):
    """Generate Excel spreadsheet."""
    import pandas as pd
    from pathlib import Path
    
    df = pd.DataFrame(data)
    df.to_excel("/output/spreadsheet.xlsx", index=False, engine='openpyxl')
    
    return {"format": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}

result = excel_generator({
    "Name": ["Alice", "Bob", "Charlie"],
    "Age": [25, 30, 35],
    "City": ["New York", "London", "Tokyo"]
})
print(result.artifacts["spreadsheet.xlsx"])
```

---

## Structured Data Outputs

### JSON

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./workspace")
@dependencies("langchain", "langchain-openai")
def json_generator(query: str):
    """Generate structured JSON output."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    import json
    
    llm = ChatOpenAI(model="gpt-4")
    result = llm.invoke(f"Extract structured data as JSON: {query}")
    
    # Parse and validate JSON
    data = json.loads(result.content)
    
    Path("/output/data.json").write_text(json.dumps(data, indent=2))
    return {"format": "application/json", "keys": list(data.keys())}

result = json_generator("Extract person info: John Doe, age 30, from NYC")
print(result.artifacts["data.json"])
```

### YAML

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./workspace")
@dependencies("pyyaml")
def yaml_generator(config: dict):
    """Generate YAML configuration."""
    import yaml
    from pathlib import Path
    
    yaml_content = yaml.dump(config, default_flow_style=False)
    Path("/output/config.yaml").write_text(yaml_content)
    
    return {"format": "application/x-yaml"}

result = yaml_generator({
    "database": {
        "host": "localhost",
        "port": 5432,
        "name": "mydb"
    }
})
print(result.artifacts["config.yaml"])
```

### CSV

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./workspace")
@dependencies("pandas")
def csv_generator(data: list):
    """Generate CSV file."""
    import pandas as pd
    from pathlib import Path
    
    df = pd.DataFrame(data)
    df.to_csv("/output/data.csv", index=False)
    
    return {"format": "text/csv", "rows": len(df)}

result = csv_generator([
    {"name": "Alice", "score": 95},
    {"name": "Bob", "score": 87},
    {"name": "Charlie", "score": 92}
])
print(result.artifacts["data.csv"])
```

### Parquet

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./workspace")
@dependencies("pandas", "pyarrow")
def parquet_generator(data: dict):
    """Generate Parquet file for big data."""
    import pandas as pd
    from pathlib import Path
    
    df = pd.DataFrame(data)
    df.to_parquet("/output/data.parquet", engine='pyarrow', compression='snappy')
    
    return {"format": "application/x-parquet", "rows": len(df)}

result = parquet_generator({
    "id": range(1000000),
    "value": [i * 2 for i in range(1000000)]
})
print(result.artifacts["data.parquet"])
```

---

## Binary Outputs

### ZIP Archives

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./workspace")
@dependencies("zipfile")
def zip_generator(files: list):
    """Create ZIP archive."""
    import zipfile
    from pathlib import Path
    
    with zipfile.ZipFile("/output/archive.zip", 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in files:
            zf.write(file_path, Path(file_path).name)
    
    return {"format": "application/zip", "files": len(files)}

result = zip_generator(["file1.txt", "file2.txt", "file3.txt"])
print(result.artifacts["archive.zip"])
```

### SQLite Databases

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./workspace")
@dependencies("sqlite3")
def sqlite_generator(data: list):
    """Create SQLite database."""
    import sqlite3
    from pathlib import Path
    
    conn = sqlite3.connect("/output/database.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT
        )
    """)
    
    cursor.executemany("INSERT INTO users (name, email) VALUES (?, ?)", data)
    conn.commit()
    conn.close()
    
    return {"format": "application/x-sqlite3", "records": len(data)}

result = sqlite_generator([
    ("Alice", "alice@example.com"),
    ("Bob", "bob@example.com")
])
print(result.artifacts["database.db"])
```

---

## Streaming Outputs

### Streaming Large Files

```python
from isolated_agents_sdk import isolated_agent, streaming_output

@isolated_agent(working_dir="./workspace")
@streaming_output(chunk_size=1024*1024)  # 1MB chunks
@dependencies("requests")
def large_file_downloader(url: str):
    """Download large file with streaming."""
    import requests
    from pathlib import Path
    
    response = requests.get(url, stream=True)
    
    with open("/output/large_file.bin", 'wb') as f:
        for chunk in response.iter_content(chunk_size=1024*1024):
            if chunk:
                f.write(chunk)
    
    return {"format": "application/octet-stream", "size": Path("/output/large_file.bin").stat().st_size}

result = large_file_downloader("https://example.com/large-file.bin")
```

### Streaming Text Generation

```python
from isolated_agents_sdk import isolated_agent, streaming_output

@isolated_agent(working_dir="./workspace")
@streaming_output(mode="text")
@dependencies("langchain", "langchain-openai")
def streaming_text_generator(prompt: str):
    """Generate text with streaming."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    llm = ChatOpenAI(model="gpt-4", streaming=True)
    
    full_text = ""
    for chunk in llm.stream(prompt):
        full_text += chunk.content
        # Stream to output
        Path("/output/stream.txt").write_text(full_text)
    
    return {"format": "text/plain", "length": len(full_text)}

result = streaming_text_generator("Write a long story about AI")
```

---

## Format Conversion

### Automatic Conversion

```python
from isolated_agents_sdk import isolated_agent, convert_output

@isolated_agent(working_dir="./workspace")
@convert_output(
    from_format="image/png",
    to_formats=["image/jpeg", "image/webp"]
)
@dependencies("pillow")
def image_converter(input_path: str):
    """Convert image to multiple formats."""
    from PIL import Image
    from pathlib import Path
    
    img = Image.open(input_path)
    
    # Original PNG
    img.save("/output/image.png")
    
    # Auto-converted to JPEG
    img.save("/output/image.jpg", quality=95)
    
    # Auto-converted to WebP
    img.save("/output/image.webp", quality=95)
    
    return {"formats": ["png", "jpeg", "webp"]}

result = image_converter("input.png")
print(result.artifacts["image.png"])
print(result.artifacts["image.jpg"])
print(result.artifacts["image.webp"])
```

### Custom Conversion

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./workspace")
@dependencies("pandas")
def format_converter(input_file: str, output_format: str):
    """Convert between data formats."""
    import pandas as pd
    from pathlib import Path
    
    # Read input (auto-detect format)
    if input_file.endswith('.csv'):
        df = pd.read_csv(input_file)
    elif input_file.endswith('.json'):
        df = pd.read_json(input_file)
    elif input_file.endswith('.xlsx'):
        df = pd.read_excel(input_file)
    
    # Write output in desired format
    if output_format == 'csv':
        df.to_csv("/output/data.csv", index=False)
    elif output_format == 'json':
        df.to_json("/output/data.json", orient='records')
    elif output_format == 'parquet':
        df.to_parquet("/output/data.parquet")
    
    return {"format": output_format, "rows": len(df)}

result = format_converter("input.csv", "parquet")
```

---

## Output Validation

### Schema Validation

```python
from isolated_agents_sdk import isolated_agent, validate_output

@isolated_agent(working_dir="./workspace")
@validate_output(
    schema={
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "email": {"type": "string", "format": "email"}
        },
        "required": ["name", "age", "email"]
    }
)
@dependencies("jsonschema")
def validated_json_generator(data: dict):
    """Generate JSON with schema validation."""
    from pathlib import Path
    import json
    
    # Output is automatically validated against schema
    Path("/output/data.json").write_text(json.dumps(data, indent=2))
    return data

result = validated_json_generator({
    "name": "Alice",
    "age": 30,
    "email": "alice@example.com"
})
```

### Content Validation

```python
from isolated_agents_sdk import isolated_agent, validate_output

@isolated_agent(working_dir="./workspace")
@validate_output(
    validators=[
        ("image/png", lambda path: Path(path).stat().st_size < 10*1024*1024),  # Max 10MB
        ("image/png", lambda path: Image.open(path).size[0] <= 4096)  # Max width 4096px
    ]
)
@dependencies("pillow")
def validated_image_generator(prompt: str):
    """Generate image with validation."""
    from PIL import Image
    from pathlib import Path
    
    img = Image.new('RGB', (1024, 1024), color='blue')
    img.save("/output/image.png")
    
    return {"format": "image/png"}

result = validated_image_generator("Generate image")
```

---

## Advanced Patterns

### Multi-Format Output

Generate multiple output formats simultaneously:

```python
from isolated_agents_sdk import isolated_agent, multi_format_output

@isolated_agent(working_dir="./workspace")
@multi_format_output(
    formats=["text/plain", "text/markdown", "text/html", "application/pdf"]
)
@dependencies("langchain", "langchain-openai", "markdown", "reportlab")
def multi_format_generator(content: str):
    """Generate content in multiple formats."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    import markdown
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    
    llm = ChatOpenAI(model="gpt-4")
    result = llm.invoke(f"Format this content: {content}")
    
    # Plain text
    Path("/output/content.txt").write_text(result.content)
    
    # Markdown
    Path("/output/content.md").write_text(f"# Content\n\n{result.content}")
    
    # HTML
    html = markdown.markdown(result.content)
    Path("/output/content.html").write_text(f"<html><body>{html}</body></html>")
    
    # PDF
    c = canvas.Canvas("/output/content.pdf", pagesize=letter)
    c.drawString(100, 750, result.content[:100])
    c.save()
    
    return {
        "formats": ["text", "markdown", "html", "pdf"],
        "primary": "text/plain"
    }

result = multi_format_generator("Important content")
print(result.artifacts["content.txt"])
print(result.artifacts["content.md"])
print(result.artifacts["content.html"])
print(result.artifacts["content.pdf"])
```

### Progressive Output

Generate output progressively for long-running tasks:

```python
from isolated_agents_sdk import isolated_agent, progressive_output

@isolated_agent(working_dir="./workspace")
@progressive_output(interval=5.0)  # Update every 5 seconds
@dependencies("langchain", "langchain-openai")
def progressive_generator(topic: str):
    """Generate content progressively."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    import time
    
    llm = ChatOpenAI(model="gpt-4")
    
    sections = ["Introduction", "Main Content", "Conclusion"]
    full_content = ""
    
    for section in sections:
        result = llm.invoke(f"Write {section} about: {topic}")
        full_content += f"\n\n## {section}\n\n{result.content}"
        
        # Progressive update
        Path("/output/content.md").write_text(full_content)
        time.sleep(1)
    
    return {"sections": len(sections)}

result = progressive_generator("AI Safety")
```

### Composite Output

Combine multiple outputs into a single package:

```python
from isolated_agents_sdk import isolated_agent, composite_output

@isolated_agent(working_dir="./workspace")
@composite_output(
    structure={
        "report": "text/markdown",
        "data": "application/json",
        "chart": "image/png",
        "summary": "text/plain"
    }
)
@dependencies("langchain", "langchain-openai", "matplotlib", "pandas")
def composite_generator(topic: str):
    """Generate composite output package."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    import matplotlib.pyplot as plt
    import json
    
    llm = ChatOpenAI(model="gpt-4")
    
    # Generate report
    report = llm.invoke(f"Write report about: {topic}")
    Path("/output/report.md").write_text(report.content)
    
    # Generate data
    data = {"topic": topic, "metrics": [1, 2, 3, 4, 5]}
    Path("/output/data.json").write_text(json.dumps(data, indent=2))
    
    # Generate chart
    plt.plot(data["metrics"])
    plt.savefig("/output/chart.png")
    plt.close()
    
    # Generate summary
    summary = llm.invoke(f"Summarize: {report.content}")
    Path("/output/summary.txt").write_text(summary.content)
    
    return {
        "components": ["report", "data", "chart", "summary"],
        "format": "composite"
    }

result = composite_generator("AI Safety")
print(result.artifacts["report.md"])
print(result.artifacts["data.json"])
print(result.artifacts["chart.png"])
print(result.artifacts["summary.txt"])
```

---

## Best Practices

### 1. **Choose Appropriate Formats**
- Use text formats for human-readable content
- Use binary formats for efficiency
- Use structured formats for data interchange
- Consider compression for large outputs

### 2. **Validate Outputs**
- Validate format correctness
- Check file sizes and dimensions
- Verify data integrity
- Use schema validation for structured data

### 3. **Handle Large Outputs**
- Use streaming for large files
- Implement progressive output for long tasks
- Consider chunking and pagination
- Use efficient formats (Parquet, WebP, etc.)

### 4. **Support Multiple Formats**
- Provide format conversion options
- Generate multiple formats when needed
- Use auto-detection for flexibility
- Document supported formats

### 5. **Optimize Performance**
- Use appropriate compression
- Cache converted formats
- Minimize format conversions
- Use efficient libraries

---

## Summary

The Isolated Agents SDK provides comprehensive multimodal output support:

1. **Text Formats** - Plain text, Markdown, HTML, LaTeX
2. **Image Formats** - PNG, JPEG, SVG, WebP
3. **Audio Formats** - MP3, WAV, FLAC
4. **Video Formats** - MP4, WebM, AVI
5. **Document Formats** - PDF, DOCX, XLSX
6. **Structured Data** - JSON, YAML, CSV, Parquet
7. **Binary Formats** - ZIP, SQLite, HDF5
8. **Streaming** - Large file streaming, progressive output
9. **Conversion** - Automatic and custom format conversion
10. **Validation** - Schema and content validation

These capabilities enable agents to generate any type of output while maintaining isolation, security, and observability.

---

**Next Steps:**
- Review [COMPOSABILITY.md](COMPOSABILITY.md) for agent composition patterns
- See [DECORATORS.md](DECORATORS.md) for decorator details
- Check [FRAMEWORK_COMPATIBILITY.md](FRAMEWORK_COMPATIBILITY.md) for framework integration