#include "pricing.hpp"
#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <vector>

namespace {
std::uint64_t integer(const std::string& s) {
    if (s.empty() || s.find_first_not_of("0123456789") != std::string::npos)
        throw std::invalid_argument("Expected unsigned integer: " + s);
    std::size_t used = 0;
    const auto value = std::stoull(s, &used);
    if (used != s.size()) throw std::invalid_argument("Invalid integer: " + s);
    return value;
}
double real(const std::string& s) {
    std::size_t used = 0;
    const double value = std::stod(s, &used);
    if (used != s.size() || !std::isfinite(value)) throw std::invalid_argument("Invalid number: " + s);
    return value;
}
double median(std::vector<double> values) {
    std::sort(values.begin(), values.end());
    const auto n = values.size();
    return n % 2 ? values[n / 2] : (values[n / 2 - 1] + values[n / 2]) / 2;
}
void row(std::ostream& out, const char* backend, std::uint64_t n, int trial,
         std::uint64_t seed, const mc::Parameters& p, double reference, const mc::Result& r) {
    out << backend << ',' << n << ',' << trial << ',' << seed << ','
        << p.spot << ',' << p.strike << ',' << p.rate << ',' << p.volatility << ',' << p.maturity << ','
        << reference << ',' << r.price << ',' << std::abs(r.price - reference) << ','
        << r.standard_error << ',' << r.ci_low << ',' << r.ci_high << ',' << r.total_ms << ',';
    if (std::string(backend) == "gpu") out << r.kernel_ms;
    out << ',';
    if (std::string(backend) == "gpu")
        out << r.d2h_ms << ',' << r.device_buffer_bytes << ',' << r.d2h_bytes;
    else out << ",,";
    out << '\n';
}
}
int main(int argc, char** argv) {
    try {
        mc::Parameters p;
        std::vector<std::uint64_t> sizes{10000, 100000, 1000000, 10000000};
        std::uint64_t seed = 42;
        int repeats = 5;
        std::string backend = "both", csv = "results.csv";
        for (int i = 1; i < argc; ++i) {
            const std::string arg = argv[i];
            if (arg == "--help") {
                std::cout << "European call Monte Carlo benchmark\n"
                    "  --backend cpu|gpu|both  (default both; no silent CPU fallback)\n"
                    "  --samples 10000,100000,1000000,10000000\n"
                    "  --repeats 5 --seed 42 --csv results.csv\n"
                    "  --spot 100 --strike 100 --rate 0.05 --volatility 0.2 --maturity 1\n";
                return 0;
            }
            if (++i == argc) throw std::invalid_argument("Missing value for " + arg);
            const std::string value = argv[i];
            if (arg == "--backend") backend = value;
            else if (arg == "--csv") csv = value;
            else if (arg == "--seed") seed = integer(value);
            else if (arg == "--repeats") {
                const auto count = integer(value);
                if (count == 0 || count > 10000) throw std::invalid_argument("Repeats must be 1..10000.");
                repeats = static_cast<int>(count);
            } else if (arg == "--samples") {
                sizes.clear();
                std::istringstream stream(value);
                std::string token;
                while (std::getline(stream, token, ',')) sizes.push_back(integer(token));
                if (sizes.empty() || value.back() == ',') throw std::invalid_argument("Invalid sample list.");
            } else if (arg == "--spot") p.spot = real(value);
            else if (arg == "--strike") p.strike = real(value);
            else if (arg == "--rate") p.rate = real(value);
            else if (arg == "--volatility") p.volatility = real(value);
            else if (arg == "--maturity") p.maturity = real(value);
            else throw std::invalid_argument("Unknown argument: " + arg);
        }
        if (backend != "cpu" && backend != "gpu" && backend != "both")
            throw std::invalid_argument("Backend must be cpu, gpu, or both.");
        for (auto n : sizes) mc::validate(p, n);
        if (seed > std::numeric_limits<std::uint64_t>::max() - static_cast<std::uint64_t>(repeats - 1))
            throw std::invalid_argument("Seed + repeats would overflow.");
        const bool cpu = backend != "gpu", gpu = backend != "cpu";
        std::string device;
        if (gpu && !mc::gpu_available(device)) throw std::runtime_error("GPU unavailable: " + device);
        const double reference = mc::black_scholes_call(p);
        std::ofstream out(csv);
        if (!out) throw std::runtime_error("Cannot open CSV: " + csv);
        out << std::setprecision(17);
        out << "backend,samples,trial,seed,spot,strike,rate,volatility,maturity,black_scholes,price,abs_error,standard_error,ci_low,ci_high,total_ms,kernel_ms,d2h_ms,device_buffer_bytes,d2h_bytes\n";
        std::cout << std::fixed << std::setprecision(6) << "Black-Scholes call: " << reference << '\n';
        if (gpu) std::cout << "GPU: " << device << '\n';
        std::cout << "Trials: " << repeats << "; seed: " << seed << "; FP64; warm-up excluded\n";
        // Warm up the context, module, allocator, and RNG before recording trials.
        if (cpu) mc::price_cpu(p, 10000, seed);
        if (gpu) mc::price_gpu(p, 10000, seed);
        std::cout << "N             CPU median ms   GPU total ms    GPU kernel ms   Speedup\n";
        for (auto n : sizes) {
            std::vector<double> cpu_times, gpu_times, kernel_times;
            for (int trial = 0; trial < repeats; ++trial) {
                const auto trial_seed = seed + static_cast<std::uint64_t>(trial);
                const auto run_cpu = [&] {
                    const auto r = mc::price_cpu(p, n, trial_seed);
                    cpu_times.push_back(r.total_ms); row(out, "cpu", n, trial, trial_seed, p, reference, r);
                };
                const auto run_gpu = [&] {
                    const auto r = mc::price_gpu(p, n, trial_seed);
                    gpu_times.push_back(r.total_ms); kernel_times.push_back(r.kernel_ms);
                    row(out, "gpu", n, trial, trial_seed, p, reference, r);
                };
                // Alternate execution order to reduce systematic order bias.
                if (trial % 2 == 0) { if (cpu) run_cpu(); if (gpu) run_gpu(); }
                else { if (gpu) run_gpu(); if (cpu) run_cpu(); }
            }
            std::cout << std::left << std::setw(14) << n << std::setw(16)
                << (cpu ? std::to_string(median(cpu_times)) : "n/a") << std::setw(16)
                << (gpu ? std::to_string(median(gpu_times)) : "n/a") << std::setw(16)
                << (gpu ? std::to_string(median(kernel_times)) : "n/a")
                << (cpu && gpu ? std::to_string(median(cpu_times) / median(gpu_times)) + "x" : "n/a") << '\n';
        }
        out.close();
        if (!out) throw std::runtime_error("Failed writing CSV.");
        std::cout << "Raw measurements saved to " << csv << '\n';
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << '\n';
        return 1;
    }
}
