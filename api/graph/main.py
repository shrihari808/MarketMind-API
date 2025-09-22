# api/graph/main.py
from fastapi import APIRouter, HTTPException
from api.graph.graph_db import KnowledgeGraph
import os
from run_pipeline import run_full_pipeline # Import the pipeline function

router = APIRouter()

# Neo4j credentials from environment variables
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

@router.get("/supply-chain/{company_name}")
async def get_supply_chain_endpoint(company_name: str):
    """
    Retrieves the supply chain for a given company from the knowledge graph.
    """
    try:
        kg = KnowledgeGraph(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        supply_chain = kg.get_supply_chain(company_name)
        kg.close()
        return {"company": company_name, "suppliers": supply_chain}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/full-analysis/{company_name}")
async def get_full_analysis_endpoint(company_name: str):
    """
    Runs the full data ingestion and extraction pipeline for a given company
    and returns the structured graph data as JSON.
    """
    try:
        # Run the entire pipeline and get the structured JSON data
        graph_data = await run_full_pipeline(company_name)
        if not graph_data:
            raise HTTPException(status_code=404, detail="Could not generate analysis for the specified company. No relevant data found.")
        return graph_data
    except Exception as e:
        # Catch any other exceptions from the pipeline
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")