from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_core.output_parsers import JsonOutputParser
from config import embeddings, llm_stream, GPT4o_mini
from langchain.prompts import ChatPromptTemplate
from .document_parser import deconstruct_pdf
from .vision_interpreter import describe_image
from api.security import api_key_auth
import os
import tempfile
import json
import time
from typing import List

router = APIRouter()

SESSION_STORES = {}

async def _is_query_image_related(query: str, image_metadata: list) -> dict:
    if not image_metadata:
        return {"is_related": False, "page_number": None}
    image_context = "\n".join([f"- An image exists on page {item['page_number']}." for item in image_metadata])
    parser = JsonOutputParser()
    prompt = ChatPromptTemplate.from_template(
        """
        You are an expert at routing user questions. A user is asking a question about a document that contains both text and images.
        Determine if the user's query is specifically asking about a chart, graph, or image on a particular page.
        Here are the pages with images:
        {image_context}
        User Query: "{query}"
        If the query refers to an image on a specific page, respond with the page number.
        If the query is general (e.g., "what is the total revenue?"), it is not related to a specific image.
        Respond in JSON format with two keys:
        1. "is_related": boolean (true if the query is about a specific image, otherwise false).
        2. "page_number": integer (the page number mentioned, or null if not related).
        {format_instructions}
        """,
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    chain = prompt | GPT4o_mini | parser
    return await chain.ainvoke({"query": query, "image_context": image_context})

@router.post("/doc_chat")
async def upload_document(
    session_id: str = Form(...),
    user_id: int = Form(...),
    plan_id: int = Form(...),
    prompt_history_id: int = Form(...),
    files: List[UploadFile] = File(...),
    api_key: str = Depends(api_key_auth)
):
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="You can upload a maximum of 5 documents.")

    all_text = ""
    all_images = []
    all_tables = []

    for file in files:
        if not file.filename.endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(await file.read())
            pdf_path = tmp.name
        
        print(f"[{time.strftime('%H:%M:%S')}] PDF saved to temp path: {pdf_path}")
        
        try:
            print(f"[{time.strftime('%H:%M:%S')}] Starting PDF deconstruction for {file.filename}...")
            data = deconstruct_pdf(pdf_path)
            print(f"[{time.strftime('%H:%M:%S')}] Deconstruction complete for {file.filename}. Found {len(data['images'])} images.")
            
            all_text += data["text"]
            all_images.extend(data["images"])
            all_tables.extend(data["tables"])
            
        finally:
            os.remove(pdf_path)

    text_chunks = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200).split_text(all_text)
    table_chunks = [table["data_as_markdown"] for table in all_tables]
    all_text_chunks = text_chunks + table_chunks
    
    print(f"[{time.strftime('%H:%M:%S')}] Creating vector store with {len(all_text_chunks)} text/table chunks...")
    
    vector_store = Chroma.from_texts(texts=all_text_chunks, embedding=embeddings)
    
    SESSION_STORES[session_id] = {
        "vector_store": vector_store,
        "image_metadata": all_images
    }
    
    print(f"[{time.strftime('%H:%M:%S')}] Documents processed. Ready for queries.")
    
    return {"message": f"{len(files)} documents with a total of {len(all_images)} images processed. You can now ask questions."}

@router.post("/doc_chat/query")
async def query_document(
    session_id: str = Form(...),
    query: str = Form(...),
    user_id: int = Form(...),
    plan_id: int = Form(...),
    prompt_history_id: int = Form(...),
    api_key: str = Depends(api_key_auth)
):
    if session_id not in SESSION_STORES:
        raise HTTPException(status_code=404, detail="Session not found. Please upload a document first.")
    
    session_data = SESSION_STORES[session_id]
    vector_store = session_data["vector_store"]
    image_metadata = session_data["image_metadata"]
    
    retriever = vector_store.as_retriever()
    context_docs = retriever.get_relevant_documents(query)
    text_context = "\n\n".join([doc.page_content for doc in context_docs])
    image_context = ""
    
    print(f"[{time.strftime('%H:%M:%S')}] Checking if query is image-related...")
    image_query_check = await _is_query_image_related(query, image_metadata)

    if image_query_check.get("is_related"):
        page_number = image_query_check.get("page_number")
        print(f"[{time.strftime('%H:%M:%S')}] Query is related to an image on page {page_number}. Analyzing now...")
        target_image = next((img for img in image_metadata if img['page_number'] == page_number), None)
        
        if target_image:
            start_vision = time.time()
            image_description = await describe_image(target_image["image_path"])
            end_vision = time.time()
            print(f"[{time.strftime('%H:%M:%S')}] On-demand vision analysis finished in {end_vision - start_vision:.2f} seconds.")
            image_context = f"\n\n--- Analysis of Image on Page {page_number} ---\n{image_description}"
        else:
            print(f"Warning: Query mentioned page {page_number}, but no image was found there.")

    full_context = text_context + image_context
    prompt = ChatPromptTemplate.from_template(
        "You are a helpful assistant. Answer the following question based on the provided document context, which may include text, tables, and analysis of relevant charts.\n\nContext:\n{context}\n\nQuestion: {question}"
    )
    chain = prompt | llm_stream

    async def stream_generator():
        async for chunk in chain.astream({"context": full_context, "question": query}):
            if chunk.content:
                yield chunk.content.encode("utf-8")

    return StreamingResponse(stream_generator(), media_type="text/plain")