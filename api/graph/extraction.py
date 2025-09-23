# api/graph/extraction.py
import asyncio
import json
from itertools import combinations
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from token_logger import log_token_usage
from langchain_community.callbacks import get_openai_callback

# Initialize the Gemini 2.0 Flash model
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.1)

async def extract_graph_from_texts_gemini(texts: list[str]) -> dict:
    """
    Extracts entities and relationships from a list of texts using the Gemini 2.0 Flash model.
    This optimized function performs both tasks in a single, efficient API call.
    """
    if not texts:
        return {"entities": [], "relations": []}

    # Create a batch of texts to process to minimize API calls
    batched_text = "\n\n---\n\n".join(texts)

    parser = JsonOutputParser()

    prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert at extracting a knowledge graph from financial texts. Your task is to identify entities and the specific, meaningful relationships between them."),
    ("human",
        """
        From the following text, extract all financial entities and their relationships.
        Format the output as a single JSON object with "entities" and "relations".

        - "entities" should be a list of objects, each with "name" and "type" (e.g., ORG, PERSON, PRODUCT, MONEY, LAW).
        - "relations" should be a list of objects, each with "entity1", "relationship", and "entity2".

        **CRITICAL INSTRUCTIONS FOR RELATIONSHIPS:**
        1.  The "relationship" MUST be a single, descriptive word in `ALL_CAPS_SNAKE_CASE`.
        2.  Examples of good relationships: `ACQUIRED`, `PARTNERED_WITH`, `LAUNCHED`, `INVESTED_IN`, `HAS_CEO`.
        3.  DO NOT use generic verbs like "is", "has", or "are".

        **Example:**
        Text: "Apple announced a new partnership with Goldman Sachs to launch a credit card. The deal is valued at $100 million."
        Output:
        {{
            "entities": [
                {{"name": "Apple", "type": "ORG"}},
                {{"name": "Goldman Sachs", "type": "ORG"}},
                {{"name": "credit card", "type": "PRODUCT"}},
                {{"name": "$100 million", "type": "MONEY"}}
            ],
            "relations": [
                {{"entity1": "Apple", "relationship": "PARTNERED_WITH", "entity2": "Goldman Sachs"}},
                {{"entity1": "Apple", "relationship": "LAUNCHED", "entity2": "credit card"}},
                {{"entity1": "partnership", "relationship": "VALUED_AT", "entity2": "$100 million"}}
            ]
        }}

        Text to process:
        {text}

        {format_instructions}
        """
    )
    ])

    chain = prompt | llm | parser

    try:
        with get_openai_callback() as cb:
            response = await chain.ainvoke({"text": batched_text, "format_instructions": parser.get_format_instructions()})
            log_token_usage(
                model_name="gemini-2.0-flash",
                input_tokens=cb.prompt_tokens,
                output_tokens=cb.completion_tokens,
                total_tokens=cb.total_tokens,
                purpose="knowledge_graph_extraction"
            )
        return response
    except Exception as e:
        print(f"An error occurred during Gemini graph extraction: {e}")
        return {"entities": [], "relations": []}