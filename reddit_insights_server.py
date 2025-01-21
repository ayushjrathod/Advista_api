from fastapi import FastAPI, Request,HTTPException
from fastapi.responses import JSONResponse

from fastapi.middleware.cors import CORSMiddleware
import requests
import json
import string
from bs4 import BeautifulSoup
from fastapi.responses import FileResponse
from nltk import word_tokenize, pos_tag
from wordcloud import WordCloud
from collections import Counter
import os
import logging

# Create FastAPI application
app = FastAPI()
logger = logging.getLogger(__name__)

# Allow all CORS (for demo purposes; consider restricting in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def fetch_search_results(query):
    """
    Fetch search results from Google Custom Search for a given query.
    """
    api_key = "AIzaSyA0NrKuXw2vuZytqHrN4TLXo1dN3Q7dLeg"
    search_engine_id = "1764ec36a096143aa"
    url = "https://www.googleapis.com/customsearch/v1"

    params = {
        "key": api_key,
        "cx": search_engine_id,
        "q": query,
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        results = response.json()
        return results
    except requests.exceptions.RequestException as e:
        print(f"Error fetching search results: {e}")
        return None

def extract_readable_content(link):
    """
    Extract readable text (paragraphs) from a given link using BeautifulSoup.
    """
    try:
        response = requests.get(link)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        paragraphs = soup.find_all('p')
        readable_text = "\n".join(p.get_text() for p in paragraphs if p.get_text().strip())
        return readable_text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching content from {link}: {e}")
        return None

def is_valid_body(body):
    """
    Check if a comment body is valid: not empty, not '[deleted]'/'[removed]', and has at least 5 words.
    """
    if not body or body == "[deleted]" or body == "[removed]":
        return False
    words = body.split()
    return len(words) >= 5

def fetch_reddit_comments(link, depth=3):
    """
    Fetch Reddit comments from the provided link, up to a specified depth.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(link + ".json", headers=headers)
        response.raise_for_status()
        reddit_data = response.json()

        # Extract post information
        post_data = reddit_data[0]["data"]["children"][0]["data"]
        post_info = {
            "title": post_data.get("title"),
            "author": post_data.get("author"),
            "score": post_data.get("score", 0),
            "upvote_ratio": post_data.get("upvote_ratio", 0),
            "body": post_data.get("selftext", "")
        }

        def parse_comments(comments, current_depth):
            if current_depth > depth or not comments:
                return []
            parsed_comments = []
            for comment in comments:
                if "body" in comment.get("data", {}):
                    comment_data = comment["data"]
                    parsed_comments.append({
                        "author": comment_data.get("author"),
                        "body": comment_data.get("body"),
                        "score": comment_data.get("score", 0),
                        "controversial": comment_data.get("controversiality", 0),
                        "is_submitter": comment_data.get("is_submitter", False),
                        "edited": bool(comment_data.get("edited")),
                        "replies": parse_comments(
                            comment_data.get("replies", {}).get("data", {}).get("children", []),
                            current_depth + 1
                        ) if comment_data.get("replies") else []
                    })
            return parsed_comments

        comments = reddit_data[1]["data"]["children"]
        return {
            "post": post_info,
            "comments": parse_comments(comments, 1)
        }
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Reddit comments from {link}: {e}")
        return None

def clean_text(text):
    """
    Remove punctuation and extra spaces from the provided text.
    """
    cleaned_text = text.translate(str.maketrans('', '', string.punctuation))
    cleaned_text = ' '.join(cleaned_text.split())
    return cleaned_text
def send_data_to_api(api_key, model, content):
    """
    Send the processed data to the Groq API endpoint with enhanced error handling.
    """
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": content
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()  # Raise an exception for bad status codes
        
        response_data = response.json()
        
        # Check if response contains error
        if 'error' in response_data:
            logger.error(f"Groq API Error: {response_data['error']}")
            return None
            
        # Validate response structure
        if 'choices' not in response_data or not response_data['choices']:
            logger.error("Invalid response structure from Groq API")
            return None
            
        return response_data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {str(e)}")
        if hasattr(e.response, 'text'):
            logger.error(f"Response text: {e.response.text}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON response: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in Groq API call: {str(e)}")
        return None

def process_reddit_data(product_query: str) -> str:
    """Process Reddit data with enhanced error handling"""
    try:
        results = fetch_search_results(product_query)
        if not results or "items" not in results:
            logger.error("No items from Google Custom Search.")
            return None

        all_comments = []
        for item in results["items"]:
            logger.info(f"Processing link: {item.get('link')}")
            if "reddit.com" in item.get("link", ""):
                reddit_data = fetch_reddit_comments(item["link"])
                if reddit_data:
                    valid_comments = [
                        comment["body"]
                        for comment in reddit_data["comments"]
                        if is_valid_body(comment.get("body", ""))
                    ]
                    all_comments.extend(valid_comments)

        if not all_comments:
            logger.error("No valid comments found.")
            return None

        cleaned_comments = clean_text(" ".join(all_comments))
        prompt = (
            "Based on these Reddit comments, analyze and list the key factors "
            "that influenced people's purchasing decisions:\n\n"
            f"{cleaned_comments}\n\n"
            "Provide your analysis in a clear, structured format."
        )

        # Validate API key presence
        groq_api_key = os.getenv("GROQ_API_KEY", "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")
        if not groq_api_key:
            logger.error("No Groq API key found")
            return None

        model = "llama-3.3-70b-versatile"
        response = send_data_to_api(groq_api_key, model, prompt)
        
        if not response:
            return None
            
        analysis = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not analysis:
            logger.error("No analysis content in Groq response")
            return None
            
        return analysis

    except Exception as e:
        logger.error(f"Error processing Reddit data: {str(e)}")
        return None
@app.post("/reddit-insights")
async def reddit_insights(payload: dict):
    """
    POST endpoint that takes a JSON body with 'product': 'string',
    fetches Reddit insights, processes the data, and returns
    the Groq API response.
    """
    # Extract the product type or category from the request
    product_query = payload.get("product", "").strip()
    if not product_query:
        return {"error": "Please provide a valid product query."}
    
    # Process Reddit data and get insights
    insights = process_reddit_data(product_query)
    if not insights:
        return {"error": "No insights found for the given product query."}
    
    # Return the insights to the client
    return insights

JSON_FILE_PATH = "comments_with_link.json"

@app.get("/generate-bow")
async def generate_bow():
    """
    Endpoint to generate a Bag of Words (BoW) from comments in the JSON file and return the counts as JSON.
    """
    try:
        # Check if the JSON file exists
        if not os.path.exists(JSON_FILE_PATH):
            raise HTTPException(status_code=404, detail="JSON file not found.")

        # Extract comments and concatenate them into a single text
        concatenated_text = extract_comments_and_concatenate_from_json(JSON_FILE_PATH)

        # Check if there is any content in the text
        if not concatenated_text.strip():
            raise HTTPException(status_code=400, detail="No comments found in the JSON file.")

        # Generate the Bag of Words (BoW)
        bow_counts = generate_bow_counts(concatenated_text)

        # Return the BoW counts as a JSON response
        return JSONResponse(content=bow_counts)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def extract_comments_and_concatenate_from_json(file_path):
    """
    Reads a JSON file, extracts all comments, and concatenates them into a single text.
    """
    concatenated_comments = ""

    with open(file_path, 'r') as file:
        # Load the JSON data
        data = json.load(file)

        # Iterate through each entry and extract comments
        for entry in data:
            if 'comments' in entry:
                concatenated_comments += " ".join(entry['comments']) + " "

    return concatenated_comments

def keep_only_nouns_and_adjectives(text):
    """
    Filters text to keep only nouns and adjectives, excluding pronouns and irrelevant symbols.
    """
    pronouns = {
        "i", "me", "my", "mine", "myself",
        "you", "your", "yours", "yourself", "yourselves",
        "he", "him", "his", "himself",
        "she", "her", "hers", "herself",
        "it", "its", "itself",
        "we", "us", "our", "ours", "ourselves",
        "they", "them", "their", "theirs", "themselves",
        "this", "that", "these", "those", "'", "ve", ".", "*", ","
    }

    # Convert text to lowercase
    text = text.lower()

    # Tokenize the text
    tokens = word_tokenize(text)

    # Perform POS tagging
    tagged_tokens = pos_tag(tokens)

    # Keep only nouns and adjectives, excluding pronouns
    filtered_tokens = [
        word for word, pos in tagged_tokens
        if (pos.startswith('NN') or pos.startswith('JJ')) and word not in pronouns
    ]

    return filtered_tokens

def generate_bow_counts(text):
    """
    Generates a Bag of Words (BoW) frequency distribution from the text.
    """
    # Filter text to keep only nouns and adjectives
    filtered_tokens = keep_only_nouns_and_adjectives(text)

    # Build a bag of words (frequency distribution)
    bow_counts = Counter(filtered_tokens)

    return dict(bow_counts) 