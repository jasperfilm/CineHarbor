"""Informational model-license notices for the local workspace."""
import json

H3_LICENSE = 'https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE'
H3_QA = 'https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/QA-about-License.md'


def describe_config(config, name='ComfyUI workflow'):
    recipe = config.get('recipe') or {}
    graph = recipe.get('graph') or {}
    # Inspect model/node bindings, never infer licenses from a user's prompt.
    bindings = {
        'model': config.get('model'),
        'nodes': {str(k): {'class_type': v.get('class_type'),
                          'model_inputs': {name: value for name, value in v.get('inputs', {}).items()
                                           if name in ('unet_name', 'ckpt_name', 'clip_name', 'vae_name',
                                                       'lora_name', 'model_name', 'checkpoint')}}
                  for k, v in graph.items() if isinstance(v, dict)},
        'model_files': recipe.get('model_files') or [],
        'custom_nodes': recipe.get('custom_nodes') or [],
        'source': recipe.get('source'),
    }
    text = json.dumps(bindings, sort_keys=True).lower()
    h3 = config.get('model') == 'h3' or 'minimaxh3' in text or 'minimax_h3' in text or 'minimax-h3' in text
    return {
        'id': 'minimax-h3' if h3 else 'custom-workflow',
        'name': 'MiniMax H3' if h3 else name,
        'links': ([{'title': 'MiniMax H3 License (offline copy)', 'url': '/licenses/models/MiniMax-H3-LICENSE.txt'},
                   {'title': 'MiniMax H3 License', 'url': H3_LICENSE},
                   {'title': 'MiniMax H3 License Q&A', 'url': H3_QA}] if h3 else []),
        'rights_granted': False,
    }
