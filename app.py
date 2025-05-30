import streamlit as st
import trafilatura
import os
import requests

# Setup Perplexity Sonar API
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
PPLX_URL = "https://api.perplexity.ai/chat/completions"

# Extraction template
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

**Strict rules:**
- ONLY include claims that appear EXACTLY and VERBATIM in the text.
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
- ONLY include claims that appear EXACTLY and VERBATIM in the text.
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

# Verification prompt (unchanged)
verification_prompts = {
    "General Analysis of Testable Claims": '''
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
}

def call_sonar(prompt):
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "sonar-pro",
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post(PPLX_URL, headers=headers, json=payload)
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
    output = call_sonar(prompt)
    claims = [line.strip() for line in output.split("\n") if line.strip() and line[0].isdigit()]
    return claims if claims else ["No explicit claims found."]

def verify_claim(claim, mode):
    prompt = verification_prompts[mode].format(claim=claim)
    return call_sonar(prompt)

def generate_questions(claim):
    prompt = f"For the following claim, propose up to 3 research questions that can guide deeper scientific investigation. Keep each question on a separate line and omit preambles or explanations.\n\nClaim: {claim}"
    response = call_sonar(prompt)
    return [q.strip("-• ") for q in response.splitlines() if q.strip()][:3]

def generate_research_report(claim, question, article):
    prompt = f'''
You are an AI researcher writing a short evidence-based report (max 300 words).

Article Context: {article}
Claim: {claim}
Research Question: {question}

Answer the question and discuss its relation to the claim clearly.
'''
    return call_sonar(prompt)

# Streamlit UI
st.title("🔬 SciCheck Agent (Perplexity Sonar)")

input_mode = st.radio("Choose input method:", ["Paste Text", "Provide URL"])
prompt_mode = st.selectbox("Choose analysis focus:", list(extraction_templates.keys()))

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
    st.session_state["reports"] = {}
    st.session_state["questions"] = {}

if "claims" in st.session_state:
    claims = st.session_state["claims"]
    if claims == ["No explicit claims found."]:
        st.info("No explicit claims found.")
    else:
        for i, claim in enumerate(claims):
            st.subheader(f"Claim {i+1}: {claim}")

            if i not in st.session_state["verdicts"]:
                verdict = verify_claim(claim, prompt_mode)
                st.session_state["verdicts"][i] = verdict
            else:
                verdict = st.session_state["verdicts"][i]

            st.markdown(f"**Model Verdict:**\n{verdict}")

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
