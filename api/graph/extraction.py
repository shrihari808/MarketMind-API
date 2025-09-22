# api/graph/extraction.py
from transformers import pipeline, AutoTokenizer
from itertools import combinations
import json
import torch
from tqdm import tqdm

def extract_entities(texts: list[str]) -> list:
    """
    Extracts named entities from a list of texts using a fine-tuned BERT model.
    """
    device = 0 if torch.cuda.is_available() else -1
    print(f"NER pipeline using device: {'cuda' if device == 0 else 'cpu'}")

    ner_pipeline = pipeline("ner", model="dslim/bert-base-NER", aggregation_strategy="simple", device=device)
    all_entities = []
    # Use tqdm for a progress bar during entity extraction
    for text in tqdm(texts, desc="Extracting Entities"):
        if not text or not text.strip():
            continue
        try:
            entities = ner_pipeline(text)
            for entity in entities:
                entity['source_text'] = text
            all_entities.extend(entities)
        except Exception as e:
            print(f"Skipping text due to NER pipeline error: {e}")
    return all_entities

def classify_relations(entity_pairs: list, texts: list[str]) -> list:
    """
    Classifies the relationship between pairs of entities using a finance-tuned model.
    This version is optimized for speed with GPU usage, batch processing, and pre-filtering.
    """
    device = 0
    print(f"Relation classification pipeline using device: {'cuda' if device == 0 else 'cpu'}")

    model_name = "yseop/distilbert-base-financial-relation-extraction"
    relation_classifier = pipeline("text-classification", model=model_name, return_all_scores=False, device=device)
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    max_model_len = tokenizer.model_max_length

    inputs_to_process = []
    original_pairs = []

    print(f"Pre-filtering {len(entity_pairs)} pairs...")
    for entity1, entity2 in entity_pairs:
        if 'source_text' not in entity1 or 'source_text' not in entity2 or entity1['source_text'] != entity2['source_text']:
            continue
        
        source_text = entity1['source_text']
        ent1_text = entity1['word']
        ent2_text = entity2['word']

        try:
            start_pos1 = source_text.index(ent1_text)
            start_pos2 = source_text.index(ent2_text)
            context_start = min(start_pos1, start_pos2)
            context_end = max(start_pos1 + len(ent1_text), start_pos2 + len(ent2_text))
            
            remaining_space = max_model_len - (len(tokenizer.tokenize(ent1_text)) + len(tokenizer.tokenize(ent2_text)) + 4)
            if remaining_space < 0: continue

            padding = remaining_space // 2
            window_start = max(0, context_start - padding)
            window_end = min(len(source_text), context_end + padding)
            snippet = source_text[window_start:window_end]

            input_text = f"{ent1_text} [SEP] {ent2_text} [SEP] {snippet}"
            inputs_to_process.append(input_text)
            original_pairs.append((entity1, entity2))

        except ValueError:
            continue
    
    print(f"Processing {len(inputs_to_process)} valid pairs in mini-batches...")

    relations = []
    if inputs_to_process:
        # Use a batch_size for more efficient processing and add a tqdm progress bar
        batch_size = 32 
        for result, (entity1, entity2) in tqdm(zip(relation_classifier(inputs_to_process, truncation=True, max_length=max_model_len, batch_size=batch_size), original_pairs), total=len(inputs_to_process), desc="Classifying Relations"):
            if result['score'] > 0.6 and result['label'] != 'no_relation':
                relations.append({
                    "entity1": entity1['word'],
                    "relationship": result['label'],
                    "entity2": entity2['word'],
                    "score": result['score']
                })

    return relations

if __name__ == '__main__':
    sample_texts = [
        "Reliance Industries has partnered with TechCorp to streamline their logistics, a deal valued at over $50 million.",
        "Microsoft reports $56B revenue in Q2, while their competitor Apple also saw strong growth."
    ]
    
    print("--- Step 1: Extracting Entities ---")
    entities = extract_entities(sample_texts)
    print("Entities:", json.dumps(entities, indent=2))

    print("\n--- Step 2: Classifying Relationships ---")
    entity_pairs = list(combinations(entities, 2))
    relations = classify_relations(entity_pairs, sample_texts)
    print("Relations:", json.dumps(relations, indent=2))