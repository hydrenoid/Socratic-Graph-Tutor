import json
import re
import os
from neo4j import GraphDatabase
from openai import OpenAI

# ==========================================
# SETUP
# ==========================================
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
MODEL_NAME = "model-identifier"

NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "" # Put your password here

PROGRESS_FILE = "student_progress.json"


class EduGraphTutor:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self.mastered_nodes = self.load_progress()  # Load previous progress
        self.current_testing_prereq = None

    def close(self):
        self.driver.close()

    # --- PERSISTENCE LOGIC ---
    def load_progress(self):
        """Loads mastered nodes from a local JSON file."""
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r') as f:
                data = json.load(f)
                print(f"Progress loaded. You have mastered: {data}")
                return set(data)
        return set()

    def save_progress(self):
        """Saves mastered nodes to a local JSON file."""
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(list(self.mastered_nodes), f)

    # --- GRAPH & MASTERY OPS ---
    def get_concept_context(self, concept_name):
        query = """
        MATCH (c:Concept) WHERE toLower(c.name) = toLower($name)
        OPTIONAL MATCH (c)-[:REQUIRES]->(p:Concept)
        RETURN c.name as official_name, c.definition as definition, collect(p.name) as prerequisites
        """
        with self.driver.session() as session:
            record = session.run(query, name=concept_name).single()
            return dict(record) if record else None

    def is_mastered(self, concept_name):
        return concept_name.lower() in [m.lower() for m in self.mastered_nodes]

    def mark_mastered(self, concept_name):
        self.mastered_nodes.add(concept_name)
        self.save_progress()  # Save to file immediately
        print(f"[PROGRESS SAVED] '{concept_name}' is now permanent.")

    # --- AI LOGIC ---
    def clean_output(self, text):
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', '', text)
        return text.strip()

    def identify_intent(self, user_input):
        with self.driver.session() as session:
            concepts = [r["name"] for r in session.run("MATCH (c:Concept) RETURN c.name as name")]

        prompt = f"User: '{user_input}'\nConcepts: {concepts}\nIdentify the concept name. Output ONLY the name."
        res = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return self.clean_output(res.choices[0].message.content).replace(".", "")

    def evaluate_answer(self, prerequisite, student_answer):
        prompt = f"Does the answer '{student_answer}' show mastery of '{prerequisite}'? Output ONLY 'YES' or 'NO'."
        res = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": "You are a strict examiner."},
                      {"role": "user", "content": prompt}],
            temperature=0
        )
        return "YES" in self.clean_output(res.choices[0].message.content).upper()

    def chat(self, user_input):
        # 1. Always check the intent first.
        # If the user asks about a DIFFERENT concept, we should let them switch.
        detected_topic = self.identify_intent(user_input)

        # 2. Handle the "Testing Loop"
        if self.current_testing_prereq:
            # ESCAPE HATCH 1: Topic Switch
            # If the user asks about something else (e.g., "Tell me about Light Energy")
            # and it's NOT the thing we are currently testing, let them switch.
            if detected_topic and detected_topic.lower() != self.current_testing_prereq.lower():
                print(f"Switching topics from {self.current_testing_prereq} to {detected_topic}...")
                self.current_testing_prereq = None  # Reset the test
                # Fall through to the standard logic below...

            # ESCAPE HATCH 2: "I don't know" / Help
            # If the user's input looks like a question about the test topic, give a hint.
            elif any(phrase in user_input.lower() for phrase in ["what is", "don't know", "help", "tell me"]):
                # Retrieve definition to give a hint
                ctx = self.get_concept_context(self.current_testing_prereq)
                return f"That's okay! {ctx['definition']}. Now, strictly speaking, how does this relate to the previous topic?"

            else:
                # Proceed with Grading
                if self.evaluate_answer(self.current_testing_prereq, user_input):
                    prev = self.current_testing_prereq
                    self.mark_mastered(prev)
                    self.current_testing_prereq = None
                    return f"Excellent! You've mastered {prev}. What would you like to know about the main topic?"
                else:
                    return f"Not quite. Focus on {self.current_testing_prereq}. (Hint: It's a type of sugar). Try again?"

        # 3. Standard Logic (New Topic)
        target = detected_topic
        context = self.get_concept_context(target)

        if not context:
            return "I don't have that in my graph. Try 'Photosynthesis', 'Glucose', or 'Energy'."

        unmastered = [p for p in context['prerequisites'] if not self.is_mastered(p)]

        print(f"\n{' PERSISTENT STATUS ':~^30}")
        print(f"Current Mastery: {list(self.mastered_nodes)}")
        print(f"Targeting: {target}")
        print(f"{'':~^30}\n")

        if unmastered:
            self.current_testing_prereq = unmastered[0]
            # Fetch the definition of the PREREQUISITE so the tutor asks a good question
            prereq_ctx = self.get_concept_context(self.current_testing_prereq)
            system_msg = f"""
            You are a Socratic Tutor.
            The student wants to learn '{target}', but they must first understand '{self.current_testing_prereq}'.

            Definition of {self.current_testing_prereq}: "{prereq_ctx['definition']}"

            TASK: Ask a simple, foundational question to check if they understand {self.current_testing_prereq}.
            Do not ask about lab tests. Ask about the definition.
            """
        else:
            system_msg = f"Explain {target} using: {context['definition']}"

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": user_input}],
            temperature=0.3
        )
        return self.clean_output(response.choices[0].message.content)


# ==========================================
# EXECUTION
# ==========================================
if __name__ == "__main__":
    tutor = EduGraphTutor()
    print("--- TUTOR ONLINE ---\n")
    while True:
        text = input("Student: ")
        if text.lower() in ['exit', 'quit']: break
        print(f"\nTutor: {tutor.chat(text)}\n")