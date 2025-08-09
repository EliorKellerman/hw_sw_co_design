import torch
from torch.profiler import profile, record_function, ProfilerActivity
import matmul_cuda  # Your compiled CUDA extension

TRACE_PATH = "trace_naive.json"

def matmul_naive(A1, A2):
    return matmul_cuda.matmul_naive_block(A1.contiguous(), A2.contiguous())

def main():
    N = 1024
    A = torch.randn(N, N, device='cuda')
    B = torch.randn(N, N, device='cuda')

    # Warm-up to initialize GPU context (avoids tracing setup overhead)
    matmul_naive(A, B)

    with profile(
        activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA],
        record_shapes=True,       # Optional, useful info
        with_stack=False,         # ⛔ Avoid long delay!
        profile_memory=False      # ⛔ Avoid large trace size!
    ) as prof:
        with record_function("matmul_naive_block"):
            matmul_naive(A, B) 

    prof.export_chrome_trace(TRACE_PATH)
    print(f"✅ Trace saved to: {TRACE_PATH}")

if __name__ == "__main__":
    main()
