import torch
import bitsandbytes as bnb

print("Testing bitsandbytes quantize_nf4...")
try:
    v = torch.randn(1024, 1024).half()
    v_cuda = v.cuda()
    print("Tensor on CUDA")
    v_quant, quant_state = bnb.functional.quantize_nf4(v_cuda, blocksize=64)
    print("Quantization successful!")
except Exception as e:
    print("Error:", e)
