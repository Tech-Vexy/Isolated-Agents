import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def rag_agent():
    """RAG agent with FAISS vector store."""
    import os as _os
    import pathlib as _pathlib
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_community.vectorstores import FAISS
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.chains import RetrievalQA
    
    # Check for API keys
    use_groq = bool(_os.environ.get("GROQ_API_KEY"))
    
    if use_groq:
        from langchain_groq import ChatGroq
        llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
        # For embeddings with Groq, we'd need another provider or local.
        # For this example, let's try to use a very small local embedding if possible,
        # or just fail if OpenAI is needed but missing.
        # However, for simplicity in this SDK example, we'll assume OpenAI if not Groq.
        # If the user only has Groq, they might need an embedding model.
        # Let's use a mock embedding if we just want to test the plumbing, 
        # or use HuggingFace if they have it.
        try:
            from langchain_community.embeddings import DeterministicFakeEmbedding
            embeddings = DeterministicFakeEmbedding(size=1536)
        except ImportError:
            from langchain_openai import OpenAIEmbeddings
            embeddings = OpenAIEmbeddings()
    else:
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        llm = ChatOpenAI(model="gpt-4", temperature=0)
        embeddings = OpenAIEmbeddings()
    
    # Load documents
    docs_path = _pathlib.Path("/workspace/documents")
    
    if not docs_path.exists() or not list(docs_path.glob("*.txt")):
        docs_path.mkdir(parents=True, exist_ok=True)
        (docs_path / "sample1.txt").write_text(
            "Artificial Intelligence is transforming how we work and live. "
            "Machine learning enables computers to learn from data."
        )
        (docs_path / "sample2.txt").write_text(
            "Natural Language Processing allows computers to understand human language. "
            "It powers chatbots, translation, and text analysis."
        )
    
    documents = []
    for file in docs_path.glob("*.txt"):
        documents.append(file.read_text())
    
    if not documents:
        raise ValueError("No documents found to process")
    
    # Split documents
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    splits = text_splitter.create_documents(documents)
    
    print(f"[*] Split {len(documents)} documents into {len(splits)} chunks")
    
    # Create vector store
    vectorstore = FAISS.from_documents(splits, embeddings)
    
    # Create QA chain
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=vectorstore.as_retriever(),
        return_source_documents=True
    )
    
    # Query
    query = "What are the main topics in these documents?"
    result = qa_chain.invoke({"query": query})
    
    # Save results
    output_dir = _pathlib.Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    (output_dir / "answer.txt").write_text(result["result"])
    (output_dir / "sources.txt").write_text(
        "\n\n".join([doc.page_content for doc in result["source_documents"]])
    )
    (output_dir / "metadata.txt").write_text(
        f"Query: {query}\n"
        f"Documents processed: {len(documents)}\n"
        f"Chunks created: {len(splits)}\n"
        f"Sources retrieved: {len(result['source_documents'])}\n"
    )
    
    print(f"[*] Processed {len(documents)} documents")
    print(f"[*] Retrieved {len(result['source_documents'])} relevant sources")


if __name__ == "__main__":
    from isolated_agents_sdk import run_agent, Policy, NetworkPolicy
    
    # Check for API keys
    use_groq = bool(os.environ.get("GROQ_API_KEY"))
    use_openai = bool(os.environ.get("OPENAI_API_KEY"))
    
    if not (use_groq or use_openai):
        print("Error: Neither GROQ_API_KEY nor OPENAI_API_KEY set", file=sys.stderr)
        sys.exit(1)
    
    provider = "Groq" if use_groq else "OpenAI"
    
    # Create directories
    workspace = Path("./workspace/documents")
    workspace.mkdir(parents=True, exist_ok=True)
    
    host_output = Path("./output")
    host_output.mkdir(exist_ok=True)
    
    print(f"Launching RAG agent using {provider} in isolated container...")
    
    # Prepare policy configuration
    allowed_endpoints = [
        "pypi.org:443", 
        "files.pythonhosted.org:443"
    ]
    if use_groq:
        allowed_endpoints.append("api.groq.com:443")
    else:
        allowed_endpoints.append("api.openai.com:443")
        
    allowed_env_vars = ["GROQ_API_KEY", "OPENAI_API_KEY"]
    pip_packages = [
        "langchain==0.3.7", 
        "langchain-community", 
        "faiss-cpu", 
        "numpy<2.0.0" # FAISS/LangChain sometimes sensitive to numpy 2.0
    ]
    if use_groq:
        pip_packages.append("langchain-groq")
    else:
        pip_packages.append("langchain-openai")
    
    # Run agent in isolated container
    result = run_agent(
        agent=rag_agent,
        working_dir="./workspace",
        host_output_path=host_output,
        policy=Policy(
            cpu_cores=4.0,
            memory_mb=2048,
            network=NetworkPolicy(
                disabled=False,
                allowed_endpoints=allowed_endpoints
            ),
            allowed_env_vars=allowed_env_vars,
            pip_packages=pip_packages,
        )
    )
    
    print(f"\n[*] Agent completed with exit code {result.exit_code}")
    
    if result.artifacts:
        print(f"\nOutput artifacts:")
        for name, path in result.artifacts.items():
            size = Path(path).stat().st_size
            print(f"  • {name} ({size} bytes)")
        
        # Display answer
        answer_path = result.artifacts.get("answer.txt")
        if answer_path:
            print(f"\nAnswer:\n{Path(answer_path).read_text()}")
    
    sys.exit(result.exit_code)
