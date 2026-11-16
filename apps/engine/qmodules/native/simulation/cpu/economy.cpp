#include "core/model.hpp"
#include <chrono>
#include <numeric>
namespace abm {
void initialize(State& s,Config c) {
    auto v=s.view();
    for(int i=0;i<c.households;++i) init_household(v,c,i);
    for(int f=0;f<c.firms;++f) init_firm(v,c,f);
}
void step_cpu(State& s,Config c,int step) {
    auto v=s.view();
    for(int f=0;f<c.firms;++f) plan_firm(v,c,f);
    for(int i=0;i<c.households;++i) decide_household(v,c,i,step);
    std::fill(s.demand.begin(),s.demand.end(),0.0);
    for(int i=0;i<c.households;++i) s.demand[i%c.firms]+=s.budget[i];
    for(int f=0;f<c.firms;++f) clear_firm(v,c,f,s.demand[f]);
    for(int i=0;i<c.households;++i) settle_household(v,c,i);
}
Row aggregate(const State& s) {
    Row r;
    for(size_t i=0;i<s.wealth.size();++i) {
        r.wealth+=s.wealth[i]; r.consumption+=s.consumption[i]; r.savings+=s.savings[i]; r.employment+=s.employment[i];
    }
    for(size_t f=0;f<s.cash.size();++f) { r.output+=s.production[f]; r.firm_cash+=s.cash[f]; }
    return r;
}
Result run_cpu(Config c) {
    c.validate(); auto start=std::chrono::steady_clock::now();
    Result r(c); r.rows.reserve(c.steps); initialize(r.state,c);
    auto initial=aggregate(r.state); r.initial_money=initial.wealth+initial.firm_cash;
    for(int t=0;t<c.steps;++t) { step_cpu(r.state,c,t); r.rows.push_back(aggregate(r.state)); }
    r.timing.total_ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
    return r;
}
}
