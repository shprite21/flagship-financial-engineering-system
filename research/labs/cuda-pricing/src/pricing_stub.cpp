#include "pricing.hpp"
#include <stdexcept>
namespace mc {
bool gpu_available(std::string& description) {
    description = "CUDA backend disabled at build time";
    return false;
}
Result price_gpu(const Parameters&, std::uint64_t, std::uint64_t) {
    throw std::runtime_error("Rebuild with MC_ENABLE_CUDA=ON to use the GPU.");
}
}
