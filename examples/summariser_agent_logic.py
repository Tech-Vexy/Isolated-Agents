"""Agent logic to be run inside the container."""
import os
import sys
from pathlib import Path

def main():
    # Inside the container, we use these paths
    ws_dir = Path("/workspace")
    out_dir = Path("/output")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Note: We don't import langchain at the top level to avoid import errors 
    # if the container is still installing things (though the SDK handles this).
    from langchain_groq import ChatGroq
    from langchain_core.messages import HumanMessage, SystemMessage

    # Collect text files (limited to first 10 files to avoid size limits)
    exclude_patterns = [".venv", ".git", "__pycache__", "node_modules", ".pytest_cache", "output"]
    
    files = []
    for fp in ws_dir.rglob("*"):
        if len(files) >= 10:
            break
        if fp.is_file() and fp.suffix in (".txt", ".md", ".py"):
            if not any(pattern in str(fp) for pattern in exclude_patterns):
                files.append(fp)
    
    files.sort()

    if not files:
        (out_dir / "summary.md").write_text("No relevant text files found in working directory.\n")
        return

    MAX_CHARS_PER_FILE = 400
    file_sections = []
    for fp in files:
        try:
            content = fp.read_text(errors="replace")[:MAX_CHARS_PER_FILE]
        except Exception as exc:
            content = f"<error reading file: {exc}>"
        
        # In the container, /workspace is the root of the provided workdir
        rel = fp.relative_to(ws_dir)
        file_sections.append(f"### {rel}\n```\n{content}\n```")

    combined = "\n\n".join(file_sections)

    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.environ["GROQ_API_KEY"],
        base_url=os.environ.get("GROQ_API_BASE"),
    )

    messages = [
        SystemMessage(content=(
            "You are a helpful assistant. "
            "Summarise the provided files concisely in Markdown. "
            "Include a one-sentence description of each file."
        )),
        HumanMessage(content=f"Please summarise these files:\n\n{combined}"),
    ]

    response = llm.invoke(messages)
    summary = response.content

    (out_dir / "summary.md").write_text(summary + "\n")
    print("\n--- SUMMARY GENERATED ---\n")
    print(summary)

if __name__ == "__main__":
    main()
