from flask import Flask, request, jsonify
from flask_cors import CORS
from review_bot import review_code

app = Flask(__name__)
CORS(app)

@app.route("/api/review", methods=["POST"])
def review():
    try:
        data = request.get_json()
        code = data.get("code")
        mode = data.get("mode")
        if not code or not mode:
            return jsonify({"error": "Missing code or mode"}), 400

        if mode == "explain":
            prompt = (
                f"You are a coding expert.\n"
                f"Please carefully explain the following Python code:\n\n{code}"
            )
        elif mode == "correct":
            prompt = (
                f"You are a code fixer.\n"
                f"Fix all errors in this Python code. Show corrected full code only:\n\n{code}"
            )
        elif mode == "complexity":
            prompt = (
                f"You are a code complexity analyzer.\n"
                f"Analyze the following Python code and provide:\n"
                f"1. Time Complexity Analysis (Big O notation)\n"
                f"2. Space Complexity Analysis\n"
                f"3. Cyclomatic complexity score\n"
                f"4. Function length and nesting depth\n"
                f"5. Specific suggestions for optimization\n\n"
                f"Format with headers using # and bullet points using →. Code: \n\n{code}"
            )
        elif mode == "duplication":
            prompt = (
                f"You are a code duplication detector.\n"
                f"Analyze the following Python code and provide:\n"
                f"1. Identify any duplicated code patterns\n"
                f"2. Suggest refactoring opportunities\n"
                f"3. List specific locations of duplicates\n"
                f"Format with headers using # and bullet points using →. Code: \n\n{code}"
            )
        else:
            return jsonify({"error": "Invalid mode"}), 400

        review = review_code(prompt)
        return jsonify({"result": review})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)