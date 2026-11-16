#include "pricing.hpp"
#include <cuda_runtime.h>
#include <curand_kernel.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <stdexcept>
#include <string>

namespace mc {
namespace {
constexpr int threads = 256;
void check(cudaError_t code, const char* operation) {
    if (code != cudaSuccess)
        throw std::runtime_error(std::string(operation) + ": " + cudaGetErrorString(code));
}
struct Moments { unsigned long long count; double mean; double m2; };
__device__ Moments merge(Moments a, Moments b) {
    if (a.count == 0) return b;
    if (b.count == 0) return a;
    const double delta = b.mean - a.mean;
    const auto count = a.count + b.count;
    return {count, a.mean + delta * (static_cast<double>(b.count) / count),
        a.m2 + b.m2 + delta * delta * (static_cast<double>(a.count) / count) * b.count};
}
__device__ void reduce(Moments value, Moments* shared, Moments* output) {
    const int lane = threadIdx.x;
    shared[lane] = value;
    __syncthreads();
    for (int offset = threads / 2; offset > 0; offset /= 2) {
        if (lane < offset) shared[lane] = merge(shared[lane], shared[lane + offset]);
        __syncthreads();
    }
    if (lane == 0) *output = shared[0];
}
__global__ void simulate(Parameters p, unsigned long long n, unsigned long long seed,
                         Moments* partial) {
    __shared__ Moments shared[threads];
    const unsigned long long id = static_cast<unsigned long long>(blockIdx.x) * blockDim.x + threadIdx.x;
    const unsigned long long stride = static_cast<unsigned long long>(gridDim.x) * blockDim.x;
    Moments local{0, 0.0, 0.0};
    if (id < n) {
        curandStatePhilox4_32_10_t state;
        curand_init(seed, id, 0, &state);
        const double drift = (p.rate - 0.5 * p.volatility * p.volatility) * p.maturity;
        const double diffusion = p.volatility * sqrt(p.maturity);
        const double discount = exp(-p.rate * p.maturity);
        for (auto i = id; i < n; i += stride) {
            const double terminal = p.spot * exp(drift + diffusion * curand_normal_double(&state));
            const double payoff = discount * fmax(terminal - p.strike, 0.0);
            ++local.count;
            const double delta = payoff - local.mean;
            local.mean += delta / static_cast<double>(local.count);
            local.m2 += delta * (payoff - local.mean);
        }
    }
    reduce(local, shared, partial + blockIdx.x);
}
__global__ void finish(const Moments* partial, int blocks, Moments* output) {
    __shared__ Moments shared[threads];
    Moments local{0, 0.0, 0.0};
    for (int i = threadIdx.x; i < blocks; i += blockDim.x) local = merge(local, partial[i]);
    reduce(local, shared, output);
}
struct Resources {
    Moments* partial = nullptr;
    Moments* output = nullptr;
    cudaEvent_t start = nullptr, stop = nullptr;
    ~Resources() {
        if (partial) cudaFree(partial);
        if (output) cudaFree(output);
        if (start) cudaEventDestroy(start);
        if (stop) cudaEventDestroy(stop);
    }
};
}
bool gpu_available(std::string& description) {
    int count = 0;
    const auto status = cudaGetDeviceCount(&count);
    if (status != cudaSuccess || count == 0) {
        description = status == cudaSuccess ? "No CUDA GPU found" : cudaGetErrorString(status);
        return false;
    }
    cudaDeviceProp prop{};
    check(cudaGetDeviceProperties(&prop, 0), "Query GPU");
    check(cudaSetDevice(0), "Select GPU");
    description = std::string(prop.name) + " (compute " + std::to_string(prop.major) + "." +
        std::to_string(prop.minor) + ", " + std::to_string(prop.multiProcessorCount) + " SMs)";
    return true;
}
Result price_gpu(const Parameters& p, std::uint64_t samples, std::uint64_t seed) {
    validate(p, samples);
    const auto begin = std::chrono::steady_clock::now();
    Result result;
    {
        int device = 0;
        cudaDeviceProp prop{};
        check(cudaGetDevice(&device), "Current device");
        check(cudaGetDeviceProperties(&prop, device), "Device properties");
        const int blocks = static_cast<int>(std::min<std::uint64_t>(
            (samples - 1) / threads + 1, static_cast<std::uint64_t>(prop.multiProcessorCount) * 32));
        Resources resources;
        check(cudaMalloc(reinterpret_cast<void**>(&resources.partial), blocks * sizeof(Moments)), "Allocate partials");
        check(cudaMalloc(reinterpret_cast<void**>(&resources.output), sizeof(Moments)), "Allocate output");
        check(cudaEventCreate(&resources.start), "Create start event");
        check(cudaEventCreate(&resources.stop), "Create stop event");
        check(cudaEventRecord(resources.start), "Record start");
        simulate<<<blocks, threads>>>(p, samples, seed, resources.partial);
        check(cudaGetLastError(), "Launch simulation");
        finish<<<1, threads>>>(resources.partial, blocks, resources.output);
        check(cudaGetLastError(), "Launch reduction");
        check(cudaEventRecord(resources.stop), "Record stop");
        check(cudaEventSynchronize(resources.stop), "Wait for kernels");
        float elapsed = 0;
        check(cudaEventElapsedTime(&elapsed, resources.start, resources.stop), "Kernel timing");
        Moments host{};
        const auto copy_begin = std::chrono::steady_clock::now();
        check(cudaMemcpy(&host, resources.output, sizeof(host), cudaMemcpyDeviceToHost), "Copy moments");
        const double copy_ms = std::chrono::duration<double, std::milli>(
            std::chrono::steady_clock::now() - copy_begin).count();
        if (host.count != samples) throw std::runtime_error("GPU reduction sample-count mismatch.");
        result = summarize(host.mean, host.m2, host.count);
        result.kernel_ms = elapsed;
        result.d2h_ms = copy_ms;
        result.d2h_bytes = sizeof(Moments);
        result.device_buffer_bytes = (static_cast<std::uint64_t>(blocks) + 1) * sizeof(Moments);
    }
    result.total_ms = std::chrono::duration<double, std::milli>(
        std::chrono::steady_clock::now() - begin).count();
    return result;
}
}
