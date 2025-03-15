import pandas as pd
import os
from openai import OpenAI
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def setup_openai_client():
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OpenAI API key not found in environment variables")
    return OpenAI(api_key=api_key)


def get_racket_details_batch(client, racket_names, batch_size=20):
    """Process multiple rackets in a single API call"""

    racket_list = "\n".join([f"- {name}" for name in racket_names])
    prompt = f"""
    For each of these badminton rackets, provide:
    1. A one-line description of key features
    2. Typical weight in grams
    3. Recommended player level (Beginner/Intermediate/Advanced)

    Rackets:
    {racket_list}

    Format your response as CSV with no headers:
    racket_name,description,weight,player_level
    """

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a badminton equipment expert. Provide concise details in CSV format."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )

        # Parse CSV response
        results = []
        lines = response.choices[0].message.content.strip().split('\n')
        for line in lines:
            parts = line.split(',')
            if len(parts) >= 4:
                results.append({
                    # Changed from 'Name' to 'Defensive Rackets'
                    'Defensive Rackets': parts[0],
                    'Description': parts[1],
                    'Weight': parts[2],
                    'Player_Level': parts[3]
                })
        return results

    except Exception as e:
        print(f"Error processing batch: {str(e)}")
        return []


def process_excel_file():
    EXCEL_FILE = "defensive.xlsx"
    BATCH_SIZE = 20  # Process 20 rackets per API call

    # Read the Excel file
    df = pd.read_excel(EXCEL_FILE)
    client = setup_openai_client()

    # Initialize new columns
    df['Description'] = ''
    df['Weight'] = ''
    df['Player_Level'] = ''

    # Process in batches
    for i in range(0, len(df), BATCH_SIZE):
        # Changed from 'Name' to 'Defensive Rackets'
        batch = df['Defensive Rackets'].iloc[i:i+BATCH_SIZE].tolist()
        print(
            f"Processing batch {i//BATCH_SIZE + 1}/{(len(df) + BATCH_SIZE - 1)//BATCH_SIZE}")

        results = get_racket_details_batch(client, batch)

        # Update dataframe with results
        for result in results:
            # Changed from 'Name' to 'Defensive Rackets'
            mask = df['Defensive Rackets'] == result['Defensive Rackets']
            df.loc[mask, 'Description'] = result['Description']
            df.loc[mask, 'Weight'] = result['Weight']
            df.loc[mask, 'Player_Level'] = result['Player_Level']

        # Save after each batch in case of interruption
        df.to_excel(EXCEL_FILE, index=False)
        print(f"Saved progress after batch {i//BATCH_SIZE + 1}")

        # Add delay between batches
        time.sleep(2)

    print("Processing complete!")


if __name__ == "__main__":
    process_excel_file()
