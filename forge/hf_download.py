import os
import config
from huggingface_hub import snapshot_download

def main():
    print(f"Starting direct HuggingFace download of {config.AIRLLM_MODEL_ID}...")
    
    # Ensure cache directory is used
    os.environ["HF_HOME"] = config._hf_cache
    
    try:
        snapshot_download(
            repo_id=config.AIRLLM_MODEL_ID,
            repo_type="model",
            resume_download=True
        )
        print("\nAll 15 parts downloaded successfully!")
    except Exception as e:
        print(f"Download failed: {e}")

if __name__ == "__main__":
    main()
