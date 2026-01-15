Markdown
# 🎓 Socratic Graph Tutor (LMS-AI)

An intelligent, persistent tutoring system that uses a **Neo4j Knowledge Graph** to enforce prerequisite-based learning. The system acts as a Socratic gatekeeper, ensuring students master fundamental concepts before moving on to complex biological processes.

## 🚀 Overview
Unlike standard chatbots that simply answer questions, this system creates a structured educational path:
1. **Intent Mapping**: Uses the LLM to route natural language to specific nodes in a graph.
2. **Prerequisite Enforcement**: Checks the graph for dependencies (e.g., you cannot learn *Cellular Respiration* without mastering *Glucose*).
3. **Persistent Progress**: Saves a "Mastery Profile" to a local JSON database so progress is never lost between sessions.
4. **Mastery Evaluation**: Acts as an examiner to judge if a student's answer is scientifically accurate.

---

## 🏗 System Architecture & Flow
The following flowchart defines the logic used by the `EduGraphTutor` and the `EduGraphManager`.



```mermaid
graph TD
    A[Student Input] --> B{Topic Extractor}
    B -->|Identify Intent| C[Neo4j Graph Query]
    C --> D{Check Mastery}
    D -->|Prereqs Mastered| E[Expert Explanation Mode]
    D -->|Prereqs Missing| F[Socratic Testing Mode]
    F --> G[Ask Foundations Question]
    G --> H[Student Answer]
    H --> I{LLM Examiner}
    I -->|Pass| J[Update Mastery File/Graph]
    I -->|Fail| K[Provide Hint / Retry]
    J --> E
Step-by-Step Logic:

Ingestion: ingest.py reads a text corpus, uses the LLM to extract entities (Concept, Definition, Prerequisite), and pushes them into Neo4j.

Intent Mapping: When a user asks a question, the AI identifies which Graph Node they are targeting using fuzzy matching.

Graph Traversal: The system performs a Cypher query to find all :REQUIRES relationships for that node.

Gatekeeping: The system compares the graph requirements against the student_progress.json file.

Evaluation: If testing a prerequisite, the LLM runs a "YES/NO" evaluation on the student's input.

📊 Knowledge Graph Visualization
Below is the dependency map currently stored in the Neo4j database:

[REPLACE THIS TEXT WITH YOUR ACTUAL SCREENSHOT] Instructions: Open Neo4j Browser, run MATCH (n)-[r]->(m) RETURN n,r,m, take a screenshot, and upload it to your repository.

🛠 Tech Stack
LLM: Kai-org/glm-4.6v-flash (via LM Studio Local Server)

Graph Database: Neo4j (Cypher Query Language)

Language: Python 3.10+

Persistence: JSON-based State Management

Regex Engine: Used for stripping reasoning tokens (<think> tags) and special tokens.

📖 Key Features
1. The "Modal Trap" Protection

The system detects if a student is struggling or attempting to switch topics during a test. It allows the student to ask "What is [concept]?" or say "I don't know" to receive scaffolding rather than being stuck in a "Try again" loop.

2. Regex Cleaning Pipeline

Because the glm-4.6v-flash model may utilize internal reasoning tokens, the system uses a robust regex pipeline to strip <think> tags and specialized markdown boxes before the student sees the output.

3. Socratic Scaffolding

If a student fails a mastery check, the AI doesn't just give the answer. It pulls the definition directly from the Neo4j node to provide a helpful hint, guiding the student to the correct conclusion.

🚦 Getting Started
Prerequisites

Neo4j Desktop installed and a database running.

LM Studio running the Kai-org/glm-4.6v-flash model with the local server enabled.

Installation

Clone the repo:

Bash
git clone [https://github.com/yourusername/socratic-graph-tutor.git](https://github.com/yourusername/socratic-graph-tutor.git)
cd socratic-graph-tutor
Install dependencies:

Bash
pip install neo4j openai
Run Ingestion:

Bash
python ingest_graph.py
Start Learning:

Bash
python tutor.py
👨‍💻 Author
Jonathon Moore


Would you like me to help you generate a **license file** or a **.gitignore** to
