# run_pipeline.py

import asyncio
import os
from dotenv import load_dotenv
from api.graph.data_ingestion import get_relevant_text
from api.graph.extraction import extract_entities_and_relations, extract_complex_events
from api.graph.graph_db import KnowledgeGraph

load_dotenv()

# --- Main Orchestration Function ---
async def run_full_pipeline(company_name: str):
    """
    Orchestrates the entire data ingestion and graph population pipeline.
    """
    print(f"--- Starting Knowledge Graph Pipeline for: {company_name} ---")

    # --- Step 1: Data Ingestion and Pre-Filtering ---
    print("\n[Step 1/3] Fetching and filtering relevant articles...")
    try:
        relevant_texts = await get_relevant_text(company_name)
        if not relevant_texts:
            print("No relevant articles found after filtering. Exiting.")
            return
        print(f"Found {len(relevant_texts)} relevant articles to process.")
    except Exception as e:
        print(f"Error during data ingestion: {e}")
        return

    # --- Step 2: Entity and Relation Extraction ---
    print("\n[Step 2/3] Extracting entities and relationships from text...")
    try:
        # --- SIMULATED DATA FOR TESTING ---
        entities = [
            {'entity_group': 'ORG', 'word': 'Reliance Industries'},
            {'entity_group': 'ORG', 'word': 'TechCorp Logistics'},
            {'entity_group': 'ORG', 'word': 'Global Petrochem'}
        ]
        simple_relations = [
            {'from': 'TechCorp Logistics', 'to': 'Reliance Industries', 'type': 'PARTNERS_WITH'},
            {'from': 'Global Petrochem', 'to': 'Reliance Industries', 'type': 'SUPPLIES'}
        ]
        
        print(f"Extracted {len(entities)} entities and {len(simple_relations)} relationships.")

    except Exception as e:
        print(f"Error during data extraction: {e}")
        return

    # --- Step 3: Populate the Knowledge Graph ---
    print("\n[Step 3/3] Populating the Neo4j database...")
    NEO4J_URI = os.getenv("NEO4J_URI")
    NEO4J_USER = os.getenv("NEO4J_USER")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

    if not all([NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD]):
        print("Neo4j credentials not found in .env file. Exiting.")
        return

    kg = KnowledgeGraph(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    try:
        # Add entities (nodes)
        for entity in entities:
            if 'word' in entity and isinstance(entity['word'], str):
                entity_name = entity['word'].strip()
                
                # --- THIS IS THE FIX ---
                # Use a consistent "Company" label if the entity is an ORG
                entity_type = "Company" if entity.get('entity_group') == 'ORG' else entity.get('entity_group', 'Unknown')
                
                print(f"  - Adding Entity: {entity_name} (Type: {entity_type})")
                kg.add_entity(entity_name, entity_type)

        # Add relationships (edges)
        for relation in simple_relations:
            print(f"  - Adding Relation: {relation['from']} -> {relation['type']} -> {relation['to']}")
            kg.add_relation(relation['from'], relation['to'], relation['type'])
        
        print("Successfully populated the graph.")
    except Exception as e:
        print(f"Error during graph population: {e}")
    finally:
        kg.close()

    print("\n--- Pipeline Finished ---")

# --- Run the Pipeline ---
if __name__ == "__main__":
    # The company you want to build the graph for
    target_company = "Tata steel"
    
    # --- THIS IS THE FIX for the "Event loop is closed" error on Windows ---
    # Clear the database before running to ensure a fresh start
    print("--- Clearing existing data from the graph ---")
    try:
        # Use the correct environment variables for the KG connection
        kg = KnowledgeGraph(os.getenv("NEO4J_URI"), os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
        with kg.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        print("Database cleared.")
        kg.close()
    except Exception as e:
        print(f"Could not clear database: {e}")
        
    # Set the policy for Windows and run the event loop manually
    if os.name == 'nt': # Check if the OS is Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    # Run the main async function
    asyncio.run(run_full_pipeline(target_company))