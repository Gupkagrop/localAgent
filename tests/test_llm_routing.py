import os
import json
import re
from llama_cpp import Llama

model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "qwen2.5-1.5b-instruct-q4_k_m.gguf")
llm = Llama(model_path=model_path, n_ctx=1024, verbose=False)

system_prompt = (
    'You are a desktop voice assistant router. Output strict JSON with keys "action", "target", "parameters". '
    'If answering a question, use action "general_answer" with parameters {"text": "Russian answer"}.'
)

resp = llm.create_chat_completion(
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Сколько планет в Солнечной системе?"}
    ],
    max_tokens=80,
    temperature=0.1
)

content = resp["choices"][0]["message"]["content"]
print("LLM Content:", content)
match = re.search(r"\{.*\}", content, re.DOTALL)
if match:
    data = json.loads(match.group(0))
    print("Parsed JSON:", data)
