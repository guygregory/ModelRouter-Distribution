from datasets import load_dataset

# Load the full dataset
ds = load_dataset("data-is-better-together/10k_prompts_ranked", split="train")

# Get a plain list of prompt strings
prompts = [row["prompt"] for row in ds]

print(len(prompts), prompts[0])
