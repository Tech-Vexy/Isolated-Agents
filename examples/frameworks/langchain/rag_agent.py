"""LangChain RAG agent with FAISS vector store.

This example demonstrates:
- Document loading and splitting
- FAISS vector store creation
- Retrieval-Augmented Generation (RAG)
- Source document tracking

Usage:
    export OPENAI_API_KEY=sk-...
    # Place documents in ./workspace/documents/
    python examples/frameworks/langchain/rag_agent.py
"""

import os
import sys
from pathlib import Path


def rag_agent():
    """RAG agent with FAISS vector store."""
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from langchain_community.vectorstores import FAISS
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.chains import RetrievalQA
    from pathlib import Path
    
    # Load documents
    docs_path = Path("/workspace/documents")
    documents = []
    
    if not docs_path.exists():
        print("No documents directory found, creating sample documents...")
        docs_path.mkdir(parents=True, exist_ok=True)
        (docs_path / "sample1.txt").write_text(
            "Artificial Intelligence is transforming how we work and live. "
            "Machine learning enables computers to learn from data."
        )
        (docs_path / "sample2.txt").write_text(
            "Natural Language Processing allows computers to understand human language. "
            "It powers chatbots, translation, and text analysis."
        )
    
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
    
    print(f"Split {len(documents)} documents into {len(splits)} chunks")
    
    # Create vector store
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_documents(splits, embeddings)
    
    # Create QA chain
    llm = ChatOpenAI(model="gpt-4")
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=vectorstore.as_retriever(),
        return_source_documents=True
    )
    
    # Query
    query = "What are the main topics in these documents?"
    result = qa_chain({"query": query})
    
    # Save results
    output_dir = Path("/output")
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
    
    print(f"✓ Processed {len(documents)} documents")
    print(f"✓ Retrieved {len(result['source_documents'])} relevant sources")


if __name__ == "__main__":
    from isolated_agents_sdk import run_agent, Policy, NetworkPolicy
    
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    # Create directories
    workspace = Path("./workspace/documents")
    workspace.mkdir(parents=True, exist_ok=True)
    
    host_output = Path("./output")
    host_output.mkdir(exist_ok=True)
    
    print("Launching RAG agent in isolated container...")
    
    result = run_agent(
        agent=rag_agent,
        working_dir="./workspace",
        host_output_path=host_output,
        policy=Policy(
            cpu_cores=4.0,
            memory_mb=2048,
            network=NetworkPolicy(disabled=False),
            allowed_env_vars=["OPENAI_API_KEY"],
            pip_packages=["langchain", "langchain-openai", "langchain-community", "faiss-cpu"],
        )
    )
    
    print(f"\n✓ Agent completed with exit code {result.exit_code}")
    
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

# Made with Bob
