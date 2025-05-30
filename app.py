import streamlit as st
import trafilatura
import os
import requests
import json

# Set OpenRouter GPT-3.5 API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GPT_MODEL = "openai/gpt-3.5-turbo"

# Extraction templates by focus
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
''',
    "Specific Focus on Scientific Claims": '''
You will be given a text. Extract a **numbered list** of explicit, scientifically testable claims related to science.

(Same rules apply as above.)
TEXT:
{text}

OUTPUT:
''',
    "Technology or Innovation Claims": '''
You will be given a text. Extract a **numbered list** of explicit, testable claims related to technology or innovation.

(Same rules apply as above.)
TEXT:
{text}

OUTPUT:
'''
}

# Model-only verification
model_verification_prompt = '''
Assess the scientific accuracy of the following claim. Provide:

1. A verdict: VERIFIED, PARTIALLY SUPPORTED, INCONCLUSIVE, or CONTRADICTED.
2. A concise justification (max 1000 characters).
3. Relevant source links, formatted as full URLs (if any).

Claim: "{claim}"

Output format:
**Verdict:** <VERDICT>
**Justification:** <Short explanation>
**Sources:**
- <URL>
- <URL>
'''

# Research question generation
def generate_questions(claim):
    prompt = f"For the following claim, propose up to 3 research questions. List them only:\n\nClaim: {claim}"
    return ask_gpt(prompt).splitlines()[:3]

# Research report
def generate_research_report(claim, question, article):
    prompt = f'''You are an AI researcher writing a 300-word report.

Claim: {claim}
Research Question: {question}
Article Context: {article}

Provide a structured, objective, and evidence-based analysis.'''
    return ask_gpt(prompt)

# Call OpenRouter GPT
def ask_gpt(prompt):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": GPT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4
    }
    response = requests.post(OPENROUTER_URL, headers=headers, json=data)
    response.raise_for_status()
    return response.json()['choices'][0]['message']['content'].strip()

# External paper retrieval
def fetch_crossref(query):
    url = f"https://api.crossref.org/works?query={query}&rows=3"
    response = requests.get(url, headers={"User-Agent": "SciCheck/1.0"})
    items = response.json().get("message", {}).get("items", [])
    return [{
        "title": item.get("title", [""])[0],
        "abstract": item.get("abstract", "Abstract not available"),
        "url": item.get("URL", "")
    } for item in items]

def fetch_core(query):
    search_url = f"https://core.ac.uk:443/api-v2/articles/search/{query}?page=1&pageSize=3&metadata=true"
    response = requests.get(search_url, headers={"Authorization": "Bearer anonymous"})
    items = response.json().get("data", [])
    return [{
        "title": item["title"],
        "abstract": item.get("description", "Abstract not available"),
        "url": item.get("urls", [""])[0]
    } for item in items]

def verify_with_papers(claim, article, papers):
    abstracts = "\n\n".join(f"{p['title']}:\n{p['abstract']}" for p in papers)
    prompt = f'''Assess the following claim using the abstracts listed below.

Claim: "{claim}"

Article Context: {article}

Sources:
{abstracts}

Output format:
**Verdict:** <VERDICT>
**Justification:** <Explanation citing paper titles if needed>
'''
    return ask_gpt(prompt)

def extract_article_from_url(url):
    downloaded = trafilatura.fetch_url(url)
    return (trafilatura.extract(downloaded) or "", url) if downloaded else ("", "Invalid article")

def extract_claims(text, focus):
    prompt = extraction_templates[focus].format(text=text)
    result = ask_gpt(prompt)
    return [line.strip() for line in result.split("\n") if line.strip() and line[0].isdigit()] or ["No explicit claims found."]

# --- Streamlit UI ---
st.set_page_config(page_title="SciCheck", layout="wide")
st.title("🔬 SciCheck Agent (GPT-3.5 via OpenRouter)")

input_mode = st.radio("Choose input method:", ["Paste Text", "Provide URL"])
focus_mode = st.selectbox("Analysis focus", list(extraction_templates.keys()))
use_external = st.toggle("Use Crossref + CORE for second opinion", value=True)

text_input = ""
if input_mode == "Paste Text":
    text_input = st.text_area("Paste article content here:")
else:
    url_input = st.text_input("Enter URL:")
    if url_input:
        text_input, _ = extract_article_from_url(url_input)
        if text_input:
            st.success("Article loaded successfully.")
        else:
            st.warning("Could not extract article.")

if text_input and st.button("Run Analysis"):
    st.session_state["claims"] = extract_claims(text_input, focus_mode)
    st.session_state["verdicts_model"] = {}
    st.session_state["verdicts_ext"] = {}
    st.session_state["ext_sources"] = {}
    st.session_state["questions"] = {}
    st.session_state["reports"] = {}

if "claims" in st.session_state:
    if st.session_state["claims"] == ["No explicit claims found."]:
        st.info("No explicit claims found.")
    else:
        for i, claim in enumerate(st.session_state["claims"]):
            st.subheader(f"Claim {i+1}: {claim}")

            # Model-based verdict
            if i not in st.session_state["verdicts_model"]:
                st.session_state["verdicts_model"][i] = ask_gpt(model_verification_prompt.format(claim=claim))
            st.markdown("**Model Verdict:**")
            st.markdown(st.session_state["verdicts_model"][i])

            # External sources
            if use_external:
                if i not in st.session_state["ext_sources"]:
                    cr = fetch_crossref(claim)
                    core = fetch_core(claim)
                    all_sources = cr + core
                    st.session_state["ext_sources"][i] = all_sources
                    st.session_state["verdicts_ext"][i] = verify_with_papers(claim, text_input, all_sources)

                st.markdown("**External Sources Verdict:**")
                st.markdown(st.session_state["verdicts_ext"][i])
                with st.expander("View abstracts used"):
                    for paper in st.session_state["ext_sources"][i]:
                        st.markdown(f"**[{paper['title']}]({paper['url']})**\n\n{paper['abstract']}")

                    json_data = json.dumps(st.session_state["ext_sources"][i], indent=2)
                    st.download_button("Download Abstracts", data=json_data, file_name=f"claim_{i+1}_abstracts.json")

            # Questions & Reports
            with st.expander("Suggested Research Questions"):
                if i not in st.session_state["questions"]:
                    st.session_state["questions"][i] = generate_questions(claim)

                for j, q in enumerate(st.session_state["questions"][i]):
                    st.markdown(f"**Q{j+1}:** {q}")
                    report_key = f"{i}_{j}"
                    if st.button(f"Generate Report for Q{j+1}", key=f"btn_{report_key}"):
                        st.session_state["reports"][report_key] = generate_research_report(claim, q, text_input)

                    if report_key in st.session_state["reports"]:
                        st.markdown(f"**Research Report:**\n{st.session_state['reports'][report_key]}")
