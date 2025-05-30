import streamlit as st
import trafilatura
import os
import requests
import json

# API setup
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Model name
MODEL = "openai/gpt-3.5-turbo"

# Headers for OpenRouter
headers_openrouter = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json"
}

# Claim extraction templates
extraction_templates = {
    "General Analysis of Testable Claims": '''
You will be given a text. Extract a **numbered list** of explicit, scientifically testable claims.

**Strict rules:**
- ONLY include claims that appear EXACTLY and VERBATIM in the text.
- Each claim must be explicitly stated.
- If no explicit, complete, testable claims exist, output exactly: "No explicit claims found."
- Absolutely DO NOT infer, paraphrase, generalize, or introduce external knowledge.
- NEVER include incomplete sentences, headings, summaries, conclusions, speculations, questions, or introductory remarks.
- Output ONLY the claims formatted as a numbered list, or "No explicit claims found."

TEXT:
{text}

OUTPUT:
'''
}

# Model-only verification
verification_prompt_model = '''
Assess the scientific accuracy of the following claim. Provide:

1. A verdict: VERIFIED, PARTIALLY SUPPORTED, INCONCLUSIVE, or CONTRADICTED.
2. A concise justification (max 1000 characters).
3. Relevant source links, formatted as full URLs.

Claim: "{claim}"

Output format:
**Verdict:** <VERDICT>
**Justification:** <Short explanation>
**Sources:**
- <URL>
- <URL>
'''

def call_openrouter(prompt):
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }
    response = requests.post(OPENROUTER_URL, headers=headers_openrouter, json=payload)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()

def extract_article_from_url(url):
    downloaded = trafilatura.fetch_url(url)
    if downloaded:
        text = trafilatura.extract(downloaded)
        return text or "", url
    return "", "Invalid article"

def extract_claims(text, focus):
    prompt = extraction_templates[focus].format(text=text)
    output = call_openrouter(prompt)
    claims = [line.strip() for line in output.split("\n") if line.strip() and line[0].isdigit()]
    return claims if claims else ["No explicit claims found."]

def fetch_crossref_papers(query):
    url = f"https://api.crossref.org/works?query={query}&rows=3"
    headers = {"User-Agent": "SciCheckAgent/1.0 (mailto:test@example.com)"}
    response = requests.get(url, headers=headers)
    results = []
    if response.status_code == 200:
        items = response.json().get("message", {}).get("items", [])
        for item in items:
            results.append({
                "title": item.get("title", ["No title"])[0],
                "abstract": item.get("abstract", "Abstract not available"),
                "url": item.get("URL", "")
            })
    return results

def fetch_core_papers(query):
    url = f"https://core.ac.uk:443/api-v2/articles/search/{query}?page=1&pageSize=3"
    headers = {"User-Agent": "SciCheckAgent/1.0"}
    response = requests.get(url)
    results = []
    if response.status_code == 200:
        items = response.json().get("data", [])
        for item in items:
            results.append({
                "title": item.get("title", "No title"),
                "abstract": item.get("description", "Abstract not available"),
                "url": item.get("fullTextUrl", "")
            })
    return results

def verify_with_model(claim):
    prompt = verification_prompt_model.format(claim=claim)
    return call_openrouter(prompt)

def verify_with_sources(article, claim, papers):
    abstracts = "\n\n".join(f"{p['title']}:\n{p.get('abstract', '')}" for p in papers)
    prompt = f"""
You are a scientific analyst. A user submitted this article:

{article}

From it, we extracted the claim: "{claim}"

Based on the following scientific abstracts, assess the truthfulness of this claim:

{abstracts}

Give a verdict: VERIFIED, PARTIALLY SUPPORTED, INCONCLUSIVE, or CONTRADICTED.
Then briefly explain why.
"""
    return call_openrouter(prompt)

# Streamlit UI
st.title("🔬 SciCheck Agent (GPT-3.5 via OpenRouter)")

input_mode = st.radio("Choose input method:", ["Paste Text", "Provide URL"])
prompt_mode = st.selectbox("Choose analysis focus:", list(extraction_templates.keys()))
use_external_sources = st.toggle("Supplement verdict with CrossRef + CORE scientific papers", value=True)

text_input = ""
article_title = "User input"

if input_mode == "Paste Text":
    text_input = st.text_area("Paste article or post content:")
elif input_mode == "Provide URL":
    url_input = st.text_input("Enter article URL:")
    if url_input:
        text_input, article_title = extract_article_from_url(url_input)
        if text_input:
            st.success("Article extracted successfully.")
        else:
            st.warning("Failed to extract article. Check URL.")

if text_input and st.button("Run Analysis"):
    st.session_state["claims"] = extract_claims(text_input, prompt_mode)
    st.session_state["article_text"] = text_input
    st.session_state["verdicts_model"] = {}
    st.session_state["verdicts_sources"] = {}
    st.session_state["papers"] = {}

if "claims" in st.session_state:
    claims = st.session_state["claims"]
    if claims == ["No explicit claims found."]:
        st.info("No explicit claims found.")
    else:
        for i, claim in enumerate(claims):
            st.subheader(f"Claim {i+1}: {claim}")

            if i not in st.session_state["verdicts_model"]:
                model_verdict = verify_with_model(claim)
                st.session_state["verdicts_model"][i] = model_verdict
            else:
                model_verdict = st.session_state["verdicts_model"][i]

            st.markdown(f"**Model Verdict:**\n{model_verdict}")

            if use_external_sources:
                if i not in st.session_state["papers"]:
                    crossref = fetch_crossref_papers(claim)
                    core = fetch_core_papers(claim)
                    all_papers = crossref + core
                    st.session_state["papers"][i] = all_papers
                else:
                    all_papers = st.session_state["papers"][i]

                if i not in st.session_state["verdicts_sources"]:
                    src_verdict = verify_with_sources(st.session_state["article_text"], claim, all_papers)
                    st.session_state["verdicts_sources"][i] = src_verdict
                else:
                    src_verdict = st.session_state["verdicts_sources"][i]

                st.markdown(f"**External Sources Verdict:**\n{src_verdict}")

                with st.expander("🔗 View Fetched Scientific Sources"):
                    for paper in all_papers:
                        st.markdown(f"**[{paper['title']}]({paper['url']})**\n\n{paper['abstract']}")

                    json_download = json.dumps(all_papers, indent=2)
                    st.download_button("📄 Download Sources JSON", json_download, file_name="sources.json")
