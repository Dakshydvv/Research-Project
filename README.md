# Smart Government Scheme Recognition and Eligibility Recommendation System

Academic Flask prototype based on the supplied research paper. It uses a rule-based eligibility filter followed by TF-IDF + cosine similarity ranking. The hybrid score is `0.6 * eligibility confidence + 0.4 * textual relevance`.

## Features
- User registration/login
- User dashboard and editable profile
- Eligibility checks: age, income, education, occupation, state and residence
- Missing scheme criteria treated as non-restrictive
- TF-IDF unigram/bigram recommendation with cosine similarity
- Ranked hybrid match score and human-readable reasons
- Rejected-scheme explanations
- Recommendation history
- Admin dashboard for adding/deleting schemes
- SQLite database and hashed passwords
- Synthetic evaluation script

## Run in VS Code / Terminal
1. Install Python 3.10+.
2. Open this folder in VS Code.
3. Create a virtual environment: `python -m venv .venv`
4. Activate it on Windows: `.venv\\Scripts\\activate`
5. Install packages: `pip install -r requirements.txt`
6. Run: `python app.py`
7. Open `http://127.0.0.1:5000`

Admin page: `http://127.0.0.1:5000/admin/login`
Demo admin credentials: `admin` / `admin123`

## Evaluation
Run `python evaluate.py` to calculate precision, recall, F1, accuracy and average response time on synthetic profiles.