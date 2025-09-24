# aigptssh/api/graph/neo4j_importer.py
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

class KnowledgeGraphImporter:
    def __init__(self, uri, user, password):
        if not all([uri, user, password]):
            raise ValueError("Neo4j credentials not found in .env file.")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def upsert_event(self, event):
        with self.driver.session() as session:
            session.execute_write(self._upsert_event_transaction, event)

    @staticmethod
    def _upsert_event_transaction(tx, event):
        event_name = event.get("event_name")
        event_type = event.get("event_type")
        event_date = event.get("date")
        summary = event.get("summary")
        amount = event.get("amount")
        sector = event.get("sector")
        confidence = event.get("confidence")
        entities = event.get("entities", [])

        # 1. Create or merge the Event node
        event_query = """
        MERGE (e:Event {name: $event_name})
        ON CREATE SET e.type = $event_type, e.date = $event_date, e.summary = $summary, e.amount = $amount, e.sector = $sector, e.confidence = $confidence
        """
        tx.run(event_query, event_name=event_name, event_type=event_type, event_date=event_date, summary=summary, amount=amount, sector=sector, confidence=confidence)

        # 2. Create or merge entity nodes and relationships
        for entity_name in entities:
            # For simplicity, we'll model all entities as 'Company' for now.
            # A more advanced implementation would determine the entity type.
            entity_query = """
            MERGE (c:Company {name: $entity_name})
            WITH c
            MATCH (e:Event {name: $event_name})
            MERGE (c)-[:INVOLVED_IN]->(e)
            """
            tx.run(entity_query, entity_name=entity_name, event_name=event_name)