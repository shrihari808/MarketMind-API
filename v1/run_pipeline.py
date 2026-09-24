# aigptssh/run_pipeline.py
import asyncio
import os
import json
from dotenv import load_dotenv
from api.graph.data_ingestion import get_relevant_text
from api.graph.extraction import extract_graph_from_texts_gemini # Updated import
from fuzzywuzzy import process

load_dotenv()

def normalize_entity_name(name):
    """
    A simple function to normalize entity names for resolution.
    """
    if not name or not isinstance(name, str):
        return ""
    name = name.lower().strip()
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
    if not relationships:
        print("No relationships to filter.")
        return []
    
    print(f"Starting with {len(relationships)} raw relationships.")
    
    # Debug: Print first few relationships to see what we're working with
    for i, rel in enumerate(relationships[:3]):
        print(f"  Sample relationship {i+1}: {rel}")
    
    invalid_labels = {'x', '', 'has', 'is', 'are'}
    
    cleaned_relations = []
    for rel in relationships:
        # Check if relationship has required fields
        if not all(key in rel for key in ['entity1', 'entity2', 'relationship']):
            print(f"  Skipping malformed relationship: {rel}")
            continue
            
        entity1 = str(rel["entity1"]).strip()
        entity2 = str(rel["entity2"]).strip()
        relationship = str(rel["relationship"]).strip()
        
        # Skip empty or very short entities
        if len(entity1) < 2 or len(entity2) < 2 or len(relationship) < 2:
            print(f"  Skipping short entities/relationship: {entity1} -> {relationship} -> {entity2}")
            continue
            
        # Skip invalid relationship labels
        if relationship.lower() in invalid_labels:
            print(f"  Skipping invalid relationship label: {relationship}")
            continue
            
        # Skip self-references
        if normalize_entity_name(entity1) == normalize_entity_name(entity2):
            print(f"  Skipping self-reference: {entity1} -> {entity2}")
            continue
            
        # Skip if entities are stop words
        if (normalize_entity_name(entity1) in STOP_WORDS or 
            normalize_entity_name(entity2) in STOP_WORDS):
            print(f"  Skipping stop word entities: {entity1} -> {entity2}")
            continue
            
        cleaned_relations.append({
            'entity1': entity1,
            'entity2': entity2,
            'relationship': relationship
        })
    
    print(f"After cleaning: {len(cleaned_relations)} relationships.")
    
    # Deduplicate the final list
    unique_relations = []
    seen_relations = set()
    for rel in cleaned_relations:
        # Create a key that handles bidirectional relationships
        entities_sorted = tuple(sorted([normalize_entity_name(rel['entity1']), normalize_entity_name(rel['entity2'])]))
        rel_key = entities_sorted + (rel['relationship'].upper(),)
        
        if rel_key not in seen_relations:
            unique_relations.append(rel)
            seen_relations.add(rel_key)
        else:
            print(f"  Removing duplicate: {rel}")
            
    print(f"After deduplication: {len(unique_relations)} relationships.")
    return unique_relations

def resolve_entities(entities: list, threshold=85) -> dict:
    """
    Resolves similar entities using fuzzy matching.
    Returns a dictionary mapping original entity names to a canonical name.
    """
    if not entities:
        return {}

    entity_names = [entity['name'] for entity in entities]
    resolved_entities = {}
    
    for name in entity_names:
        if name in resolved_entities:
            continue

        # Find matches with a score above the threshold
        matches = process.extract(name, entity_names, limit=10)
        canonical_name = name
        
        for match, score in matches:
            if score >= threshold:
                if match not in resolved_entities:
                    resolved_entities[match] = canonical_name
    
    return resolved_entities

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
    
    print(f"Raw graph_data keys: {graph_data.keys() if isinstance(graph_data, dict) else 'Not a dict'}")
    print(f"Raw graph_data: {json.dumps(graph_data, indent=2)[:500]}...")  # First 500 chars for debugging
    
    all_entities = graph_data.get("entities", [])
    relationships = graph_data.get("relations", [])
    
    print(f"Extracted {len(all_entities)} entities and {len(relationships)} relationships from Gemini.")
    
    # --- Filter and clean the extracted data ---
    meaningful_entities = [
        e for e in all_entities 
        if isinstance(e, dict) and 'name' in e and len(str(e['name'])) > 1 and normalize_entity_name(str(e['name'])) not in STOP_WORDS
    ]
    print(f"Filtered {len(all_entities)} total entities down to {len(meaningful_entities)} meaningful entities.")
    
    meaningful_relationships = filter_and_clean_relations(relationships)
    print(f"Extracted {len(meaningful_relationships)} final relationships.")
    
    # --- Entity Resolution ---
    resolved_entity_map = resolve_entities(meaningful_entities)

    # Step 3: Structuring
    print("\n[Step 3/3] Structuring data as a graph...")
    nodes = {}
    
    # First, add all unique entities from relationships to ensure they exist as nodes
    all_entities_in_relations = set()
    for rel in meaningful_relationships:
        all_entities_in_relations.add(rel['entity1'])
        all_entities_in_relations.add(rel['entity2'])
        
    for entity_name in all_entities_in_relations:
        canonical_name = resolved_entity_map.get(entity_name, entity_name)
        normalized_name = normalize_entity_name(canonical_name)
        if normalized_name and normalized_name not in nodes:
            nodes[normalized_name] = {
                "id": canonical_name,
                "type": "Unknown",  # Default type
                "mentions": 0
            }

    for entity in meaningful_entities:
        entity_name = str(entity['name'])
        
        # Use the resolved canonical name
        canonical_name = resolved_entity_map.get(entity_name, entity_name)
        
        normalized_name = normalize_entity_name(canonical_name)
        if normalized_name and normalized_name in nodes:
            nodes[normalized_name]["mentions"] += 1
            # Update type if it was 'Unknown'
            if nodes[normalized_name]["type"] == 'Unknown':
                nodes[normalized_name]["type"] = entity.get('type', 'Unknown')

    edges = []
    for rel in meaningful_relationships:
        # Resolve entities in relationships
        entity1_canonical = resolved_entity_map.get(rel["entity1"], rel["entity1"])
        entity2_canonical = resolved_entity_map.get(rel["entity2"], rel["entity2"])

        source_normalized = normalize_entity_name(entity1_canonical)
        target_normalized = normalize_entity_name(entity2_canonical)
        
        # Only add edge if both entities exist in nodes
        if source_normalized in nodes and target_normalized in nodes:
            edges.append({
                "source": source_normalized,
                "target": target_normalized,
                "label": rel["relationship"],
            })
        else:
            print(f"  Skipping edge due to missing node: {rel['entity1']} -> {rel['entity2']}")

    output_data = {
        "company": company_name, 
        "graph": {
            "nodes": list(nodes.values()), 
            "edges": edges
        }
    }
    
    print(f"Final output: {len(nodes)} nodes, {len(edges)} edges")
    print("\n--- Pipeline Finished ---")
    return output_data

# --- Run the Pipeline ---
if __name__ == "__main__":
    target_company = "Reliance Industries"
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    result = asyncio.run(run_full_pipeline(target_company))
    
    # Save the final, clean output to a file
    output_filename = "graph_output.json"
    if result:
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=4)
        print(f"✅ Successfully saved the knowledge graph to {output_filename}")
    else:
        print("Pipeline did not produce a result. Nothing to save.")