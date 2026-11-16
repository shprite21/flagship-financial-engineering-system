#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef __CUDACC__
#define HD __host__ __device__
#else
#define HD
#endif
namespace abm {
constexpr const char* model_version = "economy-local-markets-v1";
struct Config {
    int households=10000, firms=100, steps=100;
    uint32_t seed=42;
    double initial_wealth=100, firm_cash=1000, wage=1, price=1;
    double productivity=1.5, propensity=0.08, hiring_rate=0.85;
    void validate() const {
        if(households<1 || households>10000000 || firms<1 || firms>households || firms>100000 || steps<1 || steps>10000)
            throw std::invalid_argument("Invalid population, firms or timesteps");
        for(double x : {initial_wealth,firm_cash,wage,price,productivity,propensity,hiring_rate})
            if(!std::isfinite(x) || x>1e9) throw std::invalid_argument("Non-finite or oversized parameter");
        if(initial_wealth<0 || firm_cash<0 || wage<=0 || price<=0 || productivity<=0 || propensity<0 || propensity>1 || hiring_rate<0 || hiring_rate>1)
            throw std::invalid_argument("Economic parameter out of range");
    }
};
// Stateless integer hash: reproducible independently of thread scheduling.
HD inline uint32_t mix(uint32_t x) { x ^= x>>16; x*=0x7feb352du; x^=x>>15; x*=0x846ca68bu; return x^(x>>16); }
HD inline double uniform(uint32_t seed, uint32_t id, uint32_t stream) {
    return (double(mix(seed ^ mix(id+0x9e3779b9u) ^ mix(stream)))+0.5)/4294967296.0;
}
HD inline double minimum(double a,double b) { return a<b?a:b; }
HD inline int members(Config c,int f) { return (c.households-1-f)/c.firms+1; }
HD inline int hires(Config c,double cash,int count) {
    double target=::floor(c.hiring_rate*count);
    return int(minimum(target,::floor(cash/c.wage)));
}
HD inline bool employed(int rank,int count,int jobs,int step) { return (rank+step%count)%count<jobs; }
struct View {
    double *wealth,*income,*consumption,*savings,*propensity,*budget;
    int *employment;
    double *cash,*productivity,*production,*revenue,*demand,*scale;
    int *employees;
};
HD inline void init_household(View s,Config c,int i) {
    s.wealth[i]=c.initial_wealth*(0.5+uniform(c.seed,i,0));
    s.propensity[i]=minimum(1.0,c.propensity*(0.75+0.5*uniform(c.seed,i,1)));
    s.income[i]=s.consumption[i]=s.savings[i]=s.budget[i]=0; s.employment[i]=0;
}
HD inline void init_firm(View s,Config c,int f) {
    s.cash[f]=c.firm_cash; s.productivity[f]=c.productivity*(0.8+0.4*uniform(c.seed,f,2));
    s.production[f]=s.revenue[f]=s.demand[f]=s.scale[f]=0; s.employees[f]=0;
}
HD inline void plan_firm(View s,Config c,int f) {
    s.employees[f]=hires(c,s.cash[f],members(c,f));
    s.production[f]=s.productivity[f]*s.employees[f];
}
HD inline void decide_household(View s,Config c,int i,int step) {
    int f=i%c.firms;
    s.employment[i]=employed(i/c.firms,members(c,f),s.employees[f],step)?1:0;
    s.income[i]=s.employment[i]*c.wage;
    s.budget[i]=s.propensity[i]*(s.wealth[i]+s.income[i]);
}
HD inline void clear_firm(View s,Config c,int f,double demand) {
    s.demand[f]=demand;
    s.revenue[f]=minimum(demand,c.price*s.production[f]);
    s.scale[f]=demand>0?s.revenue[f]/demand:0;
    s.cash[f]+=s.revenue[f]-s.employees[f]*c.wage;
}
HD inline void settle_household(View s,Config c,int i) {
    s.consumption[i]=s.budget[i]*s.scale[i%c.firms];
    s.savings[i]=s.income[i]-s.consumption[i];
    s.wealth[i]+=s.savings[i];
}
struct State {
    std::vector<double> wealth,income,consumption,savings,propensity,budget;
    std::vector<int> employment;
    std::vector<double> cash,productivity,production,revenue,demand,scale;
    std::vector<int> employees;
    explicit State(Config c):wealth(c.households),income(c.households),consumption(c.households),savings(c.households),propensity(c.households),budget(c.households),employment(c.households),cash(c.firms),productivity(c.firms),production(c.firms),revenue(c.firms),demand(c.firms),scale(c.firms),employees(c.firms) {}
    View view() { return {wealth.data(),income.data(),consumption.data(),savings.data(),propensity.data(),budget.data(),employment.data(),cash.data(),productivity.data(),production.data(),revenue.data(),demand.data(),scale.data(),employees.data()}; }
};
struct Row { double output=0,consumption=0,savings=0,employment=0,wealth=0,firm_cash=0; };
struct Timing { double total_ms=0,kernel_ms=0,transfer_ms=0; };
struct Result { State state; std::vector<Row> rows; Timing timing; double initial_money=0; explicit Result(Config c):state(c){} };
void initialize(State&,Config);
void step_cpu(State&,Config,int);
Row aggregate(const State&);
Result run_cpu(Config);
#ifdef ABM_HAS_CUDA
Result run_cuda(Config);
std::string cuda_device();
int cuda_runtime_version();
#endif
}
