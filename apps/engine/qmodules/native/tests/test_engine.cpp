#include "core/model.hpp"
#include <iostream>
#include <numeric>
using namespace abm;
void require(bool b,const char* message){if(!b)throw std::runtime_error(message);}
void close(double a,double b,double rtol=1e-10,double atol=1e-8){require(std::abs(a-b)<=atol+rtol*std::max(std::abs(a),std::abs(b)),"Numerical mismatch");}
void compare(const std::vector<double>& a,const std::vector<double>& b){require(a.size()==b.size(),"Size mismatch");for(size_t i=0;i<a.size();++i)close(a[i],b[i]);}
void accounting(Config c){
    State s(c);initialize(s,c);auto r=aggregate(s);double initial=r.wealth+r.firm_cash;
    for(int t=0;t<c.steps;++t){auto before=aggregate(s);step_cpu(s,c,t);auto after=aggregate(s);
        close(after.wealth+after.firm_cash,initial);close(after.wealth-before.wealth,after.savings);
        close(after.consumption,std::accumulate(s.revenue.begin(),s.revenue.end(),0.0));
        close(after.employment,std::accumulate(s.employees.begin(),s.employees.end(),0.0));
        for(int i=0;i<c.households;++i){require(s.wealth[i]>=-1e-10,"Negative household wealth");close(s.savings[i],s.income[i]-s.consumption[i]);}
        for(int f=0;f<c.firms;++f){require(s.cash[f]>=-1e-10,"Negative firm cash");require(s.revenue[f]<=c.price*s.production[f]+1e-8,"Oversold supply");}
    }
}
int main(){try{
    Config c;c.households=1031;c.firms=17;c.steps=40;
    State s(c);initialize(s,c);for(int i=0;i<c.households;++i){require(s.wealth[i]>=50&&s.wealth[i]<150,"Initialization range");require(s.employment[i]==0,"Initial employment");}
    auto a=run_cpu(c),b=run_cpu(c);require(a.state.wealth==b.state.wealth,"Seed repeatability");
    c.seed++;auto other=run_cpu(c);require(a.state.wealth!=other.state.wealth,"Seeds must differ");c.seed--;
    accounting(c);
    Config hand;hand.households=1;hand.firms=1;hand.steps=1;hand.hiring_rate=1;hand.propensity=1;
    State h(hand);initialize(h,hand);double w=h.wealth[0],cash=h.cash[0],production=h.productivity[0];step_cpu(h,hand,0);
    close(h.consumption[0],production);close(h.wealth[0],w+1-production);close(h.cash[0],cash-1+production);
    for(int n:{1,7,256,257}){c.households=n;c.firms=n==1?1:3;accounting(c);c.firm_cash=0;accounting(c);c.firm_cash=1000;}
    c.households=100;c.firms=100;c.propensity=0;c.hiring_rate=1;accounting(c);
    bool rejected=false;c.wage=0;try{c.validate();}catch(...){rejected=true;}require(rejected,"Invalid config accepted");
    std::cout<<"PASS CPU: initialization, hand calculation, updates, accounting, aggregates, edge cases, reproducibility, validation\n";
#ifdef ABM_HAS_CUDA
    // Missing GPU is an explicit failure in CUDA-enabled validation, never a passing skip.
    std::cout<<"CUDA device: "<<cuda_device()<<'\n';
    for(int n:{1,257,1031}){Config g;g.households=n;g.firms=n==1?1:17;g.steps=40;auto cpu=run_cpu(g),gpu=run_cuda(g);
        compare(cpu.state.wealth,gpu.state.wealth);compare(cpu.state.cash,gpu.state.cash);compare(cpu.state.income,gpu.state.income);
        compare(cpu.state.consumption,gpu.state.consumption);compare(cpu.state.savings,gpu.state.savings);compare(cpu.state.propensity,gpu.state.propensity);
        compare(cpu.state.budget,gpu.state.budget);compare(cpu.state.productivity,gpu.state.productivity);compare(cpu.state.production,gpu.state.production);
        compare(cpu.state.revenue,gpu.state.revenue);compare(cpu.state.demand,gpu.state.demand);compare(cpu.state.scale,gpu.state.scale);
        require(cpu.state.employment==gpu.state.employment,"Employment differs");require(cpu.state.employees==gpu.state.employees,"Hires differ");
        auto again=run_cuda(g);require(gpu.state.wealth==again.state.wealth,"GPU reproducibility");
        for(size_t t=0;t<cpu.rows.size();++t){auto x=cpu.rows[t],y=gpu.rows[t];close(x.output,y.output);close(x.consumption,y.consumption);close(x.savings,y.savings);close(x.employment,y.employment);close(x.wealth,y.wealth);close(x.firm_cash,y.firm_cash);close(y.wealth+y.firm_cash,gpu.initial_money);}
    }std::cout<<"PASS CUDA: full state and every timestep agree with CPU\n";
#else
    std::cout<<"NOT RUN: CUDA consistency (build configured without CUDA)\n";
#endif
    return 0;
}catch(const std::exception& e){std::cerr<<"FAIL: "<<e.what()<<'\n';return 1;}}
