import streamlit as st
import trafilatura
import os
import requests
import json

# Setup OpenRouter API
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OR_URL = "https://openrouter.ai/api/v1/chat/completions"

# Prompt templates
extraction_templates = {
    "General Analysis of Testable Claims": '''
You will be given a text. Extract a **numbered list** of explicit, scientifically testable claims.

**Strict rules:**
- ONLY include claims that appear EXPLICITLY in the text.
- Each claim must be explicitly stated.
- If no explicit, complete, testable claims exist, output exactly: "No explicit claims found."
- Absolutely DO NOT infer, paraphrase, generalize, or introduce external knowledge.
- NEVER include incomplete sentences, headings, summaries, conclusions, speculations, questions, or introductory remarks.
- Output ONLY the claims formatted as a numbered list, or "No explicit claims found."

TEXT:
{text}

OUTPUT:
''',

    "Specific Focus on Scientific Claims": '''
You will be given a text. Extract a **numbered list** of explicit, scientifically testable claims related to science.

**Strict rules:**
- ONLY include claims that appear EXPLICITLY in the text.
- Each claim must be explicitly stated.
- If no relevant testable claims exist, output exactly: "No explicit claims found."
- Absolutely DO NOT infer, paraphrase, generalize, or introduce external knowledge.
- NEVER include incomplete sentences, headings, summaries, conclusions, speculations, questions, or introductory remarks.
- Output ONLY the claims formatted as a numbered list, or "No explicit claims found."

TEXT:
{text}

OUTPUT:
''',

    "Technology or Innovation Claims": '''
You will be given a text. Extract a **numbered list** of explicit, testable claims related to technology or innovation.

**Strict rules:**
- ONLY include claims that appear EXPLICITLY in the text.
- Each claim must be explicitly stated.
- If no relevant testable claims exist, output exactly: "No explicit claims found."
- Absolutely DO NOT infer, paraphrase, generalize, or introduce external knowledge.
- NEVER include incomplete sentences, headings, summaries, conclusions, speculations, questions, or introductory remarks.
- Output ONLY the claims formatted as a numbered list, or "No explicit claims found."

TEXT:
{text}

OUTPUT:
'''
}

verification_prompts = {
    "General Analysis of Testable Claims": '''
Assess the scientific accuracy of the following general claim. Provide:
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
''',

    "Specific Focus on Scientific Claims": '''
Assess the scientific validity of the following claim from a scientific perspective. Provide:
1. A verdict: VERIFIED, PARTIALLY SUPPORTED, INCONCLUSIVE, or CONTRADICTED.
2. A concise scientific explanation (max 1000 characters).
3. Relevant peer-reviewed or preprint source links, formatted as full URLs.

Claim: "{claim}"

Output format:
**Verdict:** <VERDICT>
**Justification:** <Short explanation>
**Sources:**
- <URL>
- <URL>
''',

    "Technology or Innovation Claims": '''
Assess the credibility of the following technology or innovation-related claim. Provide:
1. A verdict: VERIFIED, PARTIALLY SUPPORTED, INCONCLUSIVE, or CONTRADICTED.
2. A short, well-reasoned explanation with focus on technical evidence or feasibility (max 1000 characters).
3. Links to relevant technical documents, studies, or news sources.

Claim: "{claim}"

Output format:
**Verdict:** <VERDICT>
**Justification:** <Short explanation>
**Sources:**
- <URL>
- <URL>
'''
}

def call_openrouter(prompt):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mistralai/mistral-7b-instruct:free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }

    response = requests.post(OR_URL, headers=headers, json=payload)

    # Debug output
    if response.status_code != 200:
        st.error(f"API Error {response.status_code}: {response.text}")
        response.raise_for_status()

    return response.json()["choices"][0]["message"]["content"].strip()



def fetch_crossref(query):
    url = f"https://api.crossref.org/works?query={query}&rows=3"
    headers = {"User-Agent": "SciCheckAgent/1.0 (mailto:example@example.com)"}
    response = requests.get(url, headers=headers)
    results = []
    if response.status_code == 200:
        for item in response.json().get("message", {}).get("items", []):
            results.append({
                "title": item.get("title", ["No title"])[0],
                "abstract": item.get("abstract", "Abstract not available"),
                "url": item.get("URL", "")
            })
    return results

def fetch_core(query):
    url = f"https://core.ac.uk:443/api-v2/search/{query}?page=1&pageSize=3&metadata=true"
    headers = {"User-Agent": "SciCheckFallback/1.0"}
    response = requests.get(url)
    results = []
    if response.status_code == 200 and "data" in response.json():
        for item in response.json()["data"]:
            results.append({
                "title": item.get("title", "No title"),
                "abstract": item.get("description", "No abstract available"),
                "url": item.get("downloadUrl", item.get("urls", {}).get("fullText", ""))
            })
    return results

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

