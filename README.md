
# 🔬 SciCheck Agent (Powered by Perplexity Sonar)

**SciCheck Agent** is a streamlined, AI-powered tool that extracts and verifies scientific or technological claims from articles or posts. It uses the **Perplexity Sonar** model to assess scientific validity and provide concise evidence-based feedback.

---

## 🚀 Features

- **Claim Extraction**: Identifies scientifically testable claims stated *explicitly and verbatim* in the input text.
- **Claim Verification**: Evaluates each extracted claim against scientific knowledge and returns a clear verdict with source links.
- **Research Questions**: Suggests up to 3 follow-up research questions per claim.
- **Research Report Generator**: Generates a short research report addressing each question using the article context.
- **Supports URL or raw text input.**

---

## 📦 Requirements

- Python 3.8+
- Streamlit
- Requests
- TrafiLatura

Install dependencies using:

```bash
pip install streamlit requests trafilatura
```

---

## 🔑 API Key Setup

You will need a **Perplexity Sonar API key**.

1. Get your API key from [Perplexity AI](https://docs.perplexity.ai/guides/getting-started)
2. Set it as an environment variable in your terminal or `.env` file:

```bash
export PERPLEXITY_API_KEY=your_key_here
```

---

## 🧠 How It Works

1. **Input**: Provide either a URL or paste text directly.
2. **Focus**: Choose a focus mode (General, Scientific, or Technological claims).
3. **Analysis**: The system extracts claims, verifies them, and suggests research questions.
4. **Report**: Generate reports per question based on article context.

---

## 🏁 Running the App

Run the app with:

```bash
streamlit run app.py
```

---

## 📄 License

MIT License.
