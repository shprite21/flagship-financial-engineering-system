#pragma once
#include <cstdint>
#include <string>

namespace mc {
struct Parameters {
    double spot = 100.0;
    double strike = 100.0;
    double rate = 0.05;
    double volatility = 0.2;
    double maturity = 1.0;
};
struct Result {
    double price = 0.0;
    double standard_error = 0.0;
    double ci_low = 0.0;
    double ci_high = 0.0;
    double total_ms = 0.0;
    double kernel_ms = 0.0;
    double d2h_ms = 0.0; // Synchronous result transfer, after kernel completion.
    std::uint64_t device_buffer_bytes = 0; // Explicit buffers, excludes driver/context memory.
    std::uint64_t d2h_bytes = 0;
};
void validate(const Parameters& p, std::uint64_t samples);
double black_scholes_call(const Parameters& p);
Result summarize(double mean, double m2, std::uint64_t count);
Result price_cpu(const Parameters& p, std::uint64_t samples, std::uint64_t seed);
bool gpu_available(std::string& description);
Result price_gpu(const Parameters& p, std::uint64_t samples, std::uint64_t seed);
}
