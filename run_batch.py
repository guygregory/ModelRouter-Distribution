import json
import os
from datetime import datetime
from pathlib import Path
from typing import List

import httpx
from datasets import load_dataset
from dotenv import load_dotenv
from httpx import TimeoutException
from openai import APITimeoutError, AzureOpenAI
from tqdm import tqdm


CACHE_FILENAME = "prompts_cache.jsonl" # Cache of prompts to avoid re-downloading
RESULTS_FILENAME = "results_Balanced.jsonl" # Change suffix to identify different runs
STOP_AFTER_LIMIT = True  # Prevent writing more than OUTPUT_LIMIT records across runs
OUTPUT_LIMIT = 1000 # Maximum number of outputs to write if STOP_AFTER_LIMIT is True
REQUEST_TIMEOUT_SECONDS = 60.0 # Timeout for API requests in seconds, will skip problematic prompts


def log_status(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    tqdm.write(f"[{timestamp}] {message}")


def load_environment() -> None:
    load_dotenv()


def create_client() -> AzureOpenAI:
    endpoint = os.environ["AZURE_OPENAI_API_ENDPOINT"]
    deployment = os.environ["AZURE_OPENAI_API_MODEL"]
    subscription_key = os.environ["AZURE_OPENAI_API_KEY"]
    api_version = os.environ["AZURE_OPENAI_API_VERSION"]
    http_client = httpx.Client(timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS))
    return AzureOpenAI(
        api_version=api_version,
        azure_endpoint=endpoint,
        api_key=subscription_key,
        http_client=http_client,
        max_retries=0,
    )


def load_prompts(cache_path: Path) -> List[str]:
    if cache_path.exists():
        try:
            with cache_path.open("r", encoding="utf-8") as cache_file:
                return [json.loads(line)["prompt"] for line in cache_file if line.strip()]
        except (json.JSONDecodeError, KeyError):
            print("Invalid prompts cache detected. Rebuilding cache.")
            cache_path.unlink(missing_ok=True)

    dataset = load_dataset("data-is-better-together/10k_prompts_ranked", split="train")
    prompts = [row["prompt"] for row in dataset]

    with cache_path.open("w", encoding="utf-8") as cache_file:
        for prompt in prompts:
            cache_file.write(json.dumps({"prompt": prompt}) + "\n")

    return prompts


def count_existing_results(results_path: Path) -> int:
    if not results_path.exists():
        results_path.touch()
        return 0

    with results_path.open("r", encoding="utf-8") as results_file:
        return sum(1 for line in results_file if line.strip())


def process_prompts(prompts: List[str]) -> None:
    results_path = Path(__file__).with_name(RESULTS_FILENAME)

    total_prompts = len(prompts)
    processed_count = count_existing_results(results_path)

    if STOP_AFTER_LIMIT:
        if processed_count >= OUTPUT_LIMIT:
            print(f"Output limit of {OUTPUT_LIMIT} already reached. Nothing to do.")
            return
        remaining_capacity = OUTPUT_LIMIT - processed_count
    else:
        remaining_capacity = total_prompts - processed_count

    if remaining_capacity <= 0:
        print("All prompts have already been processed.")
        return

    if processed_count >= total_prompts:
        print("All prompts have already been processed.")
        return

    client = create_client()
    deployment_name = os.environ["AZURE_OPENAI_API_MODEL"]

    try:
        with results_path.open("a", encoding="utf-8") as results_file:
            max_total = processed_count + min(remaining_capacity, total_prompts - processed_count)
            prompts_to_process = prompts[processed_count : processed_count + remaining_capacity]

            log_status(
                f"Starting batch: {len(prompts_to_process)} prompts, {processed_count} existing results."
            )

            with tqdm(
                total=max_total,
                initial=processed_count,
                desc="Processing prompts",
                unit="prompt",
            ) as progress_bar:
                for index, prompt in enumerate(prompts_to_process):
                    absolute_index = processed_count + index + 1
                    prompt_preview = prompt.replace("\n", " ")[:80]
                    log_status(f"Processing prompt #{absolute_index}: {prompt_preview}")
                    try:
                        response = client.chat.completions.create(
                            stream=False,
                            messages=[
                                {"role": "system", "content": "You are a helpful assistant."},
                                {"role": "user", "content": prompt},
                            ],
                            max_tokens=8192,
                            temperature=0.7,
                            top_p=0.95,
                            frequency_penalty=0.0,
                            presence_penalty=0.0,
                            model=deployment_name,
                        )
                    except (APITimeoutError, TimeoutException):
                        log_status(
                            f"Timeout on prompt #{absolute_index} after 60 seconds. Skipping."
                        )
                        continue
                    except Exception as exc:  # noqa: BLE001
                        log_status(
                            f"Error on prompt #{absolute_index}: "
                            f"{type(exc).__name__}: {exc}. Prompt preview: {prompt_preview}"
                        )
                        continue

                    if not response.choices:
                        log_status(
                            f"Warning: empty response choices for prompt #{absolute_index}."
                        )
                        continue

                    choice = response.choices[0]
                    message_content = choice.message.content if choice.message else ""
                    model_name = response.model

                    record = {
                        "prompt": prompt,
                        "model": model_name,
                        "output": message_content,
                    }
                    results_file.write(json.dumps(record) + "\n")
                    results_file.flush()
                    progress_bar.update(1)
                    log_status(
                        f"Recorded output for prompt #{absolute_index} using model '{model_name}'."
                    )

            if STOP_AFTER_LIMIT and (processed_count + len(prompts_to_process)) >= OUTPUT_LIMIT:
                print(f"Output limit of {OUTPUT_LIMIT} reached; stopping early.")
    except KeyboardInterrupt:
        print("\nBatch interrupted by user. Progress saved.")
    finally:
        client.close()


def main() -> None:
    load_environment()
    cache_path = Path(__file__).with_name(CACHE_FILENAME)
    prompts = load_prompts(cache_path)
    process_prompts(prompts)


if __name__ == "__main__":
    main()