"""CatVTON inference pipeline adapted for MPS / CUDA / CPU.

Based on: https://github.com/Zheng-Chong/CatVTON (ICLR 2025)
Modifications:
- Auto device detection (mps → cuda → cpu)
- float16 dtype (bfloat16 not supported on MPS)
- Removed CUDA-specific flags (allow_tf32)
- Removed safety checker for simplicity
"""
import os
import inspect

import numpy as np
import torch
import tqdm
from diffusers import AutoencoderKL, DDIMScheduler, UNet2DConditionModel
from diffusers.utils.torch_utils import randn_tensor
from huggingface_hub import snapshot_download
from PIL import Image

from app.catvton.attn_processor import SkipAttnProcessor
from app.catvton.model_utils import init_adapter, get_trainable_module
from app.catvton.image_utils import (
    prepare_image,
    prepare_mask_image,
    resize_and_crop,
    resize_and_padding,
    numpy_to_pil,
)


def _best_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _best_dtype(device: str) -> torch.dtype:
    if device == "cuda":
        return torch.float16
    if device == "mps":
        return torch.float16
    return torch.float32


BASE_CKPT = "runwayml/stable-diffusion-inpainting"
ATTN_CKPT = "zhengchong/CatVTON"
ATTN_VERSION = "mix"  # uses mix-48k-1024 subfolder
VAE_CKPT = "stabilityai/sd-vae-ft-mse"


