# run_pipeline.py
import asyncio
import os
import json
from dotenv import load_dotenv
from api.graph.data_ingestion import get_relevant_text
from api.graph.extraction import extract_graph_from_texts_gemini # Updated import

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

# Words that are often misidentified as entities
STOP_WORDS = {
    'r', 'n', 'has', 'is', 'x', 'in', 'are', 'the', 'a', 'an', 'company', 'and', 'or', 'of', 'for', 'on',
    'with', 'as', 'at', 'by', 'from', 'about', 'to', 'its', 'it', 'he', 'she', 'they', 'them', 'that', 'this',
    'what', 'which', 'who', 'when', 'where', 'why', 'how', 'new', 'pradesh',
    'enterprise', 'labour', 'gmb', 'unite', 'group', 'power', 'energy', 'products', 'materials'
}

def filter_and_clean_relations(relationships: list) -> list:
    """
    Applies a final filter to remove any remaining nonsensical relationships and duplicates.
    """
    invalid_labels = {'has', 'is', 'was', 'were', 'are', 'is in', 'x'}
    
    cleaned_relations = []
    for rel in relationships:
        # Final check for invalid labels or self-references
        if rel["relationship"].lower() in invalid_labels or normalize_entity_name(rel["entity1"]) == normalize_entity_name(rel["entity2"]):
            continue
        cleaned_relations.append(rel)
    
    # Deduplicate the final list
    unique_relations = []
    seen_relations = set()
    for rel in cleaned_relations:
        rel_key = tuple(sorted((normalize_entity_name(rel['entity1']), normalize_entity_name(rel['entity2'])))) + (rel['relationship'],)
        if rel_key not in seen_relations:
            unique_relations.append(rel)
            seen_relations.add(rel_key)
            
    print(f"Deduplicated and finalized {len(unique_relations)} relationships.")
    return unique_relations

# --- Main Orchestration Function ---
async def run_full_pipeline(company_name: str):
    print(f"--- Starting Knowledge Graph Pipeline for: {company_name} ---")

    # Step 1: Data Ingestion (No changes needed here)
    print("\n[Step 1/3] Fetching and filtering relevant articles...")
    relevant_texts = await get_relevant_text(company_name)
    if not relevant_texts:
        print("No relevant articles found. Exiting.")
        return

    # Step 2: Optimized Extraction with Gemini
    print("\n[Step 2/3] Extracting entities and relationships using Gemini...")
    graph_data = await extract_graph_from_texts_gemini(relevant_texts)
    
    all_entities = graph_data.get("entities", [])
    relationships = graph_data.get("relations", [])
    
    # --- Filter and clean the extracted data ---
    meaningful_entities = [
        e for e in all_entities 
        if len(e['name']) > 1 and normalize_entity_name(e['name']) not in STOP_WORDS
    ]
    print(f"Filtered {len(all_entities)} total entities down to {len(meaningful_entities)} meaningful entities.")
    
    meaningful_relationships = filter_and_clean_relations(relationships)
    print(f"Extracted {len(meaningful_relationships)} final relationships.")

    # Step 3: Structuring
    print("\n[Step 3/3] Structuring data as a graph...")
    nodes = {}
    for entity in meaningful_entities:
        normalized_name = normalize_entity_name(entity['name'])
        if normalized_name not in nodes:
            nodes[normalized_name] = {"id": normalized_name, "type": entity['type'], "mentions": 1}
        else:
            nodes[normalized_name]["mentions"] += 1
    
    edges = [{
        "source": normalize_entity_name(rel["entity1"]),
        "target": normalize_entity_name(rel["entity2"]),
        "label": rel["relationship"],
    } for rel in meaningful_relationships]

    output_data = {"company": company_name, "graph": {"nodes": list(nodes.values()), "edges": edges}}
    
    print("\n--- Pipeline Finished ---")
    return output_data

# --- Run the Pipeline ---
if __name__ == "__main__":
    target_company = "Tata Motors"
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    result = asyncio.run(run_full_pipeline(target_company))
    
    # Save the final, clean output to a file
    output_filename = "graph_output.json"
    if result:
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=4)
        print(f"✅ Successfully saved the knowledge graph to {output_filename}")
    else:
        print("Pipeline did not produce a result. Nothing to save.")