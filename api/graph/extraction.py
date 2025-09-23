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
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1)

async def extract_graph_from_texts_gemini(texts: list[str]) -> dict:
    """
    Extracts entities and relationships from a list of texts using the Gemini 2.0 Flash model.
    This optimized function performs both tasks in a single, efficient API call.
    """
    if not texts:
        return {"entities": [], "relations": []}

    # Create a batch of texts to process to minimize API calls
    batched_text = "\n\n---\n\n".join(texts[:5])  # Limit to first 5 texts to avoid token limits

    parser = JsonOutputParser()

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert at extracting knowledge graphs from financial texts. 
        Your task is to identify entities and meaningful relationships between them.
        Always return valid JSON with both "entities" and "relations" arrays, even if they're empty."""),
        ("human",
            """
            From the following financial text, extract entities and their relationships.
            Return a JSON object with "entities" and "relations" arrays.

            **ENTITY RULES:**
            - Extract companies, people, products, locations, money amounts, dates, laws/regulations
            - Each entity needs "name" and "type" fields
            - Types: ORG, PERSON, PRODUCT, MONEY, DATE, LAW, GPE (location), PERCENT

            **RELATIONSHIP RULES:**
            - Each relationship needs "entity1", "relationship", and "entity2"
            - Relationships should be specific action verbs in CAPS: ACQUIRED, PARTNERED_WITH, LAUNCHED, INVESTED_IN, APPOINTED_AS, SUPPLIES, COMPETES_WITH
            - Don't use generic verbs like "has", "is", "are"
            - Only include relationships explicitly mentioned in the text

            **EXAMPLE:**
            Text: "Apple acquired StartupX for $100 million. Tim Cook announced the deal."
            
            Output:
            {{
                "entities": [
                    {{"name": "Apple", "type": "ORG"}},
                    {{"name": "StartupX", "type": "ORG"}},
                    {{"name": "$100 million", "type": "MONEY"}},
                    {{"name": "Tim Cook", "type": "PERSON"}}
                ],
                "relations": [
                    {{"entity1": "Apple", "relationship": "ACQUIRED", "entity2": "StartupX"}},
                    {{"entity1": "Apple", "relationship": "PAID", "entity2": "$100 million"}},
                    {{"entity1": "Tim Cook", "relationship": "ANNOUNCED", "entity2": "deal"}}
                ]
            }}

            Now process this text:
            {text}

            Return only valid JSON:
            """
        )
    ])

    chain = prompt | llm | parser

    try:
        with get_openai_callback() as cb:
            response = await chain.ainvoke({"text": batched_text})
            
            # Validate the response structure
            if not isinstance(response, dict):
                print(f"Invalid response type: {type(response)}")
                return {"entities": [], "relations": []}
                
            if "entities" not in response:
                response["entities"] = []
            if "relations" not in response:
                response["relations"] = []
                
            print(f"Gemini extracted {len(response.get('entities', []))} entities and {len(response.get('relations', []))} relations")
            
            # Debug: Print sample relationships
            relations = response.get('relations', [])
            if relations:
                print("Sample relationships from Gemini:")
                for i, rel in enumerate(relations[:3]):
                    print(f"  {i+1}: {rel}")
            else:
                print("No relationships extracted by Gemini")
                
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