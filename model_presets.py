"""Verified full-precision (BF16 / FP16 / FP32) Hugging Face model presets for 96GB G4 runtimes.

Never uses quantized weights (fp8 / int8 / gguf / fp4). Applying a preset populates
`model_files` and upgrades consumer quantized filenames in converted ComfyUI graphs
to their official full-precision counterparts.
"""
import copy
from workflow_library import validate_model_files

MODEL_PRESETS = [
    {
        'id': 'wan22_i2v_14b_fp16',
        'name': 'Wan 2.2 I2V A14B · 完整 FP16 套件',
        'kind': 'video',
        'template': 'video_wan2_2_14B_i2v',
        'approx_gb': 71.1,
        'precision': 'FP16 Full',
        'gated': False,
        'description': 'Comfy-Org 官方重打包完整 FP16 高/低噪双 14B 扩散模型 + UMT5-XXL FP16 + 4步加速 LoRA（无需网页额外申请权限）。',
        'model_files': [
            {
                'file': 'diffusion_models/wan2.2_i2v_high_noise_14B_fp16.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp16.safetensors',
                'sha256': ''
            },
            {
                'file': 'diffusion_models/wan2.2_i2v_low_noise_14B_fp16.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp16.safetensors',
                'sha256': ''
            },
            {
                'file': 'text_encoders/umt5_xxl_fp16.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp16.safetensors',
                'sha256': ''
            },
            {
                'file': 'vae/wan_2.1_vae.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors',
                'sha256': ''
            },
            {
                'file': 'loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors',
                'sha256': ''
            },
            {
                'file': 'loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors',
                'sha256': ''
            },
        ],
        'node_upgrades': {
            'wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors': 'wan2.2_i2v_high_noise_14B_fp16.safetensors',
            'wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors': 'wan2.2_i2v_low_noise_14B_fp16.safetensors',
            'umt5_xxl_fp8_e4m3fn_scaled.safetensors': 'umt5_xxl_fp16.safetensors',
        }
    },
    {
        'id': 'ltx25_i2v_22b_bf16',
        'name': 'LTX 2.5 22B I2V · 完整 BF16 音视频套件',
        'kind': 'video',
        'template': 'video_ltx2_5_i2v',
        'approx_gb': 71.1,
        'precision': 'BF16 Full',
        'gated': True,
        'description': 'Lightricks LTX-2.5 22B 完整 BF16 音画同生套件（含 2x 空间潜空间放大器）。如遇 401/403 需先在 Hugging Face 官方仓库确认许可。',
        'model_files': [
            {
                'file': 'diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors',
                'url': 'https://huggingface.co/Lightricks/LTX-2.5/resolve/main/diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors',
                'sha256': ''
            },
            {
                'file': 'text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors',
                'url': 'https://huggingface.co/Lightricks/LTX-2.5/resolve/main/text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors',
                'sha256': ''
            },
            {
                'file': 'vae/ltx-2.5-video-vae-bf16.safetensors',
                'url': 'https://huggingface.co/Lightricks/LTX-2.5/resolve/main/vae/ltx-2.5-video-vae-bf16.safetensors',
                'sha256': ''
            },
            {
                'file': 'vae/ltx-2.5-audio-vae-bf16.safetensors',
                'url': 'https://huggingface.co/Lightricks/LTX-2.5/resolve/main/vae/ltx-2.5-audio-vae-bf16.safetensors',
                'sha256': ''
            },
            {
                'file': 'latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors',
                'url': 'https://huggingface.co/Lightricks/LTX-2.5/resolve/main/latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors',
                'sha256': ''
            },
        ],
        'node_upgrades': {
            'ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors': 'ltx-2.5-22b-distilled-transformer-bf16.safetensors',
            'ltx-2.5-22b-dev-transformer-comfy-int8-convrot.safetensors': 'ltx-2.5-22b-dev-transformer-bf16.safetensors',
            'gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors': 'gemma4-12b-with-proj-ltx-2.5-bf16.safetensors',
            'gemma4_e2b_it_int8_convrot.safetensors': 'gemma4-12b-with-proj-ltx-2.5-bf16.safetensors',
        }
    },
    {
        'id': 'qwen_image_2512_bf16',
        'name': 'Qwen Image 2512 · 完整 BF16 文生图套件',
        'kind': 'image',
        'template': 'image_qwen_Image_2512',
        'approx_gb': 59.3,
        'precision': 'BF16 + FP32 LoRA',
        'gated': False,
        'description': 'Qwen-Image 2512 完整 40.8GB BF16 主模型 + 完整 Qwen2.5-VL-7B 编码器 + FP32 Lightning 4步 LoRA，适合生成高细节分镜首帧与角色三视图。',
        'model_files': [
            {
                'file': 'diffusion_models/qwen_image_2512_bf16.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_2512_bf16.safetensors',
                'sha256': ''
            },
            {
                'file': 'text_encoders/qwen_2.5_vl_7b.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b.safetensors',
                'sha256': ''
            },
            {
                'file': 'vae/qwen_image_vae.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors',
                'sha256': ''
            },
            {
                'file': 'loras/Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors',
                'url': 'https://huggingface.co/lightx2v/Qwen-Image-2512-Lightning/resolve/main/Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors',
                'sha256': ''
            },
        ],
        'node_upgrades': {
            'qwen_image_2512_fp8_e4m3fn.safetensors': 'qwen_image_2512_bf16.safetensors',
            'qwen_2.5_vl_7b_fp8_scaled.safetensors': 'qwen_2.5_vl_7b.safetensors',
        }
    },
    {
        'id': 'qwen_image_edit_2511_bf16',
        'name': 'Qwen Image Edit 2511 · 完整 BF16 锁脸改镜套件',
        'kind': 'image',
        'template': 'image_qwen_image_edit_2511',
        'approx_gb': 59.4,
        'precision': 'BF16 + FP32 LoRA',
        'gated': False,
        'description': 'Qwen-Image-Edit 2511 完整 40.9GB BF16 编辑主模型 + Qwen2.5-VL-7B + FP32 4步加速 LoRA，支持锁死角色母版五官与服装切换任意分镜景别与机位。',
        'model_files': [
            {
                'file': 'diffusion_models/qwen_image_edit_2511_bf16.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_2511_bf16.safetensors',
                'sha256': ''
            },
            {
                'file': 'text_encoders/qwen_2.5_vl_7b.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b.safetensors',
                'sha256': ''
            },
            {
                'file': 'vae/qwen_image_vae.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors',
                'sha256': ''
            },
            {
                'file': 'loras/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-fp32.safetensors',
                'url': 'https://huggingface.co/lightx2v/Qwen-Image-Edit-2511-Lightning/resolve/main/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-fp32.safetensors',
                'sha256': ''
            },
        ],
        'node_upgrades': {
            'qwen_image_edit_2511_fp8mixed.safetensors': 'qwen_image_edit_2511_bf16.safetensors',
            'qwen_image_edit_2511_fp8_e4m3fn.safetensors': 'qwen_image_edit_2511_bf16.safetensors',
            'qwen_image_edit_2511_int8_convrot.safetensors': 'qwen_image_edit_2511_bf16.safetensors',
            'qwen_2.5_vl_7b_fp8_scaled.safetensors': 'qwen_2.5_vl_7b.safetensors',
            'Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors': 'Qwen-Image-Edit-2511-Lightning-4steps-V1.0-fp32.safetensors',
        }
    },
    {
        'id': 'acestep_15_bf16',
        'name': 'ACE-Step 1.5 + 4B 规划器 · 完整精度音乐套件',
        'kind': 'audio',
        'template': 'audio_ace_step_1_5_split_4b',
        'approx_gb': 14.0,
        'precision': 'BF16 Full',
        'gated': False,
        'description': 'ACE-Step 1.5 官方完整精度音乐生成模型 + Qwen 0.6B/4B 双规划编码器，支持长达 600 秒的影片原创配乐与歌曲生成。',
        'model_files': [
            {
                'file': 'diffusion_models/acestep_v1.5_turbo.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/diffusion_models/acestep_v1.5_turbo.safetensors',
                'sha256': ''
            },
            {
                'file': 'text_encoders/qwen_0.6b_ace15.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_0.6b_ace15.safetensors',
                'sha256': ''
            },
            {
                'file': 'text_encoders/qwen_4b_ace15.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_4b_ace15.safetensors',
                'sha256': ''
            },
            {
                'file': 'vae/ace_1.5_vae.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/vae/ace_1.5_vae.safetensors',
                'sha256': ''
            },
        ],
        'node_upgrades': {}
    },
    {
        'id': 'acestep_15_xl_bf16',
        'name': 'ACE-Step 1.5 XL SFT · 旗舰完整 BF16 音乐套件',
        'kind': 'audio',
        'template': 'audio_ace_step_1_5_split_4b',
        'approx_gb': 19.2,
        'precision': 'XL BF16 Full',
        'gated': False,
        'description': 'ACE-Step 1.5 XL SFT (9.97GB BF16) 高保真音乐主模型，适合作为短片主旋律配乐轨道并直接送入粗剪台合成。',
        'model_files': [
            {
                'file': 'diffusion_models/acestep_v1.5_xl_sft_bf16.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/diffusion_models/acestep_v1.5_xl_sft_bf16.safetensors',
                'sha256': ''
            },
            {
                'file': 'text_encoders/qwen_0.6b_ace15.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_0.6b_ace15.safetensors',
                'sha256': ''
            },
            {
                'file': 'text_encoders/qwen_4b_ace15.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_4b_ace15.safetensors',
                'sha256': ''
            },
            {
                'file': 'vae/ace_1.5_vae.safetensors',
                'url': 'https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/vae/ace_1.5_vae.safetensors',
                'sha256': ''
            },
        ],
        'node_upgrades': {
            'acestep_v1.5_turbo.safetensors': 'acestep_v1.5_xl_sft_bf16.safetensors',
        }
    },
]


def list_presets():
    out = []
    for p in MODEL_PRESETS:
        validate_model_files(p['model_files'])
        out.append(copy.deepcopy(p))
    return out


def get_preset(preset_id=None, template_name=None):
    if preset_id:
        return copy.deepcopy(next((p for p in MODEL_PRESETS if p['id'] == preset_id), None))
    if template_name:
        stem = str(template_name).replace('.json', '')
        return copy.deepcopy(next((p for p in MODEL_PRESETS if p.get('template') == stem), None))
    return None


def upgrade_graph_to_preset(graph, preset):
    """Upgrade quantized consumer weight filenames inside a ComfyUI API graph to full-precision preset filenames."""
    if not preset or not isinstance(graph, dict):
        return graph
    mapping = preset.get('node_upgrades') or {}
    if not mapping:
        return graph
    out = copy.deepcopy(graph)
    for node in out.values():
        inputs = node.get('inputs')
        if not isinstance(inputs, dict):
            continue
        for k, v in list(inputs.items()):
            if isinstance(v, str) and v in mapping:
                inputs[k] = mapping[v]
    return out
