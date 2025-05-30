import streamlit as st
import trafilatura
import os
import requests

# Setup API keys
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Claim extraction templates
extraction_templates = {
    "General Analysis of Testable Claims": '''
You will be given a text. Extract a **numbered list** of explicit, scientifically testable claims.

**Strict rules:**
- ONLY include claims that appear EXACTLY and VERBATIM in the text.
- Each claim must be explicitly stated.
- If no explicit, complete, testable claims exist, output exactly: "No explicit claims found."
- DO NOT infer, paraphrase, generalize, or use external knowledge.
- Output ONLY the claims formatted as a numbered list, or "No explicit claims found."

TEXT:
{text}

OUTPUT:
''',

    "Specific Focus on Scientific Claims": '''
You will be given a text. Extract a **numbered list** of explicit, scientifically testable claims related to science.

**Strict rules:**
- ONLY include claims that appear EXACTLY and VERBATIM in the text.
- Each claim must be explicitly stated.
- If no relevant testable claims exist, output exactly: "No explicit claims found."
- DO NOT infer, paraphrase, generalize, or use external knowledge.
- Output ONLY the claims formatted as a numbered list, or "No explicit claims found."

TEXT:
{text}

OUTPUT:
''',

    "Technology or Innovation Claims": '''
You will be given a text. Extract a **numbered list** of explicit, testable claims related to technology or innovation.

**Strict rules:**
- ONLY include claims that appear EXACTLY and VERBATIM in the text.
- Each claim must be explicitly stated.
- If no relevant testable claims exist, output exactly: "No explicit claims found."
- DO NOT infer, paraphrase, generalize, or use external knowledge.
- Output ONLY the claims formatted as a numbered list, or "No explicit claims found."

TEXT:
{text}

OUTPUT:
'''
}

# Verification prompt
verification_prompt = '''
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
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openai/gpt-3.5-turbo",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0
    }
    response = requests.post(OPENROUTER_URL, headers=headers, json=payload)
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
    r = requests.get(url, headers=headers)
    results = []
    if r.status_code == 200:
        items = r.json().get("message", {}).get("items", [])
        for item in items:
            results.append(f"{item.get('title', [''])[0]}: {item.get('URL', '')}")
    return results

def fetch_core_papers(query):
    url = f"https://core.ac.uk:443/api-v2/articles/search/{query}?page=1&pageSize=3&metadata=true"
    headers = {"User-Agent": "SciCheckAgent/1.0"}
    r = requests.get(url)
    results = []
    if r.status_code == 200:
        items = r.json().get("data", [])
        for item in items:
            title = item.get("title", "No title")
            link = item.get("downloadUrl", "") or item.get("urls", [""])[0]
            results.append(f"{title}: {link}")
    return results

def verify_claim(claim, article, focus, enrich):
    base_verdict = call_openrouter(verification_prompt.format(claim=claim))
    if not enrich:
        return base_verdict
    crossref_sources = fetch_crossref_papers(claim)
    core_sources = fetch_core_papers(claim)
    source_text = "\n".join(crossref_sources + core_sources)
    enriched_prompt = f"""
Given the following article and claim:

Article: {article}
Claim: {claim}

And based on these supplemental research links:
{source_text}

Reassess the claim.
Respond in this format:
**Verdict:** <VERDICT>
**Justification:** <Short explanation>
**Sources:**
- <URL>
- <URL>
"""
    return call_openrouter(enriched_prompt)

# Streamlit UI
st.title("🔬 SciCheck Agent (GPT-3.5 + Crossref/CORE optional)")

input_mode = st.radio("Choose input method:", ["Paste Text", "Provide URL"])
prompt_mode = st.selectbox("Choose analysis focus:", list(extraction_templates.keys()))
enrich_with_sources = st.checkbox("🔍 Supplement with Crossref + CORE data")

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
    st.session_state["verdicts"] = {}

if "claims" in st.session_state:
    for i, claim in enumerate(st.session_state["claims"]):
        st.subheader(f"Claim {i+1}: {claim}")

        if i not in st.session_state["verdicts"]:
            verdict = verify_claim(claim, st.session_state["article_text"], prompt_mode, enrich_with_sources)
            st.session_state["verdicts"][i] = verdict
        else:
            verdict = st.session_state["verdicts"][i]

        st.markdown(f"**Model Verdict:**\n{verdict}")
