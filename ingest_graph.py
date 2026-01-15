import json
import re
import time
from neo4j import GraphDatabase
from openai import OpenAI

# --- CONFIGURATION ---
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
MODEL_NAME = "model-identifier"  # Ensure this matches your loaded model

# Update with your Neo4j credentials
NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "" # Put your password here


class EduGraphManager:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self.verify_connection()

    def verify_connection(self):
        try:
            self.driver.verify_connectivity()
            print("Connected to Neo4j successfully.")
        except Exception as e:
            print(f"Failed to connect to Neo4j: {e}")

    def close(self):
        self.driver.close()

    def setup_constraints(self):
        """Ensures that concept names are unique to prevent duplicates."""
        with self.driver.session() as session:
            # Create constraint (syntax may vary slightly by Neo4j version, this is standard 4.x/5.x)
            try:
                session.run("CREATE CONSTRAINT concept_name IF NOT EXISTS FOR (c:Concept) REQUIRE c.name IS UNIQUE")
                print("Unique constraints configured.")
            except Exception as e:
                print(f"Constraint setup note: {e}")

    def query(self, cypher_query, parameters=None):
        with self.driver.session() as session:
            session.run(cypher_query, parameters)

    def build_concept(self, concept, definition, related_concept=None, relation_type=None):
        """Creates a node and an optional relationship in Neo4j."""
        # 1. Merge the main concept
        cypher = """
        MERGE (c:Concept {name: $name})
        ON CREATE SET c.definition = $definition
        ON MATCH SET c.definition = $definition
        """
        self.query(cypher, {"name": concept, "definition": definition})

        # 2. If there is a prerequisite, handle the relationship
        if related_concept and relation_type:
            # Ensure the related node exists (even as a placeholder)
            self.query("MERGE (r:Concept {name: $related})", {"related": related_concept})

            # Create the relationship
            rel_cypher = f"""
            MATCH (a:Concept {{name: $name}}), (b:Concept {{name: $related}})
            MERGE (a)-[:{relation_type}]->(b)
            """
            self.query(rel_cypher, {"name": concept, "related": related_concept})
            print(f"   🔗 Linked '{concept}' -> REQUIRES -> '{related_concept}'")


# --- LLM EXTRACTION LOGIC ---
def extract_graph_data(text):
    prompt = f"""
    Analyze the educational text below and extract a list of concepts.
    For each concept, identify:
    1. "concept": The name of the concept.
    2. "definition": A short summary.
    3. "prerequisite": The name of a concept that is REQUIRED to understand this one (if mentioned).

    TEXT: {text}

    OUTPUT FORMAT:
    Provide ONLY a valid JSON list of objects. Do not add markdown blocks or conversational text.
    Example:
    [
      {{"concept": "A", "definition": "Def A", "prerequisite": "B"}},
      {{"concept": "B", "definition": "Def B", "prerequisite": null}}
    ]
    """

    print("Asking Local LLM to extract entities...")
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "system", "content": "You are a Knowledge Graph extraction engine."},
                  {"role": "user", "content": prompt}],
        temperature=0
    )

    raw_content = response.choices[0].message.content.strip()

    # Robust Regex Extraction to find the JSON List
    try:
        match = re.search(r'(\[.*\])', raw_content, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        else:
            # Fallback for single objects not in a list
            match_obj = re.search(r'(\{.*\})', raw_content, re.DOTALL)
            if match_obj:
                return [json.loads(match_obj.group(1))]
    except json.JSONDecodeError:
        print(f"JSON Parse Error. Raw Output: {raw_content}")
        return []

    return []


# --- EXECUTION ---
if __name__ == "__main__":
    graph = EduGraphManager()

    # 1. Setup Database
    graph.setup_constraints()

    # 2. Richer Text with a Dependency Chain
    # Chain: Cellular Respiration -> Glucose -> Photosynthesis -> Light Energy -> Energy
    expanded_text = """
    To understand how life works, we must start with **Cellular Respiration**, the process where cells generate power. 
    However, Cellular Respiration requires **Glucose** as a fuel source to burn. 
    Where does Glucose come from? It is created through **Photosynthesis** in plants. 
    But Photosynthesis cannot occur without **Light Energy** from the sun driving the reaction. 
    Finally, to understand any of this, one must grasp the fundamental concept of **Energy**, defined as the capacity to do work.
    """

    # 3. Extract
    entities = extract_graph_data(expanded_text)

    if not entities:
        print("No entities found. Check LLM output.")
    else:
        print(f"Extracted {len(entities)} concepts.")

    # 4. Ingest into Neo4j
    for item in entities:
        print(f"Processing: {item['concept']}")

        # Determine prerequisite (handle None/Null values)
        prereq = item.get('prerequisite')
        if prereq and prereq.lower() == 'none':
            prereq = None

        graph.build_concept(
            concept=item['concept'],
            definition=item['definition'],
            related_concept=prereq,
            relation_type="REQUIRES" if prereq else None
        )

    graph.close()
    print("\nGraph Ingestion Complete!")
    print("Open Neo4j Browser and run: MATCH (n) RETURN n")