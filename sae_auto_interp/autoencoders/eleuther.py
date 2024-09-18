from functools import partial
from typing import List
import torch

from sae import Sae

from .OpenAI.model import ACTIVATIONS_CLASSES, TopK
from .wrapper import AutoencoderLatents

DEVICE = "cuda:0"


def load_eai_autoencoders(model, ae_layers: list[int], weight_dir: str, module: str, randomize: bool = False, seed: int = 42, k: int = None):
    submodules = {}

    for layer in ae_layers:
        if module=="mlp":
            submodule = f"layers.{layer}.{module}"
        elif module=="res":
            submodule = f"layers.{layer}"
        
        if "mnt" in weight_dir:
            sae = Sae.load_from_disk(weight_dir+"/"+submodule,device=DEVICE).to(dtype=model.dtype)
        else:
            sae = Sae.load_from_hub(weight_dir,hookpoint=submodule, device=DEVICE).to(dtype=model.dtype)
        
        if randomize:
            sae = Sae.load_from_hub(weight_dir,hookpoint=submodule, device=DEVICE).to(dtype=model.dtype)
            sae = Sae(sae.d_in, sae.cfg, device=DEVICE, dtype=model.dtype, decoder=False)
        
        def _forward(sae, k,x):
            encoded = sae.pre_acts(x)
            if k is not None:
                trained_k = k
            else:
                trained_k = sae.cfg.k
            topk = TopK(trained_k, postact_fn=ACTIVATIONS_CLASSES["Identity"]())
            return topk(encoded)

        if "llama" in weight_dir:
            if module == "res":
                submodule = model.model.layers[layer]
            else:
                submodule = model.model.layers[layer].mlp
        elif "gpt2" in weight_dir:
            submodule = model.transformer.h[layer]
        else:
            submodule = model.gpt_neox.layers[layer]
        submodule.ae = AutoencoderLatents(
            sae, partial(_forward, sae, k), width=sae.d_in * sae.cfg.expansion_factor
        )

        submodules[submodule._module_path] = submodule

    with model.edit(" "):
        for path, submodule in submodules.items():
            if "embed" not in path and "mlp" not in path:
                acts = submodule.output[0]
            else:
                acts = submodule.output
            submodule.ae(acts, hook=True)

    return submodules