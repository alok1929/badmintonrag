import queue
import pyaudio
from google.cloud import speech
import os
from google.oauth2 import service_account
import pandas as pd
from openai import OpenAI
from pinecone import Pinecone
import re
from dotenv import load_dotenv

load_dotenv()

# Setup clients for recommendation engine


def setup_clients():
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
        price_match = re.findall(r'\d+(?:,\d+)?', query)
        if price_match:
            price_limit = float(price_match[0].replace(',', ''))

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
                        price = float(price_str.replace(
                            '₹', '').replace(',', ''))
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


def process_query_and_get_recommendations(query_text):
    """Process a query and return top 5 racket recommendations"""
    # Setup clients
    openai_client, pinecone_index = setup_clients()

    # Process query
    results = query_similar_rackets(query_text, openai_client, pinecone_index)

    # Display results
    print("\nRecommended rackets for your query:")
    print(f"Query: '{query_text}'")
    for match in results.matches:
        print_racket_details(match)


def stream_audio_to_text():
    # Load credentials from the working directory
    try:
        # Load credentials from environment or file path
        credentials_path = os.path.join(
            os.path.dirname(__file__), 'credentials.json')
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        speech_client = speech.SpeechClient(credentials=credentials)
    except Exception as e:
        print(f"Error initializing Google Speech-to-Text client: {str(e)}")
        raise RuntimeError("Failed to initialize Google Speech-to-Text client")

    # Audio recording parameters
    RATE = 16000
    CHUNK = int(RATE / 10)  # 100ms chunks

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code="en-US",
        enable_automatic_punctuation=True,
    )

    streaming_config = speech.StreamingRecognitionConfig(
        config=config,
        interim_results=True
    )

    # Create a thread-safe queue for audio data
    audio_queue = queue.Queue()

    def audio_callback(in_data, frame_count, time_info, status):
        audio_queue.put(in_data)
        return None, pyaudio.paContinue

    # Initialize PyAudio
    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK,
        stream_callback=audio_callback
    )

    def audio_generator():
        while True:
            chunk = audio_queue.get()
            if chunk is None:
                break
            yield speech.StreamingRecognizeRequest(audio_content=chunk)

    try:
        stream.start_stream()
        print("Listening for your racket query... Speak clearly.")
        print("Press Ctrl+C when you've finished your query to get recommendations")
        print("Example: 'I need a lightweight racket for beginners under 5000 rupees'")

        # Send the audio stream to Google Speech-to-Text
        requests = audio_generator()
        responses = speech_client.streaming_recognize(
            streaming_config, requests)

        current_transcript = ""

        # Process the responses
        for response in responses:
            if not response.results:
                continue

            result = response.results[0]
            if not result.alternatives:
                continue

            transcript = result.alternatives[0].transcript

            if result.is_final:
                current_transcript = transcript
                print(f"\nCurrent transcript: {current_transcript}")
            else:
                print(
                    f"\rInterim transcript: {transcript}", end="", flush=True)

    except KeyboardInterrupt:
        print("\n\nProcessing your query...")
        if current_transcript:
            process_query_and_get_recommendations(current_transcript)
        else:
            print("No query detected. Please try again.")
    finally:
        # Clean up
        stream.stop_stream()
        stream.close()
        p.terminate()
        audio_queue.put(None)


if __name__ == "__main__":
    # Just make sure credentials.json is in the same directory as this script
    print("Badminton Racket Recommendation System - Voice Edition")
    print("======================================================")
    print("This system will listen to your query and recommend the top 5 rackets.")
    stream_audio_to_text()
