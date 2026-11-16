#include "pricing.hpp"
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>
#include <limits>

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
void near(double value, double expected, double tolerance, const char* message) {
    require(std::isfinite(value) && std::abs(value - expected) <= tolerance, message);
}
}
int main(int argc, char** argv) {
    try {
        const bool gpu = argc == 2 && std::string(argv[1]) == "--gpu";
        if (gpu) {
            std::string device;
            require(mc::gpu_available(device), "GPU test requires a working CUDA device");
            std::cout << device << '\n';
        }
        auto price = gpu ? mc::price_gpu : mc::price_cpu;
        mc::Parameters p;
        near(mc::black_scholes_call(p), 10.450583572185565, 1e-10, "Known Black-Scholes value");
        p.maturity = 0; p.spot = 110;
        near(mc::black_scholes_call(p), 10, 1e-12, "Expiry intrinsic value");
        // Exercise fewer-than-one-block, exact-block, and partial-block sizes.
        for (const auto n : {2ULL, 255ULL, 256ULL, 257ULL, 10003ULL}) {
            const auto r = price(p, n, 42);
            near(r.price, 10, 1e-10, "Expiry simulation");
            near(r.standard_error, 0, 1e-12, "Expiry variance");
        }
        p = {}; p.volatility = 0;
        const auto deterministic = price(p, 10003, 42);
        near(deterministic.price, mc::black_scholes_call(p), 1e-10, "Zero volatility");
        near(deterministic.standard_error, 0, 1e-12, "Zero volatility variance");
        p = {}; p.rate = -0.01;
        const auto a = price(p, 1000000, 1234);
        const auto b = price(p, 1000000, 1234);
        near(a.price, b.price, 0, "Fixed-seed reproducibility");
        near(a.standard_error, b.standard_error, 0, "Reproducible variance");
        require(a.standard_error > 0, "Positive standard error");
        if (gpu) {
            const auto cpu = mc::price_cpu(p, 1000000, 9876);
            near(a.price, cpu.price, 6 * std::hypot(a.standard_error, cpu.standard_error),
                 "CPU versus GPU independent estimates");
            require(a.device_buffer_bytes > 0 && a.d2h_bytes > 0, "GPU memory accounting");
            require(a.d2h_ms >= 0 && a.kernel_ms > 0 && a.total_ms >= a.kernel_ms,
                    "Synchronized GPU timings");
        }
        // Broad statistical regression guard, not a claim of guaranteed CI coverage.
        near(a.price, mc::black_scholes_call(p), 6 * a.standard_error, "MC agrees with Black-Scholes within six SE");
        std::cout << "Negative-rate price=" << a.price << " reference=" << mc::black_scholes_call(p)
                  << " standard_error=" << a.standard_error << '\n';
        near(a.ci_high - a.price, 1.959963984540054 * a.standard_error, 1e-12, "Confidence interval");
        p = {}; p.spot = 1; p.strike = 1e10;
        const auto otm = price(p, 10003, 7);
        near(otm.price, 0, 0, "Deep out-of-money payoff");
        bool rejected = false;
        try { mc::validate(p, 1); } catch (const std::invalid_argument&) { rejected = true; }
        require(rejected, "Reject insufficient samples");
        rejected = false; p.volatility = -0.1;
        try { mc::validate(p, 100); } catch (const std::invalid_argument&) { rejected = true; }
        require(rejected, "Reject negative volatility");
        for (double bad : {-1.0, std::numeric_limits<double>::infinity(),
                           std::numeric_limits<double>::quiet_NaN()}) {
            p = {}; p.spot = bad; rejected = false;
            try { price(p, 100, 42); } catch (const std::invalid_argument&) { rejected = true; }
            require(rejected, "Backend rejects invalid spot before simulation");
        }
        p = {};
        // End-to-end distribution smoke check, not a full RNG independence test.
        const auto distribution = price(p, 1000000, 2026);
        const double v = p.volatility * std::sqrt(p.maturity);
        const double d1 = (std::log(p.spot / p.strike) +
            (p.rate + 0.5 * p.volatility * p.volatility) * p.maturity) / v;
        const auto cdf = [](double x) { return 0.5 * std::erfc(-x / std::sqrt(2.0)); };
        const double second = p.spot * p.spot * std::exp(p.volatility * p.volatility * p.maturity) * cdf(d1 + v)
            - 2 * p.spot * p.strike * std::exp(-p.rate * p.maturity) * cdf(d1)
            + p.strike * p.strike * std::exp(-2 * p.rate * p.maturity) * cdf(d1 - v);
        const double exact_price = mc::black_scholes_call(p);
        const double variance = second - exact_price * exact_price;
        near(distribution.standard_error * distribution.standard_error * 1000000,
             variance, 0.05 * variance, "Simulated payoff variance matches model");
        require(price(p, 10000, 11).price != price(p, 10000, 12).price,
                "Distinct seeds produce distinct estimates");
        double small_error2 = 0, large_error2 = 0, small_se2 = 0, large_se2 = 0;
        for (std::uint64_t seed = 100; seed < 116; ++seed) {
            const auto small = price(p, 4096, seed);
            const auto large = price(p, 65536, seed);
            small_error2 += std::pow(small.price - exact_price, 2);
            large_error2 += std::pow(large.price - exact_price, 2);
            small_se2 += small.standard_error * small.standard_error;
            large_se2 += large.standard_error * large.standard_error;
        }
        // Expected RMS ratio is 1/4; do not require monotonic errors for individual seeds.
        require(std::sqrt(large_se2 / small_se2) < 0.35, "Standard error convergence");
        require(std::sqrt(large_error2 / small_error2) < 0.65, "Multi-seed RMSE convergence");
        std::cout << "Convergence over 16 seeds, N=4096 to 65536: RMS SE ratio="
                  << std::sqrt(large_se2 / small_se2) << ", RMSE ratio="
                  << std::sqrt(large_error2 / small_error2) << '\n';
        std::cout << (gpu ? "GPU" : "CPU") << " pricing tests passed\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "FAIL: " << e.what() << '\n'; return 1;
    }
}
