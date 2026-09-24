# aigptssh/api/graph/main.py
from fastapi import APIRouter, HTTPException
from .neo4j_importer import KnowledgeGraphImporter, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from app_service.run_financial_event_pipeline import run_financial_event_pipeline

router = APIRouter()

@router.post("/event_graph/run_pipeline")
async def run_pipeline_endpoint():
    """
    Triggers the full financial event knowledge graph pipeline.
    """
    try:
        await run_financial_event_pipeline()
        return {"message": "Financial event pipeline completed successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/event_graph/get_events")
async def get_events_endpoint():
    """
    Retrieves all events from the knowledge graph.
    """
    if not all([NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD]):
        raise HTTPException(status_code=500, detail="Neo4j credentials not configured.")

    importer = KnowledgeGraphImporter(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    with importer.driver.session() as session:
        result = session.run("MATCH (e:Event) RETURN e.name AS event_name, e.type AS event_type, e.date AS date")
        events = [record.data() for record in result]
    importer.close()
    return {"events": events}