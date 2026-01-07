import pandas as pd

# Load the RAG file
df = pd.read_csv("data/rag_historic_data.csv")

# Print all columns sorted so we can find the matching one
print("--- RAG FILE COLUMNS ---")
for col in sorted(df.columns):
    print(f"'{col}'")