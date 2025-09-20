# api/graph/extraction.py
from transformers import pipeline
from config import GPT4o_mini as llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

def extract_entities_and_relations(texts: list[str]) -> tuple[list, list]:
    """
    Extracts entities and relations from a list of texts.
    """
    # 1. Entity Extraction with RoBERTa NER
    ner_pipeline = pipeline("ner", model="Jean-Baptiste/roberta-large-ner-english")
    entities = []
    for text in texts:
        entities.extend(ner_pipeline(text))

    # 2. Relation Extraction with a Fine-tuned BERT
    # NOTE: A pre-trained relation extraction model might not be readily available for your specific use case.
    # You might need to fine-tune one yourself. For this example, we will simulate this step.
    # In a real-world scenario, you would use a model from the Hugging Face Hub.
    relations = [] # This would be populated by your relation extraction model.

    return entities, relations

def extract_complex_events(texts: list[str]) -> list[dict]:
    """
    Uses an LLM to extract complex supply chain events from texts.
    """
    complex_events = []
    parser = JsonOutputParser()
    prompt = ChatPromptTemplate.from_template(
        """
        Analyze the following text and identify any complex supply chain events or relationships.
        The output should be a JSON object with "event_type" and "involved_companies".

        Text: {text}

        {format_instructions}
        """,
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    chain = prompt | llm | parser

    for text in texts:
        try:
            response = chain.invoke({"text": text})
            complex_events.append(response)
        except Exception as e:
            print(f"LLM extraction failed: {e}")
            continue

    return complex_events

if __name__ == '__main__':
    # Example usage
    sample_texts = [
        "Reliance Industries has partnered with TechCorp to streamline their logistics.",
        "A fire at a key supplier's factory has disrupted the supply chain for Auto Inc."
    ]
    entities, relations = extract_entities_and_relations(sample_texts)
    print("Entities:", entities)
    print("Relations:", relations)

    complex_events = extract_complex_events(sample_texts)
    print("Complex Events:", complex_events)