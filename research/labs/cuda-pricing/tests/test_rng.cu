#include <cuda_runtime.h>
#include <curand_kernel.h>
#include <cmath>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
constexpr int count = 262144;
void check(cudaError_t status) {
    if (status != cudaSuccess) throw std::runtime_error(cudaGetErrorString(status));
}
__global__ void draw(double* output, unsigned long long seed) {
    const int id = blockIdx.x * blockDim.x + threadIdx.x;
    curandStatePhilox4_32_10_t state;
    curand_init(seed, id, 0, &state);
    for (int i = id; i < count; i += blockDim.x * gridDim.x)
        output[i] = curand_normal_double(&state);
}
void validate(const std::vector<double>& values, const char* name) {
    double sum = 0, sum2 = 0, adjacent = 0;
    int tail = 0;
    for (int i = 0; i < count; ++i) {
        const double z = values[i];
        if (!std::isfinite(z)) throw std::runtime_error("Nonfinite normal draw");
        sum += z; sum2 += z * z;
        if (i) adjacent += z * values[i - 1];
        if (std::abs(z) > 2) ++tail;
    }
    const double mean = sum / count;
    const double variance = sum2 / count - mean * mean;
    const double correlation = (adjacent / (count - 1) - mean * mean) / variance;
    const double tail_fraction = static_cast<double>(tail) / count;
    std::cout << name << ": mean=" << mean << " variance=" << variance
              << " adjacent_correlation=" << correlation << " P(|Z|>2)=" << tail_fraction << '\n';
    if (std::abs(mean) > 6 / std::sqrt(static_cast<double>(count)) ||
        std::abs(variance - 1) > 0.025 || std::abs(correlation) > 0.02 ||
        std::abs(tail_fraction - 0.0455002639) > 0.005)
        throw std::runtime_error(std::string(name) + " normal distribution regression");
}
struct Buffer {
    double* data = nullptr;
    ~Buffer() { if (data) cudaFree(data); }
};
}
int main() {
    try {
        std::vector<double> cpu(count), gpu(count), repeat(count), changed(count);
        std::mt19937_64 rng(2026);
        std::normal_distribution<double> normal;
        for (auto& value : cpu) value = normal(rng);
        validate(cpu, "CPU mt19937_64");
        Buffer buffer;
        check(cudaMalloc(reinterpret_cast<void**>(&buffer.data), count * sizeof(double)));
        const auto sample = [&](unsigned long long seed, std::vector<double>& output) {
            draw<<<4, 256>>>(buffer.data, seed);
            check(cudaGetLastError());
            check(cudaDeviceSynchronize());
            check(cudaMemcpy(output.data(), buffer.data, count * sizeof(double), cudaMemcpyDeviceToHost));
        };
        sample(2026, gpu); sample(2026, repeat); sample(2027, changed);
        if (gpu != repeat || gpu == changed) throw std::runtime_error("Philox seed/reproducibility regression");
        validate(gpu, "GPU Philox");
        validate(changed, "GPU Philox alternate seed");
        std::cout << "RNG tests passed (statistical smoke checks, not an exhaustive randomness certification)\n";
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
