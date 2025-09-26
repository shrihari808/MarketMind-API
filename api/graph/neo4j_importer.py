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

    def get_impacted_sectors(self, event_name):
        """
        Finds all sectors impacted by a specific event.
        """
        with self.driver.session() as session:
            return session.execute_read(self._get_impacted_sectors_transaction, event_name)

    @staticmethod
    def _upsert_event_transaction(tx, event):
        event_name = event.get("event_name")
        event_type = event.get("event_type")
        event_date = event.get("date")
        summary = event.get("summary")
        amount = event.get("amount")
        sector = event.get("sector")
        confidence = event.get("confidence_score") # Corrected key
        entities = event.get("entities", {})

        # 1. Create or merge the Event node
        event_query = """
        MERGE (e:Event {name: $event_name})
        ON CREATE SET e.type = $event_type, e.date = $event_date, e.summary = $summary, e.amount = $amount, e.sector = $sector, e.confidence = $confidence
        ON MATCH SET e.type = $event_type, e.date = $event_date, e.summary = $summary, e.amount = $amount, e.sector = $sector, e.confidence = $confidence
        RETURN e
        """
        tx.run(event_query, event_name=event_name, event_type=event_type, event_date=event_date, summary=summary, amount=amount, sector=sector, confidence=confidence)

        # 2. Create Sector node and relationship if a sector is specified
        if sector:
            sector_query = """
            MATCH (e:Event {name: $event_name})
            MERGE (s:Sector {name: $sector})
            MERGE (e)-[:AFFECTS_SECTOR]->(s)
            """
            tx.run(sector_query, event_name=event_name, sector=sector)

        # 3. Create or merge specific entity nodes and relationships
        if isinstance(entities, dict):
            # Loop through the list of companies
            for company_name in entities.get("companies", []):
                company_query = """
                MERGE (c:Company {name: $company_name})
                WITH c
                MATCH (e:Event {name: $event_name})
                MERGE (c)-[:INVOLVED_IN]->(e)
                """
                tx.run(company_query, company_name=company_name, event_name=event_name)

            # Loop through the list of people
            for person_name in entities.get("people", []):
                person_query = """
                MERGE (p:Person {name: $person_name})
                WITH p
                MATCH (e:Event {name: $event_name})
                MERGE (p)-[:INVOLVED_IN]->(e)
                """
                tx.run(person_query, person_name=person_name, event_name=event_name)

            # Loop through the list of organizations
            for org_name in entities.get("organizations", []):
                org_query = """
                MERGE (o:Organization {name: $org_name})
                WITH o
                MATCH (e:Event {name: $event_name})
                MERGE (o)-[:INVOLVED_IN]->(e)
                """
                tx.run(org_query, org_name=org_name, event_name=event_name)

    @staticmethod
    def _get_impacted_sectors_transaction(tx, event_name):
        """
        Cypher query to find sectors connected to an event.
        """
        query = """
        MATCH (e:Event {name: $event_name})-[:AFFECTS_SECTOR]->(s:Sector)
        RETURN s.name AS sector
        """
        result = tx.run(query, event_name=event_name)
        return [record["sector"] for record in result]