def verify_claim_model_only(claim, mode):
    prompt = verification_prompts[mode].format(claim=claim)
    return call_openrouter(prompt)

def verify_claim_external(claim, article, sources):
    abstracts = "\n\n".join(f"{p['title']}: {p['abstract']}" for p in sources)
    prompt = f'''
A user submitted the following article:

{article}

And the following claim was extracted: "{claim}"

Evaluate the claim using the abstracts below. Give a verdict (VERIFIED, PARTIALLY SUPPORTED, INCONCLUSIVE, or CONTRADICTED), a justification, and cite relevant paper titles.

Abstracts:
{abstracts}
'''
    return call_openrouter(prompt)

def generate_questions(claim):
    prompt = f"For the following claim, propose up to 3 concise research questions. Only list questions.\n\nClaim: {claim}"
    response = call_openrouter(prompt)
    return [q.strip("-• ") for q in response.splitlines() if q.strip()][:3]

def generate_research_report(claim, question, article):
    prompt = f'''
You are an AI researcher writing a short, evidence-based report (maximum 500 words). Your task is to investigate the research question in relation to the claim using verifiable scientific knowledge.

Use the article context to ground your analysis where helpful. Clearly explain how the answer to the research question supports, contradicts, or contextualizes the claim. Provide concise reasoning, avoid speculation, and include references.

**Requirements:**
- Answer the research question with clarity and scientific grounding.
- Explicitly connect the response to the original claim.
- At the end of the report, list up to 3 relevant sources with clickable full URLs.
- Prefer recent, peer-reviewed sources when available.

---

**Article Context:**  
{article}

**Claim:**  
{claim}

**Research Question:**  
{question}

**Output Format:**
[Your evidence-based response here]

**Sources:**
- <URL>
- <URL>
'''

    return call_openrouter(prompt)

# Streamlit UI
st.title("🔬 SciCheck AI Agent")

st.markdown("""
This app extracts scientifically testable claims from a text or URL, evaluates them using:
- **Mistral-7b-instruct-based internal model verdict**
- **Crossref + CORE scientific papers (if toggled)**
""")

input_mode = st.radio("Choose input method:", ["Paste Text", "Provide URL"])
prompt_mode = st.selectbox("Choose analysis focus:", list(extraction_templates.keys()))
use_papers = st.toggle("📚 Supplement with Crossref + CORE data", value=True)

text_input = ""
if input_mode == "Paste Text":
    text_input = st.text_area("Paste article or post content:")
elif input_mode == "Provide URL":
    url_input = st.text_input("Enter article URL:")
    if url_input:
        text_input, _ = extract_article_from_url(url_input)
        if text_input:
            st.success("Article extracted successfully.")
        else:
            st.warning("Failed to extract article.")

if text_input and st.button("Run Analysis"):
    st.session_state["claims"] = extract_claims(text_input, prompt_mode)
    st.session_state["article_text"] = text_input
    st.session_state["verdicts"] = {}
    st.session_state["external"] = {}
    st.session_state["sources"] = {}
    st.session_state["questions"] = {}
    st.session_state["reports"] = {}

if "claims" in st.session_state:
    for i, claim in enumerate(st.session_state["claims"]):
        st.subheader(f"Claim {i+1}: {claim}")

        if i not in st.session_state["verdicts"]:
            st.session_state["verdicts"][i] = verify_claim_model_only(claim, prompt_mode)
        st.markdown(f"**Model Verdict:**\n{st.session_state['verdicts'][i]}")

        if use_papers:
            if i not in st.session_state["sources"]:
                crossref = fetch_crossref(claim)
                core = fetch_core(claim)
                all_sources = crossref + core
                st.session_state["sources"][i] = all_sources
                st.session_state["external"][i] = verify_claim_external(claim, st.session_state["article_text"], all_sources)

            st.markdown(f"**External Sources Verdict:**\n{st.session_state['external'][i]}")
            with st.expander("View Fetched Scientific Sources"):
                for src in st.session_state["sources"][i]:
                    st.markdown(f"- [{src['title']}]({src['url']})")

        with st.expander("Suggested Research Questions"):
            if i not in st.session_state["questions"]:
                st.session_state["questions"][i] = generate_questions(claim)
            for j, q in enumerate(st.session_state["questions"][i]):
                st.markdown(f"**Q{j+1}:** {q}")
                report_key = f"{i}_{j}"
                if st.button(f"Generate Report for Q{j+1}", key=f"btn_{report_key}"):
                    st.session_state["reports"][report_key] = generate_research_report(claim, q, st.session_state["article_text"])
                if report_key in st.session_state["reports"]:
                    st.markdown(f"**Research Report:**\n{st.session_state['reports'][report_key]}")
