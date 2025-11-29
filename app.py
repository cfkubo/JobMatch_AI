from flask import Flask, request, jsonify, render_template
import os
import PyPDF2
import requests
import logging
import json
import re
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration for Ollama (default values, can be overridden)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss") # Changed to gpt-oss

# Configuration for Brave Search API
BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY")

def perform_brave_search(query):
    if not BRAVE_SEARCH_API_KEY:
        raise ValueError("Brave Search API key not configured")

    brave_url = f"https://api.search.brave.com/res/v1/web/search?q={query}"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": BRAVE_SEARCH_API_KEY
    }
    response = requests.get(brave_url, headers=headers)
    response.raise_for_status()
    return response.json()

def call_ollama_api(prompt, model=OLLAMA_MODEL): # Removed format parameter
    url = f"{OLLAMA_BASE_URL}/api/generate"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": model,
        "prompt": prompt,
        "stream": True,  # Enable streaming
        # "format": format # Removed format parameter
    }
    try:
        with requests.post(url, headers=headers, json=data, stream=True) as response:
            response.raise_for_status()
            
            full_response_content = ""
            final_ollama_json = {}

            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        if "response" in chunk:
                            full_response_content += chunk["response"]
                        if chunk.get("done"):
                            final_ollama_json = chunk
                            break # Exit loop once generation is complete
                    except json.JSONDecodeError:
                        logger.warning(f"Could not decode JSON chunk: {line.decode('utf-8')}")
            
            final_ollama_json["response"] = full_response_content
            return final_ollama_json

    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling Ollama API: {e}")
        raise

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload_resume', methods=['POST'])
def upload_resume():
    if 'resume' not in request.files:
        return jsonify({"error": "No resume file provided"}), 400

    resume_file = request.files['resume']
    if resume_file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if resume_file:
        try:
            # For simplicity, let's assume PDF for now
            # In a real app, handle different file types (docx, txt, etc.)
            reader = PyPDF2.PdfReader(resume_file.stream)
            resume_text = ""
            for page in reader.pages:
                resume_text += page.extract_text() or ""
            
            logger.info("Resume parsed successfully.")
            
            return jsonify({"message": "Resume uploaded and parsed successfully", "resume_text": resume_text}), 200

        except Exception as e:
            logger.error(f"Error processing resume: {e}")
            return jsonify({"error": f"Failed to process resume file: {str(e)}"}), 500
    
    return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/api/analyze_resume', methods=['POST'])
def analyze_resume():
    data = request.get_json()
    resume_text = data.get('resume_text')

    if not resume_text:
        return jsonify({"error": "No resume text provided for analysis"}), 400

    try:
        # Example of the expected JSON structure
        json_example = """
        {
            "summary": "Experienced software engineer with expertise in Python, Flask, and cloud platforms.",
            "skills": ["Python", "Flask", "AWS", "Docker", "REST APIs"],
            "industries": ["Tech", "Cloud Computing"],
            "suggested_companies": ["Google", "Amazon", "Microsoft"],
            "suggested_roles": ["Software Engineer", "Backend Developer"]
        }
        """

        prompt = f"""Analyze the following resume.
        **IMPORTANT**: Your response MUST be a single JSON object.
        DO NOT include any conversational text, explanations, markdown code block wrappers (like ```json), or any other formatting outside the JSON object itself.
        The JSON object should adhere to the following structure and contain these fields:

        {json_example}

        Here is the resume text to analyze:
        {resume_text}

        Please return ONLY the JSON object.
        """
        logger.info("Calling Ollama for resume analysis...")
        ollama_response = call_ollama_api(prompt)
        
        analysis_content = ollama_response.get("response", "").strip()
        logger.info(f"Raw Ollama response content: {analysis_content}")

        # Adjusted logic to find the outermost JSON object
        # This regex looks for the first '{' and the last '}' and captures everything in between
        json_match = re.search(r'\{.*\}', analysis_content, re.DOTALL)

        if json_match:
            json_string = json_match.group(0) # group(0) returns the entire matched string
            logger.info(f"Extracted JSON string: {json_string}")
        else:
            json_string = "" # If no JSON object is found, set to empty string
            logger.warning(f"No JSON object found in Ollama response. Attempting to parse raw content: {analysis_content}")
            # If no JSON object was found by regex, it might be that the model returned *pure* JSON
            # In which case, json_string would have been assigned the analysis_content already
            # However, if it's not wrapped in anything, json.loads will handle it below.


        try:
            # If json_string is empty due to no regex match, this will raise an error, caught below.
            # Otherwise, it attempts to parse the extracted string.
            parsed_analysis = json.loads(json_string)
            return jsonify({"analysis": parsed_analysis}), 200
        except json.JSONDecodeError:
            logger.error(f"Failed to parse Ollama's JSON response after extraction attempt: {json_string}")
            return jsonify({"error": "Failed to parse AI analysis response. Check logs for details."}), 500

    except Exception as e:
        logger.error(f"Error during Ollama analysis: {e}")
        return jsonify({"error": "Failed to perform Ollama analysis"}), 500

@app.route('/api/web_search', methods=['POST'])
def web_search():
    data = request.get_json()
    analysis = data.get('analysis') # Expecting the full analysis object from Ollama

    if not analysis:
        return jsonify({"error": "No analysis data provided for web search"}), 400

    suggested_companies = analysis.get('suggested_companies', [])
    suggested_roles = analysis.get('suggested_roles', [])
    
    all_search_results = []
    queries_performed = []

    # General search based on suggested roles
    for role in suggested_roles:
        query = f'"{role}" job openings'
        queries_performed.append(query)
        try:
            results = perform_brave_search(query)
            if results and results.get('web'):
                for item in results['web']['results']:
                    all_search_results.append({
                        "title": item.get('title'),
                        "url": item.get('url'),
                        "description": item.get('description'),
                        "query_type": "general_role"
                    })
        except Exception as e:
            logger.warning(f"Error performing general role search for '{query}': {e}")
            pass # Continue with other searches

    # Targeted search for companies + roles
    for company in suggested_companies:
        for role in suggested_roles:
            query = f'"{role}" job at "{company}"'
            queries_performed.append(query)
            try:
                results = perform_brave_search(query)
                if results and results.get('web'):
                    for item in results['web']['results']:
                        all_search_results.append({
                            "title": item.get('title'),
                            "url": item.get('url'),
                            "description": item.get('description'),
                            "query_type": "targeted_company_role"
                        })
            except Exception as e:
                logger.warning(f"Error performing targeted search for '{query}': {e}")
                pass # Continue with other searches
    
    # Also perform a broad search for job posting sites, or specific ones like LinkedIn if needed.
    # For now, leveraging Brave Search for broader coverage.
    # Example: "Software Engineer jobs LinkedIn" or "tech jobs indeed"
    # This can be made more dynamic later if specific job board APIs are integrated.
    
    return jsonify({
        "message": "Web search completed",
        "queries_performed": queries_performed,
        "results": all_search_results
    }), 200

if __name__ == '__main__':
    print("Attempting to run Flask app...")
    app.run(debug=True)
