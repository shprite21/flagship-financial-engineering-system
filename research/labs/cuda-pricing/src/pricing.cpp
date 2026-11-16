#include "pricing.hpp"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <random>
#include <stdexcept>

namespace mc {
void validate(const Parameters& p, std::uint64_t samples) {
    if (!std::isfinite(p.spot) || !std::isfinite(p.strike) ||
        !std::isfinite(p.rate) || !std::isfinite(p.volatility) || !std::isfinite(p.maturity) ||
        p.spot <= 0 || p.strike <= 0 || p.volatility < 0 || p.maturity < 0)
        throw std::invalid_argument("Use finite parameters: spot/strike > 0; volatility/maturity >= 0.");
    if (samples < 2) throw std::invalid_argument("At least two simulations are required.");
    const double drift = (p.rate - 0.5 * p.volatility * p.volatility) * p.maturity;
    if (!std::isfinite(drift) || !std::isfinite(std::exp(-p.rate * p.maturity)))
        throw std::invalid_argument("Parameters exceed the supported numerical range.");
}
double black_scholes_call(const Parameters& p) {
    validate(p, 2);
    if (p.maturity == 0) return std::max(p.spot - p.strike, 0.0);
    const double discounted_strike = p.strike * std::exp(-p.rate * p.maturity);
    if (p.volatility == 0) return std::max(p.spot - discounted_strike, 0.0);
    const double vol = p.volatility * std::sqrt(p.maturity);
    const double d1 = (std::log(p.spot / p.strike) +
        (p.rate + 0.5 * p.volatility * p.volatility) * p.maturity) / vol;
    const double d2 = d1 - vol;
    const auto cdf = [](double x) { return 0.5 * std::erfc(-x / std::sqrt(2.0)); };
    const double price = p.spot * cdf(d1) - discounted_strike * cdf(d2);
    if (!std::isfinite(price)) throw std::runtime_error("Black-Scholes overflow.");
    return std::max(price, 0.0);
}
Result summarize(double mean, double m2, std::uint64_t count) {
    if (!std::isfinite(mean) || !std::isfinite(m2))
        throw std::runtime_error("Simulation overflow: choose less extreme parameters.");
    Result result;
    result.price = mean;
    result.standard_error = std::sqrt(std::max(m2, 0.0) /
        static_cast<double>(count - 1) / static_cast<double>(count));
    result.ci_low = mean - 1.959963984540054 * result.standard_error;
    result.ci_high = mean + 1.959963984540054 * result.standard_error;
    return result;
}
Result price_cpu(const Parameters& p, std::uint64_t samples, std::uint64_t seed) {
    validate(p, samples);
    const auto begin = std::chrono::steady_clock::now();
    std::mt19937_64 rng(seed);
    std::normal_distribution<double> normal(0.0, 1.0);
    const double drift = (p.rate - 0.5 * p.volatility * p.volatility) * p.maturity;
    const double diffusion = p.volatility * std::sqrt(p.maturity);
    const double discount = std::exp(-p.rate * p.maturity);
    double mean = 0.0, m2 = 0.0;
    for (std::uint64_t i = 0; i < samples; ++i) {
        const double terminal = p.spot * std::exp(drift + diffusion * normal(rng));
        const double payoff = discount * std::max(terminal - p.strike, 0.0);
        const double delta = payoff - mean;
        mean += delta / static_cast<double>(i + 1);
        m2 += delta * (payoff - mean);
    }
    auto result = summarize(mean, m2, samples);
    result.total_ms = std::chrono::duration<double, std::milli>(
        std::chrono::steady_clock::now() - begin).count();
    return result;
}
}
