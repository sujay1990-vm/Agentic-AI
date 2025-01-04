import sqlite3
import json
from langchain.agents import Tool, create_react_agent, AgentExecutor
from langchain.memory import ConversationBufferMemory
from langchain.tools import tool
from langchain_openai import AzureChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain import hub

OPENAI_DEPLOYMENT_ENDPOINT = "https://az-openai-document-question-answer-service.openai.azure.com/" 
OPENAI_API_KEY = "5d24331966b648738e5003caad552df8" 
OPENAI_API_VERSION = "2023-05-15"

OPENAI_DEPLOYMENT_NAME = "az-gpt_35_model"
OPENAI_MODEL_NAME="gpt-3.5-turbo"

OPENAI_ADA_EMBEDDING_DEPLOYMENT_NAME = "az-embedding_model" 
OPENAI_ADA_EMBEDDING_MODEL_NAME = "text-embedding-ada-002"

encoding_name = "cl100k_base"
# OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
# CHROMA_PATH = "c:\\Users\\SujaySunilNagvekar\\VM\\GEN AI\\SERFF\\vector_db\\neil_db"
# data_folder = "C:\\Users\\SujaySunilNagvekar\\VM\\GEN AI\\SERFF\\new_files"
csv_file = "C:\\Users\\SujaySunilNagvekar\\VM\\GEN AI\\Parker\\vm-GenAI_BI\\Text to SQL_V1\\Nurse_notes_parker.csv"
### Cohere API key 
db_file = "nurse_notes.db"

# Step 1: Initialize LLM
llm = AzureChatOpenAI(
                        temperature=0.1,
                        deployment_name=OPENAI_DEPLOYMENT_NAME,
                        model_name=OPENAI_MODEL_NAME,
                        azure_endpoint=OPENAI_DEPLOYMENT_ENDPOINT,
                        openai_api_version=OPENAI_API_VERSION,
                        openai_api_key=OPENAI_API_KEY            
                    )

# Step 2: Connect to SQLite Database
def connect_db(db_file):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    return conn, cursor

# Step 3: Extract Dynamic Schema
def extract_schema(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    schema = []
    for column in columns:
        schema.append({
            "Column Name": column[1],
            "Data Type": column[2],
            "Nullable": 'YES' if column[3] == 0 else 'NO',
            "Primary Key": 'YES' if column[5] > 0 else 'NO'
        })
    return schema

# Step 4: Generate Metadata for Tables
def extract_metadata(cursor, table_name):
    cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]

    metadata = []
    for col in columns:
        example_values = []
        for row in rows:
            idx = [i for i, desc in enumerate(cursor.description) if desc[0] == col]
            if idx:  # Check if index exists
                example_values.append(row[idx[0]] if row[idx[0]] is not None else "NULL")

        metadata.append({
            "Column Name": col,
            "Examples": example_values[:3]
        })
    return metadata

# Step 5: Process Multiple Tables
def process_all_tables(db_file):
    conn, cursor = connect_db(db_file)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    schema_info = {}
    metadata_info = {}

    for table in tables:
        table_name = table[0]
        schema_info[table_name] = extract_schema(cursor, table_name)
        metadata_info[table_name] = extract_metadata(cursor, table_name)

    conn.close()
    return schema_info, metadata_info

# Step 6: Save Schema and Metadata
def save_schema_metadata(schema, metadata):
    with open('schema.json', 'w') as schema_file:
        json.dump(schema, schema_file, indent=4)

    with open('metadata.json', 'w') as metadata_file:
        json.dump(metadata, metadata_file, indent=4)

# Step 7: Query Execution Tool
@tool
# Example Tool: SQL Query Executor
def query_sqlite(query: str) -> str:
    """Executes SQL query and returns results."""
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    try:
        cursor.execute(query)
        result = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        conn.close()
        return str([dict(zip(columns, row)) for row in result])
    except sqlite3.Error as e:
        conn.close()
        return f"SQL error: {e}"




# Step 8: Agent Setup
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

tools = [
    Tool(
        name="Query SQLite",
        func=query_sqlite,
        description="Use this tool to execute SQL queries on the database. Input must be a valid SQL query."
    )
]

agent = initialize_agent(
    tools, llm, agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION, verbose=True, memory=memory
)

# Step 9: Main Execution
def main():
    db_file = "claims.db"
    schema, metadata = process_all_tables(db_file)

    print("Schema Extracted Successfully!")
    print(json.dumps(schema, indent=4))

    print("Metadata Extracted Successfully!")
    print(json.dumps(metadata, indent=4))

    save_schema_metadata(schema, metadata)

    # Query the agent
    while True:
        query = input("Ask a question: ")
        if query.lower() in ['exit', 'quit']:
            break
        response = agent.run(query)
        print("Response:", response)

if __name__ == "__main__":
    main()
