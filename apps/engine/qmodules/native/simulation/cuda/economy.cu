#include "core/model.hpp"
#include <cuda_runtime.h>
#include <chrono>
#include <sstream>
namespace abm {
namespace {
void check(cudaError_t e) { if(e!=cudaSuccess) throw std::runtime_error(cudaGetErrorString(e)); }
template<class T> struct Buffer {
    T* p=nullptr;
    explicit Buffer(size_t n) { check(cudaMalloc(reinterpret_cast<void**>(&p),n*sizeof(T))); }
    ~Buffer(){ if(p) cudaFree(p); }
    Buffer(const Buffer&)=delete;
};
struct Event {
    cudaEvent_t e{}; Event(){check(cudaEventCreate(&e));} ~Event(){cudaEventDestroy(e);}
    void record(){check(cudaEventRecord(e));}
};
constexpr int threads=256;
__global__ void init_h(View v,Config c) { int i=blockIdx.x*blockDim.x+threadIdx.x; if(i<c.households) init_household(v,c,i); }
__global__ void init_f(View v,Config c) { int f=blockIdx.x*blockDim.x+threadIdx.x; if(f<c.firms) init_firm(v,c,f); }
__global__ void plan(View v,Config c) { int f=blockIdx.x*blockDim.x+threadIdx.x; if(f<c.firms) plan_firm(v,c,f); }
__global__ void decide(View v,Config c,int t) { int i=blockIdx.x*blockDim.x+threadIdx.x; if(i<c.households) decide_household(v,c,i,t); }
__global__ void clear(View v,Config c) {
    __shared__ double sums[threads]; int f=blockIdx.x,tid=threadIdx.x; double sum=0;
    for(int i=f+tid*c.firms;i<c.households;i+=threads*c.firms) sum+=v.budget[i];
    sums[tid]=sum; __syncthreads();
    for(int stride=threads/2;stride;stride/=2) { if(tid<stride) sums[tid]+=sums[tid+stride]; __syncthreads(); }
    if(tid==0) clear_firm(v,c,f,sums[0]);
}
__global__ void settle(View v,Config c) { int i=blockIdx.x*blockDim.x+threadIdx.x; if(i<c.households) settle_household(v,c,i); }
__device__ Row add(Row a,Row b) { return {a.output+b.output,a.consumption+b.consumption,a.savings+b.savings,a.employment+b.employment,a.wealth+b.wealth,a.firm_cash+b.firm_cash}; }
__global__ void local_metrics(View v,Config c,Row* partial) {
    __shared__ double storage[threads*6];
    Row* sums=reinterpret_cast<Row*>(storage);
    int f=blockIdx.x,tid=threadIdx.x; Row r{};
    for(int i=f+tid*c.firms;i<c.households;i+=threads*c.firms) {
        r.wealth+=v.wealth[i]; r.consumption+=v.consumption[i]; r.savings+=v.savings[i]; r.employment+=v.employment[i];
    }
    if(tid==0){r.output=v.production[f]; r.firm_cash=v.cash[f];}
    sums[tid]=r; __syncthreads();
    for(int stride=threads/2;stride;stride/=2){if(tid<stride)sums[tid]=add(sums[tid],sums[tid+stride]);__syncthreads();}
    if(tid==0)partial[f]=sums[0];
}
__global__ void global_metrics(Row* partial,int n,Row* out) {
    __shared__ double storage[threads*6]; Row* sums=reinterpret_cast<Row*>(storage);
    int tid=threadIdx.x; Row r{}; for(int f=tid;f<n;f+=threads)r=add(r,partial[f]);
    sums[tid]=r; __syncthreads();
    for(int stride=threads/2;stride;stride/=2){if(tid<stride)sums[tid]=add(sums[tid],sums[tid+stride]);__syncthreads();}
    if(tid==0)*out=sums[0];
}
template<class T> void copy(std::vector<T>& out,T* in) { check(cudaMemcpy(out.data(),in,out.size()*sizeof(T),cudaMemcpyDeviceToHost)); }
}
std::string cuda_device(){ int id;check(cudaGetDevice(&id));cudaDeviceProp p{};check(cudaGetDeviceProperties(&p,id));return p.name; }
int cuda_runtime_version(){ int v;check(cudaRuntimeGetVersion(&v));return v; }
Result run_cuda(Config c) {
    c.validate(); check(cudaFree(nullptr)); // Context startup is excluded; benchmark warmups are separate runs.
    auto start=std::chrono::steady_clock::now(); Result result(c);
    size_t n=c.households,f=c.firms;
    Buffer<double> d(6*n+6*f); Buffer<int> ints(n+f); Buffer<Row> partial(f),rows(c.steps+1);
    View v{d.p,d.p+n,d.p+2*n,d.p+3*n,d.p+4*n,d.p+5*n,ints.p,
           d.p+6*n,d.p+6*n+f,d.p+6*n+2*f,d.p+6*n+3*f,d.p+6*n+4*f,d.p+6*n+5*f,ints.p+n};
    Event ks,ke,ts,te; ks.record();
    init_h<<<(c.households+255)/256,256>>>(v,c); init_f<<<(c.firms+255)/256,256>>>(v,c);
    local_metrics<<<c.firms,256>>>(v,c,partial.p); global_metrics<<<1,256>>>(partial.p,c.firms,rows.p);
    for(int t=0;t<c.steps;++t){
        plan<<<(c.firms+255)/256,256>>>(v,c); decide<<<(c.households+255)/256,256>>>(v,c,t);
        clear<<<c.firms,256>>>(v,c); settle<<<(c.households+255)/256,256>>>(v,c);
        local_metrics<<<c.firms,256>>>(v,c,partial.p);global_metrics<<<1,256>>>(partial.p,c.firms,rows.p+t+1);
    }
    check(cudaGetLastError()); ke.record();check(cudaEventSynchronize(ke.e));
    float ms;check(cudaEventElapsedTime(&ms,ks.e,ke.e));result.timing.kernel_ms=ms;
    ts.record(); std::vector<Row> host_rows(c.steps+1); copy(host_rows,rows.p);
    result.initial_money=host_rows[0].wealth+host_rows[0].firm_cash;
    result.rows.assign(host_rows.begin()+1,host_rows.end());auto& s=result.state;
    copy(s.wealth,v.wealth);copy(s.income,v.income);copy(s.consumption,v.consumption);copy(s.savings,v.savings);
    copy(s.propensity,v.propensity);copy(s.budget,v.budget);copy(s.employment,v.employment);
    copy(s.cash,v.cash);copy(s.productivity,v.productivity);copy(s.production,v.production);copy(s.revenue,v.revenue);
    copy(s.demand,v.demand);copy(s.scale,v.scale);copy(s.employees,v.employees);
    te.record();check(cudaEventSynchronize(te.e));check(cudaEventElapsedTime(&ms,ts.e,te.e));result.timing.transfer_ms=ms;
    result.timing.total_ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
    return result;
}
}
