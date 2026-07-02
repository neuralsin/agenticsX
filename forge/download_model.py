import sys
import config
from airllm import AutoModel

def main():
    print(f"Starting pre-download of {config.AIRLLM_MODEL_ID} with AirLLM...")
    try:
        model = AutoModel.from_pretrained(
            config.AIRLLM_MODEL_ID,
            compression=config.AIRLLM_COMPRESSION,
            profiling_mode=False
        )
        print("Model downloaded and cached successfully!")
    except Exception as e:
        print(f"Error during download: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
