import os
import orjson 
import asyncio
import aiofiles
import time

from transformer_lens import utils
from datasets import load_dataset
from transformers import AutoTokenizer

def load_tokenized_data(
    tokenizer: AutoTokenizer,
    dataset_repo: str = "kh4dien/fineweb-100m-sample",
    dataset_name: str = "",
    dataset_split: str = "train[:15%]",
    seq_len: int = 64,
    seed: int = 22,
):
    # Load the dataset
    data = load_dataset(dataset_repo, name=dataset_name, split=dataset_split)

    # Tokenize and concatenate
    tokens = utils.tokenize_and_concatenate(
        data, 
        tokenizer, 
        max_length=seq_len
    )   

    # Shuffle the tokens
    tokens = tokens.shuffle(seed)['tokens']

    return tokens

async def execute_model(
    model,
    queries,
    output_dir: str,
    record_time=False
):
    """
    Executes a model on a list of queries and saves the results to the output directory.
    """
    from .logger import logger

    os.makedirs(output_dir, exist_ok=True)

    async def process_and_save(query):
        layer_index = query.record.feature.layer_index
        feature_index = query.record.feature.feature_index

        logger.info(f"Executing {model.name} on feature layer {layer_index}, feature {feature_index}")

        start_time = time.time()
        result = await model(query)
        end_time = time.time()

        filename = f"layer{layer_index}_feature{feature_index}.txt"
        filepath = os.path.join(output_dir, filename)

        if record_time:
            result = {
                "result": result,
                "time": end_time - start_time
            }
            
        async with aiofiles.open(filepath, mode='wb') as f:
            await f.write(orjson.dumps(result))

        logger.info(f"Saved result to {filepath}")
    
    tasks = [process_and_save(query) for query in queries]
    await asyncio.gather(*tasks)