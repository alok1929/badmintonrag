import pandas as pd
from openai import OpenAI
import os
from dotenv import load_dotenv
from pinecone import Pinecone
import re

load_dotenv()


def setup_clients():
    # Initialize OpenAI client
    client = OpenAI(
        api_key=os.getenv('OPENAI_API_KEY')
    )
    pc = Pinecone(
        api_key="pcsk_28oaCA_EprsTrhH2LrKSMQ4MK66KhgpmxTqVopVDAyW6uHmXu5MPt1jnQTVn1YXfpuxXhn")
    index = pc.Index("badminton")

    return client, index


def get_embedding(text, client):
    response = client.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding


def query_similar_rackets(query, openai_client, pinecone_index, k=5):
    # Check if query is about price
    if any(word in query.lower() for word in ['price', 'cost', 'rupees', '₹', 'under', 'below']):
        # Extract the price value from query
        price_limit = float(re.findall(
            r'\d+(?:,\d+)?', query)[0].replace(',', ''))

        # Get more results initially to filter
        query_embedding = get_embedding(query, openai_client)
        initial_results = pinecone_index.query(
            vector=query_embedding,
            top_k=20,  # Get more results to filter
            include_metadata=True
        )

        # Filter results by price
        filtered_matches = []
        for match in initial_results.matches:
            price_str = match.metadata['price']
            if price_str != 'Not available':
                try:
                    price = float(price_str.replace('₹', '').replace(',', ''))
                    if price <= price_limit:
                        filtered_matches.append(match)
                except:
                    continue

        # Return only top k filtered results
        return type('Results', (), {'matches': filtered_matches[:k]})

    # For non-price queries, use normal semantic search
    return pinecone_index.query(
        vector=get_embedding(query, openai_client),
        top_k=k,
        include_metadata=True
    )


def print_racket_details(match):
    """Print detailed racket information"""
    print("\n----------------------------------------")
    print(f"Racket: {match.metadata['name']}")
    print(f"Price: {match.metadata['price']}")
    print(f"Description: {match.metadata['description']}")
    print(f"Weight: {match.metadata['weight']}")
    print(f"Player Level: {match.metadata['player_level']}")
    print(f"Similarity Score: {match.score:.2f}")
    print("----------------------------------------")


def main():
    # Setup clients
    openai_client, pinecone_index = setup_clients()

    while True:
        # Get user query
        user_query = input("\nEnter your search query (or 'exit' to quit): ")
        if user_query.lower() == 'exit':
            break

        # Process query
        results = query_similar_rackets(
            user_query, openai_client, pinecone_index)

        # Display results
        print("\nRecommended rackets:")
        for match in results.matches:
            print_racket_details(match)


if __name__ == "__main__":
    main()