class CatVTONPipeline:
    def __init__(self, device: str | None = None):
        self.device = device or _best_device()
        self.weight_dtype = _best_dtype(self.device)

        print(f"[CatVTON] Loading on device={self.device}, dtype={self.weight_dtype}")

        self.noise_scheduler = DDIMScheduler.from_pretrained(BASE_CKPT, subfolder="scheduler")

        self.vae = AutoencoderKL.from_pretrained(VAE_CKPT).to(self.device, dtype=self.weight_dtype)

        self.unet = UNet2DConditionModel.from_pretrained(BASE_CKPT, subfolder="unet").to(self.device, dtype=self.weight_dtype)
        init_adapter(self.unet, cross_attn_cls=SkipAttnProcessor)
        self.attn_modules = get_trainable_module(self.unet, "attention")
        self._load_attn_weights()

        print("[CatVTON] Model ready.")

    def _load_attn_weights(self):
        from accelerate import load_checkpoint_in_model
        sub_folder = {
            "mix": "mix-48k-1024",
            "vitonhd": "vitonhd-16k-512",
            "dresscode": "dresscode-16k-512",
        }[ATTN_VERSION]
        repo_path = snapshot_download(repo_id=ATTN_CKPT)
        ckpt_path = os.path.join(repo_path, sub_folder, "attention")
        load_checkpoint_in_model(self.attn_modules, ckpt_path)
        print(f"[CatVTON] Attention weights loaded from {ckpt_path}")

    def _compute_vae_encodings(self, image: torch.Tensor) -> torch.Tensor:
        pixel_values = image.to(memory_format=torch.contiguous_format).float()
        pixel_values = pixel_values.to(self.vae.device, dtype=self.vae.dtype)
        with torch.no_grad():
            model_input = self.vae.encode(pixel_values).latent_dist.sample()
        return model_input * self.vae.config.scaling_factor

    def _prepare_extra_step_kwargs(self, generator, eta):
        accepts_eta = "eta" in set(inspect.signature(self.noise_scheduler.step).parameters.keys())
        extra_step_kwargs = {}
        if accepts_eta:
            extra_step_kwargs["eta"] = eta
        accepts_generator = "generator" in set(inspect.signature(self.noise_scheduler.step).parameters.keys())
        if accepts_generator:
            extra_step_kwargs["generator"] = generator
        return extra_step_kwargs

    @torch.no_grad()
    def __call__(
        self,
        person_image: Image.Image,
        garment_image: Image.Image,
        mask_image: Image.Image,
        num_inference_steps: int = 25,
        guidance_scale: float = 2.5,
        height: int = 512,
        width: int = 384,
        seed: int = 42,
    ) -> Image.Image:
        concat_dim = -2  # concatenate along height axis

        generator = torch.Generator(device="cpu").manual_seed(seed)

        # Resize inputs
        person_image = resize_and_crop(person_image, (width, height))
        mask_image = resize_and_crop(mask_image, (width, height))
        garment_image = resize_and_padding(garment_image, (width, height))

        # Prepare tensors
        image_t = prepare_image(person_image).to(self.device, dtype=self.weight_dtype)
        condition_t = prepare_image(garment_image).to(self.device, dtype=self.weight_dtype)
        mask_t = prepare_mask_image(mask_image).to(self.device, dtype=self.weight_dtype)

        # Masked image (person with clothing region zeroed out)
        masked_image = image_t * (mask_t < 0.5)

        # VAE encode
        masked_latent = self._compute_vae_encodings(masked_image)
        condition_latent = self._compute_vae_encodings(condition_t)
        mask_latent = torch.nn.functional.interpolate(mask_t, size=masked_latent.shape[-2:], mode="nearest")

        del image_t, condition_t, mask_t

        # Concat person + garment along height
        masked_latent_concat = torch.cat([masked_latent, condition_latent], dim=concat_dim)
        mask_latent_concat = torch.cat([mask_latent, torch.zeros_like(mask_latent)], dim=concat_dim)

        # Initial noise (same shape as concatenated latent)
        latents = randn_tensor(
            masked_latent_concat.shape,
            generator=generator,
            device=masked_latent_concat.device,
            dtype=self.weight_dtype,
        )

        # Scheduler
        self.noise_scheduler.set_timesteps(num_inference_steps, device=self.device)
        timesteps = self.noise_scheduler.timesteps
        latents = latents * self.noise_scheduler.init_noise_sigma

        # Classifier-free guidance
        do_cfg = guidance_scale > 1.0
        if do_cfg:
            masked_latent_concat = torch.cat([
                torch.cat([masked_latent, torch.zeros_like(condition_latent)], dim=concat_dim),
                masked_latent_concat,
            ])
            mask_latent_concat = torch.cat([mask_latent_concat] * 2)

        extra_step_kwargs = self._prepare_extra_step_kwargs(generator, eta=1.0)
        num_warmup_steps = len(timesteps) - num_inference_steps * self.noise_scheduler.order

        with tqdm.tqdm(total=num_inference_steps, desc="CatVTON inference") as pbar:
            for i, t in enumerate(timesteps):
                lat_in = torch.cat([latents] * 2) if do_cfg else latents
                lat_in = self.noise_scheduler.scale_model_input(lat_in, t)
                # Inpainting model input: noisy + mask + masked/condition
                model_input = torch.cat([lat_in, mask_latent_concat, masked_latent_concat], dim=1)

                noise_pred = self.unet(
                    model_input,
                    t.to(self.device),
                    encoder_hidden_states=None,
                    return_dict=False,
                )[0]

                if do_cfg:
                    noise_pred_uncond, noise_pred_cond = noise_pred.chunk(2)
                    noise_pred = noise_pred_uncond + guidance_scale * (noise_pred_cond - noise_pred_uncond)

                latents = self.noise_scheduler.step(noise_pred, t, latents, **extra_step_kwargs).prev_sample

                if i == len(timesteps) - 1 or ((i + 1) > num_warmup_steps and (i + 1) % self.noise_scheduler.order == 0):
                    pbar.update()

        # Keep only the person half (top half in height-concat)
        latents = latents.split(latents.shape[concat_dim] // 2, dim=concat_dim)[0]
        latents = 1 / self.vae.config.scaling_factor * latents

        result = self.vae.decode(latents.to(self.device, dtype=self.weight_dtype)).sample
        result = (result / 2 + 0.5).clamp(0, 1)
        result = result.cpu().permute(0, 2, 3, 1).float().numpy()
        return numpy_to_pil(result)[0]
