# run_pipeline.py

import asyncio
import os
import json
from itertools import combinations
from dotenv import load_dotenv
from api.graph.data_ingestion import get_relevant_text
from api.graph.extraction import extract_entities, classify_relations

load_dotenv()

def normalize_entity_name(name):
    """
    A simple function to normalize entity names for resolution.
    """
    name = name.lower()
    suffixes = ['inc.', 'ltd.', 'corp.', 'corporation', 'limited', 'llc', 'pvt ltd']
    for suffix in suffixes:
        name = name.replace(suffix, '')
    return name.strip()

# --- Main Orchestration Function ---
async def run_full_pipeline(company_name: str):
    """
    Orchestrates the entire data ingestion and graph population pipeline using a two-step extraction process.
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

    # --- Step 2: Two-Step Entity and Relation Extraction ---
    print("\n[Step 2/3] Extracting entities and relationships from text...")
    try:
        # Step 2a: Extract all entities from the texts
        entities = extract_entities(relevant_texts)
        print(f"Extracted {len(entities)} initial entities.")

        # Step 2b: Create pairs of entities (focusing on ORG) and classify their relationships
        # We create pairs where at least one entity is an organization to focus on corporate relationships.
        org_entities = [e for e in entities if e['entity_group'] == 'ORG']
        other_entities = [e for e in entities if e['entity_group'] != 'ORG']
        
        entity_pairs = []
        # Pairs of two organizations
        entity_pairs.extend(list(combinations(org_entities, 2)))
        # Pairs of an organization and another entity type
        for org in org_entities:
            for other in other_entities:
                entity_pairs.append((org, other))

        print(f"Generated {len(entity_pairs)} entity pairs for relation classification.")
        relationships = classify_relations(entity_pairs, relevant_texts)
        
        print(f"Extracted {len(relationships)} high-confidence relationships.")

    except Exception as e:
        print(f"Error during data extraction: {e}")
        return

    # --- Step 3: Entity Resolution and Graph-like JSON Structuring ---
    print("\n[Step 3/3] Resolving entities and structuring data as a graph...")
    
    nodes = {}
    edges = []

    # Process entities to create nodes
    for entity in entities:
        normalized_name = normalize_entity_name(entity['word'])
        if normalized_name not in nodes:
            nodes[normalized_name] = {"id": normalized_name, "type": entity['entity_group'], "mentions": 1}
        else:
            nodes[normalized_name]["mentions"] += 1
            
    # Process relationships to create edges
    for rel in relationships:
        source = normalize_entity_name(rel["entity1"])
        target = normalize_entity_name(rel["entity2"])
        
        if source not in nodes:
            nodes[source] = {"id": source, "type": "Unknown", "mentions": 1}
        if target not in nodes:
            nodes[target] = {"id": target, "type": "Unknown", "mentions": 1}
            
        edges.append({
            "source": source,
            "target": target,
            "label": rel["relationship"],
            "score": rel["score"]
        })

    output_data = {
        "company": company_name,
        "graph": {
            "nodes": list(nodes.values()),
            "edges": edges
        }
    }
    
    # We will return the JSON data to be used by the API endpoint
    print("\n--- Pipeline Finished ---")
    return output_data

# --- Run the Pipeline ---
if __name__ == "__main__":
    target_company = "Tata steel"
    
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    # In a real application, you would call this from your API endpoint.
    # For testing, we can run it here and print the result.
    result = asyncio.run(run_full_pipeline(target_company))
    print(json.dumps(result, indent=4))