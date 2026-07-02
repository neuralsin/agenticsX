from agents.airllm_agent import AirLLMAgent

print("Testing AirLLM load_model()...")
model = AirLLMAgent.load_model()
if model is None:
    print("Load model returned None.")
else:
    print("Load model succeeded.")
