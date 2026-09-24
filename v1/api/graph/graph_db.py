# api/graph/graph_db.py
from neo4j import GraphDatabase

class KnowledgeGraph:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def add_entity(self, entity_name, entity_type="Company"):
        with self.driver.session() as session:
            session.write_transaction(self._create_entity_node, entity_name, entity_type)

    def add_relation(self, from_entity, to_entity, relation_type):
        with self.driver.session() as session:
            session.write_transaction(self._create_relationship, from_entity, to_entity, relation_type)

    def get_supply_chain(self, company_name):
        with self.driver.session() as session:
            result = session.read_transaction(self._find_supply_chain, company_name)
            return result

    @staticmethod
    def _create_entity_node(tx, entity_name, entity_type):
        query = (
            f"MERGE (a:{entity_type} {{name: $entity_name}})"
        )
        tx.run(query, entity_name=entity_name)

    @staticmethod
    def _create_relationship(tx, from_entity, to_entity, relation_type):
        query = (
            "MATCH (a {name: $from_entity}), (b {name: $to_entity}) "
            f"MERGE (a)-[:{relation_type}]->(b)"
        )
        tx.run(query, from_entity=from_entity, to_entity=to_entity)

    @staticmethod
    def _find_supply_chain(tx, company_name):
        query = (
            "MATCH (supplier)-[:SUPPLIES]->(company:Company {name: $company_name}) "
            "RETURN supplier.name AS supplier"
        )
        result = tx.run(query, company_name=company_name)
        return [record["supplier"] for record in result]

if __name__ == '__main__':
    # Example usage: Replace with your Neo4j credentials
    # NEO4J_URI = "bolt://localhost:7687"
    # NEO4J_USER = "neo4j"
    # NEO4J_PASSWORD = "password"
    # kg = KnowledgeGraph(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    # kg.add_entity("Reliance Industries")
    # kg.add_entity("Supplier A")
    # kg.add_relation("Supplier A", "Reliance Industries", "SUPPLIES")
    # print(kg.get_supply_chain("Reliance Industries"))
    # kg.close()
    pass