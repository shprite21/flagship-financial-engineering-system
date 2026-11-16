#include "core/model.hpp"
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <limits>
using namespace abm;
static std::string quote(const std::string& s) { std::string r="\"";for(char c:s){if(c=='\\'||c=='\"')r+='\\';if(static_cast<unsigned char>(c)<32)r+=' ';else r+=c;}return r+'\"'; }
static int integer(const std::string& s) { size_t p=0;long long n=std::stoll(s,&p);if(p!=s.size()||n<0||n>std::numeric_limits<int>::max())throw std::invalid_argument("Invalid integer");return int(n); }
static double number(const std::string& s) { size_t p=0;double n=std::stod(s,&p);if(p!=s.size()||!std::isfinite(n))throw std::invalid_argument("Invalid number");return n; }
int main(int argc,char** argv) {try {
    if(argc==2 && std::string(argv[1])=="--capabilities") {
        std::cout<<"{\"model_version\":"<<quote(model_version)<<",\"cpu\":true,\"cuda\":";
#ifdef ABM_HAS_CUDA
        try{auto name=cuda_device();std::cout<<"true,\"cuda_device\":"<<quote(name)<<",\"cuda_runtime\":"<<cuda_runtime_version();}
        catch(const std::exception& e){std::cout<<"false,\"cuda_error\":"<<quote(e.what());}
#else
        std::cout<<"false,\"cuda_error\":\"Built without CUDA Toolkit\"";
#endif
        std::cout<<"}\n";return 0;
    }
    Config c;std::string device="cpu",output=".";
    std::map<std::string,std::string> args;
    for(int i=1;i<argc;i+=2){if(i+1>=argc)throw std::invalid_argument("Expected --key value");if(!args.emplace(argv[i],argv[i+1]).second)throw std::invalid_argument("Duplicate argument");}
    for(auto& a:args) {const auto& k=a.first;const auto& v=a.second;
        if(k=="--households")c.households=integer(v);else if(k=="--firms")c.firms=integer(v);else if(k=="--steps")c.steps=integer(v);
        else if(k=="--seed"){size_t p=0;auto n=std::stoull(v,&p);if(p!=v.size()||n>UINT32_MAX||v[0]=='-')throw std::invalid_argument("Invalid seed");c.seed=uint32_t(n);}
        else if(k=="--initial-wealth")c.initial_wealth=number(v);else if(k=="--firm-cash")c.firm_cash=number(v);
        else if(k=="--wage")c.wage=number(v);else if(k=="--price")c.price=number(v);else if(k=="--productivity")c.productivity=number(v);
        else if(k=="--propensity")c.propensity=number(v);else if(k=="--hiring-rate")c.hiring_rate=number(v);
        else if(k=="--device")device=v;else if(k=="--output")output=v;else throw std::invalid_argument("Unknown argument: "+k);
    }
    c.validate();if(device!="cpu"&&device!="cuda")throw std::invalid_argument("Device must be cpu or cuda");
    Result r = [&](){if(device=="cpu")return run_cpu(c);
#ifdef ABM_HAS_CUDA
        return run_cuda(c);
#else
        throw std::runtime_error("CUDA backend unavailable: rebuild with -DABM_CUDA=ON");return run_cpu(c);
#endif
    }();
    std::ofstream csv(output+"/timeseries.csv");if(!csv)throw std::runtime_error("Cannot open output directory");
    csv<<std::setprecision(17)<<"step,output,consumption,savings,employment,unemployment,average_wealth,firm_cash,total_money,average_price\n";
    double max_error=0;
    for(size_t t=0;t<r.rows.size();++t){auto row=r.rows[t];double money=row.wealth+row.firm_cash;max_error=std::max(max_error,std::abs(money-r.initial_money));
        csv<<t+1<<','<<row.output<<','<<row.consumption<<','<<row.savings<<','<<row.employment<<','<<1-row.employment/c.households<<','<<row.wealth/c.households<<','<<row.firm_cash<<','<<money<<','<<c.price<<'\n';}
    std::ofstream json(output+"/result.json");if(!json)throw std::runtime_error("Cannot write result");json<<std::setprecision(17);
    json<<"{\"model_version\":"<<quote(model_version)<<",\"device\":"<<quote(device)<<",\"total_ms\":"<<r.timing.total_ms
        <<",\"kernel_ms\":"<<(device=="cuda"?std::to_string(r.timing.kernel_ms):"null")<<",\"transfer_ms\":"<<(device=="cuda"?std::to_string(r.timing.transfer_ms):"null")
        <<",\"throughput\":"<<double(c.households)*c.steps/(r.timing.total_ms/1000)<<",\"initial_money\":"<<r.initial_money<<",\"max_money_error\":"<<max_error;
    auto bounds=std::minmax_element(r.state.wealth.begin(),r.state.wealth.end());double lo=*bounds.first,hi=*bounds.second,width=hi>lo?(hi-lo)/30:1;
    int bins[30]={};for(double w:r.state.wealth){int b=std::min(29,int((w-lo)/width));++bins[b];}
    json<<",\"wealth_histogram\":[";for(int b=0;b<30;++b){if(b)json<<',';json<<"{\"low\":"<<lo+b*width<<",\"high\":"<<lo+(b+1)*width<<",\"count\":"<<bins[b]<<'}';}
    json<<"],\"firms\":[";for(int f=0;f<std::min(c.firms,256);++f){if(f)json<<',';json<<"{\"id\":"<<f<<",\"output\":"<<r.state.production[f]<<",\"cash\":"<<r.state.cash[f]<<",\"employees\":"<<r.state.employees[f]<<'}';}
    json<<"],\"firm_sample_limit\":256}\n";
    csv.close();json.close();if(!csv||!json)throw std::runtime_error("Failed writing results");
    std::cout<<"Simulation complete: "<<device<<", "<<r.timing.total_ms<<" ms\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
