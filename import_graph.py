import json
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

# --- Load credentials from .env file ---
load_dotenv()

# --- Neo4j Connection Details from Environment ---
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

class KnowledgeGraphImporter:
    def __init__(self, uri, user, password):
        if not all([uri, user, password]):
            raise ValueError("Neo4j credentials not found in .env file. Please check your configuration.")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def import_graph(self, json_data):
        with self.driver.session() as session:
            # Check for constraint
            constraints = session.run("SHOW CONSTRAINTS").data()
            if not any(c['name'] == 'constraint_entity_id' for c in constraints):
                session.run("CREATE CONSTRAINT constraint_entity_id FOR (n:Entity) REQUIRE n.id IS UNIQUE;")

            # Import nodes
            session.execute_write(self._create_nodes, json_data["graph"]["nodes"])

            # Import relationships
            session.execute_write(self._create_relationships, json_data["graph"]["edges"])

    @staticmethod
    def _create_nodes(tx, nodes):
        query = """
        UNWIND $nodes AS node
        MERGE (e:Entity {id: node.id})
        SET e.type = node.type, e.mentions = node.mentions
        """
        tx.run(query, nodes=nodes)

    @staticmethod
    def _create_relationships(tx, edges):
        # --- THIS IS THE CORRECTED QUERY ---
        # It now uses toLower() to match nodes regardless of case.
        query = """
        UNWIND $edges AS edge
        MATCH (source:Entity) WHERE toLower(source.id) = toLower(edge.source)
        MATCH (target:Entity) WHERE toLower(target.id) = toLower(edge.target)
        CALL apoc.create.relationship(source, edge.label, {}, target) YIELD rel
        RETURN count(rel)
        """
        tx.run(query, edges=edges)

if __name__ == '__main__':
    with open('graph_output.json', 'r', encoding='utf-8') as f:
        graph_data = json.load(f)

    importer = KnowledgeGraphImporter(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    importer.import_graph(graph_data)
    importer.close()

    print("✅ Graph data re-imported successfully with all relationships!")