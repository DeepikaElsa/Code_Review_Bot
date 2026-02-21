import requests

def review_code(prompt: str):
    url = "http://127.0.0.1:11434/api/generate"

    payload = {
        "model": "llama3.2:latest",   # change only if you want another model
        "prompt": prompt,
        "stream": False,
        "temperature": 0.2
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        print("Raw response text:", response.text)

        response.raise_for_status()
        result = response.json()

        # Ollama returns output in "response"
        return result.get("response", "No response from model")

    except requests.exceptions.RequestException as e:
        return f"Request failed: {e}"

    except ValueError:
        return f"Invalid JSON response:\n{response.text}"
