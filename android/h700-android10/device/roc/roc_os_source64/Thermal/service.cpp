// SPDX-License-Identifier: Apache-2.0
#include "Model.h"
#include <android/hardware/thermal/2.0/IThermal.h>
#include <android-base/properties.h>
#include <hidl/HidlTransportSupport.h>
#include <algorithm>
#include <chrono>
#include <map>
#include <mutex>
#include <thread>
#include <unistd.h>
#include <grp.h>
#include <sstream>
using namespace android::hardware;
namespace T=android::hardware::thermal::V2_0;
namespace V=android::hardware::thermal::V1_0;
using android::sp;
static V::ThermalStatus status(bool ok=true) { V::ThermalStatus s{}; s.code=ok?V::ThermalStatusCode::SUCCESS:V::ThermalStatusCode::FAILURE; if(!ok)s.debugMessage="No supported readable data or invalid callback";return s; }
class Thermal final: public T::IThermal {
 struct Callback {sp<T::IThermalChangedCallback> cb;bool filter;T::TemperatureType type;};
 std::mutex mu; std::vector<Callback> callbacks;
 static T::Temperature convert(const roc::Sensor& s) {T::Temperature t{};t.type=static_cast<T::TemperatureType>(s.type);t.name=s.name;t.value=s.value;t.throttlingStatus=static_cast<T::ThrottlingSeverity>(s.severity);return t;}
 public:
 Return<void> getTemperatures(getTemperatures_cb cb) override {std::vector<V::Temperature> v;for(const auto&s:roc::sensors()){V::Temperature t{};t.type=static_cast<V::TemperatureType>(s.type);t.name=s.name;t.currentValue=s.value;t.throttlingThreshold=s.hot[2];t.shutdownThreshold=s.hot[6];t.vrThrottlingThreshold=roc::unknown();v.push_back(t);}cb(status(!v.empty()),v);return Void();}
 Return<void> getCpuUsages(getCpuUsages_cb cb) override {std::vector<V::CpuUsage> v; std::ifstream f("/proc/stat");std::string line;
 long ticks=sysconf(_SC_CLK_TCK); if(ticks<=0){cb(status(false),{});return Void();}
 while(std::getline(f,line)){std::istringstream in(line);std::string name;in>>name;if(name.size()<4||name.substr(0,3)!="cpu"||name[3]<'0'||name[3]>'9')continue;unsigned long long n[8]={};bool ok=true;for(auto &x:n)if(!(in>>x)){ok=false;break;}if(!ok)continue;
 V::CpuUsage c{};c.name=name;unsigned long long total=0;for(auto x:n)total+=x;c.active=(total-n[3]-n[4])*1000/ticks;c.total=total*1000/ticks;long long online=1;roc::number("/sys/devices/system/cpu/"+name+"/online",online);c.isOnline=online!=0;v.push_back(c);}
 cb(status(!v.empty()),v);return Void();}
 Return<void> getCoolingDevices(getCoolingDevices_cb cb) override {cb(status(),{});return Void();}
 Return<void> getCurrentTemperatures(bool f,T::TemperatureType type,getCurrentTemperatures_cb cb) override {std::vector<T::Temperature> v;for(const auto&s:roc::sensors())if(!f||s.type==static_cast<int>(type))v.push_back(convert(s));cb(status(),v);return Void();}
 Return<void> getTemperatureThresholds(bool f,T::TemperatureType type,getTemperatureThresholds_cb cb) override {std::vector<T::TemperatureThreshold> v;for(const auto&s:roc::sensors())if(!f||s.type==static_cast<int>(type)){T::TemperatureThreshold t{};t.type=static_cast<T::TemperatureType>(s.type);t.name=s.name;t.vrThrottlingThreshold=roc::unknown();for(int i=0;i<7;i++){t.hotThrottlingThresholds[i]=s.hot[i];t.coldThrottlingThresholds[i]=roc::unknown();}v.push_back(t);}cb(status(),v);return Void();}
 Return<void> getCurrentCoolingDevices(bool f,T::CoolingType type,getCurrentCoolingDevices_cb cb) override {std::vector<T::CoolingDevice> v;for(const auto&s:roc::coolers())if(!f||s.type==static_cast<int>(type)){T::CoolingDevice t{};t.type=static_cast<T::CoolingType>(s.type);t.name=s.name;t.value=s.value;v.push_back(t);}cb(status(),v);return Void();}
 Return<void> registerThermalChangedCallback(const sp<T::IThermalChangedCallback>& c,bool f,T::TemperatureType type,registerThermalChangedCallback_cb cb) override {bool ok=c!=nullptr;{std::lock_guard<std::mutex> l(mu);for(const auto&x:callbacks)if(interfacesEqual(x.cb,c))ok=false;if(ok)callbacks.push_back({c,f,type});}cb(status(ok));return Void();}
 Return<void> unregisterThermalChangedCallback(const sp<T::IThermalChangedCallback>& c,unregisterThermalChangedCallback_cb cb) override {bool removed=false;{std::lock_guard<std::mutex> l(mu);callbacks.erase(std::remove_if(callbacks.begin(),callbacks.end(),[&](const Callback&x){bool eq=interfacesEqual(x.cb,c);removed|=eq;return eq;}),callbacks.end());}cb(status(c!=nullptr&&removed));return Void();}
 void monitor() {std::thread([this]{std::map<std::string,std::pair<float,int>> last;for(;;){std::vector<Callback> list;{std::lock_guard<std::mutex> l(mu);list=callbacks;}
   for(const auto&s:roc::sensors()){auto old=last.find(s.name);bool changed=old==last.end()||old->second.second!=s.severity||std::isnan(old->second.first)!=std::isnan(s.value)||std::fabs(old->second.first-s.value)>=.1f;if(!changed)continue;
    for(const auto&c:list)if(!c.filter||static_cast<int>(c.type)==s.type){auto ret=c.cb->notifyThrottling(convert(s));if(!ret.isOk()){std::lock_guard<std::mutex> l(mu);callbacks.erase(std::remove_if(callbacks.begin(),callbacks.end(),[&](const Callback&x){return interfacesEqual(x.cb,c.cb);}),callbacks.end());}}
    last[s.name]={s.value,s.severity};}
   std::this_thread::sleep_for(std::chrono::seconds(2));}}).detach();}
};
int main(){if(android::base::GetProperty("ro.product.device","")!="rgsp"||android::base::GetProperty("persist.vendor.rgsp.input_profile","")!="rg34xxsp")return 1;
 if(geteuid()==0 && (setgroups(0,nullptr)!=0||setgid(1000)!=0||setuid(1000)!=0))return 4;
 if(geteuid()!=1000)return 5;
 configureRpcThreadpool(2,true);sp<Thermal> s=new Thermal;if(s->registerAsService("default")!=android::OK)return 2;s->monitor();joinRpcThreadpool();return 3;}
