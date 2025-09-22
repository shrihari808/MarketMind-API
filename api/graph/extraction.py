# api/graph/extraction.py
from transformers import pipeline
from itertools import combinations
import json

def extract_entities(texts: list[str]) -> list:
    """
    Extracts named entities from a list of texts using a fine-tuned BERT model.
    """
    ner_pipeline = pipeline("ner", model="dslim/bert-base-NER", grouped_entities=True)
    all_entities = []
    for text in texts:
        # The grouped_entities=True option aggregates word pieces (like ##corp) into a single entity.
        entities = ner_pipeline(text)
        # We add the source text to each entity for context in the next step.
        for entity in entities:
            entity['source_text'] = text
        all_entities.extend(entities)
    return all_entities

def classify_relations(entity_pairs: list, texts: list[str]) -> list:
    """
    Classifies the relationship between pairs of entities using a finance-tuned model.
    """
    relation_classifier = pipeline("text-classification", model="yseop/distilbert-base-financial-relation-extraction", return_all_scores=False)
    
    relations = []
    for entity1, entity2 in entity_pairs:
        # The model expects input in the format: "entity1 [SEP] entity2 [SEP] text"
        # We find the common source text for the entity pair.
        source_text = ""
        if 'source_text' in entity1 and 'source_text' in entity2 and entity1['source_text'] == entity2['source_text']:
            source_text = entity1['source_text']
        else:
            # Fallback: find a text that contains both entities if they came from different chunks
            for text in texts:
                if entity1['word'] in text and entity2['word'] in text:
                    source_text = text
                    break
        
        if not source_text:
            continue

        input_text = f"{entity1['word']} [SEP] {entity2['word']} [SEP] {source_text}"
        
        # Get the relationship with the highest score
        result = relation_classifier(input_text)
        
        # The model returns a list, we take the first element.
        if result:
            top_result = result[0]
            # We only consider relationships with a confidence score above a certain threshold
            if top_result['score'] > 0.8 and top_result['label'] != 'no_relation':
                relations.append({
                    "entity1": entity1['word'],
                    "relationship": top_result['label'],
                    "entity2": entity2['word'],
                    "score": top_result['score']
                })
                
    return relations

if __name__ == '__main__':
    # Example usage
    sample_texts = [
        "Reliance Industries has partnered with TechCorp to streamline their logistics.",
        "Microsoft reports $56B revenue in Q2."
    ]
    
    print("--- Step 1: Extracting Entities ---")
    entities = extract_entities(sample_texts)
    print("Entities:", json.dumps(entities, indent=2))

    print("\n--- Step 2: Classifying Relationships ---")
    # Create pairs of entities found in the text
    entity_pairs = list(combinations(entities, 2))
    relations = classify_relations(entity_pairs, sample_texts)
    print("Relations:", json.dumps(relations, indent=2))