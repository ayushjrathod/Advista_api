import json
import os
import string
from collections import Counter

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from nltk import pos_tag, word_tokenize
from wordcloud import WordCloud

# Create FastAPI application
app = FastAPI()

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

def save_to_file(data, filename, file_format="json"):
    """
    Save data to a file in either JSON or XML format.
    """
    try:
        if file_format == "json":
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        elif file_format == "xml":
            from dicttoxml import dicttoxml
            xml_data = dicttoxml(data, custom_root="results", attr_type=False)
            with open(filename, "wb") as f:
                f.write(xml_data)
        print(f"Data saved to {filename}")
    except Exception as e:
        print(f"Error saving data to file: {e}")

def display_results_and_save_content(results):
    """
    Processes the search results, extracts relevant data, fetches Reddit comments,
    and saves the results in multiple files.
    """
    if not results or "items" not in results:
        print("No results found.")
        return

    extracted_data = []
    all_comments_with_link = []
    print("\nSearch Results:\n")

    for index, item in enumerate(results["items"], start=1):
        title = item.get("title", "No title")
        link = item.get("link", "No link")
        snippet = item.get("snippet", "No description")

        print(f"{index}. {title}")
        print(f"   Link: {link}")
        print(f"   Snippet: {snippet}\n")

        readable_content = extract_readable_content(link)
        reddit_data = fetch_reddit_comments(link) if "reddit.com" in link else None

        if reddit_data:
            # Filter valid comments
            valid_comments = [
                comment["body"]
                for comment in reddit_data["comments"]
                if is_valid_body(comment.get("body", ""))
            ]
            if valid_comments:
                all_comments_with_link.append({
                    "title": title,
                    "link": link,
                    "comments": valid_comments
                })

        current_item = {
            "title": title,
            "link": link,
            "snippet": snippet,
            "readable_content": readable_content,
            "reddit_data": reddit_data,
        }

        extracted_data.append(current_item)

    # Save the complete data to JSON and XML
    save_to_file(extracted_data, "search_results.json", file_format="json")
    save_to_file(extracted_data, "search_results.xml", file_format="xml")

    # Save comments with link
    save_to_file(all_comments_with_link, "comments_with_link.json", file_format="json")

    print(f"\nFound {len(all_comments_with_link)} posts with valid comments")
    print("Complete results saved to search_results.json and search_results.xml")
    print("Comments with links saved to comments_with_link.json")

def clean_text(text):
    """
    Remove punctuation and extra spaces from the provided text.
    """
    cleaned_text = text.translate(str.maketrans('', '', string.punctuation))
    cleaned_text = ' '.join(cleaned_text.split())
    return cleaned_text

def read_and_process_file(file_path):
    """
    Read the JSON file, concatenate comments from the 3rd saved item (index 2),
    then construct the final message with a special prompt at the end.
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
        
    # Caution: data[2] must exist in this file, so ensure the file has at least 3 entries.
    # This is directly from the user-provided code snippet. Adjust as needed.
    all_comments = " ".join(data[0]["comments"])
    cleaned_comments = clean_text(all_comments)
    
    # Construct the final message
    final_message = (
        "read this carefully and answer the question at the end: "
        f"{cleaned_comments} "
        "from this extract, send key triggers that made people buy a specific product"
    )
    return final_message

def send_data_to_api(api_key, model, content):
    """
    Send the processed data to the Groq API endpoint and return the response.
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
    
    response = requests.post(url, headers=headers, data=json.dumps(data))
    return response.json()

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
    
    # Step 1: Fetch search results
    results = fetch_search_results(product_query)
    
    # Step 2: Process and save content to files (including 'comments_with_link.json')
    display_results_and_save_content(results)
    
    # Step 3: Read the 'comments_with_link.json' file, build final prompt
    # (This uses user-provided code that references data[2] in the JSON file.)
    final_message = read_and_process_file("comments_with_link.json")
    
    # Step 4: Send data to the Groq API
    groq_api_key = "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"
    model = "llama-3.3-70b-versatile"
    groq_response = send_data_to_api(groq_api_key, model, final_message)
    
    # Return the Groq API response to the client
    return groq_response

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
